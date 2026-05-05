/**
 * Tiny dev server for the Long Dark map.
 *
 * Usage:
 *   node dev-server.js              # serves on http://127.0.0.1:8765/
 *   PORT=9000 node dev-server.js
 *
 * Static file serving for index.html, maps/, data/, etc., plus a single API
 * endpoint used by the in-page bbox editor:
 *
 *   POST /api/place-box
 *     body: { region, name, bbox: [x1, y1, x2, y2] }   (coords are 0..1)
 *     -> writes data/place_boxes.json with the new value (or upsert),
 *        also rewrites the PLACE_BOXES_START/END block in index.html
 *
 * Stdlib only — no npm install required.
 */
'use strict';

const http = require('http');
const fs   = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = __dirname;
const PORT = Number(process.env.PORT) || 8765;
const HOST = '127.0.0.1';

const BOXES_FILE     = path.join(ROOT, 'data', 'place_boxes.json');
const OVERRIDES_FILE = path.join(ROOT, 'data', 'place_boxes_overrides.json');
const MERGE_SCRIPT   = path.join(ROOT, 'tools', 'merge_boxes.py');
const PYTHON         = path.join(ROOT, '.venv', 'bin', 'python');
const HTML_FILE      = path.join(ROOT, 'index.html');
const SENTINEL_START = '// PLACE_BOXES_START';
const SENTINEL_END   = '// PLACE_BOXES_END';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png':  'image/png',
  '.svg':  'image/svg+xml',
  '.txt':  'text/plain; charset=utf-8',
};

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let bytes = 0;
    req.on('data', c => {
      bytes += c.length;
      if (bytes > 1_000_000) { reject(new Error('body too large')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); }
    });
    req.on('error', reject);
  });
}

function loadJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { return {}; }
}

function inlineIntoHtml(boxes) {
  let html;
  try { html = fs.readFileSync(HTML_FILE, 'utf8'); }
  catch { return false; }
  const re = new RegExp(
    `(${SENTINEL_START}\\n)[\\s\\S]*?(\\n\\s*${SENTINEL_END})`
  );
  if (!re.test(html)) return false;
  const body = `const PLACE_BOXES = ${JSON.stringify(boxes, null, 2)};`;
  fs.writeFileSync(HTML_FILE, html.replace(re, `$1${body}$2`));
  return true;
}

// Run merge_boxes.py to fold the new override into data/place_boxes.json AND
// inline the merged result into index.html. Falls back to in-process merging
// if Python isn't available, so the dev server still works on a clean clone.
function runMerge() {
  if (fs.existsSync(PYTHON) && fs.existsSync(MERGE_SCRIPT)) {
    const r = spawnSync(PYTHON, [MERGE_SCRIPT, '--inline'], { cwd: ROOT, encoding: 'utf8' });
    if (r.status === 0) return { ok: true, source: 'merge_boxes.py' };
    console.warn('merge_boxes.py failed:', r.stderr || r.stdout);
  }
  // Fallback: layer overrides on top of whatever's already in place_boxes.json.
  const boxes = loadJson(BOXES_FILE);
  const overrides = loadJson(OVERRIDES_FILE);
  for (const [region, names] of Object.entries(overrides)) {
    if (!boxes[region]) boxes[region] = {};
    Object.assign(boxes[region], names);
  }
  fs.writeFileSync(BOXES_FILE, JSON.stringify(boxes, null, 2) + '\n');
  inlineIntoHtml(boxes);
  return { ok: true, source: 'fallback' };
}

function round5(v) { return Math.round(v * 1e5) / 1e5; }

function isFiniteFraction(v) {
  return typeof v === 'number' && Number.isFinite(v) && v >= -0.001 && v <= 1.001;
}

async function handleApi(req, res) {
  if (req.method === 'POST' && req.url === '/api/place-box') {
    let body;
    try { body = await readJsonBody(req); }
    catch (e) { return send(res, 400, { error: 'bad json: ' + e.message }); }

    const { region, name, bbox } = body || {};
    if (typeof region !== 'string' || !region) return send(res, 400, { error: 'region required' });
    if (typeof name !== 'string'   || !name)   return send(res, 400, { error: 'name required' });
    if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every(isFiniteFraction)) {
      return send(res, 400, { error: 'bbox must be [x1,y1,x2,y2] of 0..1 fractions' });
    }
    const [x1, y1, x2, y2] = bbox;
    if (x2 <= x1 || y2 <= y1) return send(res, 400, { error: 'bbox is empty (x2<=x1 or y2<=y1)' });

    // Save into the overrides layer so re-running the OCR pipeline doesn't
    // wipe manual fixes. merge_boxes.py reads this file and folds it in.
    const overrides = loadJson(OVERRIDES_FILE);
    if (!overrides[region]) overrides[region] = {};
    const rounded = [round5(x1), round5(y1), round5(x2), round5(y2)];
    overrides[region][name] = rounded;
    fs.writeFileSync(OVERRIDES_FILE, JSON.stringify(overrides, null, 2) + '\n');

    const merge = runMerge();

    console.log(`saved ${region}/${name} -> ${JSON.stringify(rounded)}` +
                ` (overrides + ${merge.source})`);
    return send(res, 200, { ok: true, region, name, bbox: rounded });
  }
  send(res, 404, { error: 'not found' });
}

function send(res, status, obj) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

function serveStatic(req, res) {
  let urlPath = req.url.split('?')[0];
  if (urlPath === '/') urlPath = '/index.html';
  // resolve and clamp under ROOT
  const requested = path.normalize(path.join(ROOT, decodeURIComponent(urlPath)));
  if (!requested.startsWith(ROOT)) {
    res.writeHead(403); res.end('forbidden'); return;
  }
  fs.stat(requested, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404); res.end('404'); return; }
    res.writeHead(200, {
      'Content-Type':  MIME[path.extname(requested).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    fs.createReadStream(requested).pipe(res);
  });
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) return handleApi(req, res);
  serveStatic(req, res);
});

server.listen(PORT, HOST, () => {
  console.log(`dev server: http://${HOST}:${PORT}/`);
  console.log('In the detail view: D + shift-drag → adjust corners → click Save.');
});
