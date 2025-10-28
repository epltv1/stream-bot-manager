from flask import Flask, Response, send_from_directory
from flask_cors import CORS
import os
from config import HOST, PORT, EMBED_BASE_URL, SEGMENT_DIR
from utils import r
import threading

app = Flask(__name__)
CORS(app)

@app.route('/<sid>.m3u8')
def m3u8(sid):
    sid = sid.rsplit('.', 1)[0]
    data = r.hgetall(f'stream:{sid}')
    if not data or data.get(b'active') != b'True':
        return "#EXTM3U\n#ENDED\n", 404

    segments = data.get(b'segments', b'').decode().split(',')
    if not segments or segments == ['']:
        return "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXT-X-MEDIA-SEQUENCE:0\n", 200

    out = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:10",
        f"#EXT-X-MEDIA-SEQUENCE:{int(data[b'sequence']) - len(segments)}"
    ]
    for seg in segments:
        if seg:
            out += [f"#EXTINF:5.0,", f"{EMBED_BASE_URL}/seg/{sid}/{seg}"]
    # NO #EXT-X-ENDLIST → LIVE

    return "\n".join(out), 200, {'Content-Type': 'application/x-mpegURL'}

@app.route('/seg/<sid>/<name>')
def seg(sid, name):
    path = os.path.join(SEGMENT_DIR, f"{sid}_{name}")
    if not os.path.exists(path):
        return "Not ready", 404
    return send_from_directory(SEGMENT_DIR, f"{sid}_{name}", mimetype='video/MP2T')

# Start downloader threads
def start_downloaders():
    time.sleep(2)
    for key in r.keys('stream:*'):
        data = r.hgetall(key)
        if data.get(b'active') == b'True':
            sid = key.decode().split(':')[1]
            threading.Thread(target=utils.segment_downloader, args=(sid,), daemon=True).start()

threading.Thread(target=start_downloaders, daemon=True).start()

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
