#!/usr/bin/env python3
"""
Unit tests for email retry/queue system in email_service.py.

Covers:
- EmailService initialization with retry config
- Exponential backoff retry on SMTP failures
- Failed-email queue (enqueue, snapshot, clear, retry_failed)
- Input validation (no recipients, no subject, no body)
- ACS retry on AzureError with fallback to SMTP
- Thread-safety of failed queue
"""

import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure no real SMTP/ACS credentials leak into tests
os.environ.pop("MAIL_USERNAME", None)
os.environ.pop("MAIL_PASSWORD", None)
os.environ.pop("SMTP_USERNAME", None)
os.environ.pop("SMTP_PASSWORD", None)
os.environ.pop("GMAIL_USER", None)
os.environ.pop("GMAIL_APP_PASSWORD", None)
os.environ.pop("ACS_CONNECTION_STRING", None)
os.environ.pop("ACS_SENDER_EMAIL", None)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_service import EmailService, FailedEmail


class TestEmailServiceInit(unittest.TestCase):
    """Test EmailService initialization and retry configuration."""

    def test_default_retry_config(self):
        svc = EmailService()
        self.assertEqual(svc.max_retries, 3)
        self.assertEqual(svc.retry_base_delay, 0.5)

    def test_custom_retry_config(self):
        svc = EmailService(config={"max_retries": 5, "retry_base_delay": 1.0})
        self.assertEqual(svc.max_retries, 5)
        self.assertEqual(svc.retry_base_delay, 1.0)

    def test_empty_failed_queue_on_init(self):
        svc = EmailService()
        self.assertEqual(svc.failed_queue_size, 0)
        self.assertEqual(svc.get_failed_queue_snapshot(), [])


class TestInputValidation(unittest.TestCase):
    """Test that send_email rejects invalid inputs without retrying."""

    def setUp(self):
        self.svc = EmailService()

    def test_no_recipients_returns_false(self):
        result = self.svc.send_email(
            to_emails=[], subject="Test", body_text="Hello"
        )
        self.assertFalse(result)
        self.assertEqual(self.svc.last_error, "No recipient emails provided")
        # Should NOT be queued — it's a validation error, not a transient failure
        self.assertEqual(self.svc.failed_queue_size, 0)

    def test_no_subject_returns_false(self):
        result = self.svc.send_email(
            to_emails=["a@b.com"], subject="", body_text="Hello"
        )
        self.assertFalse(result)

    def test_no_body_returns_false(self):
        result = self.svc.send_email(
            to_emails=["a@b.com"], subject="Test"
        )
        self.assertFalse(result)


class TestSMTPRetry(unittest.TestCase):
    """Test SMTP retry with exponential backoff."""

    def _make_svc_with_smtp(self):
        """Create an EmailService with SMTP credentials configured."""
        svc = EmailService(config={"max_retries": 3, "retry_base_delay": 0.01})
        svc.username = "test@example.com"
        svc.password = "password123"
        svc.default_sender = "test@example.com"
        svc.acs_connection_string = None  # Ensure no ACS
        svc._acs_client = None
        svc.acs_sender_email = None
        return svc

    @patch.object(EmailService, "_create_smtp_connection")
    def test_smtp_succeeds_on_first_attempt(self, mock_smtp):
        svc = self._make_svc_with_smtp()
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="Test",
            body_text="Hello world",
        )

        self.assertTrue(result)
        self.assertEqual(svc.last_provider, "SMTP")
        self.assertEqual(svc.last_status, "sent")
        self.assertEqual(svc.failed_queue_size, 0)
        mock_smtp.assert_called_once()
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("email_service.time.sleep")
    @patch.object(EmailService, "_create_smtp_connection")
    def test_smtp_retries_on_failure_then_succeeds(self, mock_smtp, mock_sleep):
        svc = self._make_svc_with_smtp()

        # Fail first 2 times, succeed on 3rd
        mock_server_fail = MagicMock()
        mock_server_fail.send_message.side_effect = ConnectionError("SMTP down")

        mock_server_ok = MagicMock()

        mock_smtp.side_effect = [
            mock_server_fail,
            mock_server_fail,
            mock_server_ok,
        ]

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="Test",
            body_text="Hello",
        )

        self.assertTrue(result)
        self.assertEqual(mock_smtp.call_count, 3)
        # Exponential backoff: sleep called twice (after attempt 1 and 2)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(svc.failed_queue_size, 0)

    @patch("email_service.time.sleep")
    @patch.object(EmailService, "_create_smtp_connection")
    def test_smtp_exhausts_retries_and_queues(self, mock_smtp, mock_sleep):
        svc = self._make_svc_with_smtp()

        mock_server = MagicMock()
        mock_server.send_message.side_effect = ConnectionError("SMTP down")
        mock_smtp.return_value = mock_server

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="Queued email",
            body_text="Will fail",
        )

        self.assertFalse(result)
        self.assertEqual(mock_smtp.call_count, 3)  # max_retries
        self.assertEqual(mock_sleep.call_count, 2)  # retries - 1
        # Email should be in failed queue
        self.assertEqual(svc.failed_queue_size, 1)

        snapshot = svc.get_failed_queue_snapshot()
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0]["subject"], "Queued email")
        self.assertEqual(snapshot[0]["to_emails"], ["user@example.com"])
        self.assertIn("SMTP down", snapshot[0]["last_error"])

    def test_smtp_missing_credentials_queues_email(self):
        svc = EmailService()
        # No SMTP creds, no ACS — should queue
        svc.username = None
        svc.password = None
        svc.acs_connection_string = None
        svc._acs_client = None
        svc.acs_sender_email = None

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="No creds",
            body_text="Should queue",
        )

        self.assertFalse(result)
        self.assertEqual(svc.last_error, "Missing SMTP credentials")
        self.assertEqual(svc.failed_queue_size, 1)

    @patch("email_service.time.sleep")
    @patch.object(EmailService, "_create_smtp_connection")
    def test_exponential_backoff_delays(self, mock_smtp, mock_sleep):
        svc = self._make_svc_with_smtp()
        svc.retry_base_delay = 1.0

        mock_server = MagicMock()
        mock_server.send_message.side_effect = ConnectionError("fail")
        mock_smtp.return_value = mock_server

        svc.send_email(
            to_emails=["a@b.com"], subject="Test", body_text="Hi"
        )

        # Delays: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0
        calls = mock_sleep.call_args_list
        self.assertAlmostEqual(calls[0][0][0], 1.0)
        self.assertAlmostEqual(calls[1][0][0], 2.0)


