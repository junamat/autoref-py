'use strict';

import { esc } from '/static/shared/util.js';
import { modColor } from '/static/shared/modColors.js';
import { state } from '../state.js';

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
  const hasBracket = state.context?.has_bracket !== false;
  const maxVal = Math.max(...rows.map(r => hasBracket ? r.picks : (r.play_count || 0)), 1);

  const tbody = rows.map(r => {
    const val = hasBracket ? r.picks : (r.play_count || 0);
    const barW = Math.round((val / maxVal) * 60);
    const avgFmt = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    const accFmt = r.avg_acc != null ? `${(r.avg_acc * 100).toFixed(2)}%` : '—';
    const label = r.name || r.beatmap_id;
    const href = `https://osu.ppy.sh/b/${encodeURIComponent(r.beatmap_id)}`;
    // Pool mod takes priority over player mods for color
    const modsArg = r.pool_mod ? [r.pool_mod] : (r.mods && r.mods.length ? r.mods : r.beatmap_id);
    const color = modColor(r.name, modsArg);
    const picked = r.protects_picked ?? 0;
    const unused = r.protects_unused ?? 0;
    const meta = (r.artist || r.title || r.version)
      ? `<div style="font-size:10px;color:var(--muted);margin-top:2px">${esc(r.artist)} — ${esc(r.title)} [${esc(r.version)}]</div>`
      : '';
    const bracketCells = hasBracket ? `
      <td class="r" style="color:var(--red)">${r.bans}</td>
      <td class="r" style="color:var(--yellow)" title="protects total">${r.protects}</td>
      <td class="r" style="color:var(--green)" title="protects that were then picked">${picked}</td>
      <td class="r" style="color:var(--muted)" title="protects that were not picked">${unused}</td>` : '';
    return `<tr>
      <td class="mono" style="font-weight:700" title="beatmap ${esc(r.beatmap_id)}">
        <a href="${href}" target="_blank" rel="noopener" style="color:${color};text-decoration:none">${esc(label)}</a>
        ${meta}
      </td>
      <td class="r" style="color:var(--blue)">${val}
        <span class="pick-bar" style="width:${barW}px;background:var(--blue);opacity:0.5"></span>
      </td>${bracketCells}
      <td class="r">${avgFmt}</td>
      <td class="r" style="color:var(--green)">${accFmt}</td>
    </tr>`;
  }).join('');

  const bracketHeaders = hasBracket ? `
      <th class="r">bans</th>
      <th class="r">prot</th>
      <th class="r" title="protects that were then picked">prot ✓</th>
      <th class="r" title="protects that were not picked">prot ✗</th>` : '';
  const firstColHeader = hasBracket ? 'picks' : 'played';

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>map</th>
      <th class="r">${firstColHeader}</th>${bracketHeaders}
      <th class="r">avg score</th>
      <th class="r">avg acc</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}
