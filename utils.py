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
    """Convert title to safe URL ID (max 20 chars, alphanumeric only)"""
    slug = re.sub(r'[^a-zA-Z0-9]+', '', title.lower())
    return slug[:20] or 'stream'

def store_stream(stream_id, m3u8_url, title):
    """Store stream in Redis with title and start time"""
    start_time = time.time()
    pipe = r.pipeline()
    pipe.hset(f'stream:{stream_id}', mapping={
        'url': m3u8_url,
        'title': title,
        'start_time': start_time,
        'active': 'True'
    })
    pipe.expire(f'stream:{stream_id}', 86400 * 7)  # Auto-delete after 7 days
    pipe.execute()

def remove_stream(stream_id):
    """Stop stream and mark for deletion"""
    if r.exists(f'stream:{stream_id}'):
        r.hset(f'stream:{stream_id}', 'active', 'False')
        r.expire(f'stream:{stream_id}', 60)  # Delete in 1 min
        return True
    return False

def get_uptime(start_time):
    """Human-readable uptime: 5s, 2m 30s, 1h 15m, 3d"""
    delta = time.time() - float(start_time)
    if delta < 60:
        return f"{int(delta)}s"
    if delta < 3600:
        return f"{int(delta//60)}m {int(delta%60)}s"
    if delta < 86400:
        return f"{int(delta//3600)}h {int(delta%3600//60)}m"
    return f"{int(delta//86400)}d"

def get_active_streams():
    """Return list of all active streams"""
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
    """Detect if stream needs proxy (CORS, domain lock, etc.)"""
    try:
        resp = requests.head(m3u8_url, timeout=8, allow_redirects=True)
        if resp.status_code >= 400:
            return True
        # Check CORS
        cors = resp.headers.get('Access-Control-Allow-Origin', '')
        if cors and cors != '*':
            return True
        # Optional: Add domain-specific checks
    except:
        return True
    return False

def get_proxy_url(m3u8_url, stream_id):
    """Return proxied URL if needed, else original"""
    return f"{EMBED_BASE_URL}/{stream_id}.m3u8" if needs_proxy(m3u8_url) else m3u8_url

def get_screenshot(m3u8_url):
    """Capture 1 frame from stream (returns BytesIO or None)"""
    try:
        process = (
            ffmpeg
            .input(m3u8_url, ss=1, t=1)
            .filter('scale', 640, -1)
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True, timeout=15)
        )
        return io.BytesIO(process[0])
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return None
