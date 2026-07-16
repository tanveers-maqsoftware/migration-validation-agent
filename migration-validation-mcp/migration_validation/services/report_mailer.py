"""Emails a finished validation report to the configured recipients.

Delivery uses plain SMTP (stdlib ``smtplib``) so it works with Microsoft 365
(``smtp.office365.com``), Gmail app passwords, or any relay — configured
entirely through ``.env`` (see ``config/settings.py``). When the settings are
absent the mailer reports itself unconfigured instead of raising, so a run
never fails just because email delivery is not set up.
"""

import smtplib
from email.message import EmailMessage
from pathlib import Path


class ReportMailer:
    """Sends ``Validation_Report_*.md`` files over SMTP."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        sender: str,
        default_recipients: str,
        subject_prefix: str,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.sender = sender
        self.default_recipients = _split_recipients(default_recipients)
        self.subject_prefix = subject_prefix

    def is_configured(self) -> bool:
        return bool(self.host and self.sender and self.default_recipients)

    def send(
        self,
        report_path: Path,
        subject: str | None = None,
        recipients: list[str] | None = None,
        summary_line: str | None = None,
    ) -> dict:
        """Send the report as email body + attachment; return delivery info."""
        to_addresses = recipients or self.default_recipients
        if not (self.host and self.sender and to_addresses):
            raise ValueError(
                "Email is not configured: set SMTP_HOST, EMAIL_FROM and "
                "EMAIL_TO in .env (plus SMTP_USERNAME/SMTP_PASSWORD if your "
                "relay requires login)."
            )
        if not report_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")

        report_text = report_path.read_text(encoding="utf-8")
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = ", ".join(to_addresses)
        message["Subject"] = subject or self._default_subject(
            report_path, summary_line
        )

        body_parts = []
        if summary_line:
            body_parts.append(summary_line)
        body_parts.append(report_text)
        body_parts.append(
            "-- \nSent automatically by the Migration Validation MCP server."
        )
        message.set_content("\n\n".join(body_parts))
        message.add_attachment(
            report_text.encode("utf-8"),
            maintype="text",
            subtype="markdown",
            filename=report_path.name,
        )

        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            if self.use_tls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)

        return {
            "recipients": to_addresses,
            "subject": message["Subject"],
            "attachment": report_path.name,
        }

    def _default_subject(
        self, report_path: Path, summary_line: str | None
    ) -> str:
        subject = f"{self.subject_prefix} {report_path.stem}".strip()
        if summary_line:
            subject = f"{subject} — {summary_line}"
        return subject


def _split_recipients(raw: str) -> list[str]:
    return [address.strip() for address in raw.split(",") if address.strip()]
