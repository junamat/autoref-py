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

/* ── tabs ────────────────────────────────────────────────────── */
const tabs = document.querySelectorAll('.stats-tab');
const panels = document.querySelectorAll('.tab-panel');
let extrasLoaded = false;
let standingsLoaded = false;
let resultsLoaded = false;
let teamPerfLoaded = false;
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    tabs.forEach(t => t.classList.toggle('active', t === tab));
    panels.forEach(p => { p.hidden = p.dataset.panel !== target; });
    if (target === 'extras'       && !extrasLoaded)    loadExtras();
    if (target === 'standings'    && !standingsLoaded) loadStandings();
    if (target === 'results'      && !resultsLoaded)   loadResults();
    if (target === 'performances' && !teamPerfLoaded)  loadTeamPerformances();
  });
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

  renderLeaderboard(data.leaderboard || [], data.metric_col, data.ascending, data.method, data.total_maps || 0);
  renderMappool(data.mappool || []);
  renderPlots(data.mappool || []);

  // Invalidate extras cache; refetch next time the tab opens.
  extrasLoaded = false;
  standingsLoaded = false;
  resultsLoaded = false;
  teamPerfLoaded = false;
  if (document.querySelector('.tab-panel[data-panel="extras"]:not([hidden])')) {
    loadExtras();
  }
  if (document.querySelector('.tab-panel[data-panel="standings"]:not([hidden])')) {
    loadStandings();
  }
  if (document.querySelector('.tab-panel[data-panel="results"]:not([hidden])')) {
    loadResults();
  }
  if (document.querySelector('.tab-panel[data-panel="performances"]:not([hidden])')) {
    loadTeamPerformances();
  }
}

/* ── extras ──────────────────────────────────────────────────── */
async function loadExtras() {
  extrasLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });

  const closest = document.getElementById('extras-closest-wrap');
  const blowouts = document.getElementById('extras-blowouts-wrap');
  const carries = document.getElementById('extras-carries-wrap');
  closest.innerHTML = blowouts.innerHTML = carries.innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(`/api/stats/extras?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    closest.innerHTML = blowouts.innerHTML = carries.innerHTML = msg;
    return;
  }

  closest.innerHTML  = renderDiffTable(data.closest_maps || [], 'closest');
  blowouts.innerHTML = renderDiffTable(data.biggest_blowouts || [], 'blowout');
  carries.innerHTML  = renderCarryTable(data.biggest_carries || []);
}

function mapLink(name, beatmapId) {
  const href = `https://osu.ppy.sh/b/${encodeURIComponent(beatmapId)}`;
  const label = name || beatmapId;
  return `<a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);font-weight:700;text-decoration:none">${esc(label)}</a>`;
}

function renderDiffTable(rows, kind) {
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

function renderCarryTable(rows) {
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

/* ── leaderboard ─────────────────────────────────────────────── */
const GRADE_COLOR = {
  X:  'var(--yellow)', XH: 'var(--yellow)',
  S:  'var(--yellow)', SH: 'var(--yellow)',
  A:  'var(--green)',
  B:  'var(--blue)',
  C:  'var(--orange)',
  D:  'var(--red)',
  F:  'var(--muted)',
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

function renderLeaderboard(rows, metricCol, ascending, method, totalMaps) {
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

/* ── mappool stats ───────────────────────────────────────────── */
function renderMappool(rows) {
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
  const maxPicks = Math.max(...rows.map(r => r.picks), 1);

  const tbody = rows.map(r => {
    const barW = Math.round((r.picks / maxPicks) * 60);
    const avgFmt = r.avg_score != null ? Math.round(r.avg_score).toLocaleString() : '—';
    const accFmt = r.avg_acc  != null ? `${(r.avg_acc * 100).toFixed(2)}%` : '—';
    const label = r.name || r.beatmap_id;
    const href = `https://osu.ppy.sh/b/${encodeURIComponent(r.beatmap_id)}`;
    const picked = r.protects_picked ?? 0;
    const unused = r.protects_unused ?? 0;
    return `<tr>
      <td class="mono" style="font-weight:700" title="beatmap ${esc(r.beatmap_id)}"><a href="${href}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none">${esc(label)}</a></td>
      <td class="r" style="color:var(--blue)">${r.picks}
        <span class="pick-bar" style="width:${barW}px;background:var(--blue);opacity:0.5"></span>
      </td>
      <td class="r" style="color:var(--red)">${r.bans}</td>
      <td class="r" style="color:var(--yellow)" title="protects total">${r.protects}</td>
      <td class="r" style="color:var(--green)" title="protects that were then picked">${picked}</td>
      <td class="r" style="color:var(--muted)" title="protects that were not picked">${unused}</td>
      <td class="r">${avgFmt}</td>
      <td class="r" style="color:var(--green)">${accFmt}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="stats-table">
    <thead><tr>
      <th>map</th>
      <th class="r">picks</th>
      <th class="r">bans</th>
      <th class="r">prot</th>
      <th class="r" title="protects that were then picked">prot ✓</th>
      <th class="r" title="protects that were not picked">prot ✗</th>
      <th class="r">avg score</th>
      <th class="r">avg acc</th>
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
  const mappoolSection = document.getElementById('plots-mappool-section');
  const perfSection = document.getElementById('plots-perf-section');
  const mappoolWrap = document.getElementById('plots-mappool-wrap');
  const perfWrap = document.getElementById('plots-perf-wrap');
  if (!await checkPlotsAvailable()) {
    mappoolSection.hidden = true;
    perfSection.hidden = true;
    return;
  }
  mappoolSection.hidden = false;
  perfSection.hidden = false;

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

  mappoolWrap.innerHTML = plotBlock('pickban_heat', 'Pick / ban / protect heat');

  perfWrap.innerHTML = `
    <div class="plot-controls">${beatmapSelect}</div>
    <div id="plot-distribution"></div>
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

/* ── standings ───────────────────────────────────────────────── */
async function loadStandings() {
  standingsLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });
  const wrap = document.getElementById('standings-wrap');
  const teamWrap = document.getElementById('team-standings-wrap');
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

  // Per-map cards
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

  // Team standings: same card grid as individual, one card per map
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

/* ── results (qualifiers grid) ───────────────────────────────── */
async function loadResults() {
  resultsLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const params = new URLSearchParams({ count_failed: countFailed, method: currentMethod, aggregate, ...currentFilterParams() });
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

/* ── team performances ───────────────────────────────────────── */
async function loadTeamPerformances() {
  teamPerfLoaded = true;
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

/* ── boot ────────────────────────────────────────────────────── */
loadFilterOptions().then(load);
