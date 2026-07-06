// Labo v2 : monument agrandi/simplifié, jugé à l'échelle réelle (1x) avec loupe pixelisée.
import { writeFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import * as P from '@phosphor-icons/react';

function rose(cx, cy, d, r) {
  const h = Math.sqrt(r * r - (d * d) / 2);
  const k = +(d / 2 + h / Math.SQRT2).toFixed(2);
  const R = d + r;
  const pts = [[0, -R], [k, -k], [R, 0], [k, k], [0, R], [-k, k], [-R, 0], [-k, -k]]
    .map(([x, y]) => [+(cx + x).toFixed(2), +(cy + y).toFixed(2)]);
  let p = `M ${pts[0][0]} ${pts[0][1]} `;
  for (let i = 1; i <= 8; i++) p += `A ${r} ${r} 0 0 1 ${pts[i % 8][0]} ${pts[i % 8][1]} `;
  return p + 'Z';
}

// ANCIEN (v1 — jugé bouillie) : marges 32+, 6 éléments, rosace Ø60
function v1(size) {
  const R = rose(128, 88, 14, 16);
  return `<svg width="${size}" height="${size}" viewBox="0 0 256 256" fill="currentColor">
    <path fill-rule="evenodd" d="M 128 44 L 198 108 L 198 204 L 58 204 L 58 108 Z M 104 204 L 104 152 A 24 24 0 0 1 152 152 L 152 204 Z" opacity="0.2"/>
    <path d="${R}"/>
    <g fill="none" stroke="currentColor" stroke-width="16" stroke-linecap="round" stroke-linejoin="round">
      <path d="M 44 114 L 128 40 L 212 114"/><path d="M 58 114 L 58 210"/><path d="M 198 114 L 198 210"/>
      <path d="M 32 210 L 224 210"/><path d="M 104 210 L 104 152 A 24 24 0 0 1 152 152 L 152 210"/>
    </g>
  </svg>`;
}

// V2 : pentagone plein cadre (1 trait fermé), rosace Ø80, porte large, pas de ligne de sol
function v2(size, { sw = 16, rd = 19, rr = 21, cy = 100 } = {}) {
  const R = rose(128, cy, rd, rr);
  return `<svg width="${size}" height="${size}" viewBox="0 0 256 256" fill="currentColor">
    <path fill-rule="evenodd" d="M 128 30 L 220 110 L 220 218 L 36 218 L 36 110 Z M 100 218 L 100 160 A 28 28 0 0 1 156 160 L 156 218 Z" opacity="0.2"/>
    <path d="${R}"/>
    <g fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">
      <path d="M 128 30 L 220 110 L 220 218 L 36 218 L 36 110 Z"/>
      <path d="M 100 218 L 100 160 A 28 28 0 0 1 156 160 L 156 218"/>
    </g>
  </svg>`;
}

// V3 : comme V2 mais rosace encore plus grosse (Ø92) et trait 18
const v3 = (s) => v2(s, { sw: 18, rd: 22, rr: 24, cy: 98 });

const ph = (n, s) => renderToStaticMarkup(React.createElement(P[n], { size: s, weight: 'duotone' }));

const navRow = (render, label) => `
  <div class="nav"><span class="logo">◈</span>
    <span class="item">${ph('SquaresFour', 19)} Tableau de bord</span>
    <span class="item active">${render(19)} Mes projets</span>
    <span class="item">${ph('Files', 19)} Mes documents</span>
    <span class="item">${ph('BookOpen', 19)} Blog</span>
    <span class="lbl">${label}</span>
  </div>`;

const sizesRow = (render, label) => `
  <div class="sizes"><span class="lbl">${label}</span>
    ${[14, 16, 19, 24, 32, 48].map((s) => `<span class="cell">${render(s)}<i>${s}</i></span>`).join('')}
    <span class="tile blue">${render(20)}</span><span class="tile orange">${render(20)}</span>
  </div>`;

const html = `<!doctype html><meta charset="utf-8"><style>
body{font-family:-apple-system,sans-serif;background:#f8f7f4;color:#222;margin:0;padding:16px;width:860px}
.nav{display:flex;align-items:center;gap:22px;background:#fdfcfa;border:1px solid #eee;border-radius:8px;padding:12px 16px;margin:6px 0;font-size:13.5px;color:#4b5563}
.nav .item{display:inline-flex;align-items:center;gap:7px;font-weight:500}
.nav .active{color:#0a369d}
.nav svg{color:#4b5563}.nav .active svg{color:#0a369d}
.logo{color:#f17105;font-size:20px}
.lbl{margin-left:auto;font-size:10px;color:#999}
.sizes{display:flex;align-items:flex-end;gap:14px;background:#fff;border:1px solid #eee;border-radius:8px;padding:10px 14px;margin:6px 0;color:#0a369d}
.sizes .lbl{margin:0;width:130px;align-self:center}
.cell{display:inline-flex;flex-direction:column;align-items:center;gap:3px}.cell i{font-size:9px;color:#aaa;font-style:normal}
.tile{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:9px}
.tile.blue{background:#e8eefc;color:#0a369d}.tile.orange{background:#fdeeda;color:#f17105}
h2{font-size:13px;margin:14px 0 4px}
</style>
<h2>Nav à l'échelle réelle (19 px, 1x)</h2>
${navRow(v1, 'V1 (actuel)')}${navRow(v2, 'V2')}${navRow(v3, 'V3 rosace max')}
<h2>Gamme de tailles (1x)</h2>
${sizesRow(v1, 'V1 (actuel)')}${sizesRow(v2, 'V2')}${sizesRow(v3, 'V3 rosace max')}
${sizesRow((s) => ph('Bank', s), 'Bank (référence)')}
`;
writeFileSync('/tmp/icons-audit/mlab2.html', html);
console.log('lab2 OK');
