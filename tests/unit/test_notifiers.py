"""Unit tests for notification backends."""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.notify.base import BaseNotifier, NotificationManager
from src.notify.wechat import WeChatNotifier
from src.notify.dingtalk import DingTalkNotifier
from src.notify.telegram import TelegramNotifier
from src.notify.bark import BarkNotifier


# ─── Dummy notifier for testing NotificationManager ───

class DummyNotifier(BaseNotifier):
    """Test notifier that records calls."""
    def __init__(self, name="dummy", should_fail=False):
        self.name = name
        self.should_fail = should_fail
        self.calls = []

    async def send(self, title, body, screenshot_path=None):
        self.calls.append((title, body, screenshot_path))
        if self.should_fail:
            raise RuntimeError(f"{self.name} failure")
        return True


class TestNotificationManager:
    """Tests for NotificationManager."""

    @pytest.mark.asyncio
    async def test_fans_out_to_all_channels(self):
        ch1 = DummyNotifier("ch1")
        ch2 = DummyNotifier("ch2")
        manager = NotificationManager([ch1, ch2])

        await manager.send("Title", "Body text")

        assert len(ch1.calls) == 1
        assert len(ch2.calls) == 1
        assert ch1.calls[0] == ("Title", "Body text", None)

    @pytest.mark.asyncio
    async def test_no_channels(self):
        manager = NotificationManager([])
        await manager.send("Title", "Body")  # Should not raise

    @pytest.mark.asyncio
    async def test_channel_failure_doesnt_block_others(self):
        ch1 = DummyNotifier("good")
        ch2 = DummyNotifier("bad", should_fail=True)
        ch3 = DummyNotifier("also_good")
        manager = NotificationManager([ch1, ch2, ch3])

        await manager.send("Title", "Body")

        # Good channels still received
        assert len(ch1.calls) == 1
        assert len(ch3.calls) == 1
        # Bad channel also attempted
        assert len(ch2.calls) == 1

    @pytest.mark.asyncio
    async def test_with_screenshot_path(self):
        ch = DummyNotifier("test")
        manager = NotificationManager([ch])

        await manager.send("Title", "Body", screenshot_path="/tmp/screenshot.png")
        assert ch.calls[0][2] == "/tmp/screenshot.png"


class TestWeChatNotifier:
    """Tests for WeChat Work notifier."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = WeChatNotifier("https://qyapi.weixin.qq.com/webhook/test")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"errcode": 0})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Test", "Hello world")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        notifier = WeChatNotifier("https://qyapi.weixin.qq.com/webhook/test")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"errcode": 40001, "errmsg": "invalid"})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Test", "Hello")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        notifier = WeChatNotifier("https://qyapi.weixin.qq.com/webhook/test")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await notifier.send("Test", "Hello")
            assert result is False

    @pytest.mark.asyncio
    async def test_send_marks_down_content(self):
        notifier = WeChatNotifier("https://qyapi.weixin.qq.com/webhook/test")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"errcode": 0})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            await notifier.send("Alert", "Something happened")

            # Verify it sent markdown type
            call_args = mock_session.post.call_args
            payload = call_args[1]["json"]
            assert payload["msgtype"] == "markdown"
            assert "Alert" in payload["markdown"]["content"]


class TestDingTalkNotifier:
    """Tests for DingTalk notifier."""

    def test_sign_url_no_secret(self):
        notifier = DingTalkNotifier("https://oapi.dingtalk.com/robot/send?key=abc")
        signed = notifier._sign_url()
        assert signed == "https://oapi.dingtalk.com/robot/send?key=abc"

    def test_sign_url_with_secret(self):
        notifier = DingTalkNotifier(
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            secret="SECtest123",
        )
        signed = notifier._sign_url()
        assert "timestamp=" in signed
        assert "sign=" in signed
        assert signed.startswith("https://oapi.dingtalk.com/robot/send?access_token=abc")

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = DingTalkNotifier("https://oapi.dingtalk.com/robot/send?key=abc")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"errcode": 0})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Title", "Body content")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        notifier = DingTalkNotifier("https://oapi.dingtalk.com/robot/send?key=abc")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"errcode": 1, "errmsg": "fail"})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Title", "Body")
            assert result is False


class TestTelegramNotifier:
    """Tests for Telegram notifier."""

    @pytest.mark.asyncio
    async def test_send_text_only(self):
        notifier = TelegramNotifier("test_token", "123456")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_post = AsyncMock()
            mock_post.__aenter__ = AsyncMock(return_value=mock_post)
            mock_post.__aexit__ = AsyncMock(return_value=None)
            mock_post.json = AsyncMock(return_value={"ok": True})
            mock_session.post.return_value = mock_post
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Title", "Body")
            assert result is True

    @pytest.mark.asyncio
    async def test_api_base_url(self):
        notifier = TelegramNotifier("my_bot_token", "98765")
        assert notifier.api_base == "https://api.telegram.org/botmy_bot_token"
        assert notifier.chat_id == "98765"

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        notifier = TelegramNotifier("test_token", "123")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await notifier.send("Title", "Body")
            assert result is False


class TestBarkNotifier:
    """Tests for Bark notifier."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        notifier = BarkNotifier(device_key="test_device_key")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_get = AsyncMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_get)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_get.json = AsyncMock(return_value={"code": 200})
            mock_session.get.return_value = mock_get
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Title", "Body text")
            assert result is True

    @pytest.mark.asyncio
    async def test_send_no_device_key(self):
        notifier = BarkNotifier(device_key="")

        result = await notifier.send("Title", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_server(self):
        notifier = BarkNotifier(
            server="https://custom.bark.server",
            device_key="abc123",
        )
        assert notifier.server == "https://custom.bark.server"
        assert notifier.device_key == "abc123"

    @pytest.mark.asyncio
    async def test_send_returns_false_on_error(self):
        notifier = BarkNotifier(device_key="test_key")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_get = AsyncMock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_get)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_get.json = AsyncMock(return_value={"code": 500, "message": "error"})
            mock_session.get.return_value = mock_get
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await notifier.send("Title", "Body")
            assert result is False
