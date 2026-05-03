'use strict';

import { esc } from '/static/shared/util.js';

function buildQs(ctx, extra = {}) {
  return new URLSearchParams({
    theme: ctx.theme(),
    count_failed: ctx.countFailed(),
    ...ctx.filterParams(),
    ...extra,
  });
}

export function plotUrl(ctx, name, params = {}) {
  const qs = buildQs(ctx, { format: 'png', _t: Date.now(), ...params });
  return `/api/stats/plot/${name}?${qs.toString()}`;
}

export function plotBlock(ctx, name, title, params = {}) {
  const baseQs = buildQs(ctx, params);
  const svgUrl = `/api/stats/plot/${name}?format=svg&${baseQs.toString()}`;
  const hiresUrl = `/api/stats/plot/${name}?format=hires&${baseQs.toString()}`;
  return `<div class="plot-block" data-plot="${esc(name)}">
    <div class="plot-head">
      <span class="plot-title">${esc(title)}</span>
      <div class="plot-actions">
        <a class="plot-action" href="${svgUrl}" download>SVG</a>
        <a class="plot-action" href="${hiresUrl}" download>HQ PNG</a>
      </div>
    </div>
    <img class="plot-img" loading="lazy" alt="${esc(title)}" src="${plotUrl(ctx, name, params)}">
  </div>`;
}
