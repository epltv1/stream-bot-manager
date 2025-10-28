from flask import Flask, Response, request
from flask_cors import CORS
import requests
from utils import r
from config import HOST, PORT, SECRET_KEY, EMBED_BASE_URL

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": "*"}})

@app.route('/<stream_id>.m3u8')
def serve_m3u8(stream_id):
    stream_id = stream_id.rsplit('.', 1)[0]
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        content = "#EXTM3U\n# Stream Ended\n"
        return content, 404, {
            'Content-Type': 'application/x-mpegURL',
            'Access-Control-Allow-Origin': '*'
        }

    original_url = data[b'url'].decode()

    try:
        resp = requests.get(original_url, timeout=15)
        resp.raise_for_status()
        content = resp.text

        base_path = original_url.rsplit('/', 1)[0] + '/'
        proxy_base = f"{request.url_root}{stream_id}/"
        content = content.replace(base_path, proxy_base)

        return content, 200, {
            'Content-Type': 'application/x-mpegURL',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-cache'
        }
    except:
        content = "#EXTM3U\n# Proxy Failed\n"
        return content, 502, {
            'Content-Type': 'application/x-mpegURL',
            'Access-Control-Allow-Origin': '*'
        }

@app.route('/<stream_id>/<path:segment>')
def proxy_segment(stream_id, segment):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "", 404

    original_url = data[b'url'].decode()
    base_url = original_url.rsplit('/', 1)[0] + '/'
    ts_url = base_url + segment

    try:
        resp = requests.get(ts_url, stream=True, timeout=15)
        resp.raise_for_status()
        return Response(
            resp.iter_content(8192),
            content_type='video/MP2T',
            headers={
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache'
            }
        )
    except:
        return "", 502

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
