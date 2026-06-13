# 🎫 大麦网自动抢票 Bot

自动抢票工具，针对大麦网 (damai.cn) 演出/演唱会票务平台。基于 Python + Playwright 浏览器自动化，支持 Docker 部署。

## 功能特性

- 🚀 **毫秒级精确计时** — NTP 时间同步，确保在开售瞬间触发购买
- 🕵️ **反检测** — WebDriver 隐藏、指纹伪装、人机操作模拟（Bézier 鼠标轨迹）
- 📢 **多渠道通知** — 企业微信 / 钉钉 / Telegram / Bark / Email 并行推送
- 🔐 **会话持久化** — Cookie 自动保存/恢复，无需重复登录
- 🐳 **Docker 一键部署** — 内置 Chromium + 中文字体，无需手动安装依赖
- 🧩 **状态机架构** — 清晰的状态流转，便于调试和扩展

## 快速开始

### 前置条件

- Python 3.11+
- 或 Docker + Docker Compose

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入以下必填项：
# DAMAI_EVENT_URL=https://detail.damai.cn/item.htm?id=XXXXXXX  (演出页面URL)
# DAMAI_SALE_TIME=2026-06-15T10:00:00+08:00  (开售时间，ISO格式)
```

### 2. 获取登录 Cookie（首次运行）

**本地运行：**
```bash
pip install -r requirements.txt
playwright install chromium
python -m scripts.login_helper
# 在弹出的浏览器中扫描二维码登录
```

**Docker 运行（需要 X11 支持，macOS 需 XQuartz）：**
```bash
docker compose build
docker compose --profile tools run --rm damai-login
```

### 3. 运行抢票 Bot

**本地运行：**
```bash
python -m src.main
```

**Docker 运行：**
```bash
docker compose up damai-bot
```

### 4. 自定义事件配置

可以为特定演出创建配置覆盖文件：

```bash
cp config/events/example_concert.yaml config/events/my_event.yaml
# 编辑 my_event.yaml，设置演出URL、票价档位、票数等
python -m src.main --event-config config/events/my_event.yaml
```

## 项目架构

核心是一个**状态机驱动的浏览器自动化流程**：

```
INIT → LOGGING_IN → LOGGED_IN → NAVIGATING → WAITING_FOR_SALE
       → SELECTING_TICKET → SUBMITTING_ORDER → PAYMENT_PENDING → DONE
```

```
ticket-bot/
├── config/
│   ├── default.yaml             # 主配置（含 ${ENV_VAR} 占位符）
│   ├── selectors.yaml           # DOM 选择器（大麦改版时只需更新此文件）
│   └── events/                  # 演出专属配置覆盖
├── src/
│   ├── main.py                  # 入口，命令行解析
│   ├── config/
│   │   └── loader.py            # YAML + 环境变量 → 类型化配置
│   ├── core/
│   │   ├── snatcher.py          # 状态机编排（核心）
│   │   ├── browser.py           # Playwright 浏览器生命周期
│   │   ├── scheduler.py         # NTP 同步倒计时
│   │   └── retry.py             # 退避重试工具
│   ├── actions/
│   │   ├── login.py             # Cookie 恢复 / QR 扫码登录
│   │   ├── navigate.py          # 事件页面导航 + 票档解析
│   │   ├── select_ticket.py     # 选票档 + 数量 + 点击购买
│   │   ├── submit_order.py      # 订单确认页填写提交
│   │   └── payment.py           # 支付页面检测
│   ├── anti_detect/
│   │   ├── fingerprint.py       # Stealth JS 注入
│   │   ├── humanize.py          # Bézier 曲线 / 随机延迟
│   │   └── captcha.py           # 验证码检测与求解（可扩展）
│   ├── notify/
│   │   ├── base.py              # 通知接口 + 多通道管理器
│   │   ├── wechat.py            # 企业微信 webhook
│   │   ├── dingtalk.py          # 钉钉自定义机器人
│   │   ├── telegram.py          # Telegram Bot API
│   │   ├── bark.py              # Bark iOS 推送
│   │   └── email_notify.py      # SMTP 邮件
│   ├── persistence/
│   │   ├── cookies.py           # Cookie JSON 存储
│   │   └── state.py             # 运行时状态检查点
│   └── utils/
│       ├── logger.py            # Loguru 日志设置
│       ├── screenshot.py        # 截图管理
│       └── time_sync.py         # NTP 时钟同步
├── scripts/
│   ├── login_helper.py          # 交互式扫码登录工具
│   └── selector_validator.py    # 选择器有效性验证工具
├── tests/
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── e2e/                     # 端到端测试
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 配置说明

### 全部配置项

