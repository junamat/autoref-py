'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state } from '../state.js';
import { currentFilterParams } from '../filters.js';

export async function loadResults() {
  state.resultsLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const params = new URLSearchParams({
    count_failed: countFailed, method: state.currentMethod, aggregate,
    ...currentFilterParams(),
  });
  const wrap = document.getElementById('results-wrap');
  if (wrap) wrap.innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(`/api/stats/results?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    if (wrap) wrap.innerHTML = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    return;
  }

  if (!data.has_data || !data.teams.length) {
    if (wrap) wrap.innerHTML = '<div class="empty-msg">no team data yet — team_index must be set in game_scores</div>';
    return;
  }

  const maps = data.map_order;
  const teams = data.teams;

  const headerCells = maps.map(m => {
    const label = m.name || m.beatmap_id;
    const href = `https://osu.ppy.sh/b/${encodeURIComponent(m.beatmap_id)}`;
    return `<th class="r" style="white-space:nowrap"><a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none">${esc(label)}</a></th>`;
  }).join('');

  const bodyRows = teams.map((t, i) => {
    const rankClass = i < 3 ? `rank-${i+1}` : '';
    const mapCells = maps.map(m => {
      const cell = t.maps[m.beatmap_id];
      if (!cell) return `<td class="r muted">—</td>`;
      const rankBadge = cell.map_rank === 1
        ? `<span style="color:var(--yellow);font-weight:700;margin-left:3px">★</span>`
        : `<span class="mono xs muted" style="margin-left:3px">#${cell.map_rank}</span>`;
      return `<td class="r mono xs">${cell.total_score.toLocaleString()}${rankBadge}</td>`;
    }).join('');
    const total = t.total_metric != null ? t.total_metric.toFixed(3) : '—';
    return `<tr>
      <td class="rank-cell ${rankClass}">${i + 1}</td>
      <td style="font-weight:700">${esc(t.team_name)}</td>
      ${mapCells}
      <td class="r" style="color:var(--blue);font-weight:700">${total}</td>
    </tr>`;
  }).join('');

  const arrow = data.ascending ? '▲' : '▼';
  const totalLabel = data.metric_col ? `${esc(data.metric_col)} ${arrow}` : `total ${arrow}`;
  if (wrap) wrap.innerHTML = `<div style="overflow-x:auto">
    <table class="stats-table">
      <thead><tr>
        <th>#</th><th>team</th>
        ${headerCells}
        <th class="r">${totalLabel}</th>
      </tr></thead>
      <tbody>${bodyRows}</tbody>
    </table>
  </div>`;
}
