"""SMTP email notifier."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import Optional

from loguru import logger

from src.notify.base import BaseNotifier


class EmailNotifier(BaseNotifier):
    """SMTP email notification.

    Basic email notification via SMTP. Supports HTML body and
    optional screenshot attachment.
    """

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 465,
        smtp_user: str = "",
        smtp_password: str = "",
        from_addr: str = "",
        to_addr: str = "",
        use_ssl: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.use_ssl = use_ssl

    async def send(
        self,
        title: str,
        body: str,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """Send email notification with optional screenshot attachment."""
        if not self.smtp_host or not self.to_addr:
            logger.warning("Email not configured — skipping")
            return False

        msg = MIMEMultipart()
        msg["Subject"] = f"[DamaiBot] {title}"
        msg["From"] = self.from_addr
        msg["To"] = self.to_addr

        # HTML body
        html_body = f"<h2>{title}</h2><p>{body}</p>"
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach screenshot if available
        if screenshot_path:
            import os
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    img = MIMEImage(f.read())
                    img.add_header(
                        "Content-Disposition", "attachment",
                        filename="screenshot.png"
                    )
                    msg.attach(img)

        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()

            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_addr, self.to_addr, msg.as_string())
            server.quit()

            logger.info("Email notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False
