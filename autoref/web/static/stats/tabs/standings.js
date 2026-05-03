'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state } from '../state.js';
import { currentFilterParams } from '../filters.js';

export async function loadStandings() {
  state.standingsLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });
  const wrap = document.getElementById('standings-wrap');
  if (wrap) wrap.innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(`/api/stats/standings?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    if (wrap) wrap.innerHTML = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    return;
  }

  if (!data.maps || !data.maps.length) {
    if (wrap) wrap.innerHTML = '<div class="empty-msg">no score data yet</div>';
    return;
  }

  const cards = data.maps.map(m => {
    const title = m.name
      ? `<a href="https://osu.ppy.sh/b/${encodeURIComponent(m.beatmap_id)}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none;font-weight:700">${esc(m.name)}</a>`
      : `<span style="color:var(--blue);font-weight:700">${m.beatmap_id}</span>`;

    const rows = m.players.map(p => {
      const rankClass = p.rank <= 3 ? `rank-${p.rank}` : '';
      const mods = (p.mods || []).join('');
      const modsBadge = mods ? `<span style="font-size:9px;color:var(--yellow);margin-left:3px">+${esc(mods)}</span>` : '';
      return `<tr>
        <td class="rank-cell ${rankClass}">${p.rank}</td>
        <td>${esc(p.username || p.user_id)}${modsBadge}</td>
        <td class="r mono xs">${p.score.toLocaleString()}</td>
        <td class="r" style="color:var(--green)">${(p.accuracy * 100).toFixed(2)}%</td>
        <td class="r mono xs muted">${p.z.toFixed(2)}</td>
      </tr>`;
    }).join('');

    return `<div class="standings-card">
      <div class="standings-card-head">${title}</div>
      <div class="standings-card-body">
        <table class="stats-table">
          <thead><tr>
            <th>#</th><th>player</th>
            <th class="r">score</th><th class="r">acc</th><th class="r">z</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }).join('');

  if (wrap) wrap.innerHTML = `<div class="standings-grid">${cards}</div>`;

  const teamSection = document.getElementById('team-standings-section');
  if (data.has_teams && teamSection) {
    teamSection.hidden = false;
    const teamCards = data.maps.map(m => {
      const title = m.name
        ? `<a href="https://osu.ppy.sh/b/${encodeURIComponent(m.beatmap_id)}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none;font-weight:700">${esc(m.name)}</a>`
        : `<span style="color:var(--blue);font-weight:700">${m.beatmap_id}</span>`;

      const rows = (m.team_totals || []).map((t, i) => {
        const rank = i + 1;
        const rankClass = rank <= 3 ? `rank-${rank}` : '';
        return `<tr>
          <td class="rank-cell ${rankClass}">${rank}</td>
          <td style="font-weight:700">${esc(t.team_name)}</td>
          <td class="r mono xs">${t.total_score.toLocaleString()}</td>
          <td class="r mono xs muted">${t.avg_z.toFixed(2)}</td>
        </tr>`;
      }).join('');

      return `<div class="standings-card">
        <div class="standings-card-head">${title}</div>
        <div class="standings-card-body">
          <table class="stats-table">
            <thead><tr>
              <th>#</th><th>team</th>
              <th class="r">total score</th><th class="r">avg z</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
    }).join('');

    const teamWrap = document.getElementById('team-standings-wrap');
    if (teamWrap) teamWrap.innerHTML = `<div class="standings-grid">${teamCards}</div>`;
  }
}
