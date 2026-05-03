'use strict';

import { esc } from '/static/shared/util.js';
import { state } from './state.js';

export function currentFilterParams() {
  const round = document.getElementById('cfg-round')?.value || '';
  const pool = document.getElementById('cfg-pool')?.value || '';
  const out = {};
  if (round) out.round_name = round;
  if (pool) out.pool_id = pool;
  return out;
}

export function currentPoolDefaults() {
  const pool = document.getElementById('cfg-pool')?.value || '';
  return (state.filterOptions?.pool_defaults?.[pool]) || {};
}

export async function loadFilterOptions() {
  try {
    const res = await fetch('/api/stats/filters');
    if (!res.ok) return;
    state.filterOptions = await res.json();
  } catch { return; }

  const roundSel = document.getElementById('cfg-round');
  const poolSel = document.getElementById('cfg-pool');
  const poolLbl = document.getElementById('cfg-pool-label');

  if (state.filterOptions.rounds && state.filterOptions.rounds.length) {
    roundSel.innerHTML = `<option value="">all rounds</option>` +
      state.filterOptions.rounds.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
    roundSel.hidden = false;
  }
  refreshPoolOptions();
  if (state.filterOptions.pools && state.filterOptions.pools.length > 1) {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }
}

export function refreshPoolOptions() {
  if (!state.filterOptions) return;
  const round = document.getElementById('cfg-round').value;
  const poolSel = document.getElementById('cfg-pool');
  const poolLbl = document.getElementById('cfg-pool-label');

  const allowed = round
    ? new Set(state.filterOptions.combos.filter(c => c.round_name === round).map(c => c.pool_id))
    : new Set(state.filterOptions.pools.map(p => p.id));

  const visiblePools = state.filterOptions.pools.filter(p => allowed.has(p.id));
  const prev = poolSel.value;
  poolSel.innerHTML = `<option value="">all pools</option>` +
    visiblePools.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  poolSel.value = visiblePools.some(p => p.id === prev) ? prev : '';

  if (visiblePools.length <= 1 && (state.filterOptions.pools.length <= 1)) {
    poolSel.hidden = true;
    poolLbl.hidden = true;
  } else {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }
}
