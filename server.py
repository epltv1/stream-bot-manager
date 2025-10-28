from flask import Flask, render_template, request, Response, jsonify
from flask_cors import CORS
import requests
from utils import get_proxy_url, health_check, r
from config import HOST, PORT, SECRET_KEY, EMBED_BASE_URL

app = Flask(__name__, template_folder='templates')
app.secret_key = SECRET_KEY
CORS(app)

@app.route('/embed/<stream_id>')
def embed(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "<h1>Stream Ended</h1>", 404

    m3u8_url = data[b'url'].decode()
    title = data[b'title'].decode()
    source = get_proxy_url(m3u8_url, stream_id)
    viewers = int(data[b'viewers'])

    return render_template('embed.html',
                           stream_id=stream_id,
                           source=source,
                           title=title,
                           viewers=viewers)

@app.route('/proxy/<stream_id>')
def proxy(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "Stream Ended", 404
    m3u8_url = data[b'url'].decode()
    resp = requests.get(m3u8_url, stream=True)
    return Response(resp.iter_content(chunk_size=8192),
                    content_type=resp.headers.get('Content-Type', 'application/x-mpegURL'))

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

@app.route('/health/<stream_id>')
def get_health(stream_id):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return jsonify({'live': False})
    return jsonify({'live': health_check(data[b'url'].decode())})

if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
