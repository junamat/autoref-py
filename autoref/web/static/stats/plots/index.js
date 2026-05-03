'use strict';

import { bySection, SECTION_MAPPOOL, SECTION_PERF } from './registry.js';
import './static.js';
import './consistency.js';

let _available = null;

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

  await mountSection(mappoolWrap, bySection(SECTION_MAPPOOL), ctx);
  await mountSection(perfWrap, bySection(SECTION_PERF), ctx);
}

async function mountSection(wrap, plots, ctx) {
  wrap.innerHTML = plots.map(p => `<div class="plot-slot" data-plot="${p.name}"></div>`).join('');
  for (const p of plots) {
    const slot = wrap.querySelector(`.plot-slot[data-plot="${p.name}"]`);
    if (!slot) continue;
    try {
      await p.mount(slot, ctx);
    } catch (e) {
      slot.innerHTML = `<div class="empty-msg">plot ${p.name} failed: ${e.message}</div>`;
    }
  }
}
