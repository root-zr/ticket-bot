"""Unit tests for config loader — YAML parsing, env substitution, merging."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config.loader import (
    _substitute_env_vars,
    _deep_substitute,
    _deep_merge,
    _build_dataclass,
    _build_config,
    load_config,
    BotConfig,
    BrowserConfig,
    EventConfig,
    TimingConfig,
    AntiDetectConfig,
    NotificationConfig,
    NotificationChannelConfig,
    PersistenceConfig,
    LoggingConfig,
    RetryConfig,
    ViewportConfig,
)


class TestEnvVarSubstitution:
    """Tests for ${ENV_VAR} substitution."""

    def test_simple_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello_world")
        result = _substitute_env_vars("prefix_${TEST_VAR}_suffix")
        assert result == "prefix_hello_world_suffix"

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        result = _substitute_env_vars("${A}_${B}")
        assert result == "1_2"

    def test_missing_var_raises(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        with pytest.raises(EnvironmentError, match="NONEXISTENT_VAR"):
            _substitute_env_vars("${NONEXISTENT_VAR}")

    def test_no_substitution_needed(self):
        result = _substitute_env_vars("plain_string")
        assert result == "plain_string"

    def test_empty_string(self):
        result = _substitute_env_vars("")
        assert result == ""

    def test_deep_substitute_dict(self, monkeypatch):
        monkeypatch.setenv("URL", "https://example.com")
        monkeypatch.setenv("KEY", "secret123")
        data = {
            "url": "${URL}",
            "nested": {"key": "${KEY}"},
            "list": ["${URL}", "static"],
            "number": 42,
        }
        result = _deep_substitute(data)
        assert result["url"] == "https://example.com"
        assert result["nested"]["key"] == "secret123"
        assert result["list"] == ["https://example.com", "static"]
        assert result["number"] == 42


class TestDeepMerge:
    """Tests for deep dict merging."""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_override_adds_new_keys(self):
        base = {"a": 1}
        override = {"b": {"nested": True}}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": {"nested": True}}

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        override = {"a": 1}
        result = _deep_merge({}, override)
        assert result == {"a": 1}


class TestBuildDataclass:
    """Tests for building dataclass instances from dicts."""

    def test_viewport_config_defaults(self):
        vp = _build_dataclass(ViewportConfig, {})
        assert vp.width == 1920
        assert vp.height == 1080

    def test_viewport_config_custom(self):
        vp = _build_dataclass(ViewportConfig, {"width": 1280, "height": 720})
        assert vp.width == 1280
        assert vp.height == 720

    def test_browser_config(self):
        bc = _build_dataclass(BrowserConfig, {
            "headless": False,
            "slow_mo": 100,
            "timeout": 15000,
        })
        assert bc.headless is False
        assert bc.slow_mo == 100
        assert bc.timeout == 15000
        assert bc.viewport.width == 1920  # default

    def test_event_config(self):
        ec = _build_dataclass(EventConfig, {
            "url": "https://example.com",
            "ticket_count": 2,
            "price_tier": 1,
        })
        assert ec.url == "https://example.com"
        assert ec.ticket_count == 2
        assert ec.price_tier == 1

    def test_timing_config(self):
        tc = _build_dataclass(TimingConfig, {
            "sale_time": "2026-06-15T10:00:00+08:00",
        })
        assert tc.sale_time == "2026-06-15T10:00:00+08:00"
        assert tc.ntp_server == "ntp.aliyun.com"  # default
        assert tc.refresh_interval_ms == 500

    def test_anti_detect_config(self):
        ad = _build_dataclass(AntiDetectConfig, {
            "stealth_mode": True,
            "captcha_solver": "2captcha",
        })
        assert ad.stealth_mode is True
        assert ad.captcha_solver == "2captcha"
        assert ad.min_action_delay_ms == 50  # default

    def test_notification_channel_config(self):
        ch = _build_dataclass(NotificationChannelConfig, {
            "type": "wechat_work",
            "webhook_url": "https://example.com/webhook",
            "enabled": True,
        })
        assert ch.type == "wechat_work"
        assert ch.webhook_url == "https://example.com/webhook"
        assert ch.enabled is True

    def test_persistence_config(self):
        pc = _build_dataclass(PersistenceConfig, {
            "cookies_file": "/custom/path/cookies.json",
        })
        assert pc.cookies_file == "/custom/path/cookies.json"
        assert pc.encrypt_cookies is True  # default

    def test_logging_config(self):
        lc = _build_dataclass(LoggingConfig, {"level": "DEBUG"})
        assert lc.level == "DEBUG"
        assert lc.rotation == "10 MB"  # default

    def test_retry_config(self):
        rc = _build_dataclass(RetryConfig, {
            "max_attempts": 10,
            "base_delay_ms": 1000,
        })
        assert rc.max_attempts == 10
        assert rc.base_delay_ms == 1000
        assert rc.jitter is True  # default


class TestBuildConfig:
    """Tests for building full BotConfig from raw dict."""

    def test_build_minimal_config(self):
        raw = {
            "event": {
                "url": "https://example.com",
                "ticket_count": 1,
            },
            "timing": {
                "sale_time": "2026-06-15T10:00:00+08:00",
            },
        }
        config = _build_config(raw)
        assert isinstance(config, BotConfig)
        assert config.event.url == "https://example.com"
        assert config.timing.sale_time == "2026-06-15T10:00:00+08:00"
        assert config.browser.headless is True  # default

    def test_build_full_config(self):
        raw = {
            "browser": {"headless": False, "timeout": 60000},
            "event": {"url": "https://example.com", "ticket_count": 2},
            "timing": {"sale_time": "2026-06-15T10:00:00+08:00"},
            "anti_detect": {"stealth_mode": True},
            "persistence": {"cookies_file": "/tmp/cookies.json"},
            "logging": {"level": "DEBUG"},
            "retry": {"max_attempts": 5},
            "notifications": {
                "enabled": False,
                "channels": [],
            },
        }
        config = _build_config(raw)
        assert config.browser.headless is False
        assert config.browser.timeout == 60000
        assert config.event.ticket_count == 2
        assert config.retry.max_attempts == 5
        assert config.logging.level == "DEBUG"
        assert config.notifications.enabled is False

    def test_build_with_notification_channels(self):
        raw = {
            "event": {"url": "https://example.com"},
            "timing": {"sale_time": "2026-06-15T10:00:00+08:00"},
            "notifications": {
                "enabled": True,
                "channels": [
                    {
                        "type": "wechat_work",
                        "webhook_url": "https://hook.example.com",
                        "enabled": True,
                    },
                    {
                        "type": "telegram",
                        "bot_token": "token123",
                        "chat_id": "456",
                        "enabled": False,
                    },
                ],
            },
        }
        config = _build_config(raw)
        assert len(config.notifications.channels) == 2
        assert config.notifications.channels[0].type == "wechat_work"
        assert config.notifications.channels[1].type == "telegram"


class TestLoadConfig:
    """Integration-style tests for the full config loading pipeline."""

    def test_load_with_yaml_files(self, tmp_path, monkeypatch):
        """Test loading config from actual YAML files."""
        monkeypatch.setenv("DAMAI_EVENT_URL", "https://detail.damai.cn/item.htm?id=99999")
        monkeypatch.setenv("DAMAI_SALE_TIME", "2026-12-25T20:00:00+08:00")

        # Create a minimal config
        config_yaml = tmp_path / "test_config.yaml"
        config_yaml.write_text("""
