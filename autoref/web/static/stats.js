'use strict';

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
  load();  // re-fetch so plots re-render in the new palette
});

/* ── state ───────────────────────────────────────────────────── */
let currentMethod = 'zscore';
let methodsReady  = false;
let filterOptions = null;  // { pools:[{id,name}], rounds:[str], combos:[{pool_id,round_name}] }

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

document.getElementById('cfg-round').addEventListener('change', () => {
  refreshPoolOptions();
  load();
});
document.getElementById('cfg-pool').addEventListener('change', load);

/* ── pool/round filter ───────────────────────────────────────── */
async function loadFilterOptions() {
  try {
    const res = await fetch('/api/stats/filters');
    if (!res.ok) return;
    filterOptions = await res.json();
  } catch { return; }

  const roundSel = document.getElementById('cfg-round');
  const poolSel  = document.getElementById('cfg-pool');
  const poolLbl  = document.getElementById('cfg-pool-label');

  // Round selector — only show if at least one round was recorded.
  if (filterOptions.rounds && filterOptions.rounds.length) {
    roundSel.innerHTML = `<option value="">all rounds</option>` +
      filterOptions.rounds.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
    roundSel.hidden = false;
  }
  // Pool selector — show only when more than one pool exists, or filtering by round
  // would otherwise be ambiguous. We re-render the options based on current round.
  refreshPoolOptions();
  if (filterOptions.pools && filterOptions.pools.length > 1) {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }
}

function refreshPoolOptions() {
  if (!filterOptions) return;
  const round = document.getElementById('cfg-round').value;
  const poolSel = document.getElementById('cfg-pool');
  const poolLbl = document.getElementById('cfg-pool-label');

  // Pools that actually have data for the chosen round (or all pools if no round).
  const allowed = round
    ? new Set(filterOptions.combos.filter(c => c.round_name === round).map(c => c.pool_id))
    : new Set(filterOptions.pools.map(p => p.id));

  const visiblePools = filterOptions.pools.filter(p => allowed.has(p.id));
  const prev = poolSel.value;
  poolSel.innerHTML = `<option value="">all pools</option>` +
    visiblePools.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  // Restore previous selection if still valid; otherwise fall back to "all".
  poolSel.value = visiblePools.some(p => p.id === prev) ? prev : '';

  // Auto-hide the pool dropdown when a round narrows it to a single option.
  if (visiblePools.length <= 1 && (filterOptions.pools.length <= 1)) {
    poolSel.hidden = true;
    poolLbl.hidden = true;
  } else {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }
}

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
function currentFilterParams() {
  const round = document.getElementById('cfg-round')?.value || '';
  const pool  = document.getElementById('cfg-pool')?.value  || '';
  const out = {};
  if (round) out.round_name = round;
  if (pool)  out.pool_id    = pool;
  return out;
}

