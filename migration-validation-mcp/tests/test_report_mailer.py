"""Unit tests for SMTP report delivery."""

import smtplib
from pathlib import Path

import pytest

from migration_validation.services import report_mailer
from migration_validation.services.report_mailer import ReportMailer


class FakeSMTP:
    """Captures the SMTP conversation instead of talking to a server."""

    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args = None
        self.sent_messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.sent_messages.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(report_mailer.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


def _mailer(**overrides) -> ReportMailer:
    config = dict(
        host="smtp.example.com",
        port=587,
        username="bot@example.com",
        password="secret",
        use_tls=True,
        sender="bot@example.com",
        default_recipients="lead@example.com, qa@example.com",
        subject_prefix="[Migration Validation]",
    )
    config.update(overrides)
    return ReportMailer(**config)


def _report_file(tmp_path: Path) -> Path:
    path = tmp_path / "Validation_Report_20260716_010203.md"
    path.write_text("# Validation Report\n\nAccuracy: 40%\n", encoding="utf-8")
    return path


def test_unconfigured_mailer_reports_not_configured():
    mailer = _mailer(host="", sender="", default_recipients="")
    assert not mailer.is_configured()
    with pytest.raises(ValueError, match="not configured"):
        mailer.send(Path("whatever.md"))


def test_send_delivers_body_attachment_and_subject(tmp_path):
    mailer = _mailer()
    report = _report_file(tmp_path)

    delivery = mailer.send(report, summary_line="2/5 visuals pass (40%)")

    smtp = FakeSMTP.instances[-1]
    assert smtp.started_tls
    assert smtp.login_args == ("bot@example.com", "secret")
    message = smtp.sent_messages[0]
    assert message["To"] == "lead@example.com, qa@example.com"
    assert "Validation_Report_20260716_010203" in message["Subject"]
    assert "2/5 visuals pass (40%)" in message["Subject"]
    attachments = [part for part in message.iter_attachments()]
    assert attachments[0].get_filename() == report.name
    assert delivery["recipients"] == ["lead@example.com", "qa@example.com"]


def test_send_recipient_override_and_missing_report(tmp_path):
    mailer = _mailer()
    report = _report_file(tmp_path)

    delivery = mailer.send(report, recipients=["pm@example.com"])
    message = FakeSMTP.instances[-1].sent_messages[0]
    assert message["To"] == "pm@example.com"
    assert delivery["recipients"] == ["pm@example.com"]

    with pytest.raises(FileNotFoundError):
        mailer.send(tmp_path / "missing.md")
