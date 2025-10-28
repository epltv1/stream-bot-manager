import os
import time
import re
import redis
import requests
import threading
from urllib.parse import urljoin
from config import REDIS_URL, SEGMENT_DIR

r = redis.from_url(REDIS_URL)
os.makedirs(SEGMENT_DIR, exist_ok=True)

def slugify(title):
    return re.sub(r'[^a-zA-Z0-9]+', '', title.lower())[:20] or 'stream'

def store_stream(stream_id, m3u8_url, title):
    pipe = r.pipeline()
    pipe.hset(f'stream:{stream_id}', mapping={
        'url': m3u8_url,
        'title': title,
        'start_time': time.time(),
        'active': 'True',
        'sequence': 0,
        'segments': ''  # will store: seg_0.ts,seg_1.ts,...
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

# Background downloader
def segment_downloader(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data: return
    source_url = data[b'url'].decode()

    seen_urls = set()
    sequence = int(data.get(b'sequence', b'0'))
    max_segments = 6  # keep ~30 seconds (6 x 5s)

    while r.hget(f'stream:{stream_id}', 'active') == b'True':
        try:
            resp = requests.get(source_url, timeout=10)
            lines = resp.text.split('\n')
            segment_urls = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith('http'):
                        line = urljoin(source_url, line)
                    segment_urls.append(line)

            new_segments = []
            for url in segment_urls:
                if url not in seen_urls:
                    name = f"seg_{sequence}.ts"
                    path = os.path.join(SEGMENT_DIR, f"{stream_id}_{name}")
                    seg_resp = requests.get(url, timeout=10)
                    with open(path, 'wb') as f:
                        f.write(seg_resp.content)
                    seen_urls.add(url)
                    new_segments.append(name)
                    sequence += 1

                    # Keep only last N segments
                    current = r.hget(f'stream:{stream_id}', 'segments')
                    seg_list = current.decode().split(',') if current else []
                    seg_list = seg_list[-max_segments:] + [name]
                    r.hset(f'stream:{stream_id}', 'segments', ','.join(seg_list))
                    r.hset(f'stream:{stream_id}', 'sequence', sequence)

                    # Clean old files
                    for old in seg_list[:-max_segments]:
                        old_path = os.path.join(SEGMENT_DIR, f"{stream_id}_{old}")
                        if os.path.exists(old_path):
                            os.remove(old_path)

            time.sleep(5)  # Check every 5 sec
        except:
            time.sleep(5)

    # Cleanup on stop
    for f in os.listdir(SEGMENT_DIR):
        if f.startswith(f"{stream_id}_"):
            os.remove(os.path.join(SEGMENT_DIR, f))
