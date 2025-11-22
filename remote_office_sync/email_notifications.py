"""Email notification system for sync alerts."""

import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


@dataclass
class EmailConfig:
    """Email configuration."""

    enabled: bool
    smtp_host: Optional[str]
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    from_addr: Optional[str] = None
    to_addrs: List[str] = None

    def __post_init__(self) -> None:
        """Validate config."""
        if self.to_addrs is None:
            self.to_addrs = []

        if self.enabled and not self.smtp_host:
            logger.warning("Email enabled but SMTP host not configured")


@dataclass
class ConflictAlert:
    """Conflict alert details."""

    file_path: str
    conflict_type: str
    left_mtime: Optional[float] = None
    right_mtime: Optional[float] = None
    left_size: Optional[int] = None
    right_size: Optional[int] = None
    action_taken: str = "created clash files"


@dataclass
class ErrorAlert:
    """Error alert details."""

    error_message: str
    error_type: str = "Sync Error"
    affected_file: Optional[str] = None


class EmailNotifier:
    """Sends email notifications for conflicts and errors."""

    def __init__(self, config: EmailConfig):
        """Initialize email notifier.

        Args:
            config: Email configuration
        """
        self.config = config

    def send_conflict_email(self, alerts: List[ConflictAlert]) -> bool:
        """Send email notification for conflicts.

        Args:
            alerts: List of ConflictAlert objects

        Returns:
            True if email sent successfully
        """
        if not self.config.enabled:
            logger.debug("Email notifications disabled")
            return False

        if not self.config.to_addrs:
            logger.warning("No recipient addresses configured")
            return False

        try:
            subject = f"Sync Conflict Alert - {len(alerts)} conflict(s) detected"
            body = self._build_conflict_message(alerts)

            return self._send_email(subject, body)
        except Exception as e:
            logger.error(f"Failed to send conflict email: {e}")
            return False

    def send_error_email(self, alerts: List[ErrorAlert]) -> bool:
        """Send email notification for errors.

        Args:
            alerts: List of ErrorAlert objects

        Returns:
            True if email sent successfully
        """
        if not self.config.enabled:
            logger.debug("Email notifications disabled")
            return False

        if not self.config.to_addrs:
            logger.warning("No recipient addresses configured")
            return False

        try:
            subject = f"Sync Error Alert - {len(alerts)} error(s) occurred"
            body = self._build_error_message(alerts)

            return self._send_email(subject, body)
        except Exception as e:
            logger.error(f"Failed to send error email: {e}")
            return False

    def _build_conflict_message(self, alerts: List[ConflictAlert]) -> str:
        """Build conflict notification message.

        Args:
            alerts: List of ConflictAlert objects

        Returns:
            Formatted message body
        """
        lines = [
            "Sync Conflict Alert",
            "=" * 50,
            f"\nTotal conflicts: {len(alerts)}\n",
        ]

        for i, alert in enumerate(alerts, 1):
            lines.append(f"Conflict {i}:")
            lines.append(f"  File: {alert.file_path}")
            lines.append(f"  Type: {alert.conflict_type}")
            if alert.left_mtime:
                lines.append(f"  Left modified: {alert.left_mtime}")
            if alert.right_mtime:
                lines.append(f"  Right modified: {alert.right_mtime}")
            if alert.left_size:
                lines.append(f"  Left size: {alert.left_size} bytes")
            if alert.right_size:
                lines.append(f"  Right size: {alert.right_size} bytes")
            lines.append(f"  Action: {alert.action_taken}")
            lines.append("")

        return "\n".join(lines)

    def _build_error_message(self, alerts: List[ErrorAlert]) -> str:
        """Build error notification message.

        Args:
            alerts: List of ErrorAlert objects

        Returns:
            Formatted message body
        """
        lines = [
            "Sync Error Alert",
            "=" * 50,
            f"\nTotal errors: {len(alerts)}\n",
        ]

        for i, alert in enumerate(alerts, 1):
            lines.append(f"Error {i}:")
            lines.append(f"  Type: {alert.error_type}")
            if alert.affected_file:
                lines.append(f"  File: {alert.affected_file}")
            lines.append(f"  Message: {alert.error_message}")
            lines.append("")

        return "\n".join(lines)

    def _send_email(self, subject: str, body: str) -> bool:
        """Send email using SMTP.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            True if sent successfully
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.config.from_addr or self.config.username
            msg["To"] = ", ".join(self.config.to_addrs)
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                if self.config.username and self.config.password:
                    server.login(self.config.username, self.config.password)

                server.send_message(msg)

            logger.info(f"Sent email: {subject}")
            return True
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
