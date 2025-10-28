from flask import Flask, Response, jsonify
from flask_cors import CORS
import requests
from utils import get_proxy_url, r
from config import HOST, PORT, SECRET_KEY, EMBED_BASE_URL

app = Flask(__name__)
CORS(app)

@app.route('/<stream_id>.m3u8')
def serve_m3u8(stream_id):
    # Remove .m3u8
    stream_id = stream_id.rsplit('.', 1)[0]
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "#EXTM3U\n# Stream Ended\n", 404, {'Content-Type': 'application/x-mpegURL'}

    original_url = data[b'url'].decode()
    proxied = get_proxy_url(original_url, stream_id)

    if proxied == original_url:
        # Redirect to original
        return Response("", 302, {'Location': original_url})
    else:
        # Proxy the .m3u8
        try:
            resp = requests.get(original_url, timeout=10)
            content = resp.text
            # Rewrite .ts paths to go through proxy
            base = f"{EMBED_BASE_URL}/{stream_id}/"
            content = content.replace(
                original_url.rsplit('/', 1)[0] + '/',
                base
            )
            return content, 200, {'Content-Type': 'application/x-mpegURL'}
        except:
            return "#EXTM3U\n# Proxy Failed\n", 502

@app.route('/<stream_id>/<path:segment>')
def proxy_segment(stream_id, segment):
    data = r.hgetall(f'stream:{stream_id}')
    if not data or data.get(b'active') != b'True':
        return "", 404
    base_url = data[b'url'].decode().rsplit('/', 1)[0] + '/'
    ts_url = base_url + segment
    try:
        resp = requests.get(ts_url, stream=True, timeout=10)
        return Response(resp.iter_content(8192), content_type='video/MP2T')
    except:
        return "", 502

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, threaded=True)
