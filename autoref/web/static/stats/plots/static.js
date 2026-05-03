'use strict';

import { esc } from '/static/shared/util.js';
import { register, SECTION_MAPPOOL, SECTION_PERF } from './registry.js';
import { plotBlock } from './url.js';

register({
  name: 'pickban_heat',
  section: SECTION_MAPPOOL,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'pickban_heat', 'Pick / ban / protect heat');
  },
});

register({
  name: 'score_distribution',
  section: SECTION_PERF,
  mount(host, ctx) {
    const played = ctx.mappoolRows.filter(r => r.avg_score != null);
    if (!played.length) {
      host.innerHTML = `
        <div class="plot-controls"><span>no played maps yet</span></div>
        <div id="plot-distribution"></div>
      `;
      return;
    }
    const opts = played.map(r => {
      const label = r.name || r.beatmap_id;
      return `<option value="${r.beatmap_id}" data-label="${esc(label)}">${esc(label)}</option>`;
    }).join('');
    host.innerHTML = `
      <div class="plot-controls">
        <label>map <select id="plot-beatmap">${opts}</select></label>
      </div>
      <div id="plot-distribution"></div>
    `;
    const sel = host.querySelector('#plot-beatmap');
    const dist = host.querySelector('#plot-distribution');
    const renderDist = () => {
      const label = sel.options[sel.selectedIndex]?.dataset.label || sel.value;
      dist.innerHTML = plotBlock(ctx, 'score_distribution',
        `Score distribution · ${label}`,
        { beatmap_id: sel.value, label });
    };
    sel.addEventListener('change', renderDist);
    renderDist();
  },
});
