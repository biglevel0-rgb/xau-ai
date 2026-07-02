# Deploying XAU-AI to a Linux server

The container runs the analysis loop and pushes LONG/SHORT signals to your
Telegram (owner-only). It uses the **TwelveData** cloud provider — MetaTrader 5
is Windows-only and is not part of the image.

## 0. Security first (do this before anything else)

Any token/password that was ever pasted into a chat or file must be treated as
leaked:

1. **Telegram bot token** — open @BotFather → `/revoke` → get a new token.
2. **Server password** — change it, then prefer key-only SSH:
   ```bash
   # from your local machine
   ssh-keygen -t ed25519 -C "xau-ai"
   ssh-copy-id user@YOUR_SERVER_IP
   # then, on the server, disable password login in /etc/ssh/sshd_config:
   #   PasswordAuthentication no
   sudo systemctl restart ssh
   ```
3. Never commit `.env`. It is git-ignored and excluded from the Docker image.

## 1. Install Docker on the server

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in afterwards
docker compose version
```

## 2. Get the code and configure secrets

```bash
git clone <your-repo-url> xau-ai && cd xau-ai
cp .env.example .env
nano .env    # fill in the REAL values:
#   TELEGRAM_BOT_TOKEN=...      (the NEW token from BotFather)
#   TELEGRAM_OWNER_CHAT_ID=262846950
#   TWELVEDATA_API_KEY=...      (from twelvedata.com)
```

Tune `config/settings.yaml` (thresholds, weights, timeframes, `related_symbols`)
to taste — it is mounted read-only, so edits take effect on the next restart, no
rebuild needed.

## 3. Build and run

```bash
docker compose up -d --build
docker compose logs -f          # watch it work
```

The service analyses every `ANALYZE_INTERVAL_SECONDS` (default 300s) and sends
only LONG/SHORT to the owner chat. `restart: unless-stopped` keeps it alive
across crashes and reboots.

## 4. Operate

```bash
docker compose ps               # status
docker compose logs --tail=100  # recent output
docker compose restart          # after editing config/.env
docker compose down             # stop
docker compose up -d --build    # after pulling new code
```

Decisions are persisted under `./journal/` on the host.

## Notes & limits

- **Data**: XAU/USD volume is not provided by TwelveData, so volume-based
  confidence is limited; the rest of the stack is unaffected.
- **Not financial advice / no profit guarantee.** Calibrate on out-of-sample
  history (`xau calibrate`) and review the journal before trusting weights.
- To run locally against CSV instead of the cloud, use `--provider csv`.
