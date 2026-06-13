"""Snatcher state machine — core ticket-snatching orchestration."""

from __future__ import annotations

import asyncio
import enum
from loguru import logger

from src.config.loader import BotConfig
from src.core.browser import BrowserManager
from src.core.scheduler import CountdownScheduler
from src.actions.login import LoginAction
from src.actions.navigate import NavigateAction
from src.actions.select_ticket import SelectTicketAction
from src.actions.submit_order import SubmitOrderAction
from src.actions.payment import PaymentDetector
from src.anti_detect.captcha import CaptchaHandler, create_solver
from src.notify.base import NotificationManager, BaseNotifier
from src.utils.screenshot import ScreenshotManager
from src.persistence.state import RunState, StatePersistence


class State(enum.Enum):
    """State machine states for the ticket-snatching flow."""
    INIT = "init"
    LOGGING_IN = "logging_in"
    LOGGED_IN = "logged_in"
    NAVIGATING = "navigating"
    WAITING_FOR_SALE = "waiting_for_sale"
    SELECTING_TICKET = "selecting_ticket"
    SUBMITTING_ORDER = "submitting_order"
    PAYMENT_PENDING = "payment_pending"
    DONE = "done"
    FAILED = "failed"


class SnatcherStateMachine:
    """Core state machine driving the ticket-snatching flow.

    Each state maps to an async handler method. The machine runs
    until reaching a terminal state (DONE or FAILED).
    """

    def __init__(
        self,
        browser: BrowserManager,
        scheduler: CountdownScheduler,
        notifier: NotificationManager,
        config: BotConfig,
    ):
        self.browser = browser
        self.scheduler = scheduler
        self.notifier = notifier
        self.config = config
        self.state = State.INIT
        self.attempt = 0
        self.max_attempts = config.retry.max_attempts

        # Captcha handler
        solver = create_solver(config)
        self.captcha_handler = CaptchaHandler(
            browser.page if browser._page else None,
            solver,
            notifier,
        )

        # Action handlers (initialized after browser starts)
        self._login: LoginAction | None = None
        self._navigate: NavigateAction | None = None
        self._select: SelectTicketAction | None = None
        self._submit: SubmitOrderAction | None = None
        self._payment: PaymentDetector | None = None
        self.screenshots = ScreenshotManager(config.logging.screenshot_dir)
        self.state_persistence = StatePersistence()

    def _init_actions(self) -> None:
        """Initialize action handlers after browser has started."""
        self._login = LoginAction(self.browser, self.config)
        self._navigate = NavigateAction(self.browser, self.config)
        self.captcha_handler.page = self.browser.page
        self._select = SelectTicketAction(
            self.browser, self.config, self.captcha_handler
        )
        self._submit = SubmitOrderAction(
            self.browser, self.config, self.captcha_handler
        )
        self._payment = PaymentDetector(self.browser, self.config)

    async def run(self) -> State:
        """Execute the state machine until terminal state."""
        # Save initial run state
        from datetime import datetime, timezone
        self.state_persistence.save(
            RunState(
                state=self.state.value,
                attempt=self.attempt,
                started_at=datetime.now(timezone.utc).isoformat(),
                last_update=datetime.now(timezone.utc).isoformat(),
                error=None,
            )
        )

        handlers = {
            State.INIT: self._handle_init,
            State.LOGGING_IN: self._handle_login,
            State.LOGGED_IN: self._handle_navigate,
            State.WAITING_FOR_SALE: self._handle_wait_for_sale,
            State.SELECTING_TICKET: self._handle_select_ticket,
            State.SUBMITTING_ORDER: self._handle_submit_order,
            State.PAYMENT_PENDING: self._handle_payment,
        }

        while self.state not in (State.DONE, State.FAILED):
            handler = handlers.get(self.state)
            if handler is None:
                logger.error(f"No handler for state: {self.state}")
                self.state = State.FAILED
                break

            logger.info(f"Entering state: {self.state.value}")
            try:
                self.state = await handler()
                # Update run state checkpoint
                self.state_persistence.save(
                    RunState(
                        state=self.state.value,
                        attempt=self.attempt,
                        started_at=self.state_persistence.load().started_at if self.state_persistence.load() else "",
                        last_update="",
                        error=None,
                    )
                )
            except Exception as e:
                logger.exception(f"Error in state {self.state.value}: {e}")
                await self.screenshots.capture(
                    self.browser.page, f"error_{self.state.value}"
                )
                self.state = await self._handle_error(e)

        logger.info(f"State machine finished — final state: {self.state.value}")
        return self.state

    async def _handle_init(self) -> State:
        """Initialize browser and actions."""
        await self.browser.start()
        self._init_actions()

        await self.notifier.send(
            "🤖 Bot 已启动",
            f"目标: {self.config.event.url}\n开售时间: {self.config.timing.sale_time}",
        )
        return State.LOGGING_IN

    async def _handle_login(self) -> State:
        """Login via cookie restoration or QR code."""
        is_logged_in = await self._login.restore_or_login()
        if not is_logged_in:
            raise RuntimeError("Login failed — could not establish session")
        return State.LOGGED_IN

    async def _handle_navigate(self) -> State:
        """Navigate to event page and parse ticket info."""
        success = await self._navigate.go_to_event_page()
        if not success:
            raise RuntimeError("Failed to navigate to event page")

        info = await self._navigate.parse_ticket_info()
        logger.info(f"Event page loaded — {len(info.get('tiers', []))} tiers available")

        return State.WAITING_FOR_SALE

    async def _handle_wait_for_sale(self) -> State:
        """Wait for exact sale time with countdown."""
        await self.notifier.send(
            "⏳ 进入倒计时",
            f"开售时间: {self.config.timing.sale_time}",
        )

        await self.scheduler.wait_until_sale_time(
            page=self.browser.page,
            refresh_interval_ms=self.config.timing.refresh_interval_ms,
        )
        return State.SELECTING_TICKET

    async def _handle_select_ticket(self) -> State:
        """Select target ticket and click buy."""
        self.attempt += 1
        logger.info(f"Attempt {self.attempt}/{self.max_attempts}")

        success = await self._select.select_and_buy()
        if not success:
            if self.attempt >= self.max_attempts:
                await self.notifier.send(
                    "❌ 抢票失败", "超过最大重试次数"
                )
                return State.FAILED

            # Retry: refresh page and try again
            await asyncio.sleep(self.config.timing.retry_interval_ms / 1000)
            await self.browser.page.reload()
            return State.SELECTING_TICKET

        return State.SUBMITTING_ORDER

    async def _handle_submit_order(self) -> State:
        """Fill and submit the order."""
        success = await self._submit.fill_and_submit()
        if not success:
            # Captcha or queue — retry from ticket selection
            return State.SELECTING_TICKET
        return State.PAYMENT_PENDING

    async def _handle_payment(self) -> State:
        """Detect payment page and notify user."""
        is_payment = await self._payment.wait_for_payment_page(timeout=15000)
        if is_payment:
            path = await self.screenshots.capture(
                self.browser.page, "payment_page"
            )
            await self.notifier.send(
                "🎫 抢票成功！",
                "已到达支付页面，请尽快完成付款！\n"
                f"事件: {self.config.event.url}",
                screenshot_path=path,
            )
            return State.DONE
        else:
            logger.warning("Payment page not detected — order may have failed")
            await self.notifier.send(
                "⚠️ 订单状态不确定",
                "未能检测到支付页面，请手动检查",
            )
            return State.FAILED

    async def _handle_error(self, error: Exception) -> State:
        """Decide whether to retry or fail based on error type."""
        await self.notifier.send(
            "⚠️ 抢票异常",
            f"状态: {self.state.value}\n错误: {str(error)}",
        )

        # Update run state with error info
        self.state_persistence.save(
            RunState(
                state=self.state.value,
                attempt=self.attempt,
                started_at=self.state_persistence.load().started_at if self.state_persistence.load() else "",
                last_update="",
                error=str(error),
            )
        )

        if self.attempt < self.max_attempts:
            return State.SELECTING_TICKET  # Retry from selection
        return State.FAILED