async function load() {
  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const params = new URLSearchParams({
    method: currentMethod, count_failed: countFailed, aggregate,
    ...currentFilterParams(),
  });
  const url = `/api/stats?${params.toString()}`;

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
  renderPlots(data.mappool || []);
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
    const label = r.name || r.beatmap_id;
    return `<tr>
      <td class="mono" style="color:var(--blue);font-weight:700" title="beatmap ${esc(r.beatmap_id)}">${esc(label)}</td>
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

/* ── plots ───────────────────────────────────────────────────── */
let plotsAvailable = null;  // null = unknown, true/false = checked

async function checkPlotsAvailable() {
  if (plotsAvailable !== null) return plotsAvailable;
  try {
    const res = await fetch('/api/stats/plots');
    const data = await res.json();
    plotsAvailable = !!data.available;
  } catch { plotsAvailable = false; }
  return plotsAvailable;
}

function plotUrl(name, params = {}) {
  const theme = document.body.classList.contains('light') ? 'light' : 'dark';
  const countFailed = activeVal('cfg-failed') !== 'false';
  const qs = new URLSearchParams({
    theme, count_failed: countFailed, format: 'png', _t: Date.now(),
    ...currentFilterParams(),
    ...params,
  });
  return `/api/stats/plot/${name}?${qs.toString()}`;
}

function plotBlock(name, title, params = {}) {
  const baseQs = new URLSearchParams({
    theme: document.body.classList.contains('light') ? 'light' : 'dark',
    count_failed: activeVal('cfg-failed') !== 'false',
    ...currentFilterParams(),
    ...params,
  });
  const svgUrl   = `/api/stats/plot/${name}?format=svg&${baseQs.toString()}`;
  const hiresUrl = `/api/stats/plot/${name}?format=hires&${baseQs.toString()}`;
  return `<div class="plot-block" data-plot="${esc(name)}">
    <div class="plot-head">
      <span class="plot-title">${esc(title)}</span>
      <div class="plot-actions">
        <a class="plot-action" href="${svgUrl}" download>SVG</a>
        <a class="plot-action" href="${hiresUrl}" download>HQ PNG</a>
      </div>
    </div>
    <img class="plot-img" loading="lazy" alt="${esc(title)}" src="${plotUrl(name, params)}">
  </div>`;
}

async function renderPlots(mappoolRows) {
  const section = document.getElementById('plots-section');
  const wrap = document.getElementById('plots-wrap');
  if (!await checkPlotsAvailable()) {
    section.hidden = true;
    return;
  }
  section.hidden = false;

  // played-only: maps with at least one play (avg_score present means scores exist)
  const played = mappoolRows.filter(r => r.avg_score != null);

  const beatmapSelect = played.length
    ? `<label>map <select id="plot-beatmap">${
        played.map(r => {
          const label = r.name || r.beatmap_id;
          return `<option value="${r.beatmap_id}" data-label="${esc(label)}">${esc(label)}</option>`;
        }).join('')
      }</select></label>`
    : '<span>no played maps yet</span>';

  wrap.innerHTML = `
    <div class="plot-controls">${beatmapSelect}</div>
    <div id="plot-distribution"></div>
    ${plotBlock('pickban_heat', 'Pick / ban / protect heat')}
    ${interactiveConsistencyBlock()}
  `;

  if (played.length) {
    const sel = document.getElementById('plot-beatmap');
    const renderDist = () => {
      const label = sel.options[sel.selectedIndex]?.dataset.label || sel.value;
      document.getElementById('plot-distribution').innerHTML = plotBlock(
        'score_distribution',
        `Score distribution · ${label}`,
        { beatmap_id: sel.value, label },
      );
    };
    sel.addEventListener('change', renderDist);
    renderDist();
  }

  loadConsistencyPlot();
}

/* ── interactive consistency scatter ─────────────────────────── */
function interactiveConsistencyBlock() {
  const baseQs = new URLSearchParams({
    theme: document.body.classList.contains('light') ? 'light' : 'dark',
    count_failed: activeVal('cfg-failed') !== 'false',
    ...currentFilterParams(),
  });
  const svgUrl   = `/api/stats/plot/consistency_scatter?format=svg&${baseQs.toString()}`;
  const hiresUrl = `/api/stats/plot/consistency_scatter?format=hires&${baseQs.toString()}`;
  return `<div class="plot-block" data-plot="consistency_scatter">
    <div class="plot-head">
      <span class="plot-title">Player consistency</span>
      <input type="text" class="iplot-search" id="iplot-search" placeholder="search player…">
      <span class="iplot-hint">hover dots · dot size = maps played</span>
      <div class="plot-actions">
        <a class="plot-action" href="${svgUrl}" download>SVG</a>
        <a class="plot-action" href="${hiresUrl}" download>HQ PNG</a>
      </div>
    </div>
    <div class="iplot-wrap" id="iplot-consistency">
      <div class="empty-msg">loading…</div>
    </div>
  </div>`;
}

async function loadConsistencyPlot() {
  const host = document.getElementById('iplot-consistency');
  if (!host) return;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });
  let data;
  try {
    const res = await fetch(`/api/stats/plot/consistency_scatter/data?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    host.innerHTML = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    return;
  }
  if (!data.points || !data.points.length) {
    host.innerHTML = '<div class="empty-msg">no score data yet</div>';
    return;
  }
  renderConsistencySVG(host, data);
}

