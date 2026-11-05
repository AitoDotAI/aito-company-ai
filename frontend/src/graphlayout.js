// A small force layout for the knowledge-graph explorer: nodes repel, links
// pull, everything drifts to the centre. Seeded, so the same graph always
// lands the same way (a stable picture, and a testable one). Presentation
// only: positions, never a ranking (rule 2 owns every number).

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export function layout(nodes, edges, { width = 900, height = 560, iterations = 260, seed = 7 } = {}) {
  const rand = rng(seed);
  const pos = new Map();
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const p = nodes.map(() => ({ x: (rand() - 0.5) * width * 0.8, y: (rand() - 0.5) * height * 0.8, vx: 0, vy: 0 }));
  const links = edges
    .map((e) => [index.get(e.source), index.get(e.target)])
    .filter(([a, b]) => a !== undefined && b !== undefined);
  const n = nodes.length;
  const k = Math.sqrt((width * height) / Math.max(n, 1)) * 0.55;   // ideal link length
  for (let it = 0; it < iterations; it++) {
    const cool = 1 - it / iterations;
    // repulsion (all pairs: the graph is a few hundred nodes)
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = p[i].x - p[j].x, dy = p[i].y - p[j].y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 0.01) { dx = rand() - 0.5; dy = rand() - 0.5; d2 = 0.01; }
        const f = (k * k) / d2 * 0.02;
        p[i].vx += dx * f; p[i].vy += dy * f;
        p[j].vx -= dx * f; p[j].vy -= dy * f;
      }
    }
    // attraction along links
    for (const [a, b] of links) {
      const dx = p[b].x - p[a].x, dy = p[b].y - p[a].y;
      const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = ((d - k) / d) * 0.06;
      p[a].vx += dx * f; p[a].vy += dy * f;
      p[b].vx -= dx * f; p[b].vy -= dy * f;
    }
    for (const q of p) {
      q.vx -= q.x * 0.004; q.vy -= q.y * 0.004;               // gravity to the centre
      const step = Math.min(Math.hypot(q.vx, q.vy), 30 * cool + 1);
      const m = Math.hypot(q.vx, q.vy) || 1;
      q.x += (q.vx / m) * step; q.y += (q.vy / m) * step;
      q.vx *= 0.5; q.vy *= 0.5;
    }
  }
  // fit into the box with a margin
  const xs = p.map((q) => q.x), ys = p.map((q) => q.y);
  const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 0);
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys, 0);
  const sx = (width - 60) / Math.max(maxX - minX, 1), sy = (height - 60) / Math.max(maxY - minY, 1);
  const s = Math.min(sx, sy);
  nodes.forEach((node, i) => {
    pos.set(node.id, { x: 30 + (p[i].x - minX) * s + ((width - 60) - (maxX - minX) * s) / 2,
                       y: 30 + (p[i].y - minY) * s + ((height - 60) - (maxY - minY) * s) / 2 });
  });
  return pos;
}

// degree per node id, for node size
export function degrees(edges) {
  const d = new Map();
  for (const e of edges) {
    d.set(e.source, (d.get(e.source) || 0) + 1);
    d.set(e.target, (d.get(e.target) || 0) + 1);
  }
  return d;
}
