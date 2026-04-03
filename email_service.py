"""
Email Service Module
Handles email sending functionality with template support
"""

import logging
import os
import smtplib
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Optional Azure Communication Services Email client
try:
    from azure.communication.email import EmailClient
    from azure.core.exceptions import AzureError

    try:  # Azure credentials helper (used for manual client construction)
        from azure.core.credentials import AzureKeyCredential  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        AzureKeyCredential = None  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    EmailClient = None
    AzureError = Exception
    AzureKeyCredential = None  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FailedEmail:
    """Represents a failed email stored in the retry queue."""

    to_emails: List[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    from_email: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    attempts: int = 0
    last_error: str = ""
    created_at: datetime = field(default_factory=datetime.now)


def load_env_file(env_file=".env"):
    """Load environment variables from .env file"""
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    # Set environment variable if not already set
                    if key not in os.environ:
                        os.environ[key] = value


# Load .env file automatically
load_env_file()


class EmailService:
    """Email service for sending templated emails"""

    def __init__(self, config=None):
        """Initialize email service with configuration"""
        self.config = config or {}
        # Last send diagnostics
        self.last_provider: Optional[str] = None  # 'ACS' | 'SMTP' | None
        self.last_error: Optional[str] = None
        self.last_status: Optional[str] = None
        self.last_sender: Optional[str] = None
        self.last_recipients: List[str] = []
        self.last_message_id: Optional[str] = None

        # Retry configuration
        self.max_retries: int = int(self.config.get("max_retries", 3))
        self.retry_base_delay: float = float(
            self.config.get("retry_base_delay", 0.5)
        )

        # Thread-safe failed email queue (capped at 1000 entries)
        self._failed_queue: deque = deque(maxlen=1000)
        self._queue_lock = threading.Lock()

        # SMTP Configuration from environment variables (support multiple naming schemes)
        # Preferred MAIL_*; fall back to SMTP_*; then GMAIL_*
        self.smtp_server = (
            os.environ.get("MAIL_SERVER")
            or os.environ.get("SMTP_SERVER")
            or "smtp.gmail.com"
        )
        self.smtp_port = int(
            os.environ.get("MAIL_PORT") or os.environ.get("SMTP_PORT") or 587
        )
        use_tls_raw = (
            os.environ.get("MAIL_USE_TLS") or os.environ.get("SMTP_USE_TLS") or "True"
        )
        self.use_tls = str(use_tls_raw).lower() == "true"

        # Credentials
        self.username = (
            os.environ.get("MAIL_USERNAME")
            or os.environ.get("SMTP_USERNAME")
            or os.environ.get("GMAIL_USER")
        )
        self.password = (
            os.environ.get("MAIL_PASSWORD")
            or os.environ.get("SMTP_PASSWORD")
            or os.environ.get("GMAIL_APP_PASSWORD")
        )
        # Sender
        self.default_sender = (
            os.environ.get("MAIL_DEFAULT_SENDER")
            or os.environ.get("SMTP_DEFAULT_SENDER")
            or self.username
        )

        # Azure Communication Services Email configuration
        self.acs_connection_string = os.environ.get("ACS_CONNECTION_STRING")
        self.acs_sender_email = os.environ.get("ACS_SENDER_EMAIL")
        self._acs_client = None

        # Template configuration
        self.template_dir = os.path.join(
            os.path.dirname(__file__), "templates", "email"
        )
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Validate configuration
        self._validate_config()

    def _reset_last_result(self):
        self.last_provider = None
        self.last_error = None
        self.last_status = None
        self.last_sender = None
        self.last_recipients = []
        self.last_message_id = None

    def get_last_send_result(self) -> Dict[str, Any]:
        return {
            "provider": self.last_provider,
            "error": self.last_error,
            "status": self.last_status,
            "sender": self.last_sender,
            "recipients": list(self.last_recipients) if self.last_recipients else [],
            "message_id": self.last_message_id,
        }

    def _validate_config(self):
        """Validate email configuration"""
        # If ACS is configured and client available, consider service functional
        if self.acs_connection_string and self.acs_sender_email and EmailClient:
            return True

        # Otherwise, require SMTP configuration
        if not self.username or not self.password:
            logger.warning(
                "Email credentials not configured (MAIL_/SMTP_/GMAIL_). "
                "Email service will not function."
            )
            return False

        if not self.smtp_server:
            logger.warning(
                "SMTP server not configured. Email service will not function."
            )
            return False

        return True

    def _get_acs_client(self) -> Optional[Any]:
        """Create or return ACS EmailClient if configured."""
        if not (self.acs_connection_string and EmailClient):
            return None
        if self._acs_client is None:
            try:
                # The EmailClient constructor expects (endpoint, credential).
                # Use SDK helper to build client from full connection string.
                if hasattr(EmailClient, "from_connection_string"):
                    self._acs_client = EmailClient.from_connection_string(
                        self.acs_connection_string
                    )
                else:
                    # Robust fallback: parse connection string and construct
                    # client with explicit endpoint and AzureKeyCredential.
                    endpoint, access_key = self._parse_acs_connection_string(
                        self.acs_connection_string
                    )
                    if not AzureKeyCredential:
                        raise RuntimeError(
                            "AzureKeyCredential unavailable; upgrade azure-core package"
                        )
                    self._acs_client = EmailClient(
                        endpoint, AzureKeyCredential(access_key)
                    )
            except Exception as e:
                logger.error(f"Failed to create ACS EmailClient: {e}")
                self._acs_client = None
        return self._acs_client

    @staticmethod
    def _parse_acs_connection_string(conn_str: str) -> tuple[str, str]:
        """Parse ACS connection string into (endpoint, access_key).

        Expected formats (case-insensitive keys):
            endpoint=https://<resource>.communication.azure.com/;accesskey=<key>
            endpoint=https://...;accessKey=<key>
        """
        # Split by semicolons and then by the first '=' per segment
        parts = {}
        for segment in conn_str.split(";"):
            segment = segment.strip()
            if not segment:
                continue
            if "=" not in segment:
                continue
            k, v = segment.split("=", 1)
            parts[k.strip().lower()] = v.strip()

        endpoint = parts.get("endpoint") or parts.get("endpoints") or ""
        access_key = (
            parts.get("accesskey") or parts.get("access_key") or parts.get("key") or ""
        )

        if not endpoint or not access_key:
            raise ValueError(
                "Invalid ACS connection string: missing endpoint or access key"
            )

        return endpoint, access_key

    def _create_smtp_connection(self):
        """Create and configure SMTP connection"""
        try:
            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            # Enable TLS if configured
            if self.use_tls:
                server.starttls()

            # Login with credentials
            if self.username and self.password:
                server.login(self.username, self.password)

            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {str(e)}")
            raise

    # ------------------------------------------------------------------
    # Retry / queue helpers
    # ------------------------------------------------------------------

    def _enqueue_failed(
        self,
        to_emails: List[str],
        subject: str,
        body_text: Optional[str],
        body_html: Optional[str],
        from_email: Optional[str],
        cc_emails: Optional[List[str]],
        bcc_emails: Optional[List[str]],
        attachments: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Add a failed email to the retry queue (thread-safe)."""
        entry = FailedEmail(
            to_emails=list(to_emails),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=from_email,
            cc_emails=list(cc_emails) if cc_emails else None,
            bcc_emails=list(bcc_emails) if bcc_emails else None,
            attachments=attachments,
            attempts=self.max_retries,
            last_error=self.last_error or "unknown",
        )
        with self._queue_lock:
            self._failed_queue.append(entry)
        logger.info(
            "Email queued for later retry (queue size: %d): %s → %s",
            len(self._failed_queue),
            subject,
            to_emails,
        )

    @property
    def failed_queue_size(self) -> int:
        """Number of emails waiting in the failed-email retry queue."""
        return len(self._failed_queue)

    def get_failed_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Return a serialisable snapshot of the failed-email queue."""
        with self._queue_lock:
            return [
                {
                    "to_emails": e.to_emails,
                    "subject": e.subject,
                    "attempts": e.attempts,
                    "last_error": e.last_error,
                    "created_at": e.created_at.isoformat(),
                }
                for e in self._failed_queue
            ]

    def clear_failed_queue(self) -> int:
        """Drop all entries from the failed-email queue. Returns count removed."""
        with self._queue_lock:
            count = len(self._failed_queue)
            self._failed_queue.clear()
        logger.info("Cleared %d entries from the failed-email queue", count)
        return count

    def retry_failed(self) -> Tuple[int, int]:
        """Retry all emails in the failed queue.

        Returns:
            (succeeded, failed) counts.
        """
        with self._queue_lock:
            pending = list(self._failed_queue)
            self._failed_queue.clear()

        succeeded = 0
        still_failed: List[FailedEmail] = []

        for entry in pending:
            ok = self.send_email(
                to_emails=entry.to_emails,
                subject=entry.subject,
                body_text=entry.body_text,
                body_html=entry.body_html,
                from_email=entry.from_email,
                cc_emails=entry.cc_emails,
                bcc_emails=entry.bcc_emails,
                attachments=entry.attachments,
            )
            if ok:
                succeeded += 1
            else:
                # send_email already re-enqueues on failure; pop it back so we
                # don't double-enqueue.  We'll re-add the original entry with
                # an updated attempt count instead.
                with self._queue_lock:
                    # Remove the auto-enqueued entry (the last one)
                    if self._failed_queue:
                        self._failed_queue.pop()
                entry.attempts += self.max_retries
                entry.last_error = self.last_error or "retry failed"
                still_failed.append(entry)

        # Re-enqueue entries that still failed
        with self._queue_lock:
            for entry in still_failed:
                self._failed_queue.append(entry)

        logger.info(
            "Retry complete: %d succeeded, %d still failed",
            succeeded,
            len(still_failed),
        )
        return succeeded, len(still_failed)

    # ------------------------------------------------------------------
    # Core send with retry
    # ------------------------------------------------------------------

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Send email with retry and exponential backoff.

        Tries ACS first (if configured) with up to *max_retries* attempts,
        then falls back to SMTP with the same retry policy.  Emails that
        exhaust all retries are placed on the failed-email queue for later
        retry via :meth:`retry_failed`.
        """
        try:
            self._reset_last_result()

            # -- Validate inputs --
            if not to_emails:
                logger.error("No recipient emails provided")
                self.last_error = "No recipient emails provided"
                return False
            if not subject:
                logger.error("No email subject provided")
                return False
            if not body_text and not body_html:
                logger.error("No email body provided")
                return False

            sender_email = (
                from_email or self.acs_sender_email or self.default_sender or ""
            )
            self.last_sender = sender_email
            self.last_recipients = list(to_emails)

            # =============================================================
            # ACS attempt (with retry)
            # =============================================================
            acs_client = self._get_acs_client()
            if acs_client and self.acs_sender_email:
                self.last_provider = "ACS"

                # Build ACS message payload (once)
                acs_recipients: Dict[str, Any] = {
                    "to": [{"address": addr} for addr in to_emails]
                }
                if cc_emails:
                    acs_recipients["cc"] = [
                        {"address": addr} for addr in cc_emails
                    ]
                if bcc_emails:
                    acs_recipients["bcc"] = [
                        {"address": addr} for addr in bcc_emails
                    ]
                content: Dict[str, str] = {"subject": subject}
                if body_text:
                    content["plainText"] = body_text
                if body_html:
                    content["html"] = body_html
                acs_message = {
                    "senderAddress": self.acs_sender_email,
                    "recipients": acs_recipients,
                    "content": content,
                }

                for attempt in range(self.max_retries):
                    try:
                        operation = acs_client.begin_send(acs_message)
                        result = operation.result()

                        # Extract message ID
                        message_id = None
                        if hasattr(result, "message_id"):
                            message_id = getattr(result, "message_id", None)
                        elif isinstance(result, dict):
                            message_id = (
                                result.get("messageId") or result.get("id")
                            )
                        self.last_message_id = message_id

                        # Fetch status if supported
                        status_value = None
                        try:
                            if message_id and hasattr(
                                acs_client, "get_send_status"
                            ):
                                status_obj = acs_client.get_send_status(
                                    message_id
                                )
                                if hasattr(status_obj, "status"):
                                    status_value = getattr(
                                        status_obj, "status", None
                                    )
                                elif isinstance(status_obj, dict):
                                    status_value = status_obj.get("status")
                        except Exception:
                            status_value = None

                        normalized = str(status_value or "queued").lower()
                        self.last_status = normalized

                        if normalized in (
                            "queued",
                            "succeeded",
                            "success",
                            "completed",
                        ):
                            logger.info(
                                "ACS email queued/sent to %d recipients: %s "
                                "(message_id=%s)",
                                len(to_emails),
                                subject,
                                message_id,
                            )
                            return True

                        # Non-retryable status — fall through to SMTP
                        logger.warning(
                            "ACS returned status %s (message_id=%s), "
                            "falling back to SMTP",
                            normalized,
                            message_id,
                        )
                        break

                    except AzureError as e:
                        self.last_error = f"ACS error: {e}"
                        if attempt < self.max_retries - 1:
                            delay = self.retry_base_delay * (2 ** attempt)
                            logger.warning(
                                "ACS attempt %d/%d failed, retrying in "
                                "%.1fs: %s",
                                attempt + 1,
                                self.max_retries,
                                delay,
                                e,
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                "ACS failed after %d attempts: %s. "
                                "Falling back to SMTP.",
                                self.max_retries,
                                e,
                            )
                    except Exception as e:
                        self.last_error = f"ACS unexpected error: {e}"
                        logger.error(
                            "Unexpected ACS error: %s. Falling back to SMTP.",
                            e,
                        )
                        break  # Don't retry unexpected errors

            # =============================================================
            # SMTP attempt (with retry)
            # =============================================================
            self.last_provider = "SMTP"
            if not (self.username and self.password):
                logger.error(
                    "SMTP fallback unavailable: missing credentials. "
                    "Set MAIL_USERNAME/MAIL_PASSWORD or "
                    "SMTP_USERNAME/SMTP_PASSWORD "
                    "(or GMAIL_USER/GMAIL_APP_PASSWORD)."
                )
                self.last_error = "Missing SMTP credentials"
                self._enqueue_failed(
                    to_emails, subject, body_text, body_html,
                    from_email, cc_emails, bcc_emails, attachments,
                )
                return False

            # Build MIME message (once)
            msg = MIMEMultipart("alternative")
            msg["From"] = sender_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject
            if cc_emails:
                msg["Cc"] = ", ".join(cc_emails)
            if bcc_emails:
                msg["Bcc"] = ", ".join(bcc_emails)
            if body_text:
                msg.attach(MIMEText(body_text, "plain", "utf-8"))
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))
            if attachments:
                for att in attachments:
                    if "filename" in att and "content" in att:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(att["content"])
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f'attachment; filename= {att["filename"]}',
                        )
                        msg.attach(part)

            all_recipients = list(to_emails)
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)

            for attempt in range(self.max_retries):
                try:
                    server = self._create_smtp_connection()
                    try:
                        server.send_message(msg, to_addrs=all_recipients)
                    finally:
                        server.quit()

                    logger.info(
                        "SMTP email sent to %d recipients: %s",
                        len(all_recipients),
                        subject,
                    )
                    self.last_status = "sent"
                    return True
                except Exception as e:
                    self.last_error = str(e)
                    if attempt < self.max_retries - 1:
                        delay = self.retry_base_delay * (2 ** attempt)
                        logger.warning(
                            "SMTP attempt %d/%d failed, retrying in "
                            "%.1fs: %s",
                            attempt + 1,
                            self.max_retries,
                            delay,
                            e,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "SMTP failed after %d attempts: %s",
                            self.max_retries,
                            e,
                        )

            # Both providers exhausted — queue for later retry
            self._enqueue_failed(
                to_emails, subject, body_text, body_html,
                from_email, cc_emails, bcc_emails, attachments,
            )
            return False

        except Exception as e:
            self.last_error = str(e)
            logger.error("Failed to send email: %s", e)
            self._enqueue_failed(
                to_emails, subject, body_text, body_html,
                from_email, cc_emails, bcc_emails, attachments,
            )
            return False

    def send_templated_email(
        self,
        to_emails: List[str],
        template_name: str,
        template_data: Optional[Dict[str, Any]] = None,
        subject: Optional[str] = None,
        from_email: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        Send email using Jinja2 template

        Args:
            to_emails: List of recipient email addresses
            template_name: Name of template file (without .html extension)
            template_data: Dictionary of data to pass to template
            subject: Email subject (if not in template)
            from_email: Sender email (defaults to configured sender)
            cc_emails: List of CC recipients (optional)
            bcc_emails: List of BCC recipients (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Load template
            template = self.jinja_env.get_template(f"{template_name}.html")

            # Prepare template data
            data = template_data or {}
            data.update(
                {
                    "current_date": datetime.now().strftime("%Y-%m-%d"),
                    "current_year": datetime.now().year,
                }
            )

            # Render template
            html_content = template.render(**data)

            # Extract subject from template if not provided
            if not subject:
                # Try to extract subject from template data or use default
                subject = data.get(
                    "subject", f"RFPO Application - {template_name.title()}"
                )

            # Create plain text version
            # Preserve hyperlinks by converting <a href="URL">Text</a> to
            # "Text (URL)" before stripping remaining tags.
            import re

            # Replace anchor tags with "text (url)"
            anchor_pattern = re.compile(
                r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                flags=re.IGNORECASE | re.DOTALL,
            )
            interim = anchor_pattern.sub(r"\2 (\1)", html_content)

            # Strip remaining HTML tags
            text_content = re.sub("<[^<]+?>", "", interim)
            text_content = re.sub(r"\n\s*\n", "\n\n", text_content)

            # Send email
            return self.send_email(
                to_emails=to_emails,
                subject=str(subject or ""),
                body_text=text_content,
                body_html=html_content,
                from_email=from_email,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
            )

        except Exception as e:
            logger.error(f"Failed to send templated email: {str(e)}")
            return False

    def send_welcome_email(
        self,
        user_email: str,
        user_name: str,
        temp_password: Optional[str] = None,
        show_user_link: Optional[bool] = None,
        show_admin_link: Optional[bool] = None,
    ) -> bool:
        """
        Send welcome email to new user

        Args:
            user_email: User's email address
            user_name: User's display name
            temp_password: Temporary password (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # Resolve app login URLs
        user_login_url = (
            os.environ.get("USER_APP_URL")
            or os.environ.get("APP_URL")
            or "http://localhost:5000"
        ) + "/login"
        admin_login_url = (
            os.environ.get("ADMIN_APP_URL")
            or os.environ.get("APP_URL")
            or "http://localhost:5111"
        ) + "/login"

        # Defaults: previous behavior shows only user link if not specified
        show_user = True if show_user_link is None else bool(show_user_link)
        show_admin = False if show_admin_link is None else bool(show_admin_link)

        template_data = {
            "user_name": user_name,
            "user_email": user_email,
            "temp_password": temp_password,
            # Back-compat single login_url retained (user app)
            "login_url": user_login_url,
            # New: explicit URLs and flags for role-based buttons
            "user_login_url": user_login_url,
            "admin_login_url": admin_login_url,
            "show_user_link": show_user,
            "show_admin_link": show_admin,
            "support_email": os.environ.get("SUPPORT_EMAIL", "support@rfpo.com"),
            "subject": "Welcome to RFPO Application - Your Account is Ready",
        }

        return self.send_templated_email(
            to_emails=[user_email],
            template_name="welcome",
            template_data=template_data,
            subject=template_data["subject"],
        )

    def send_password_changed_email(
        self,
        user_email: str,
        user_name: str,
        change_ip: Optional[str] = None,
    ) -> bool:
        """
        Send password change notification email

        Args:
            user_email: User's email address
            user_name: User's display name
            change_ip: IP address where password was changed (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            "user_name": user_name,
            "user_email": user_email,
            "change_ip": change_ip,
            "change_timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            "current_date": datetime.now().strftime("%B %d, %Y"),
            "current_time": datetime.now().strftime("%I:%M %p"),
            "current_year": datetime.now().year,
            "login_url": (
                os.environ.get("USER_APP_URL")
                or os.environ.get("APP_URL")
                or "http://localhost:5000"
            )
            + "/login",
            "support_email": os.environ.get("SUPPORT_EMAIL", "support@rfpo.com"),
            "subject": ("Password Changed - RFPO Application Security Notification"),
        }

        return self.send_templated_email(
            to_emails=[user_email],
            template_name="password_changed",
            template_data=template_data,
            subject=template_data["subject"],
        )

    def send_approval_notification(
        self,
        user_email: str,
        user_name: str,
        rfpo_id: str,
        approval_type: str,
    ) -> bool:
        """
        Send approval notification email

        Args:
            user_email: User's email address
            user_name: User's display name
            rfpo_id: RFPO ID requiring approval
            approval_type: Type of approval needed

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            "user_name": user_name,
            "rfpo_id": rfpo_id,
            "approval_type": approval_type,
            "rfpo_url": (
                os.environ.get("ADMIN_APP_URL")
                or os.environ.get("APP_URL")
                or "http://localhost:5111"
            )
            + f"/admin/rfpo/{rfpo_id}/edit",
            "subject": f"RFPO Approval Required - {rfpo_id}",
        }

        return self.send_templated_email(
            to_emails=[user_email],
            template_name="approval_notification",
            template_data=template_data,
            subject=template_data["subject"],
        )

    def send_user_added_to_project_email(
        self,
        user_email: str,
        user_name: str,
        project_name: str,
        role: str,
    ) -> bool:
        """
        Send notification when user is added to a project

        Args:
            user_email: User's email address
            user_name: User's display name
            project_name: Name of the project
            role: User's role in the project

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            "user_name": user_name,
            "project_name": project_name,
            "role": role,
            "projects_url": (
                os.environ.get("ADMIN_APP_URL")
                or os.environ.get("APP_URL")
                or "http://localhost:5111"
            )
            + "/admin/projects",
            "subject": f"Added to Project: {project_name}",
        }

        return self.send_templated_email(
            to_emails=[user_email],
            template_name="user_added_to_project",
            template_data=template_data,
            subject=template_data["subject"],
        )

    def test_connection(self) -> bool:
        """
        Test email service connection

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            server = self._create_smtp_connection()
            try:
                # Test connection by getting server status
                status = server.noop()
                return status[0] == 250
            finally:
                server.quit()
        except Exception as e:
            logger.error(f"Email connection test failed: {str(e)}")
            return False


# Global email service instance
email_service = EmailService()


# Convenience functions


def send_welcome_email(
    user_email: str,
    user_name: str,
    temp_password: Optional[str] = None,
    show_user_link: Optional[bool] = None,
    show_admin_link: Optional[bool] = None,
) -> bool:
    """
    Send welcome email to new user, optionally controlling which links show.

    When flags are None, defaults match prior behavior:
    show user link only.
    """
    return email_service.send_welcome_email(
        user_email,
        user_name,
        temp_password,
        show_user_link,
        show_admin_link,
    )


def send_password_changed_email(
    user_email: str,
    user_name: str,
    change_ip: Optional[str] = None,
) -> bool:
    """Send password change notification email"""
    return email_service.send_password_changed_email(user_email, user_name, change_ip)


def send_approval_notification(
    user_email: str,
    user_name: str,
    rfpo_id: str,
    approval_type: str,
) -> bool:
    """Send approval notification email"""
    return email_service.send_approval_notification(
        user_email, user_name, rfpo_id, approval_type
    )


def send_user_added_to_project_email(
    user_email: str,
    user_name: str,
    project_name: str,
    role: str,
) -> bool:
    """Send notification when user is added to a project"""
    return email_service.send_user_added_to_project_email(
        user_email, user_name, project_name, role
    )


def test_email_connection() -> bool:
    """Test email service connection"""
    return email_service.test_connection()