class TestFailedEmailQueue(unittest.TestCase):
    """Test the failed email queue management."""

    def setUp(self):
        self.svc = EmailService()

    def test_enqueue_and_snapshot(self):
        self.svc._enqueue_failed(
            to_emails=["a@b.com"],
            subject="Test",
            body_text="Hello",
            body_html=None,
            from_email=None,
            cc_emails=None,
            bcc_emails=None,
            attachments=None,
        )
        self.assertEqual(self.svc.failed_queue_size, 1)
        snap = self.svc.get_failed_queue_snapshot()
        self.assertEqual(snap[0]["subject"], "Test")
        self.assertIn("created_at", snap[0])

    def test_clear_queue(self):
        self.svc._enqueue_failed(
            ["a@b.com"], "S1", "B", None, None, None, None, None
        )
        self.svc._enqueue_failed(
            ["c@d.com"], "S2", "B", None, None, None, None, None
        )
        self.assertEqual(self.svc.failed_queue_size, 2)

        removed = self.svc.clear_failed_queue()
        self.assertEqual(removed, 2)
        self.assertEqual(self.svc.failed_queue_size, 0)

    def test_queue_cap_at_1000(self):
        for i in range(1050):
            self.svc._enqueue_failed(
                [f"u{i}@b.com"], f"S{i}", "B", None, None, None, None, None
            )
        self.assertEqual(self.svc.failed_queue_size, 1000)

    @patch.object(EmailService, "_create_smtp_connection")
    def test_retry_failed_succeeds(self, mock_smtp):
        """Test that retry_failed re-sends queued emails."""
        # Set up SMTP
        self.svc.username = "test@example.com"
        self.svc.password = "password"
        self.svc.default_sender = "test@example.com"
        self.svc.acs_connection_string = None
        self.svc._acs_client = None
        self.svc.acs_sender_email = None

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # Enqueue a failed email
        self.svc._enqueue_failed(
            ["user@example.com"], "Retry me", "Body", None,
            None, None, None, None,
        )
        self.assertEqual(self.svc.failed_queue_size, 1)

        # Now retry — SMTP will succeed
        succeeded, failed = self.svc.retry_failed()
        self.assertEqual(succeeded, 1)
        self.assertEqual(failed, 0)
        self.assertEqual(self.svc.failed_queue_size, 0)

    @patch("email_service.time.sleep")
    @patch.object(EmailService, "_create_smtp_connection")
    def test_retry_failed_still_fails(self, mock_smtp, mock_sleep):
        """Emails that fail during retry_failed stay in queue."""
        self.svc.username = "test@example.com"
        self.svc.password = "password"
        self.svc.default_sender = "test@example.com"
        self.svc.acs_connection_string = None
        self.svc._acs_client = None
        self.svc.acs_sender_email = None
        self.svc.max_retries = 1  # Speed up test

        mock_server = MagicMock()
        mock_server.send_message.side_effect = ConnectionError("still down")
        mock_smtp.return_value = mock_server

        self.svc._enqueue_failed(
            ["user@example.com"], "Still failing", "Body", None,
            None, None, None, None,
        )

        succeeded, failed = self.svc.retry_failed()
        self.assertEqual(succeeded, 0)
        self.assertEqual(failed, 1)
        self.assertEqual(self.svc.failed_queue_size, 1)

    def test_thread_safety_of_queue(self):
        """Queue operations from multiple threads don't corrupt data."""
        errors = []

        def enqueue_batch(start, count):
            try:
                for i in range(count):
                    self.svc._enqueue_failed(
                        [f"t{start + i}@b.com"],
                        f"S{start + i}",
                        "B", None, None, None, None, None,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=enqueue_batch, args=(i * 100, 100))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(self.svc.failed_queue_size, 500)


