from unittest.mock import Mock, patch

import pytest

from src.utils.notifier import EmailNotifier, WebhookNotifier


def test_email_notifier_requires_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    n = EmailNotifier(host=None)
    with pytest.raises(ValueError):
        n.send(["qa@example.com"], "subj", "body")


@patch("smtplib.SMTP")
def test_email_notifier_sends(mock_smtp):
    n = EmailNotifier(host="localhost", port=2525, sender="cm3@test")
    n.send(["qa@example.com"], "subj", "body")
    assert mock_smtp.called


@patch("urllib.request.urlopen")
def test_webhook_notifier_posts(mock_urlopen):
    mock_urlopen.return_value.__enter__ = Mock(return_value=Mock())
    mock_urlopen.return_value.__exit__ = Mock(return_value=False)
    n = WebhookNotifier()
    n.send("https://example.com/webhook", {"text": "ok"})
    assert mock_urlopen.called
