'use strict';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

/* ── state ───────────────────────────────────────────────────── */
let currentMethod = 'zscore';
let methodsReady  = false;

/* ── config toggles ──────────────────────────────────────────── */
function activeVal(groupId) {
  return document.querySelector(`#${groupId} .cfg-opt.active`)?.dataset.val;
}

document.getElementById('cfg-failed').addEventListener('click', e => {
  const opt = e.target.closest('.cfg-opt');
  if (!opt) return;
  document.querySelectorAll('#cfg-failed .cfg-opt').forEach(o => o.classList.remove('active'));
  opt.classList.add('active');
  load();
});

document.getElementById('cfg-aggregate').addEventListener('click', e => {
  const opt = e.target.closest('.cfg-opt');
  if (!opt) return;
  document.querySelectorAll('#cfg-aggregate .cfg-opt').forEach(o => o.classList.remove('active'));
  opt.classList.add('active');
  load();
});

document.getElementById('stats-reload').addEventListener('click', load);

/* ── method toggle (populated from API) ─────────────────────── */
function buildMethodToggle(methods) {
  const toggle = document.getElementById('cfg-calc');
  toggle.innerHTML = methods.map(m =>
    `<div class="cfg-opt${m.key === currentMethod ? ' active' : ''}" data-val="${esc(m.key)}">${esc(m.label)}</div>`
  ).join('');
  toggle.addEventListener('click', e => {
    const opt = e.target.closest('.cfg-opt');
    if (!opt) return;
    toggle.querySelectorAll('.cfg-opt').forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    currentMethod = opt.dataset.val;
    load();
  });
}

/* ── fetch + render ──────────────────────────────────────────── */
async function load() {
  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const url = `/api/stats?method=${currentMethod}&count_failed=${countFailed}&aggregate=${aggregate}`;

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

  if (!methodsReady && data.methods) {
    buildMethodToggle(data.methods);
    methodsReady = true;
  }

  renderLeaderboard(data.leaderboard || [], data.metric_col, data.ascending, data.method);
  renderMappool(data.mappool || []);
}

/* ── leaderboard ─────────────────────────────────────────────── */
function renderLeaderboard(rows, metricCol, ascending, method) {
  const wrap = document.getElementById('leaderboard-wrap');
  if (!rows.length) {
    wrap.innerHTML = '<div class="empty-msg">no data — play some matches first</div>';
    return;
  }

  const label = document.querySelector(`#cfg-calc .cfg-opt.active`)?.textContent || metricCol;
  const isPlacement = method === 'placements';

  // for bar: placements lower=better so invert; others higher=better
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
    return `<tr>
      <td class="rank-cell ${rankClass}">${rank}</td>
      <td>${esc(r.username || r.user_id)}</td>
      <td class="r">${r.maps_played}</td>
      <td class="z-bar-cell">
        <div class="z-bar-wrap">
          <div class="z-bar-bg"><div class="z-bar-fill" style="width:${pct}%"></div></div>
          <span class="z-val">${fmt}</span>
        </div>
      </td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>#</th>
      <th>player</th>
      <th class="r">maps</th>
      <th>${esc(label)} ▼</th>
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

  rows = [...rows].sort((a, b) => (b.picks + b.bans + b.protects) - (a.picks + a.bans + a.protects));
  const maxPicks = Math.max(...rows.map(r => r.picks), 1);

  const tbody = rows.map(r => {
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
