'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state, invalidateTabs } from '../state.js';
import { currentFilterParams } from '../filters.js';
import { buildMethodToggle } from '../methods.js';
import { renderLeaderboard } from '../tables/leaderboard.js';
import { renderMappool } from '../tables/mappool.js';
import { renderPlots } from '../plots/index.js';
import { loadExtras } from './extras.js';
import { loadStandings } from './standings.js';
import { loadResults } from './results.js';
import { loadTeamPerformances } from './teamPerf.js';

function buildPlotCtx(mappoolRows) {
  return {
    mappoolRows,
    theme: () => document.body.classList.contains('light') ? 'light' : 'dark',
    countFailed: () => activeVal('cfg-failed') !== 'false',
    filterParams: () => currentFilterParams(),
  };
}

export async function load() {
  const countFailed = activeVal('cfg-failed') !== 'false';
  const aggregate = activeVal('cfg-aggregate') || 'sum';
  const params = new URLSearchParams({
    method: state.currentMethod, count_failed: countFailed, aggregate,
    ...currentFilterParams(),
  });
  const url = `/api/stats?${params.toString()}`;

  document.getElementById('leaderboard-wrap').innerHTML = '<div class="empty-msg">loading…</div>';
  document.getElementById('mappool-wrap').innerHTML = '<div class="empty-msg">loading…</div>';

  let data;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    document.getElementById('leaderboard-wrap').innerHTML = msg;
    document.getElementById('mappool-wrap').innerHTML = msg;
    return;
  }

  if (!state.methodsReady && data.methods) {
    buildMethodToggle(data.methods, load);
    state.methodsReady = true;
  }

  renderLeaderboard(data.leaderboard || [], data.metric_col, data.ascending, data.method, data.total_maps || 0);
  renderMappool(data.mappool || []);
  renderPlots(buildPlotCtx(data.mappool || []));

  invalidateTabs();
  if (document.querySelector('.tab-panel[data-panel="extras"]:not([hidden])')) loadExtras();
  if (document.querySelector('.tab-panel[data-panel="standings"]:not([hidden])')) loadStandings();
  if (document.querySelector('.tab-panel[data-panel="results"]:not([hidden])')) loadResults();
  if (document.querySelector('.tab-panel[data-panel="performances"]:not([hidden])')) loadTeamPerformances();
}