event:
  url: "${DAMAI_EVENT_URL}"
  ticket_count: 1
timing:
  sale_time: "${DAMAI_SALE_TIME}"
browser:
  headless: true
notifications:
  enabled: false
  channels: []
""")

        # Create selectors file
        selectors_yaml = tmp_path / "selectors.yaml"
        selectors_yaml.write_text("""
login:
  test_selector: ".login-btn"
event_page:
  test_selector: ".buy-btn"
""")

        config = load_config(
            config_path=str(config_yaml),
            selectors_path=str(selectors_yaml),
        )

        assert config.event.url == "https://detail.damai.cn/item.htm?id=99999"
        assert config.timing.sale_time == "2026-12-25T20:00:00+08:00"
        assert config.browser.headless is True
        assert config.notifications.enabled is False
        assert config.selectors.login["test_selector"] == ".login-btn"

    def test_load_with_event_override(self, tmp_path, monkeypatch):
        """Test merging event-specific overrides."""
        monkeypatch.setenv("DAMAI_EVENT_URL", "https://example.com/event1")
        monkeypatch.setenv("DAMAI_SALE_TIME", "2026-06-15T10:00:00+08:00")

        base_yaml = tmp_path / "base.yaml"
        base_yaml.write_text("""
event:
  url: "${DAMAI_EVENT_URL}"
  ticket_count: 1
  price_tier: 0
timing:
  sale_time: "${DAMAI_SALE_TIME}"
notifications:
  enabled: false
  channels: []
""")

        event_yaml = tmp_path / "event_override.yaml"
        event_yaml.write_text("""
event:
  ticket_count: 3
  price_text: "880元"
""")

        config = load_config(
            config_path=str(base_yaml),
            event_config_path=str(event_yaml),
        )

        # Overridden values
        assert config.event.ticket_count == 3
        assert config.event.price_text == "880元"
        # Original values preserved
        assert config.event.url == "https://example.com/event1"


class TestBotConfigDefaults:
    """Verify default values for BotConfig and sub-configs."""

    def test_botconfig_default_construction(self):
        config = BotConfig()
        assert isinstance(config.browser, BrowserConfig)
        assert isinstance(config.event, EventConfig)
        assert isinstance(config.timing, TimingConfig)
        assert isinstance(config.anti_detect, AntiDetectConfig)
        assert isinstance(config.notifications, NotificationConfig)
        assert isinstance(config.persistence, PersistenceConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.retry, RetryConfig)

    def test_default_headless(self):
        config = BotConfig()
        assert config.browser.headless is True

    def test_default_timeout(self):
        config = BotConfig()
        assert config.browser.timeout == 30000

    def test_default_viewport(self):
        config = BotConfig()
        assert config.browser.viewport.width == 1920
        assert config.browser.viewport.height == 1080

    def test_default_retry_max_attempts(self):
        config = BotConfig()
        assert config.retry.max_attempts == 50

    def test_default_ntp_server(self):
        config = BotConfig()
        assert config.timing.ntp_server == "ntp.aliyun.com"
