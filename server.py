from flask import Flask, Response, request, send_from_directory
from flask_cors import CORS
import requests
import re
from utils import r, SEGMENT_DIR, fetch_and_cache_segment, get_active_streams
from config import HOST, PORT, EMBED_BASE_URL
import os

app = Flask(__name__)
CORS(app)

def build_restream_m3u8(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "#EXTM3U\n# Stream Ended\n"

    source_url = data[b'url'].decode()
    try:
        resp = requests.get(source_url, timeout=15)
        resp.raise_for_status()
        content = resp.text
    except:
        return "#EXTM3U\n# Source Unreachable\n"

    lines = content.split('\n')
    m3u8 = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:10", "#EXT-X-MEDIA-SEQUENCE:0"]

    segment_index = 0
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            if not line.startswith('http'):
                line = requests.compat.urljoin(source_url, line)
            segment_name = f"seg_{segment_index}.ts"
            fetch_and_cache_segment(stream_id, line, segment_name)
            m3u8.append(f"#EXTINF:10.0,")
            m3u8.append(f"{EMBED_BASE_URL}/segment/{stream_id}/{segment_name}")
            segment_index += 1

    m3u8.append("#EXT-X-ENDLIST")
    return "\n".join(m3u8)

@app.route('/<stream_id>.m3u8')
def restream_m3u8(stream_id):
    stream_id = stream_id.rsplit('.', 1)[0]
    m3u8_content = build_restream_m3u8(stream_id)
    return Response(
        m3u8_content,
        content_type='application/x-mpegURL',
        headers={'Access-Control-Allow-Origin': '*'}
    )

@app.route('/segment/<stream_id>/<segment_name>')
def serve_segment(stream_id, segment_name):
    path = os.path.join(SEGMENT_DIR, f"{stream_id}_{segment_name}")
    if not os.path.exists(path):
        return "Segment not ready", 404
    return send_from_directory(SEGMENT_DIR, f"{stream_id}_{segment_name}", mimetype='video/MP2T')

@app.route('/')
def index():
    streams = get_active_streams()
    html = "<h1>Active Streams</h1><ul>"
    for s in streams:
        html += f"<li><a href='/{s['id']}.m3u8'>{s['title']}</a> ({s['uptime']})</li>"
    html += "</ul>"
    return html

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
