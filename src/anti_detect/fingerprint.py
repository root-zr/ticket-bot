"""Anti-detection fingerprint patches — stealth JS injection."""

from __future__ import annotations

from playwright.async_api import BrowserContext

from loguru import logger


# Stealth JS script injected before any page load
STEALTH_JS = """
() => {
    // 1. Override navigator.webdriver — most common detection vector
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });

    // 2. Spoof chrome.runtime to appear as a normal Chrome browser
    window.chrome = {
        runtime: {
            onMessage: { addListener: () => {}, removeListener: () => {} },
            sendMessage: () => {},
            connect: () => {},
        },
    };

    // 3. Override permissions.query — headless Chrome reports 'notifications' as 'denied'
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

    // 4. Spoof plugins array — headless Chrome has 0 plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ],
        configurable: true,
    });

    // 5. Spoof language — headless default is 'en-US' only
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
        configurable: true,
    });

    // 6. Override navigator.platform — some checks look for 'Win32' etc.
    Object.defineProperty(navigator, 'platform', {
        get: () => 'Win32',
        configurable: true,
    });

    // 7. Mask iframe contentWindow detection
    // Some anti-bot scripts check if an iframe's contentWindow has webdriver
    try {
        const originalAttachShadow = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function (...args) {
            const shadowRoot = originalAttachShadow.apply(this, args);
            shadowRoot.__proto__ = Object.create(shadowRoot.__proto__);
            return shadowRoot;
        };
    } catch (e) {}

    // 8. Fake WebGL vendor/renderer — some fingerprinting uses this
    try {
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function (parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
        };
    } catch (e) {}
}
"""


async def apply_stealth(context: BrowserContext) -> None:
    """Inject stealth script into every new page in the browser context.

    This patches the most common browser automation detection vectors:
    - navigator.webdriver flag
    - chrome.runtime presence
    - permissions query behavior
    - navigator.plugins count
    - navigator.languages
    - navigator.platform
    - Shadow DOM detection
    - WebGL fingerprinting
    """
    await context.add_init_script(STEALTH_JS)
    logger.info("Stealth fingerprint patches injected")
