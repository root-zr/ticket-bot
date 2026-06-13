"""Unit tests for email notifier."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.notify.email_notify import EmailNotifier


class TestEmailNotifier:
    """Tests for EmailNotifier."""

    @pytest.mark.asyncio
    async def test_unconfigured_skips(self):
        notifier = EmailNotifier()
        result = await notifier.send("Title", "Body")
        # Should return false without raising
        assert result is False

    @pytest.mark.asyncio
    async def test_send_with_no_host(self):
        notifier = EmailNotifier()  # No host configured
        result = await notifier.send("Title", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_user="user",
            smtp_password="pass",
            from_addr="from@example.com",
            to_addr="to@example.com",
        )

        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            result = await notifier.send("Alert", "Something happened")
            assert result is True
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_with_screenshot(self, tmp_path):
        screenshot = tmp_path / "test.png"
        # Write a minimal valid PNG file
        screenshot.write_bytes(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f'
            b'\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=465,
            from_addr="from@example.com",
            to_addr="to@example.com",
        )

        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            result = await notifier.send(
                "Title", "Body", screenshot_path=str(screenshot)
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_error_handled(self):
        notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=465,
            from_addr="from@example.com",
            to_addr="to@example.com",
        )

        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_smtp.side_effect = Exception("Connection refused")

            result = await notifier.send("Title", "Body")
            assert result is False

    @pytest.mark.asyncio
    async def test_non_ssl_mode(self):
        notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=587,
            use_ssl=False,
            from_addr="from@example.com",
            to_addr="to@example.com",
        )

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            result = await notifier.send("Title", "Body")
            assert result is True
            mock_server.starttls.assert_called_once()
