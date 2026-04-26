'use strict';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ── theme ───────────────────────────────────────────────────── */
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'light') document.body.classList.add('light');
document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

/* ── config toggles ──────────────────────────────────────────── */
function activeVal(groupId) {
  return document.querySelector(`#${groupId} .cfg-opt.active`)?.dataset.val;
}

document.querySelectorAll('.cfg-toggle').forEach(toggle => {
  toggle.addEventListener('click', e => {
    const opt = e.target.closest('.cfg-opt');
    if (!opt) return;
    toggle.querySelectorAll('.cfg-opt').forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    load();
  });
});

document.getElementById('stats-reload').addEventListener('click', load);

/* ── fetch + render ──────────────────────────────────────────── */
async function load() {
  const countFailed = activeVal('cfg-failed') !== 'false';
  const url = `/api/stats?count_failed=${countFailed}`;

  document.getElementById('leaderboard-wrap').innerHTML = '<div class="empty-msg">loading…</div>';
  document.getElementById('mappool-wrap').innerHTML     = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    document.getElementById('leaderboard-wrap').innerHTML = msg;
    document.getElementById('mappool-wrap').innerHTML     = msg;
    return;
  }

  renderLeaderboard(data.leaderboard || []);
  renderMappool(data.mappool || []);
}

/* ── leaderboard ─────────────────────────────────────────────── */
function renderLeaderboard(rows) {
  const wrap = document.getElementById('leaderboard-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-msg">no data — play some matches first</div>';
    return;
  }

  const maxZ = Math.max(...rows.map(r => Math.abs(r.z_sum)), 1);

  const tbody = rows.map((r, i) => {
    const rank = i + 1;
    const rankClass = rank <= 3 ? `rank-${rank}` : '';
    const pct = Math.min(100, (Math.abs(r.z_sum) / maxZ) * 100).toFixed(1);
    const zFmt = r.z_sum.toFixed(4);
    const avgFmt = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    return `<tr>
      <td class="rank-cell ${rankClass}">${rank}</td>
      <td>${esc(r.username || r.user_id)}</td>
      <td class="r">${r.maps_played}</td>
      <td class="z-bar-cell">
        <div class="z-bar-wrap">
          <div class="z-bar-bg"><div class="z-bar-fill" style="width:${pct}%"></div></div>
          <span class="z-val">${zFmt}</span>
        </div>
      </td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>#</th>
      <th>player</th>
      <th class="r">maps</th>
      <th>z-sum ▼</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}

/* ── mappool stats ───────────────────────────────────────────── */
function renderMappool(rows) {
  const wrap = document.getElementById('mappool-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-msg">no map action data yet</div>';
    return;
  }

  // sort by total actions desc
  rows = [...rows].sort((a, b) => (b.picks + b.bans + b.protects) - (a.picks + a.bans + a.protects));

  const maxPicks = Math.max(...rows.map(r => r.picks), 1);

  const tbody = rows.map(r => {
    const total = r.picks + r.bans + r.protects;
    const pickPct = total ? ((r.picks / total) * 100).toFixed(0) : 0;
    const barW = Math.round((r.picks / maxPicks) * 60);
    const avgFmt = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    return `<tr>
      <td class="mono" style="color:var(--blue);font-weight:700">${esc(r.beatmap_id)}</td>
      <td class="r" style="color:var(--blue)">${r.picks}
        <span class="pick-bar" style="width:${barW}px;background:var(--blue);opacity:0.5"></span>
      </td>
      <td class="r" style="color:var(--red)">${r.bans}</td>
      <td class="r" style="color:var(--yellow)">${r.protects}</td>
      <td class="r">${avgFmt}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>map</th>
      <th class="r">picks</th>
      <th class="r">bans</th>
      <th class="r">protects</th>
      <th class="r">avg score</th>
    </tr></thead>
    <tbody>${tbody}</tbody>
  </table>`;
}

/* ── boot ────────────────────────────────────────────────────── */
load();
