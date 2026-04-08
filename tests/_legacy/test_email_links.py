import os

from email_service import EmailService


def _patch_send_email_capture():
    sent = {}

    def fake_send_email(
        self,
        to_emails,
        subject,
        body_text=None,
        body_html=None,
        **kwargs,
    ):
        sent["to"] = list(to_emails)
        sent["subject"] = subject
        sent["text"] = body_text or ""
        sent["html"] = body_html or ""
        return True

    return sent, fake_send_email


def test_welcome_email_uses_user_app_url(monkeypatch):
    # Arrange environment
    os.environ.pop("APP_URL", None)
    os.environ["USER_APP_URL"] = "https://rfpo-user.example.com"

    svc = EmailService()

    # Patch send_email to capture content without sending
    sent, fake_send = _patch_send_email_capture()
    monkeypatch.setattr(EmailService, "send_email", fake_send)

    # Act
    svc.send_welcome_email("test@example.com", "Test User", temp_password="abc123")

    # Assert
    assert "https://rfpo-user.example.com/login" in sent["html"]
    assert "https://rfpo-user.example.com/login" in sent["text"]


def test_password_changed_uses_user_app_url(monkeypatch):
    # Arrange environment
    os.environ.pop("APP_URL", None)
    os.environ["USER_APP_URL"] = "https://rfpo-user.example.com"

    svc = EmailService()

    # Patch send_email to capture content without sending
    sent, fake_send = _patch_send_email_capture()
    monkeypatch.setattr(EmailService, "send_email", fake_send)

    # Act
    svc.send_password_changed_email("test@example.com", "Test User")

    # Assert
    assert "https://rfpo-user.example.com/login" in sent["html"]
    assert "https://rfpo-user.example.com/login" in sent["text"]
