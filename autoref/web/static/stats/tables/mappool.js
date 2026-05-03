'use strict';

import { esc } from '/static/shared/util.js';

export function renderMappool(rows) {
  const wrap = document.getElementById('mappool-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-msg">no map action data yet</div>';
    return;
  }

  rows = [...rows].sort((a, b) => {
    const aOrder = a.pool_order ?? 99999;
    const bOrder = b.pool_order ?? 99999;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return (b.picks + b.bans + b.protects) - (a.picks + a.bans + a.protects);
  });
  const maxPicks = Math.max(...rows.map(r => r.picks), 1);

  const tbody = rows.map(r => {
    const barW = Math.round((r.picks / maxPicks) * 60);
    const avgFmt = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    const accFmt = r.avg_acc != null ? `${(r.avg_acc * 100).toFixed(2)}%` : '—';
    const label = r.name || r.beatmap_id;
    const href = `https://osu.ppy.sh/b/${encodeURIComponent(r.beatmap_id)}`;
    const picked = r.protects_picked ?? 0;
    const unused = r.protects_unused ?? 0;
    return `<tr>
      <td class="mono" style="font-weight:700" title="beatmap ${esc(r.beatmap_id)}"><a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none">${esc(label)}</a></td>
      <td class="r" style="color:var(--blue)">${r.picks}
        <span class="pick-bar" style="width:${barW}px;background:var(--blue);opacity:0.5"></span>
      </td>
      <td class="r" style="color:var(--red)">${r.bans}</td>
      <td class="r" style="color:var(--yellow)" title="protects total">${r.protects}</td>
      <td class="r" style="color:var(--green)" title="protects that were then picked">${picked}</td>
      <td class="r" style="color:var(--muted)" title="protects that were not picked">${unused}</td>
      <td class="r">${avgFmt}</td>
      <td class="r" style="color:var(--green)">${accFmt}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>map</th>
      <th class="r">picks</th>
      <th class="r">bans</th>
      <th class="r">prot</th>
      <th class="r" title="protects that were then picked">prot ✓</th>
      <th class="r" title="protects that were not picked">prot ✗</th>
      <th class="r">avg score</th>
      <th class="r">avg acc</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}
