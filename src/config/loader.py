"""Configuration loader — YAML + env var merging, typed config via dataclasses."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ─── Config Dataclasses ───


@dataclass
class ViewportConfig:
    width: int = 1920
    height: int = 1080


@dataclass
class BrowserConfig:
    headless: bool = True
    slow_mo: int = 0
    timeout: int = 30000
    viewport: ViewportConfig = field(default_factory=ViewportConfig)
    user_agent: str = ""
    proxy: str = ""


@dataclass
class EventConfig:
    url: str = ""
    ticket_count: int = 1
    price_tier: int = 0
    price_text: str = ""


@dataclass
class TimingConfig:
    sale_time: str = ""
    ntp_server: str = "ntp.aliyun.com"
    pre_load_seconds: int = 30
    refresh_interval_ms: int = 500
    retry_interval_ms: int = 1000


@dataclass
class AntiDetectConfig:
    stealth_mode: bool = True
    humanize_actions: bool = True
    min_action_delay_ms: int = 50
    max_action_delay_ms: int = 200
    captcha_solver: str = "none"
    captcha_api_key: str = ""


@dataclass
class NotificationChannelConfig:
    type: str = ""
    webhook_url: str = ""
    secret: str = ""
    bot_token: str = ""
    chat_id: str = ""
    server: str = ""
    device_key: str = ""
    enabled: bool = False


@dataclass
class NotificationConfig:
    enabled: bool = True
    channels: list[NotificationChannelConfig] = field(default_factory=list)
    events: list[str] = field(default_factory=lambda: [
        "order_success", "captcha_required", "error", "sold_out",
    ])


@dataclass
class PersistenceConfig:
    cookies_file: str = "data/cookies/damai_cookies.json"
    encrypt_cookies: bool = True
    encryption_key: str = ""


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "data/logs/bot_{time}.log"
    rotation: str = "10 MB"
    screenshot_on_error: bool = True
    screenshot_dir: str = "data/screenshots"


@dataclass
class RetryConfig:
    max_attempts: int = 50
    base_delay_ms: int = 500
    max_delay_ms: int = 3000
    backoff_multiplier: float = 1.5
    jitter: bool = True


@dataclass
class SelectorsConfig:
    """Loaded from config/selectors.yaml separately."""
    login: dict = field(default_factory=dict)
    event_page: dict = field(default_factory=dict)
    order_page: dict = field(default_factory=dict)
    captcha: dict = field(default_factory=dict)
    payment: dict = field(default_factory=dict)


@dataclass
class BotConfig:
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    event: EventConfig = field(default_factory=EventConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    anti_detect: AntiDetectConfig = field(default_factory=AntiDetectConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    selectors: SelectorsConfig = field(default_factory=SelectorsConfig)


# ─── Loading Logic ───


def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with os.environ value, raising if missing."""
    pattern = re.compile(r"\$\{(\w+)\}")

    def replacer(match):
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            raise EnvironmentError(
                f"Environment variable '{var_name}' is required but not set."
            )
        return env_val

    return pattern.sub(replacer, value)


def _deep_substitute(obj):
    """Recursively substitute env vars in all string values."""
    if isinstance(obj, dict):
        return {k: _deep_substitute(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_substitute(item) for item in obj]
    elif isinstance(obj, str):
        return _substitute_env_vars(obj)
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _build_dataclass(dc_type, data: dict):
    """Build a dataclass instance from a dict, mapping fields recursively."""
    if not isinstance(data, dict):
        return data

    field_types = {f.name: f.type for f in dc_type.__dataclass_fields__.values()}
    kwargs = {}

    for field_name, field_type_str in field_types.items():
        raw_value = data.get(field_name)

        # Resolve the actual type from the type string
        if raw_value is None:
            continue

        # Check if the field type is another dataclass we defined
        actual_type = dc_type.__dataclass_fields__[field_name].type
        # Handle string-type annotations (from __future__ import annotations)
        if isinstance(actual_type, str):
            # Look up in our registry of dataclass types
            _dc_registry = {
                "ViewportConfig": ViewportConfig,
                "BrowserConfig": BrowserConfig,
                "EventConfig": EventConfig,
                "TimingConfig": TimingConfig,
                "AntiDetectConfig": AntiDetectConfig,
                "NotificationChannelConfig": NotificationChannelConfig,
                "NotificationConfig": NotificationConfig,
                "PersistenceConfig": PersistenceConfig,
                "LoggingConfig": LoggingConfig,
                "RetryConfig": RetryConfig,
                "SelectorsConfig": SelectorsConfig,
            }
            resolved = _dc_registry.get(actual_type)
            if resolved and isinstance(raw_value, dict):
                kwargs[field_name] = _build_dataclass(resolved, raw_value)
                continue

        kwargs[field_name] = raw_value

    return dc_type(**kwargs)


def _build_config(raw: dict) -> BotConfig:
    """Build a typed BotConfig from a raw dict."""
    config = BotConfig()

    # Build each section
    if "browser" in raw:
        config.browser = _build_dataclass(BrowserConfig, raw["browser"])
    if "event" in raw:
        config.event = _build_dataclass(EventConfig, raw["event"])
    if "timing" in raw:
        config.timing = _build_dataclass(TimingConfig, raw["timing"])
    if "anti_detect" in raw:
        config.anti_detect = _build_dataclass(AntiDetectConfig, raw["anti_detect"])
    if "persistence" in raw:
        config.persistence = _build_dataclass(PersistenceConfig, raw["persistence"])
    if "logging" in raw:
        config.logging = _build_dataclass(LoggingConfig, raw["logging"])
    if "retry" in raw:
        config.retry = _build_dataclass(RetryConfig, raw["retry"])

    # Notifications: build channels list
    if "notifications" in raw:
        notif_raw = raw["notifications"]
        channels = []
        for ch in notif_raw.get("channels", []):
            channels.append(_build_dataclass(NotificationChannelConfig, ch))
        config.notifications = NotificationConfig(
            enabled=notif_raw.get("enabled", True),
            channels=channels,
            events=notif_raw.get("events", config.notifications.events),
        )

    return config


def load_config(
    config_path: str = "config/default.yaml",
    event_config_path: Optional[str] = None,
    selectors_path: str = "config/selectors.yaml",
) -> BotConfig:
    """Load and merge configuration from YAML files + env vars.

    1. Load default.yaml
    2. Optionally merge event-specific overrides
    3. Substitute ${ENV_VAR} placeholders
    4. Build typed BotConfig
    5. Load selectors.yaml separately (no env substitution)
    """
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    # Merge event-specific overrides
    if event_config_path and Path(event_config_path).exists():
        with open(event_config_path) as f:
            event_overrides = yaml.safe_load(f)
        if event_overrides:
            raw = _deep_merge(raw, event_overrides)

    # Substitute environment variables
    raw = _deep_substitute(raw)

    # Build typed config
    config = _build_config(raw)

    # Load selectors separately (no env var substitution needed)
    if Path(selectors_path).exists():
        with open(selectors_path) as f:
            selectors_raw = yaml.safe_load(f)
        if selectors_raw:
            config.selectors = SelectorsConfig(**selectors_raw)

    return config
