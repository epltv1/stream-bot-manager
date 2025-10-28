import os

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
HOST = '0.0.0.0'
PORT = 5000
SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
EMBED_BASE_URL = 'https://stream.futbol-x.site'
REDIS_URL = 'redis://localhost:6379/0'
SEGMENT_DIR = '/tmp/stream_segments'
