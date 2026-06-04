'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { modColor } from '/static/shared/modColors.js';
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
    const modsArg = m.pool_mod ? [m.pool_mod] : (m.mods && m.mods.length ? m.mods : m.beatmap_id);
    const color = modColor(m.name, modsArg);
    const code = m.name
      ? `<span style="color:${color};font-weight:700">${esc(m.name)}</span>`
      : `<span style="color:${color};font-weight:700">${m.beatmap_id}</span>`;
    const meta = (m.artist || m.title || m.version)
      ? `<div style="font-size:10px;color:var(--muted);margin-top:2px">${esc(m.artist)} — ${esc(m.title)} [${esc(m.version)}]</div>`
      : '';
    const banner = m.beatmapset_id
      ? `linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.85)), url(https://assets.ppy.sh/beatmaps/${m.beatmapset_id}/covers/cover.jpg)`
      : '';
    const bannerStyle = banner ? `background-image:${banner};background-size:cover;background-position:center;` : '';
    const mapUrl = `https://osu.ppy.sh/b/${encodeURIComponent(m.beatmap_id)}`;

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
        <td class="r mono xs muted">${p.z_acc.toFixed(2)}</td>
      </tr>`;
    }).join('');

    return `<div class="standings-card">
      <a class="standings-card-head" href="${mapUrl}" target="_blank" rel="noopener" style="${bannerStyle}">${code}${meta}</a>
      <div class="standings-card-body">
        <table class="stats-table">
          <thead><tr>
            <th>#</th><th>player</th>
            <th class="r">score</th><th class="r">acc</th><th class="r">z</th><th class="r">z-acc</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
  }).join('');

  if (wrap) wrap.innerHTML = `<div class="standings-grid">${cards}</div>`;

  const teamSection = document.getElementById('team-standings-section');
  if (data.has_teams && teamSection && state.context?.has_teams !== false) {
    teamSection.hidden = false;
    const teamCards = data.maps.map(m => {
      const modsArg = m.pool_mod ? [m.pool_mod] : (m.mods && m.mods.length ? m.mods : m.beatmap_id);
      const color = modColor(m.name, modsArg);
      const code = m.name
        ? `<span style="color:${color};font-weight:700">${esc(m.name)}</span>`
        : `<span style="color:${color};font-weight:700">${m.beatmap_id}</span>`;
      const meta = (m.artist || m.title || m.version)
        ? `<div style="font-size:10px;color:var(--muted);margin-top:2px">${esc(m.artist)} — ${esc(m.title)} [${esc(m.version)}]</div>`
        : '';
      const banner = m.beatmapset_id
        ? `linear-gradient(rgba(0,0,0,0.65), rgba(0,0,0,0.85)), url(https://assets.ppy.sh/beatmaps/${m.beatmapset_id}/covers/cover.jpg)`
        : '';
      const bannerStyle = banner ? `background-image:${banner};background-size:cover;background-position:center;` : '';
      const mapUrl = `https://osu.ppy.sh/b/${encodeURIComponent(m.beatmap_id)}`;

      const rows = (m.team_totals || []).map((t, i) => {
        const rank = i + 1;
        const rankClass = rank <= 3 ? `rank-${rank}` : '';
        return `<tr>
          <td class="rank-cell ${rankClass}">${rank}</td>
          <td style="font-weight:700">${esc(t.team_name)}</td>
          <td class="r mono xs">${t.total_score.toLocaleString()}</td>
          <td class="r mono xs muted">${t.avg_z.toFixed(2)}</td>
          <td class="r mono xs muted">${t.avg_z_acc.toFixed(2)}</td>
        </tr>`;
      }).join('');

      return `<div class="standings-card">
        <a class="standings-card-head" href="${mapUrl}" target="_blank" rel="noopener" style="${bannerStyle}">${code}${meta}</a>
        <div class="standings-card-body">
          <table class="stats-table">
            <thead><tr>
              <th>#</th><th>team</th>
              <th class="r">total score</th><th class="r">avg z</th><th class="r">avg z-acc</th>
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
