# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ticket-bot** — 大麦网 (damai.cn) 自动抢票工具。Python + Playwright 浏览器自动化，Docker 部署。

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run bot (requires .env with DAMAI_EVENT_URL and DAMAI_SALE_TIME)
python -m src.main

# Run with custom event config
python -m src.main --event-config config/events/my_concert.yaml

# Login helper (get cookies via QR scan)
python -m scripts.login_helper

# Validate selectors against live site
python -m scripts.selector_validator

# Docker
docker compose build
docker compose up damai-bot
docker compose --profile tools run --rm damai-login  # cookie login

# Tests
pytest tests/unit/
pytest tests/integration/
```

## Architecture

Core is a **state machine** (`src/core/snatcher.py`) with states: `INIT → LOGGING_IN → NAVIGATING → WAIT_FOR_SALE → SELECTING_TICKET → SUBMITTING_ORDER → PAYMENT_PENDING → DONE/FAILED`. Each state maps to an async handler.

Key flow:
1. Bot starts → launches stealth Chromium via `src/core/browser.py`
2. Login via cookie restore or QR scan (`src/actions/login.py`)
3. Navigate to event page, parse ticket tiers (`src/actions/navigate.py`)
4. NTP-synced countdown until sale time (`src/core/scheduler.py`)
5. Select tier + quantity + click buy (`src/actions/select_ticket.py`)
6. Submit order on confirmation page (`src/actions/submit_order.py`)
7. Detect payment page → notify user (`src/actions/payment.py`)

## Key Patterns

- **Config**: `config/default.yaml` + `.env` env vars. Loader in `src/config/loader.py` merges YAML → substitutes `${VAR}` → builds typed dataclasses. Selectors live separately in `config/selectors.yaml` for easy updates when 大麦网 changes DOM.
- **Anti-detect**: Three modules in `src/anti_detect/` — fingerprint.js injection, humanized Bézier-curve mouse movements, captcha handler with pluggable solver backends.
- **Notifications**: `src/notify/base.py` defines `BaseNotifier` interface + `NotificationManager` that fans out to all enabled channels concurrently. Channels: WeChat Work, DingTalk, Telegram, Bark.
- **Persistence**: Cookies saved as Playwright storage state JSON in `data/cookies/`. Run state checkpointed in `data/logs/run_state.json`.
- **Browser**: Playwright async API, Chromium only. Stealth patches injected via `add_init_script`. Headless/headful toggle via `DAMAI_HEADLESS` env var.

## Docker

`Dockerfile` — python:3.11-slim + Chromium + Chinese fonts (fonts-wqy-zenhei). `shm_size: 2gb` required for Chromium. `network_mode: host` for lowest latency to damai.cn servers. `restart: "no"` (one-shot job).
