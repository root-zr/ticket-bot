"""Humanized actions — random delays and Bézier-curve mouse movements."""

from __future__ import annotations

import asyncio
import random
import math

from loguru import logger


async def human_delay(min_ms: int = 50, max_ms: int = 200) -> None:
    """Wait a random duration to simulate human reaction time."""
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


async def human_click(page, selector: str, min_ms: int = 50, max_ms: int = 200) -> None:
    """Click an element with a random delay before the action."""
    await human_delay(min_ms, max_ms)
    await page.click(selector)


async def human_fill(page, selector: str, value: str, delay_per_char: int = 50) -> None:
    """Fill an input field character by character with random delays."""
    await page.click(selector)
    await page.fill(selector, "")  # Clear existing content
    for char in value:
        await page.type(selector, char, delay=random.randint(delay_per_char, delay_per_char * 3))


def generate_drag_path(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    num_steps: int = 30,
) -> list[tuple[float, float, float]]:
    """Generate a Bézier-curve drag path with variable speed.

    Returns list of (x, y, delay_seconds) tuples.

    Simulates human behavior:
    - Fast start (acceleration)
    - Slow middle (aiming)
    - Slight overshoot + correction at end
    """
    # Control points for cubic Bézier with overshoot
    overshoot_x = end_x + random.uniform(5, 15)
    cp1_x = start_x + (end_x - start_x) * 0.2
    cp1_y = start_y + random.uniform(-5, 5)
    cp2_x = start_x + (end_x - start_x) * 0.8
    cp2_y = end_y + random.uniform(-5, 5)

    path = []
    for i in range(num_steps + 1):
        t = i / num_steps

        # Cubic Bézier interpolation
        x = (
            (1 - t) ** 3 * start_x
            + 3 * (1 - t) ** 2 * t * cp1_x
            + 3 * (1 - t) * t ** 2 * cp2_x
            + t ** 3 * overshoot_x
        )
        y = (
            (1 - t) ** 3 * start_y
            + 3 * (1 - t) ** 2 * t * cp1_y
            + 3 * (1 - t) * t ** 2 * cp2_y
            + t ** 3 * end_y
        )

        # Variable speed: fast → slow → fast
        if t < 0.2:
            delay = random.uniform(0.005, 0.015)   # Fast start
        elif t < 0.8:
            delay = random.uniform(0.015, 0.040)   # Slow middle (aiming)
        else:
            delay = random.uniform(0.008, 0.020)   # Accelerate to end

        # Add slight Y-axis jitter (human hands aren't perfectly straight)
        y += random.uniform(-1, 1)

        path.append((x, y, delay))

    # Correction: move back from overshoot to exact target
    for i in range(5):
        t = i / 4
        x = overshoot_x + (end_x - overshoot_x) * t
        path.append((x, end_y + random.uniform(-0.5, 0.5), 0.03))

    return path


async def human_drag(page, element, target_x: float) -> None:
    """Simulate a human-like drag from element center to target_x offset.

    Used primarily for slider captcha solving.

    Args:
        page: Playwright Page object for mouse operations.
        element: The draggable element handle.
        target_x: X-offset in pixels to drag the element.
    """
    box = await element.bounding_box()
    if box is None:
        logger.warning("Element has no bounding box — cannot drag")
        return

    start_x = box["x"] + box["width"] / 2
    start_y = box["y"] + box["height"] / 2

    path = generate_drag_path(start_x, start_y, start_x + target_x, start_y)

    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    for px, py, delay in path:
        await page.mouse.move(px, py)
        await asyncio.sleep(delay)
    await page.mouse.up()


async def human_scroll(page, direction: str = "down", distance: int = 300) -> None:
    """Scroll the page with a human-like pattern (multiple small scrolls)."""
    steps = random.randint(3, 6)
    delta = distance // steps

    for _ in range(steps):
        dy = delta + random.randint(-20, 20)
        if direction == "up":
            dy = -dy
        await page.mouse.wheel(0, dy)
        await asyncio.sleep(random.uniform(0.05, 0.15))
