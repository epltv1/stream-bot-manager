from flask import Flask, render_template, request, Response, jsonify, send_from_directory
from flask_cors import CORS
import requests
from utils import get_proxy_url, health_check, r
from config import HOST, PORT, SECRET_KEY, EMBED_BASE_URL

app = Flask(__name__, template_folder='templates')
app.secret_key = SECRET_KEY
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all

# Serve static files (Clappr from CDN, but just in case)
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# === EMBED PAGE ===
@app.route('/embed/<stream_id>')
def embed(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "<h1 style='color:white;background:black;text-align:center;padding:50px;'>Stream Ended</h1>", 404

    m3u8_url = data[b'url'].decode()
    title = data[b'title'].decode()
    source = get_proxy_url(m3u8_url, stream_id)
    viewers = int(data[b'viewers'])

    return render_template('embed.html',
                           stream_id=stream_id,
                           source=source,
                           title=title,
                           viewers=viewers)

# === PROXY .m3u8 & .ts FILES ===
@app.route('/proxy/<stream_id>')
def proxy_m3u8(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "Stream Ended", 404
    url = data[b'url'].decode()
    try:
        resp = requests.get(url, stream=True, timeout=10)
        resp.raise_for_status()
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type=resp.headers.get('Content-Type', 'application/vnd.apple.mpegurl'),
            headers={'Access-Control-Allow-Origin': '*'}
        )
    except:
        return "Proxy Error", 502

# === PROXY .ts SEGMENTS (CRITICAL FIX) ===
@app.route('/proxy/<stream_id>/<path:segment>')
def proxy_segment(stream_id, segment):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "Stream Ended", 404
    base_url = data[b'url'].decode().rsplit('/', 1)[0] + '/'
    ts_url = base_url + segment
    try:
        resp = requests.get(ts_url, stream=True, timeout=10)
        resp.raise_for_status()
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type='video/MP2T',
            headers={'Access-Control-Allow-Origin': '*'}
        )
    except:
        return "Segment Error", 502

# === VIEWERS UPDATE ===
@app.route('/viewers/<stream_id>', methods=['POST'])
def update_viewers(stream_id):
    action = request.json.get('action')
    current = int(r.hget(f'stream:{stream_id}', 'viewers') or 0)
    new = max(0, current + (1 if action == 'inc' else -1))
    r.hset(f'stream:{stream_id}', 'viewers', new)
    return jsonify({'viewers': new})

@app.route('/viewers/<stream_id>')
def get_viewers(stream_id):
    count = int(r.hget(f'stream:{stream_id}', 'viewers') or 0)
    return jsonify({'viewers': count})

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
