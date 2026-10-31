# Deployment Guide: Pixel Promotion Claim Assistant

This document outlines deployment strategies for running the **Pixel Promotion Claim Assistant** Telegram bot across various environments (Local, Replit, Docker, and Linux VPS with systemd).

---

## 1. Prerequisites

- **Python**: Version 3.10 or higher (Python 3.11, 3.12, and 3.13 supported).
- **Telegram Bot Token**: Generated from [@BotFather](https://t.me/BotFather).
- **Database**: SQLite (default, zero configuration required) or PostgreSQL (for production multi-worker environments).
- **Optional - Android SDK / ADB**: For physical device verification via ADB.

---

## 2. Local Environment Setup

### Windows (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/TrkQuang/v01.git
cd v01

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
$env:TELEGRAM_BOT_TOKEN="your_token_from_botfather"
$env:DATABASE_URL="sqlite:///pixel_diagnostics.db"

# 5. Run test suite to verify installation
pytest tests -v

# 6. Start the bot
python main.py
```

### Linux / macOS (Bash)

```bash
# 1. Clone repository
git clone https://github.com/TrkQuang/v01.git
cd v01

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export TELEGRAM_BOT_TOKEN="your_token_from_botfather"
export DATABASE_URL="sqlite:///pixel_diagnostics.db"

# 5. Run test suite
pytest tests -v

# 6. Launch the bot
python3 main.py
```

---

## 3. Replit Deployment

The repository includes native `.replit` and `replit.nix` configuration.

1. Import the GitHub repository into your Replit workspace.
2. In the Replit sidebar, open **Secrets** (Environment Variables).
3. Add the key `TELEGRAM_BOT_TOKEN` with your bot token.
4. (Optional) Set `DATABASE_URL` or let it default to SQLite (`pixel_diagnostics.db`).
5. Click the green **Run** button. The configured `.replit` workflow will install dependencies and start `python main.py`.

---

## 4. Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run as non-root user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
```

### Docker Compose (`docker-compose.yml`)

```yaml
version: "3.8"

services:
  claim-assistant:
    build: .
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=postgresql://botuser:secretpassword@postgres:5432/pixel_claim
      - LOG_LEVEL=INFO
    depends_on:
      postgres:
        condition: service_healthy

  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: pixel_claim
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U botuser -d pixel_claim"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

Launch with:
```bash
docker compose up -d
```

---

## 5. Linux VPS Deployment (systemd)

To run the assistant as a persistent background daemon on Ubuntu / Debian:

1. Create a service user:
   ```bash
   sudo useradd -m -s /bin/bash pixelbot
   sudo su - pixelbot
   git clone https://github.com/TrkQuang/v01.git app
   cd app
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   exit
   ```

2. Create `/etc/systemd/system/pixel-bot.service`:
   ```ini
   [Unit]
   Description=Pixel Promotion Claim Assistant Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=pixelbot
   WorkingDirectory=/home/pixelbot/app
   Environment="TELEGRAM_BOT_TOKEN=your_token_here"
   Environment="DATABASE_URL=sqlite:////home/pixelbot/app/pixel_diagnostics.db"
   ExecStart=/home/pixelbot/app/.venv/bin/python main.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and activate the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable pixel-bot
   sudo systemctl start pixel-bot
   sudo systemctl status pixel-bot
   ```

4. View live logs:
   ```bash
   sudo journalctl -u pixel-bot -f
   ```

---

## 6. Health Checks & Verification

Verify platform operational status via Telegram or shell:

- Send `/status` to the bot to verify database connectivity, active session counts, and system status.
- Run tests at any time without disrupting running services:
  ```bash
  pytest tests -v
  ```
