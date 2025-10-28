import requests
import ffmpeg
import io
import time
import re
import redis
from config import REDIS_URL, EMBED_BASE_URL
from urllib.parse import urlparse

r = redis.from_url(REDIS_URL)

def slugify(title):
    slug = re.sub(r'[^a-zA-Z0-9]+', '', title.lower())
    return slug[:20] or 'stream'

def store_stream(stream_id, m3u8_url, title):
    start_time = time.time()
    pipe = r.pipeline()
    pipe.hset(f'stream:{stream_id}', mapping={
        'url': m3u8_url,
        'title': title,
        'start_time': start_time,
        'active': 'True'
    })
    pipe.expire(f'stream:{stream_id}', 86400 * 7)
    pipe.execute()

def remove_stream(stream_id):
    if r.exists(f'stream:{stream_id}'):
        r.hset(f'stream:{stream_id}', 'active', 'False')
        r.expire(f'stream:{stream_id}', 60)
        return True
    return False

def get_uptime(start_time):
    delta = time.time() - float(start_time)
    if delta < 60: return f"{int(delta)}s"
    if delta < 3600: return f"{int(delta//60)}m {int(delta%60)}s"
    if delta < 86400: return f"{int(delta//3600)}h {int(delta%3600//60)}m"
    return f"{int(delta//86400)}d"

def get_active_streams():
    streams = []
    for key in r.keys('stream:*'):
        data = r.hgetall(key)
        if data.get(b'active') == b'True':
            sid = key.decode().split(':')[1]
            streams.append({
                'id': sid,
                'title': data[b'title'].decode(),
                'uptime': get_uptime(data[b'start_time']),
                'url': data[b'url'].decode()
            })
    return sorted(streams, key=lambda x: x['title'])

def needs_proxy(m3u8_url):
    """FORCE PROXY ON EVERY STREAM"""
    return True  # ← This forces proxy for all

def get_proxy_url(m3u8_url, stream_id):
    return f"{EMBED_BASE_URL}/{stream_id}.m3u8"

def get_screenshot(m3u8_url):
    try:
        process = (
            ffmpeg
            .input(m3u8_url, ss=1, t=1)
            .filter('scale', 640, -1)
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True, timeout=15)
        )
        return io.BytesIO(process[0])
    except:
        return None
