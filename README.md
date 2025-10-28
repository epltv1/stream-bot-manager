# Stream Bot Manager

A Telegram bot + embed player to manage live m3u8 streams.

## Features
- `/stream <m3u8> <title>` → Start stream + get embed link
- `/live` → See all live streams with **real-time**:
  - Screenshot
  - Title
  - Uptime (seconds → days)
  - Viewers count
  - Stop button
  - Embed link
- Embed player with:
  - Auto quality
  - PiP (Picture-in-Picture)
  - Live / Offline badge
  - Real-time viewers
  - Proxy for restricted streams
- Runs 24/7 on VPS
- Uses `stream.futbol-x.site` (no IP shown)

## Deploy
```bash
git clone https://github.com/yourusername/stream-bot-manager.git
cd stream-bot-manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_TOKEN='your_bot_token'
python server.py