function renderConsistencySVG(host, data) {
  const points = data.points;
  const W = host.clientWidth || 720;
  const H = Math.max(360, Math.round(W * 0.5));
  const M = { top: 28, right: 16, bottom: 38, left: 52 };
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  // axis ranges with a small pad
  const xs = points.map(p => p.mean_z);
  const ys = points.map(p => p.std_z);
  const pad = (lo, hi) => {
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo;
    return [lo - span * 0.08, hi + span * 0.08];
  };
  const [xMin, xMax] = pad(Math.min(...xs, 0), Math.max(...xs, 0));
  let [yMin, yMax]   = pad(Math.min(...ys), Math.max(...ys));
  yMin = 0;  // stddev cannot be negative

  const sx = v => M.left + ((v - xMin) / (xMax - xMin)) * innerW;
  const sy = v => M.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

  const nMax = Math.max(...points.map(p => p.n));
  const rOf = n => 4 + 6 * (nMax > 0 ? n / nMax : 0);

  // ticks: 5 nicely spaced values per axis
  const ticks = (lo, hi, count = 5) => {
    const step = (hi - lo) / (count - 1);
    return Array.from({ length: count }, (_, i) => lo + step * i);
  };
  const xTicks = ticks(xMin, xMax);
  const yTicks = ticks(yMin, yMax);
  const fmt = v => Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2);

  const stdMedian = data.std_median;

  // top-N labels (mirror server-side behavior, but rendered as SVG text)
  const top = [...points].sort((a, b) => b.mean_z - a.mean_z).slice(0, 5);
  const topIds = new Set(top.map(p => p.user_id));

  const dots = points.map(p => `<circle class="dot" data-uid="${p.user_id}"
    cx="${sx(p.mean_z).toFixed(1)}" cy="${sy(p.std_z).toFixed(1)}" r="${rOf(p.n).toFixed(1)}"></circle>`).join('');
  const labels = top.map(p => `<text class="label"
    x="${(sx(p.mean_z) + 6).toFixed(1)}" y="${(sy(p.std_z) - 6).toFixed(1)}">${esc(p.username)}</text>`).join('');

  const grid = [
    ...xTicks.map(t => `<line x1="${sx(t).toFixed(1)}" y1="${M.top}" x2="${sx(t).toFixed(1)}" y2="${M.top + innerH}"/>`),
    ...yTicks.map(t => `<line x1="${M.left}" y1="${sy(t).toFixed(1)}" x2="${M.left + innerW}" y2="${sy(t).toFixed(1)}"/>`),
  ].join('');

  const xAxisTicks = xTicks.map(t =>
    `<text x="${sx(t).toFixed(1)}" y="${M.top + innerH + 14}" text-anchor="middle">${fmt(t)}</text>`).join('');
  const yAxisTicks = yTicks.map(t =>
    `<text x="${M.left - 6}" y="${(sy(t) + 3).toFixed(1)}" text-anchor="end">${fmt(t)}</text>`).join('');

  const guides = [
    // x = 0 vertical guide
    (xMin <= 0 && xMax >= 0)
      ? `<line class="guide" x1="${sx(0).toFixed(1)}" y1="${M.top}" x2="${sx(0).toFixed(1)}" y2="${M.top + innerH}"/>` : '',
    // median std horizontal guide
    (stdMedian != null && stdMedian >= yMin && stdMedian <= yMax)
      ? `<line class="guide" x1="${M.left}" y1="${sy(stdMedian).toFixed(1)}" x2="${M.left + innerW}" y2="${sy(stdMedian).toFixed(1)}"/>` : '',
  ].join('');

  host.innerHTML = `
    <svg class="iplot" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      <text class="title" x="${(W / 2).toFixed(1)}" y="16" text-anchor="middle">player consistency · skill vs. spread (n=${points.length})</text>
      <g class="grid">${grid}</g>
      ${guides}
      <g class="axis">
        <line x1="${M.left}" y1="${M.top + innerH}" x2="${M.left + innerW}" y2="${M.top + innerH}"/>
        <line x1="${M.left}" y1="${M.top}" x2="${M.left}" y2="${M.top + innerH}"/>
        ${xAxisTicks}
        ${yAxisTicks}
      </g>
      <text class="axis-label" x="${(M.left + innerW / 2).toFixed(1)}" y="${H - 6}" text-anchor="middle">mean z-score (skill →)</text>
      <text class="axis-label" transform="translate(14 ${(M.top + innerH / 2).toFixed(1)}) rotate(-90)" text-anchor="middle">z-score stddev (← consistent · variable →)</text>
      <g class="dots">${dots}</g>
      <g class="labels">${labels}</g>
    </svg>
    <div class="iplot-tip" id="iplot-tip"></div>
  `;

  const tip = host.querySelector('#iplot-tip');
  const svg = host.querySelector('svg');
  const byUid = new Map(points.map(p => [String(p.user_id), p]));

  const showTip = (circle) => {
    const p = byUid.get(circle.dataset.uid);
    if (!p) return;
    tip.innerHTML = `
      <div class="tip-name">${esc(p.username)}</div>
      <div class="tip-row">maps: <b>${p.n}</b></div>
      <div class="tip-row">mean z: <b>${p.mean_z.toFixed(3)}</b></div>
      <div class="tip-row">σ z: <b>${p.std_z.toFixed(3)}</b></div>
    `;
    const hostRect = host.getBoundingClientRect();
    const cRect = circle.getBoundingClientRect();
    const x = cRect.left + cRect.width / 2 - hostRect.left;
    const y = cRect.top - hostRect.top;
    tip.style.opacity = '1';
    // place after measuring so we can clamp inside the host
    requestAnimationFrame(() => {
      const tipW = tip.offsetWidth;
      const tipH = tip.offsetHeight;
      let left = x - tipW / 2;
      let top  = y - tipH - 8;
      if (left < 4) left = 4;
      if (left + tipW > host.clientWidth - 4) left = host.clientWidth - tipW - 4;
      if (top < 4) top = y + cRect.height + 8;
      tip.style.left = `${left}px`;
      tip.style.top  = `${top}px`;
    });
  };
  const hideTip = () => { tip.style.opacity = '0'; };

  svg.querySelectorAll('.dot').forEach(c => {
    c.addEventListener('mouseenter', () => showTip(c));
    c.addEventListener('mouseleave', hideTip);
    c.addEventListener('focus',      () => showTip(c));
    c.addEventListener('blur',       hideTip);
    c.setAttribute('tabindex', '0');
  });

  const search = document.getElementById('iplot-search');
  if (search) {
    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      svg.querySelectorAll('.dot').forEach(c => {
        const p = byUid.get(c.dataset.uid);
        if (!q) { c.classList.remove('dim', 'active'); return; }
        const hit = p && p.username.toLowerCase().includes(q);
        c.classList.toggle('active', hit);
        c.classList.toggle('dim', !hit);
      });
    });
  }
}

/* ── boot ────────────────────────────────────────────────────── */
loadFilterOptions().then(load);
