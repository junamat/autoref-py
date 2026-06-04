'use strict';

import {
  bySection,
  SECTION_MAPPOOL,
  SECTION_MAP_ANALYSIS,
  SECTION_MATCHFLOW,
  SECTION_PLAYER,
  SECTION_TEAM,
  SECTION_META,
  SCOPE_QUALIFIERS,
  SCOPE_BRACKET,
} from './registry.js';
import { state } from '../state.js';
import './static.js';
import './consistency.js';
import './new_plots.js';

const SECTIONS = [
  { key: SECTION_MAPPOOL, sectionId: 'plots-mappool-section', wrapId: 'plots-mappool-wrap' },
  { key: SECTION_MAP_ANALYSIS, sectionId: 'plots-map-analysis-section', wrapId: 'plots-map-analysis-wrap' },
  { key: SECTION_MATCHFLOW, sectionId: 'plots-matchflow-section', wrapId: 'plots-matchflow-wrap' },
  { key: SECTION_PLAYER, sectionId: 'plots-player-section', wrapId: 'plots-player-wrap' },
  { key: SECTION_TEAM, sectionId: 'plots-team-section', wrapId: 'plots-team-wrap' },
  { key: SECTION_META, sectionId: 'plots-meta-section', wrapId: 'plots-meta-wrap' },
];

let _available = null;
let _lastPlotCtx = null;

export async function checkPlotsAvailable() {
  if (_available !== null) return _available;
  try {
    const res = await fetch('/api/stats/plots');
    const data = await res.json();
    _available = !!data.available;
  } catch { _available = false; }
  return _available;
}

export async function renderPlots(ctx) {
  if (!await checkPlotsAvailable()) {
    for (const s of SECTIONS) {
      const el = document.getElementById(s.sectionId);
      if (el) el.hidden = true;
    }
    return;
  }

  // Build a signature of what affects plots (not method)
  const context = ctx.context ? ctx.context() : {};
  const poolDefaults = ctx.poolDefaults ? ctx.poolDefaults() : {};
  const plotCtxSig = JSON.stringify({
    theme: ctx.theme(),
    countFailed: ctx.countFailed(),
    filterParams: ctx.filterParams(),
    scope: poolDefaults.scope || (context.has_bracket ? 'bracket' : 'qualifiers'),
    hasBracket: context.has_bracket,
    hasTb: context.has_tb,
    rounds: state.filterOptions?.rounds?.length,
  });

  // Skip re-render if nothing plot-relevant changed
  if (_lastPlotCtx === plotCtxSig) return;
  _lastPlotCtx = plotCtxSig;
  
  // Get scope from pool's stats_defaults, or fall back to auto-detection
  let scope;
  if (poolDefaults.scope === 'qualifiers') {
    scope = SCOPE_QUALIFIERS;
  } else if (poolDefaults.scope === 'bracket') {
    scope = SCOPE_BRACKET;
  } else {
    // Auto-detect: if has_bracket actions, use bracket scope; otherwise qualifiers
    scope = context.has_bracket ? SCOPE_BRACKET : SCOPE_QUALIFIERS;
  }

  for (const s of SECTIONS) {
    const section = document.getElementById(s.sectionId);
    const wrap = document.getElementById(s.wrapId);
    if (!section || !wrap) continue;
    const plots = bySection(s.key, scope);
    
    // Hide meta analysis if only 1 round exists
    if (s.key === SECTION_META && state.filterOptions?.rounds?.length <= 1) {
      section.hidden = true;
      wrap.innerHTML = '';
      continue;
    }
    
    // Check if any plots in this section are visible after applying conditions
    const visiblePlots = plots.filter(p => !p.condition || p.condition(context));
    if (visiblePlots.length === 0) {
      section.hidden = true;
      wrap.innerHTML = '';
      continue;
    }
    
    section.hidden = false;
    await mountSection(wrap, plots, ctx);
  }
}

async function mountSection(wrap, plots, ctx) {
  const context = ctx.context ? ctx.context() : {};
  const visiblePlots = plots.filter(p => !p.condition || p.condition(context));
  
  if (visiblePlots.length === 0) {
    wrap.innerHTML = '';
    return;
  }
  
  wrap.innerHTML = `<div class="plots-grid">${visiblePlots.map(p => `<div class="plot-slot" data-plot="${p.name}"></div>`).join('')}</div>`;
  for (const p of visiblePlots) {
    const slot = wrap.querySelector(`.plot-slot[data-plot="${p.name}"]`);
    if (!slot) continue;
    try {
      await p.mount(slot, ctx);
    } catch (e) {
      slot.innerHTML = `<div class="empty-msg">plot ${p.name} failed: ${e.message}</div>`;
    }
  }
}
