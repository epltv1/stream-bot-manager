import os

# === TELEGRAM BOT ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# === SERVER ===
HOST = '0.0.0.0'
PORT = 5000
SECRET_KEY = os.getenv('SECRET_KEY', 'change_this_in_production')

# === EMBED URL ===
EMBED_BASE_URL = 'https://stream.futbol-x.site'  # Change after Cloudflare setup

# === REDIS ===
REDIS_URL = 'redis://localhost:6379/0'

# === HEALTH CHECK ===
HEALTH_CHECK_INTERVAL = 30
