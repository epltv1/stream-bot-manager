// ---------------------------------------------------------------
//  FULL SERVER CODE (copy-paste exactly)
// ---------------------------------------------------------------
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const { Low } = require('lowdb');
const { JSONFile } = require('lowdb/node');
const ffmpeg = require('fluent-ffmpeg');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const path = require('path');
const cors = require('cors');
const Parser = require('m3u8-parser');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, { cors: { origin: "*" } });

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// ---------- DB ----------
let db;
(async () => {
  const adapter = new JSONFile('db.json');
  db = new Low(adapter);
  await db.read();
  db.data ||= { streams: [] };
  await db.write();
  if (!fs.existsSync('screenshots')) fs.mkdirSync('screenshots');
})();

// ---------- PROXY (always used) ----------
app.get('/proxy/:streamId/:...?', async (req, res) => {
  const streamId = req.params.streamId;
  const relative = req.params['...'] || '';
  await db.read();
  const stream = db.data.streams.find(s => s.id === streamId);
  if (!stream || !stream.active) return res.status(404).send('Stream ended');

  const target = relative ? new URL(relative, stream.baseUrl).href : stream.playlistUrl;

  try {
    let data, type = 'application/vnd.apple.mpegurl';
    if (relative.endsWith('.m3u8') || !relative) {
      // rewrite playlist
      const resp = await axios.get(stream.playlistUrl, { responseType: 'arraybuffer', timeout: 10000 });
      const parser = new Parser();
      parser.push(resp.data.toString());
      parser.end();
      const rewritten = parser.manifest.segments.map(s => `#EXTINF:${s.duration},\n/proxy/${streamId}/${s.uri}`).join('\n');
      data = Buffer.from(`#EXTM3U\n${rewritten}`);
    } else {
      const resp = await axios.get(target, { responseType: 'arraybuffer', timeout: 10000, headers: { 'User-Agent': 'Mozilla/5.0' } });
      data = resp.data;
      type = resp.headers['content-type'] || 'video/mp2t';
    }
    res.set('Content-Type', type);
    res.set('Access-Control-Allow-Origin', '*');
    res.set('Cache-Control', 'no-cache');
    res.send(data);
  } catch (e) {
    console.error(e.message);
    res.status(500).send('Proxy error');
  }
});

// ---------- API ----------
app.post('/api/streams', async (req, res) => {
  const { m3u8, title } = req.body;
  const url = new URL(m3u8);
  const baseUrl = url.origin + url.pathname.replace(/[^/]+$/, '');
  const id = uuidv4().slice(0, 8);
  const startTime = Date.now();
  const stream = { id, title, playlistUrl: m3u8, baseUrl, startTime, active: true, status: 'live', viewers: 0 };
  await db.read();
  db.data.streams.push(stream);
  await db.write();
  startMonitoring(id);
  res.json({ id, embedUrl: `http://45.33.127.60/embed/${id}` });
});

app.get('/api/streams', async (req, res) => {
  await db.read();
  const list = db.data.streams.map(s => ({
    ...s,
    uptime: formatUptime(s.startTime),
    screenshot: `/screenshots/${s.id}.jpg?t=${Date.now()}`
  }));
  res.json(list);
});

app.delete('/api/streams/:id', async (req, res) => {
  await db.read();
  const idx = db.data.streams.findIndex(s => s.id === req.params.id);
  if (idx !== -1) {
    db.data.streams[idx].active = false;
    await db.write();
  }
  res.json({ success: true });
});

app.get('/embed/:id', async (req, res) => {
  await db.read();
  const stream = db.data.streams.find(s => s.id === req.params.id && s.active);
  if (!stream) return res.send('<h1 style="color:#fff;background:#000;padding:50px;text-align:center;">Stream ended</h1>');
  res.sendFile(path.join(__dirname, 'public/index.html'));
});

app.get('/api/stream/:id', async (req, res) => {
  await db.read();
  const stream = db.data.streams.find(s => s.id === req.params.id && s.active);
  if (!stream) return res.status(404).json({ error: 'Not found' });
  stream.proxyUrl = `/proxy/${stream.id}/`;
  res.json(stream);
});

// ---------- SOCKET.IO ----------
const activeSockets = new Map();
io.on('connection', socket => {
  socket.on('joinStream', id => {
    if (!activeSockets.has(id)) activeSockets.set(id, new Set());
    activeSockets.get(id).add(socket.id);
    socket.join(id);
    updateViewers(id);
  });
  socket.on('heartbeat', () => {});
  socket.on('disconnect', () => {
    for (const [id, set] of activeSockets) {
      if (set.delete(socket.id) && set.size === 0) {
        activeSockets.delete(id);
        updateViewers(id);
      }
    }
  });
});

async function updateViewers(id) {
  const count = activeSockets.get(id)?.size || 0;
  await db.read();
  const s = db.data.streams.find(x => x.id === id);
  if (s) {
    s.viewers = count;
    await db.write();
    io.to(id).emit('viewersUpdate', count);
  }
}

// ---------- MONITORING ----------
async function startMonitoring(id) {
  const interval = setInterval(async () => {
    await db.read();
    const s = db.data.streams.find(x => x.id === id);
    if (!s || !s.active) return clearInterval(interval);
    await takeScreenshot(`/proxy/${id}/`, id);
    try {
      await axios.head(`http://localhost/proxy/${id}/`, { timeout: 5000 });
      s.status = 'live';
    } catch {
      s.status = 'offline';
    }
    await db.write();
    io.emit('streamUpdate', s);
  }, 30000);
  takeScreenshot(`/proxy/${id}/`, id);
}

function takeScreenshot(url, id) {
  return new Promise(resolve => {
    ffmpeg(url, { timeout: 30000 })
      .screenshots({
        count: 1,
        timemarks: ['1'],
        size: '320x180',
        filename: `${id}.jpg`,
        folder: 'screenshots'
      })
      .on('end', resolve)
      .on('error', () => resolve());
  });
}

function formatUptime(start) {
  const diff = Math.floor((Date.now() - start) / 1000);
  const d = Math.floor(diff / 86400); const h = Math.floor((diff % 86400) / 3600);
  const m = Math.floor((diff % 3600) / 60); const s = diff % 60;
  return `${d ? d + 'd ' : ''}${h}h ${m}m ${s}s`.trim();
}

// ---------- START ----------
server.listen(80, () => console.log('Server on http://45.33.127.60'));
