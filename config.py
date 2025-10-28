import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN')
HOST = '0.0.0.0'
PORT = 5000
SECRET_KEY = os.getenv('SECRET_KEY', 'change_me')
EMBED_BASE_URL = 'https://stream.futbol-x.site'
REDIS_URL = 'redis://localhost:6379/0'
