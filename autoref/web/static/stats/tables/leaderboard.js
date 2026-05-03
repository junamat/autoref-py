'use strict';

import { esc } from '/static/shared/util.js';

const GRADE_COLOR = {
  X: 'var(--yellow)', XH: 'var(--yellow)',
  S: 'var(--yellow)', SH: 'var(--yellow)',
  A: 'var(--green)',
  B: 'var(--blue)',
  C: 'var(--orange)',
  D: 'var(--red)',
  F: 'var(--muted)',
};

function bestCell(best) {
  if (!best) return '<span class="muted">—</span>';
  const label = best.name || best.beatmap_id;
  const href = `https://osu.ppy.sh/b/${encodeURIComponent(best.beatmap_id)}`;
  const grade = best.rank || '';
  const gradeColor = GRADE_COLOR[grade] || 'var(--muted)';
  const mods = (best.mods || []).join('');
  const modsBadge = mods ? `<span style="font-size:9px;color:var(--yellow);margin-left:4px">+${esc(mods)}</span>` : '';
  return `
    <span style="display:inline-flex;align-items:center;gap:6px">
      <a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);font-weight:700;text-decoration:none">${esc(label)}</a>${modsBadge}
      <span style="color:${gradeColor};font-weight:700;font-size:10px">${esc(grade)}</span>
      <span class="mono xs muted">${(best.accuracy * 100).toFixed(2)}%</span>
      <span class="mono xs">${best.score.toLocaleString()}</span>
    </span>`;
}

export function renderLeaderboard(rows, metricCol, ascending, method, totalMaps) {
  const wrap = document.getElementById('leaderboard-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-msg">no data — play some matches first</div>';
    return;
  }

  const label = document.querySelector(`#cfg-calc .cfg-opt.active`)?.textContent || metricCol;
  const isPlacement = method === 'placements';

  const values = rows.map(r => r[metricCol] ?? 0);
  const maxVal = Math.max(...values.map(Math.abs), 1);

  const tbody = rows.map((r, i) => {
    const rank = i + 1;
    const rankClass = rank <= 3 ? `rank-${rank}` : '';
    const val = r[metricCol] ?? 0;
    const pct = isPlacement
      ? Math.min(100, (1 - (val - 1) / (maxVal - 1 || 1)) * 100).toFixed(1)
      : Math.min(100, (Math.abs(val) / maxVal) * 100).toFixed(1);
    const fmt = Number.isInteger(val) ? val.toLocaleString() : val.toFixed(4);
    const participation = totalMaps > 0 ? r.maps_played / totalMaps : 0;
    const star = participation > 0.7 ? '<span style="color:var(--yellow)" title="played >70% of pool">★</span>' : '';
    const avgScore = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    const avgAcc = r.avg_acc != null ? `${(r.avg_acc * 100).toFixed(2)}%` : '—';
    return `<tr>
      <td class="rank-cell ${rankClass}">${star}${rank}</td>
      <td>${esc(r.username || r.user_id)}</td>
      <td class="z-bar-cell">
        <div class="z-bar-wrap">
          <div class="z-bar-bg"><div class="z-bar-fill" style="width:${pct}%"></div></div>
          <span class="z-val">${fmt}</span>
        </div>
      </td>
      <td class="r">${avgScore}</td>
      <td class="r" style="color:var(--green)">${avgAcc}</td>
      <td class="r">${r.maps_played}</td>
      <td>${bestCell(r.best)}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>#</th>
      <th>player</th>
      <th>${esc(label)} ▼</th>
      <th class="r">avg score</th>
      <th class="r">avg acc</th>
      <th class="r">maps</th>
      <th>best score</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}