class TestFailedEmailDataclass(unittest.TestCase):
    """Test the FailedEmail dataclass."""

    def test_defaults(self):
        fe = FailedEmail(to_emails=["a@b.com"], subject="Test")
        self.assertEqual(fe.attempts, 0)
        self.assertEqual(fe.last_error, "")
        self.assertIsNone(fe.body_text)
        self.assertIsNone(fe.attachments)
        self.assertIsNotNone(fe.created_at)

    def test_full_construction(self):
        fe = FailedEmail(
            to_emails=["a@b.com", "c@d.com"],
            subject="Hello",
            body_text="plain",
            body_html="<b>html</b>",
            from_email="sender@b.com",
            cc_emails=["cc@b.com"],
            bcc_emails=["bcc@b.com"],
            attachments=[{"filename": "f.txt", "content": b"data"}],
            attempts=3,
            last_error="timeout",
        )
        self.assertEqual(len(fe.to_emails), 2)
        self.assertEqual(fe.attempts, 3)


class TestACSRetry(unittest.TestCase):
    """Test ACS retry behavior with fallback to SMTP."""

    def _make_svc_with_acs_and_smtp(self):
        svc = EmailService(
            config={"max_retries": 2, "retry_base_delay": 0.01}
        )
        svc.username = "test@example.com"
        svc.password = "password"
        svc.default_sender = "test@example.com"
        svc.acs_connection_string = "endpoint=https://test.comm.azure.com/;accesskey=abc123"
        svc.acs_sender_email = "acs@mail.com"
        return svc

    @patch("email_service.time.sleep")
    @patch.object(EmailService, "_create_smtp_connection")
    @patch.object(EmailService, "_get_acs_client")
    def test_acs_fails_with_azure_error_retries_then_falls_back_to_smtp(
        self, mock_get_acs, mock_smtp, mock_sleep
    ):
        svc = self._make_svc_with_acs_and_smtp()

        # Simulate ACS raising on all attempts.
        # Note: when azure SDK is not installed, AzureError = Exception,
        # so all exceptions are retried (the "unexpected" path is unreachable).
        mock_client = MagicMock()
        mock_client.begin_send.side_effect = Exception("ACS boom")
        mock_get_acs.return_value = mock_client

        # SMTP succeeds
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="Fallback",
            body_text="Hello",
        )

        self.assertTrue(result)
        # ACS exhausts all max_retries attempts before falling back
        self.assertEqual(mock_client.begin_send.call_count, svc.max_retries)
        # SMTP should have been used as fallback
        mock_smtp.assert_called()
        self.assertEqual(svc.last_provider, "SMTP")

    @patch.object(EmailService, "_get_acs_client")
    def test_acs_succeeds_does_not_use_smtp(self, mock_get_acs):
        svc = self._make_svc_with_acs_and_smtp()

        mock_poller = MagicMock()
        mock_poller.result.return_value = {"messageId": "msg-123"}

        mock_client = MagicMock()
        mock_client.begin_send.return_value = mock_poller
        # Mock get_send_status to return a proper status object
        mock_status = MagicMock()
        mock_status.status = "Succeeded"
        mock_client.get_send_status.return_value = mock_status
        mock_get_acs.return_value = mock_client

        result = svc.send_email(
            to_emails=["user@example.com"],
            subject="ACS Only",
            body_text="Hello",
        )

        self.assertTrue(result)
        self.assertEqual(svc.last_provider, "ACS")
        self.assertEqual(svc.last_message_id, "msg-123")
        self.assertEqual(svc.last_status, "succeeded")


class TestDiagnostics(unittest.TestCase):
    """Test last-send diagnostics are populated correctly."""

    @patch.object(EmailService, "_create_smtp_connection")
    def test_diagnostics_after_successful_send(self, mock_smtp):
        svc = EmailService()
        svc.username = "u"
        svc.password = "p"
        svc.default_sender = "sender@b.com"
        svc.acs_connection_string = None
        svc._acs_client = None
        svc.acs_sender_email = None

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        svc.send_email(
            to_emails=["a@b.com"],
            subject="Diag",
            body_text="Hello",
        )

        diag = svc.get_last_send_result()
        self.assertEqual(diag["provider"], "SMTP")
        self.assertEqual(diag["status"], "sent")
        self.assertEqual(diag["sender"], "sender@b.com")
        self.assertEqual(diag["recipients"], ["a@b.com"])
        self.assertIsNone(diag["error"])


if __name__ == "__main__":
    unittest.main()
