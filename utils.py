import os
import time
import re
import redis
import requests
from urllib.parse import urljoin
from config import REDIS_URL

r = redis.from_url(REDIS_URL)
SEGMENT_DIR = "/tmp/stream_segments"  # Will store .ts files
os.makedirs(SEGMENT_DIR, exist_ok=True)

def slugify(title):
    return re.sub(r'[^a-zA-Z0-9]+', '', title.lower())[:20] or 'stream'

def store_stream(stream_id, m3u8_url, title):
    start_time = time.time()
    pipe = r.pipeline()
    pipe.hset(f'stream:{stream_id}', mapping={
        'url': m3u8_url,
        'title': title,
        'start_time': start_time,
        'active': 'True',
        'sequence': 0
    })
    pipe.expire(f'stream:{stream_id}', 86400 * 7)
    pipe.execute()

def remove_stream(stream_id):
    if r.exists(f'stream:{stream_id}'):
        r.hset(f'stream:{stream_id}', 'active', 'False')
        r.expire(f'stream:{stream_id}', 60)
        return True
    return False

def get_active_streams():
    streams = []
    for key in r.keys('stream:*'):
        data = r.hgetall(key)
        if data.get(b'active') == b'True':
            sid = key.decode().split(':')[1]
            streams.append({
                'id': sid,
                'title': data[b'title'].decode(),
                'uptime': f"{int(time.time() - float(data[b'start_time']))}s",
                'url': data[b'url'].decode()
            })
    return sorted(streams, key=lambda x: x['title'])

def fetch_and_cache_segment(stream_id, segment_url, segment_name):
    """Download .ts and save to disk"""
    path = os.path.join(SEGMENT_DIR, f"{stream_id}_{segment_name}")
    if os.path.exists(path):
        return path

    try:
        resp = requests.get(segment_url, timeout=15)
        resp.raise_for_status()
        with open(path, 'wb') as f:
            f.write(resp.content)
        return path
    except:
        return None
