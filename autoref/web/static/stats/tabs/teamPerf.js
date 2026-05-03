'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state } from '../state.js';
import { currentFilterParams } from '../filters.js';

export async function loadTeamPerformances() {
  state.teamPerfLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });
  const wrap = document.getElementById('team-perf-wrap');
  if (wrap) wrap.innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(`/api/stats/team_performances?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    if (wrap) wrap.innerHTML = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    return;
  }

  if (!data.teams || !data.teams.length) {
    if (wrap) wrap.innerHTML = '<div class="empty-msg">no team data yet</div>';
    return;
  }

  const section = document.getElementById('team-performances-section');
  if (section) section.hidden = false;

  const tbody = data.teams.map((t, i) => {
    const rankClass = i < 3 ? `rank-${i+1}` : '';
    const winRate = t.win_rate != null ? `${(t.win_rate * 100).toFixed(0)}%` : '—';
    const avgZ = t.avg_z != null ? t.avg_z.toFixed(3) : '—';
    const avgScore = t.avg_score != null ? Math.round(t.avg_score).toLocaleString() : '—';
    return `<tr>
      <td class="rank-cell ${rankClass}">${i + 1}</td>
      <td style="font-weight:700">${esc(t.team_name)}</td>
      <td class="r">${t.matches_played}</td>
      <td class="r" style="color:var(--green)">${t.wins} <span class="muted xs">(${winRate})</span></td>
      <td class="r mono xs muted">${avgZ}</td>
      <td class="r">${avgScore}</td>
      <td class="r">${t.maps_played}</td>
    </tr>`;
  }).join('');

  if (wrap) wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>#</th><th>team</th>
      <th class="r">matches</th><th class="r">wins</th>
      <th class="r">avg z</th><th class="r">avg score</th><th class="r">maps</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}
