from flask import Flask, Response, send_from_directory
from flask_cors import CORS
import requests
import os
from config import HOST, PORT, EMBED_BASE_URL, SEGMENT_DIR
from utils import r, fetch_segment

app = Flask(__name__)
CORS(app)

@app.route('/<sid>.m3u8')
def m3u8(sid):
    sid = sid.rsplit('.', 1)[0]
    data = r.hgetall(f'stream:{sid}')
    if not data or data.get(b'active') != b'True':
        return "#EXTM3U\n#ENDED\n", 404
    url = data[b'url'].decode()
    try:
        resp = requests.get(url, timeout=15)
        lines = resp.text.split('\n')
    except:
        return "#EXTM3U\n#SOURCE DOWN\n", 502
    out = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:10"]
    i = 0
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            if not line.startswith('http'):
                line = requests.compat.urljoin(url, line)
            name = f"seg_{i}.ts"
            fetch_segment(sid, line, name)
            out += [f"#EXTINF:10.0,", f"{EMBED_BASE_URL}/seg/{sid}/{name}"]
            i += 1
    out.append("#EXT-X-ENDLIST")
    return "\n".join(out), 200, {'Content-Type': 'application/x-mpegURL'}

@app.route('/seg/<sid>/<name>')
def seg(sid, name):
    path = os.path.join(SEGMENT_DIR, f"{sid}_{name}")
    if not os.path.exists(path):
        return "Not ready", 404
    return send_from_directory(SEGMENT_DIR, f"{sid}_{name}", mimetype='video/MP2T')

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
