#!/usr/bin/env node
// Converts an India TopoJSON (with a `states` object, e.g. udit-001/india-maps-data
// topojson/india.json) into projected, simplified SVG paths → data/india-map.json.
// Usage: node scripts/build_india_map.js <india.topo.json>

const fs   = require('fs');
const path = require('path');

const src = process.argv[2];
if (!src) { console.error('Usage: node scripts/build_india_map.js <india.topo.json>'); process.exit(1); }
const topo = JSON.parse(fs.readFileSync(src, 'utf8'));

const WIDTH = 1000, PAD = 10, TOLERANCE = 0.55;
const LAT0 = 22 * Math.PI / 180;
const { scale: [sx, sy], translate: [tx, ty] } = topo.transform;

const arcsLL = topo.arcs.map(arc => {
  let x = 0, y = 0;
  return arc.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; });
});

const [minLon, minLat, maxLon, maxLat] = topo.bbox;
const projRaw = ([lon, lat]) => [lon * Math.cos(LAT0), -lat];
const [x0, y0] = projRaw([minLon, maxLat]);
const [x1, y1] = projRaw([maxLon, minLat]);
const k = (WIDTH - 2 * PAD) / (x1 - x0);
const HEIGHT = Math.ceil((y1 - y0) * k + 2 * PAD);
const project = ll => { const [x, y] = projRaw(ll); return [(x - x0) * k + PAD, (y - y0) * k + PAD]; };

function simplify(pts, tol) {
  if (pts.length < 3) return pts;
  const keep = new Uint8Array(pts.length);
  keep[0] = keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop();
    const [ax, ay] = pts[a], [bx, by] = pts[b];
    const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy) || 1e-9;
    let max = 0, idx = -1;
    for (let i = a + 1; i < b; i++) {
      const d = Math.abs(dy * (pts[i][0] - ax) - dx * (pts[i][1] - ay)) / len;
      if (d > max) { max = d; idx = i; }
    }
    if (max > tol && idx > 0) { keep[idx] = 1; stack.push([a, idx], [idx, b]); }
  }
  return pts.filter((_, i) => keep[i]);
}

// Simplify per arc so neighbouring states keep identical shared borders.
const arcsRaw = arcsLL.map(arc => arc.map(project));
const arcsXY  = arcsRaw.map(arc => simplify(arc, TOLERANCE));

function ring(indices, arcs = arcsXY) {
  const out = [];
  for (const i of indices) {
    const a = i >= 0 ? arcs[i] : arcs[~i].slice().reverse();
    out.push(...(out.length ? a.slice(1) : a));
  }
  return out.length < 4 && arcs === arcsXY ? ring(indices, arcsRaw) : out;
}

const area = r => { let s = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) s += (r[j][0] + r[i][0]) * (r[j][1] - r[i][1]); return s / 2; };

function centroid(r) {
  let cx = 0, cy = 0, a = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const f = r[j][0] * r[i][1] - r[i][0] * r[j][1];
    cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f; a += f;
  }
  return a ? [cx / (3 * a), cy / (3 * a)] : r[0];
}

const fmt = n => Math.round(n * 10) / 10;

// Greedy colouring over shared borders, so the plain map never paints neighbours alike.
const geoms = topo.objects.states.geometries;
const arcOwners = new Map();
geoms.forEach((g, gi) => {
  (g.type === 'Polygon' ? [g.arcs] : g.arcs).flat(2).forEach(i => {
    const a = i < 0 ? ~i : i;
    if (!arcOwners.has(a)) arcOwners.set(a, new Set());
    arcOwners.get(a).add(gi);
  });
});
const nbrs = geoms.map(() => new Set());
for (const owners of arcOwners.values()) for (const x of owners) for (const y of owners) if (x !== y) nbrs[x].add(y);
const colour = new Array(geoms.length).fill(-1);
geoms.map((_, i) => i).sort((a, b) => nbrs[b].size - nbrs[a].size).forEach(i => {
  const used = new Set([...nbrs[i]].map(j => colour[j]));
  let c = 0; while (used.has(c)) c++;
  colour[i] = c;
});
const states = geoms.map((g, gi) => {
  const polys = g.type === 'Polygon' ? [g.arcs] : g.arcs;
  let d = '', best = null, bestA = 0, total = 0;
  for (const poly of polys) {
    poly.forEach((r, ri) => {
      const pts = ring(r);
      if (pts.length < 3) return;
      const A = Math.abs(area(pts));
      if (ri === 0) { total += A; if (A > bestA) { bestA = A; best = pts; } }
      d += 'M' + pts.map(([x, y]) => `${fmt(x)},${fmt(y)}`).join('L') + 'Z';
    });
  }
  return { name: g.properties.st_nm, d, label: centroid(best).map(fmt), area: Math.round(total), colour: colour[gi] };
}).filter(s => s.d).sort((a, b) => a.name.localeCompare(b.name));

const proj = { lat0: 22, k, x0, y0, pad: PAD };
const out = { width: WIDTH, height: HEIGHT, proj, states };
const dest = path.join(__dirname, '..', 'data', 'india-map.json');
fs.writeFileSync(dest, JSON.stringify(out));
console.log(`Wrote ${dest} — ${states.length} states, ${(fs.statSync(dest).size / 1024).toFixed(0)} KB, viewBox 0 0 ${WIDTH} ${HEIGHT}`);
