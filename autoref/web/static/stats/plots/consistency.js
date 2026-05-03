'use strict';

import { esc } from '/static/shared/util.js';
import { register, SECTION_PERF } from './registry.js';

function shellHtml(ctx) {
  const baseQs = new URLSearchParams({
    theme: ctx.theme(),
    count_failed: ctx.countFailed(),
    ...ctx.filterParams(),
  });
  const svgUrl = `/api/stats/plot/consistency_scatter?format=svg&${baseQs.toString()}`;
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

async function loadData(ctx) {
  const params = new URLSearchParams({
    count_failed: ctx.countFailed(),
    ...ctx.filterParams(),
  });
  const res = await fetch(`/api/stats/plot/consistency_scatter/data?${params.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function renderSVG(host, data) {
  const points = data.points;
  const W = host.clientWidth || 720;
  const H = Math.max(360, Math.round(W * 0.5));
  const M = { top: 28, right: 16, bottom: 38, left: 52 };
  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const xs = points.map(p => p.mean_z);
  const ys = points.map(p => p.std_z);
  const pad = (lo, hi) => {
    if (lo === hi) { lo -= 1; hi += 1; }
    const span = hi - lo;
    return [lo - span * 0.08, hi + span * 0.08];
  };
  const [xMin, xMax] = pad(Math.min(...xs, 0), Math.max(...xs, 0));
  let [yMin, yMax] = pad(Math.min(...ys), Math.max(...ys));
  yMin = 0;

  const sx = v => M.left + ((v - xMin) / (xMax - xMin)) * innerW;
  const sy = v => M.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH;

  const nMax = Math.max(...points.map(p => p.n));
  const rOf = n => 4 + 6 * (nMax > 0 ? n / nMax : 0);

  const ticks = (lo, hi, count = 5) => {
    const step = (hi - lo) / (count - 1);
    return Array.from({ length: count }, (_, i) => lo + step * i);
  };
  const xTicks = ticks(xMin, xMax);
  const yTicks = ticks(yMin, yMax);
  const fmt = v => Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2);

  const stdMedian = data.std_median;

  const top = [...points].sort((a, b) => b.mean_z - a.mean_z).slice(0, 5);

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
    (xMin <= 0 && xMax >= 0)
      ? `<line class="guide" x1="${sx(0).toFixed(1)}" y1="${M.top}" x2="${sx(0).toFixed(1)}" y2="${M.top + innerH}"/>` : '',
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
    requestAnimationFrame(() => {
      const tipW = tip.offsetWidth;
      const tipH = tip.offsetHeight;
      let left = x - tipW / 2;
      let top = y - tipH - 8;
      if (left < 4) left = 4;
      if (left + tipW > host.clientWidth - 4) left = host.clientWidth - tipW - 4;
      if (top < 4) top = y + cRect.height + 8;
      tip.style.left = `${left}px`;
      tip.style.top = `${top}px`;
    });
  };
  const hideTip = () => { tip.style.opacity = '0'; };

  svg.querySelectorAll('.dot').forEach(c => {
    c.addEventListener('mouseenter', () => showTip(c));
    c.addEventListener('mouseleave', hideTip);
    c.addEventListener('focus', () => showTip(c));
    c.addEventListener('blur', hideTip);
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

register({
  name: 'consistency_scatter',
  section: SECTION_PERF,
  async mount(host, ctx) {
    host.innerHTML = shellHtml(ctx);
    const inner = host.querySelector('#iplot-consistency');
    if (!inner) return;
    let data;
    try {
      data = await loadData(ctx);
    } catch (e) {
      inner.innerHTML = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
      return;
    }
    if (!data.points || !data.points.length) {
      inner.innerHTML = '<div class="empty-msg">no score data yet</div>';
      return;
    }
    renderSVG(inner, data);
  },
});
