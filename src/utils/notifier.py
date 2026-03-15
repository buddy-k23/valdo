"""Notification utilities for suite completion events."""

from __future__ import annotations

import json
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any
from urllib import request


@dataclass
class EmailNotifier:
    """Send plain-text notifications over SMTP.

    SMTP settings are read from env vars: `SMTP_HOST`, `SMTP_PORT`, and `SMTP_FROM`.
    """

    host: str | None = None
    port: int | None = None
    sender: str | None = None

    def __post_init__(self) -> None:
        self.host = self.host or os.getenv("SMTP_HOST")
        self.port = self.port or int(os.getenv("SMTP_PORT", "25"))
        self.sender = self.sender or os.getenv("SMTP_FROM", "cm3-batch@localhost")

    def send(self, to: list[str], subject: str, body: str) -> None:
        """Send a plain text email."""
        if not self.host:
            raise ValueError("SMTP_HOST is required")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(to)
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(msg)


@dataclass
class WebhookNotifier:
    """Send JSON payload notifications to webhook URLs."""

    def send(self, url: str, payload: dict[str, Any]) -> None:
        """POST a JSON payload to a webhook URL."""
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10):
            return
