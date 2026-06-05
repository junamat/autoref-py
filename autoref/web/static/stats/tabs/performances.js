'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state, invalidateTabs, tabAffects } from '../state.js';
import { currentFilterParams, currentPoolDefaults } from '../filters.js';
import { buildMethodToggle } from '../methods.js';
import { renderLeaderboard } from '../tables/leaderboard.js';
import { renderMappool } from '../tables/mappool.js';
import { renderPlots } from '../plots/index.js';
import { loadExtras } from './extras.js';
import { loadStandings } from './standings.js';
import { loadResults } from './results.js';
import { loadTeamPerformances } from './teamPerf.js';

let cachedMappoolData = null;

function buildPlotCtx(mappoolRows) {
  return {
    mappoolRows,
    theme: () => document.body.classList.contains('light') ? 'light' : 'dark',
    countFailed: () => activeVal('cfg-failed') !== 'false',
    filterParams: () => currentFilterParams(),
    context: () => state.context || {},
    poolDefaults: () => currentPoolDefaults(),
  };
}

export async function loadMappool(changed = 'filter') {
  if (!tabAffects('mappool', [changed]) && cachedMappoolData) return;

  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const params = new URLSearchParams({
    method: state.currentMethod, count_failed: countFailed, aggregate,
    ...currentFilterParams(),
  });
  const url = `/api/stats?${params.toString()}`;

  document.getElementById('mappool-wrap').innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    document.getElementById('mappool-wrap').innerHTML = msg;
    return;
  }

  cachedMappoolData = data.mappool || [];
  renderMappool(cachedMappoolData);
  renderPlots(buildPlotCtx(cachedMappoolData));
  state.mappoolLoaded = true;
}

export async function load(changed = 'filter') {
  const perfAffected = tabAffects('performances', [changed]);

  if (perfAffected) {
    const countFailed = activeVal('cfg-failed') !== 'false';
    const aggregate = activeVal('cfg-aggregate') || 'sum';
    const params = new URLSearchParams({
      method: state.currentMethod, count_failed: countFailed, aggregate,
      ...currentFilterParams(),
    });
    const url = `/api/stats?${params.toString()}`;

    document.getElementById('leaderboard-wrap').innerHTML = '<div class="empty-msg">loading…</div>';

    let data;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } catch (e) {
      const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
      document.getElementById('leaderboard-wrap').innerHTML = msg;
      return;
    }

    if (!state.methodsReady && data.methods) {
      buildMethodToggle(data.methods, (c) => load(c || 'method'));
      state.methodsReady = true;
    }

    renderLeaderboard(data.leaderboard || [], data.metric_col, data.ascending, data.method, data.total_maps || 0);

    if (!cachedMappoolData) {
      cachedMappoolData = data.mappool || [];
      renderMappool(cachedMappoolData);
      renderPlots(buildPlotCtx(cachedMappoolData));
      state.mappoolLoaded = true;
    }

    invalidateTabs();
  } else {
    if (tabAffects('extras', [changed])) state.extrasLoaded = false;
    if (tabAffects('standings', [changed])) state.standingsLoaded = false;
    if (tabAffects('results', [changed])) state.resultsLoaded = false;
    if (tabAffects('teamPerf', [changed])) state.teamPerfLoaded = false;
    if (tabAffects('mappool', [changed])) {
      state.mappoolLoaded = false;
      cachedMappoolData = null;
    }
  }

  if (document.querySelector('.tab-panel[data-panel="extras"]:not([hidden])') && tabAffects('extras', [changed])) loadExtras();
  if (document.querySelector('.tab-panel[data-panel="standings"]:not([hidden])') && tabAffects('standings', [changed])) loadStandings();
  if (document.querySelector('.tab-panel[data-panel="results"]:not([hidden])') && tabAffects('results', [changed])) loadResults();
  if (document.querySelector('.tab-panel[data-panel="performances"]:not([hidden])') && tabAffects('teamPerf', [changed])) loadTeamPerformances();
  if (document.querySelector('.tab-panel[data-panel="mappool"]:not([hidden])') && tabAffects('mappool', [changed])) loadMappool(changed);
}