| 配置路径 | 类型 | 默认值 | 说明 |
|---------|------|--------|------|
| `browser.headless` | bool | `true` | 无头模式；调试时设 `false` |
| `browser.slow_mo` | int | `0` | 操作间延迟(ms)，调试用 |
| `browser.timeout` | int | `30000` | 页面加载超时(ms) |
| `browser.viewport.width` | int | `1920` | 浏览器窗口宽度 |
| `browser.viewport.height` | int | `1080` | 浏览器窗口高度 |
| `event.url` | str | — | 演出详情页 URL（必填） |
| `event.ticket_count` | int | `1` | 购买票数 (1-6) |
| `event.price_tier` | int | `0` | 票档索引（0=最低价） |
| `event.price_text` | str | `""` | 按票价文字匹配（如"880元"） |
| `timing.sale_time` | str | — | 开售时间 ISO 格式（必填） |
| `timing.ntp_server` | str | `ntp.aliyun.com` | NTP 服务器 |
| `timing.pre_load_seconds` | int | `30` | 提前加载页面秒数 |
| `timing.refresh_interval_ms` | int | `500` | 最后倒计时刷新间隔 |
| `anti_detect.stealth_mode` | bool | `true` | 启用指纹伪装 |
| `anti_detect.humanize_actions` | bool | `true` | 启用操作人机化 |
| `anti_detect.captcha_solver` | str | `none` | 验证码方案选择 |
| `retry.max_attempts` | int | `50` | 最大重试次数 |
| `logging.level` | str | `INFO` | 日志级别 |

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DAMAI_EVENT_URL` | ✅ | 演出详情页URL |
| `DAMAI_SALE_TIME` | ✅ | 开售时间 (ISO 8601) |
| `DAMAI_HEADLESS` | ❌ | 是否无头模式 (默认true) |
| `CAPTCHA_API_KEY` | ❌ | 验证码API密钥 |
| `COOKIE_ENCRYPT_KEY` | ❌ | Cookie 加密密钥 |
| `WECHAT_WEBHOOK_URL` | ❌ | 企业微信webhook |
| `DINGTALK_WEBHOOK_URL` | ❌ | 钉钉webhook |
| `DINGTALK_SECRET` | ❌ | 钉钉签名密钥 |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram Bot token |
| `TELEGRAM_CHAT_ID` | ❌ | Telegram 聊天ID |
| `BARK_DEVICE_KEY` | ❌ | Bark推送设备key |

## 通知渠道

支持以下推送渠道（并行发送，单渠道失败不影响其他）：

| 渠道 | 配置方式 | 支持截图 | 备注 |
|------|---------|---------|------|
| 企业微信 | Webhook URL | ❌ | Markdown 消息 |
| 钉钉 | Webhook URL + Secret | ❌ | 支持签名验证 |
| Telegram | Bot Token + Chat ID | ✅ | 截图附件 |
| Bark | Device Key | ❌ | iOS 推送 |
| Email | SMTP 配置 | ✅ | HTML + 截图附件 |

抢票成功时，Bot 会推送支付页面截图，请尽快手动完成付款。

## 验证码方案

目前支持三种验证码处理方案（可扩展）：

| 方案 | `captcha_solver` | 说明 |
|------|-----------------|------|
| 手动 | `manual` / `none` | 在 headful 模式下人工解决 |
| 2Captcha | `2captcha` | 2captcha.com API（需实现） |
| 超级鹰 | `cjy` | chaojiying.com API（需实现） |

建议使用 **headful 模式**（`DAMAI_HEADLESS=false`）运行，以便在看到验证码时手动解决。

## Docker 说明

### 国内加速构建

设置以下环境变量使用国内镜像加速：

```bash
# 一站式国内加速
export USE_CHINA_MIRROR=true
export PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
docker compose build
```

或者使用 `.env` 文件：

```bash
# .env 中添加
USE_CHINA_MIRROR=true
PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
```

### 配置说明

- 基于 `python:3.11-slim`，内置 Chromium + 中文字体
- `shm_size: 2gb` — Chromium 需要（默认64MB会崩溃）
- `network_mode: host` — 最低延迟（避免NAT开销）
- `restart: "no"` — 一次性任务，完成后不重启
- Cookie、截图、日志通过 volume 持久化

## 开发

### 运行测试

```bash
# 安装测试依赖
pip install -r requirements.txt

# 运行所有单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行端到端测试
pytest tests/e2e/ -v
```

### 验证选择器

当大麦网更新页面结构时，运行选择器验证脚本确认是否需要更新配置：

```bash
python -m scripts.selector_validator
```

### 添加新的验证码求解器

继承 `CaptchaSolver` 基类并实现两个方法：

```python
from src.anti_detect.captcha import CaptchaSolver

class MySolver(CaptchaSolver):
    async def solve_slider(self, bg_image: bytes, slider_image: bytes) -> dict:
        # 返回 {'x': pixel_offset}
        ...

    async def solve_click_order(self, image: bytes, prompt: str) -> list:
        # 返回 [(x1,y1), (x2,y2), ...]
        ...
```

然后在 `captcha.py` 的 `create_solver()` 中注册即可。

## 常见问题

### Q: Cookie 过期怎么办？
直接重新运行 `python -m scripts.login_helper` 获取新的 Cookie。

### Q: 按钮状态显示"即将开抢"但明明到时间了？
系统时间可能不同步。检查 NTP 同步状态，或切换 NTP 服务器。

### Q: 运行 Docker 时 Chrome 崩溃？
确保设置了 `shm_size: "2gb"`，共享内存不足是 Chromium 在 Docker 中的常见问题。

### Q: 选择器失效了怎么办？
大麦网可能更新了 DOM 结构。运行 `python -m scripts.selector_validator` 检查哪些选择器失效，然后更新 `config/selectors.yaml`。

### Q: 如何提高抢票成功率？
1. 使用 `network_mode: host` 消除 Docker NAT 延迟
2. 确保 NTP 同步正常（国内推荐 `ntp.aliyun.com`）
3. 设置更短的 `refresh_interval_ms`（如 200ms）
4. 在 headful 模式下运行，以便快速应对验证码
5. 确保网络稳定，延迟低于 50ms

## 注意事项

- ⚠️ 本工具仅供个人学习和研究使用，请勿用于商业牟利
- ⚠️ 使用本工具可能导致账号被封禁，风险自负
- ⚠️ 大麦网可能更新反爬机制，需及时更新相应的反检测策略
- ⚠️ 支付环节需手动完成，Bot 的职责在到达支付页面后结束

## License

MIT — see [LICENSE](LICENSE)
