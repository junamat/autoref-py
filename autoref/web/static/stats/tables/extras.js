'use strict';

import { esc } from '/static/shared/util.js';

export function mapLink(name, beatmapId) {
  const href = `https://osu.ppy.sh/b/${encodeURIComponent(beatmapId)}`;
  const label = name || beatmapId;
  return `<a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);font-weight:700;text-decoration:none">${esc(label)}</a>`;
}

export function renderPpTable(rows, mode) {
  if (!rows.length) return '<div class="empty-msg">no pp data (rosu-pp-py not installed?)</div>';
  const isZ = mode === 'zpp';
  const metricCol = isZ ? 'z-pp' : 'pp';
  const tbody = rows.map((r, i) => {
    const mods = (r.mods || []).join('');
    const modsBadge = mods ? `<span style="font-size:9px;color:var(--yellow);margin-left:4px">+${esc(mods)}</span>` : '';
    const metric = isZ ? r.zpp.toFixed(2) : r.pp.toFixed(0);
    const ppCell = isZ ? `<td class="r mono xs muted" title="raw pp">${r.pp.toFixed(0)}</td>` : '';
    return `<tr>
      <td class="rank-cell">${i + 1}</td>
      <td>${esc(r.username || r.user_id)}</td>
      <td>${mapLink(r.name, r.beatmap_id)}${modsBadge}</td>
      <td class="r mono">${r.score.toLocaleString()}</td>
      <td class="r" style="color:var(--green)">${(r.accuracy * 100).toFixed(2)}%</td>
      ${ppCell}
      <td class="r" style="color:var(--blue);font-weight:700">${metric}</td>
    </tr>`;
  }).join('');
  const ppHeader = isZ ? '<th class="r">pp</th>' : '';
  return `<table class="stats-table">
    <thead><tr>
      <th>#</th><th>player</th><th>map</th><th class="r">score</th><th class="r">acc</th>
      ${ppHeader}<th class="r">${metricCol} ▼</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}

export function renderDiffTable(rows, kind) {
  if (!rows.length) return '<div class="empty-msg">no pick data yet</div>';
  const tbody = rows.map((r, i) => {
    const round = r.round_name ? `<span class="mono xs muted">${esc(r.round_name)}</span>` : '';
    const aName = r.team_a_name || `team ${1}`;
    const bName = r.team_b_name || `team ${2}`;
    const aWin = r.winner === 'a', bWin = r.winner === 'b';
    const winStyle = 'color:var(--green);font-weight:700';
    const loseStyle = 'color:var(--muted)';
    const aStyle = aWin ? winStyle : (bWin ? loseStyle : '');
    const bStyle = bWin ? winStyle : (aWin ? loseStyle : '');
    return `<tr>
      <td class="rank-cell">${i + 1}</td>
      <td>${round}<div><span style="${aStyle}">${esc(aName)}</span> <span class="muted">vs</span> <span style="${bStyle}">${esc(bName)}</span></div></td>
      <td>${mapLink(r.name, r.beatmap_id)}</td>
      <td class="r mono"><span style="${aStyle}">${r.team_a.toLocaleString()}</span> <span class="muted">vs</span> <span style="${bStyle}">${r.team_b.toLocaleString()}</span></td>
      <td class="r" style="color:var(--${kind === 'closest' ? 'green' : 'red'});font-weight:700">${r.diff.toLocaleString()}</td>
    </tr>`;
  }).join('');
  return `<table class="stats-table">
    <thead><tr>
      <th>#</th><th>match</th><th>pick</th><th class="r">team scores</th>
      <th class="r">score diff ${kind === 'closest' ? '▲' : '▼'}</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}

export function renderCarryTable(rows) {
  if (!rows.length) return '<div class="empty-msg">no carry data yet (need team_size > 1)</div>';
  const tbody = rows.map((r, i) => {
    const mods = (r.mods || []).join('');
    const modsBadge = mods ? `<span style="font-size:9px;color:var(--yellow);margin-left:4px">+${esc(mods)}</span>` : '';
    return `<tr>
      <td class="rank-cell">${i + 1}</td>
      <td>${esc(r.username || r.user_id)}</td>
      <td>${mapLink(r.name, r.beatmap_id)}${modsBadge}</td>
      <td class="r mono">${r.score.toLocaleString()}</td>
      <td class="r" style="color:var(--green)">${(r.accuracy * 100).toFixed(2)}%</td>
      <td class="r mono xs muted" title="player z">${r.z.toFixed(2)}</td>
      <td class="r mono xs muted" title="team avg z">${r.team_avg_z.toFixed(2)}</td>
      <td class="r" style="color:var(--blue);font-weight:700" title="player z minus team avg z">${r.carry_z.toFixed(2)}</td>
    </tr>`;
  }).join('');
  return `<table class="stats-table">
    <thead><tr>
      <th>#</th><th>player</th><th>pick</th>
      <th class="r">score</th><th class="r">acc</th>
      <th class="r">z</th><th class="r">team z</th>
      <th class="r">carry z ▼</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}
