'use strict';

import { esc } from '/static/shared/util.js';
import { setCustomColors } from '/static/shared/modColors.js';
import { state, invalidateTabs } from './state.js';

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
    const pool = document.getElementById('cfg-pool')?.value || '';
    if (pool && state.filterOptions.pool_colors?.[pool]) {
      setCustomColors(state.filterOptions.pool_colors[pool]);
    } else {
      setCustomColors({});
    }
  } catch { return; }

  const roundSel = document.getElementById('cfg-round');
  const poolSel = document.getElementById('cfg-pool');
  const poolLbl = document.getElementById('cfg-pool-label');

  if (state.filterOptions.rounds && state.filterOptions.rounds.length) {
    roundSel.innerHTML = `<option value="">all rounds</option>` +
      state.filterOptions.rounds.map(r => `<option value="${esc(r)}">${esc(r)}</option>`).join('');
    roundSel.hidden = false;
    // Auto-select OQ26 if it exists
    if (state.filterOptions.rounds.includes('OQ26')) {
      roundSel.value = 'OQ26';
    }
  }
  refreshPoolOptions();
  if (state.filterOptions.pools && state.filterOptions.pools.length >= 1) {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }
}

export async function loadContext() {
  const params = new URLSearchParams(currentFilterParams());
  try {
    const res = await fetch(`/api/stats/context?${params.toString()}`);
    if (!res.ok) return;
    state.context = await res.json();
  } catch { return; }
  applyContext(state.context);
  invalidateTabs();
}

export function applyContext(ctx) {
  if (!ctx) return;
  const teamStandingsSec = document.getElementById('team-standings-section');
  const teamPerfSec = document.getElementById('team-performances-section');
  if (teamStandingsSec) teamStandingsSec.hidden = !ctx.has_teams;
  if (teamPerfSec) teamPerfSec.hidden = !ctx.has_teams;
  const closestSec = document.getElementById('extras-closest-section');
  const blowoutsSec = document.getElementById('extras-blowouts-section');
  const carriesSec = document.getElementById('extras-carries-section');
  if (closestSec) closestSec.hidden = !ctx.has_bracket;
  if (blowoutsSec) blowoutsSec.hidden = !ctx.has_bracket;
  if (carriesSec) carriesSec.hidden = !ctx.has_teams;
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
  
  // Auto-select OpenQualifiers4wc26 pool if it exists, otherwise first pool if only one
  const preferredPool = visiblePools.find(p => p.name === 'OpenQualifiers4wc26' || p.id === 'OpenQualifiers4wc26');
  if (preferredPool) {
    poolSel.value = preferredPool.id;
  } else if (visiblePools.length === 1 && !prev) {
    poolSel.value = visiblePools[0].id;
  } else {
    poolSel.value = visiblePools.some(p => p.id === prev) ? prev : '';
  }

  if (visiblePools.length <= 1 && (state.filterOptions.pools.length <= 1)) {
    // Still show selector if there's at least 1 pool in store
    if (state.filterOptions.pools.length === 0) {
      poolSel.hidden = true;
      poolLbl.hidden = true;
    } else {
      poolSel.hidden = false;
      poolLbl.hidden = false;
    }
  } else {
    poolSel.hidden = false;
    poolLbl.hidden = false;
  }

  const pool = poolSel.value;
  if (pool && state.filterOptions.pool_colors?.[pool]) {
    setCustomColors(state.filterOptions.pool_colors[pool]);
  } else {
    setCustomColors({});
  }
}
