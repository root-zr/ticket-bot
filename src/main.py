"""Entry point — orchestrates the full ticket-snatching flow."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from dotenv import load_dotenv
from loguru import logger

from src.config.loader import load_config, BotConfig
from src.core.browser import BrowserManager
from src.core.scheduler import CountdownScheduler
from src.core.snatcher import SnatcherStateMachine, State
from src.notify.base import NotificationManager, BaseNotifier
from src.notify.wechat import WeChatNotifier
from src.notify.dingtalk import DingTalkNotifier
from src.notify.telegram import TelegramNotifier
from src.notify.bark import BarkNotifier
from src.utils.logger import setup_logging


def build_notifier(config: BotConfig) -> NotificationManager:
    """Build notification manager from config channels."""
    channels: list[BaseNotifier] = []

    if not config.notifications.enabled:
        return NotificationManager(channels)

    for ch_config in config.notifications.channels:
        if not ch_config.enabled:
            continue

        try:
            if ch_config.type == "wechat_work":
                channels.append(WeChatNotifier(ch_config.webhook_url))
            elif ch_config.type == "dingtalk":
                channels.append(
                    DingTalkNotifier(ch_config.webhook_url, ch_config.secret)
                )
            elif ch_config.type == "telegram":
                channels.append(
                    TelegramNotifier(ch_config.bot_token, ch_config.chat_id)
                )
            elif ch_config.type == "bark":
                channels.append(
                    BarkNotifier(ch_config.server, ch_config.device_key)
                )
        except Exception as e:
            logger.warning(f"Failed to create notifier '{ch_config.type}': {e}")

    logger.info(f"Notification channels: {[type(c).__name__ for c in channels]}")
    return NotificationManager(channels)


async def run_bot(config: BotConfig) -> State:
    """Main bot execution flow."""
    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
        rotation=config.logging.rotation,
    )

    # Build components
    browser = BrowserManager(config)
    scheduler = CountdownScheduler(config)
    notifier = build_notifier(config)

    # Create and run state machine
    sm = SnatcherStateMachine(browser, scheduler, notifier, config)
    final_state = await sm.run()

    # Cleanup
    try:
        await browser.save_storage_state()
    except Exception:
        pass
    await browser.close()

    return final_state


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="大麦网自动抢票 Bot — Damai Auto-Ticket Snatcher"
    )
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to default config YAML file",
    )
    parser.add_argument(
        "--event-config",
        default=None,
        help="Path to event-specific override config YAML",
    )
    args = parser.parse_args()

    # Load .env file
    load_dotenv()

    # Load configuration
    try:
        config = load_config(
            config_path=args.config,
            event_config_path=args.event_config,
        )
    except EnvironmentError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Setup basic logging before full config
    setup_logging(level="INFO")

    logger.info("=" * 50)
    logger.info("大麦网自动抢票 Bot")
    logger.info("=" * 50)
    logger.info(f"Event URL: {config.event.url}")
    logger.info(f"Ticket count: {config.event.ticket_count}")
    logger.info(f"Sale time: {config.timing.sale_time}")
    logger.info(f"Headless: {config.browser.headless}")
    logger.info("=" * 50)

    # Run bot with graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        final_state = loop.run_until_complete(run_bot(config))
        if final_state == State.DONE:
            logger.info("✅ Bot completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Bot failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
