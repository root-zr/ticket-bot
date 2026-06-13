# ── Stage 1: Base with Playwright browsers ──
FROM python:3.11-slim AS base

# Use Chinese Debian mirrors for faster apt (configured via ARG)
ARG USE_CHINA_MIRROR=false
RUN if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true; \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true; \
    fi

# Install system deps required by Playwright Chromium + Chinese fonts
# Also includes all Chromium runtime deps that playwright install-deps would install
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2t64 \
    libxshmfence1 \
    libglib2.0-0t64 \
    libdbus-1-3 \
    libexpat1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    libgtk-3-0t64 \
    libgdk-pixbuf2.0-0t64 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libenchant-2-2 \
    libsecret-1-0 \
    libhyphen0 \
    libmanette-0.2-0 \
    libflite1 \
    libgl1-mesa-glx \
    libegl1 \
    libgles2 \
    libopengl0 \
    libwoff1 \
    libvpx9 \
    libevent-2.1-7t64 \
    libgudev-1.0-0 \
    libnotify4 \
    libxslt1.1 \
    libvulkan1 \
    libepoxy0 \
    libjpeg62-turbo \
    libpng16-16t64 \
    libwebp7 \
    libwebpdemux2 \
    libwebpmux3 \
    libavif16 \
    libjbig0 \
    libtiff6 \
    liblcms2-2 \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fonts-unifont \
    fonts-liberation \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to China Standard Time
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Install Python dependencies (with optional Chinese mirror)
COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

# Install Playwright Chromium browser only (saves ~500MB vs all browsers)
# System deps already installed above; skip playwright install-deps
# PLAYWRIGHT_DOWNLOAD_HOST: override for Chinese mirrors
ARG PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net
ENV PLAYWRIGHT_DOWNLOAD_HOST=${PLAYWRIGHT_DOWNLOAD_HOST}
# Increase download timeout for slow connections (default is 30s)
ENV PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=120000
RUN playwright install chromium

# ── Stage 2: Application ──
FROM base AS app

COPY . .

# Create data directories
RUN mkdir -p data/cookies data/screenshots data/logs

# Non-root user for security
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Default command
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--config", "config/default.yaml"]
