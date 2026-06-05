'use strict';

import { state } from '/static/stats/state.js';
import { loadFilterOptions, loadContext, refreshPoolOptions } from '/static/stats/filters.js';
import { applyPoolDefaults } from '/static/stats/methods.js';
import { load, loadMappool } from '/static/stats/tabs/performances.js';
import { loadExtras } from '/static/stats/tabs/extras.js';
import { loadStandings } from '/static/stats/tabs/standings.js';
import { loadResults } from '/static/stats/tabs/results.js';
import { loadTeamPerformances } from '/static/stats/tabs/teamPerf.js';
import { initNav } from '/static/shared/nav.js';

initNav({ active: 'stats' }).then(() => {
  document.getElementById('theme-toggle').addEventListener('click', () => load('filter'));
});

/* ── tabs ────────────────────────────────────────────────────── */
const tabs = document.querySelectorAll('.stats-tab');
const panels = document.querySelectorAll('.tab-panel');
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    tabs.forEach(t => t.classList.toggle('active', t === tab));
    panels.forEach(p => { p.hidden = p.dataset.panel !== target; });
    if (target === 'extras' && !state.extrasLoaded) loadExtras();
    if (target === 'standings' && !state.standingsLoaded) loadStandings();
    if (target === 'results' && !state.resultsLoaded) loadResults();
    if (target === 'performances' && !state.teamPerfLoaded) loadTeamPerformances();
    if (target === 'mappool' && !state.mappoolLoaded) loadMappool('filter');
  });
});

/* ── config toggles ──────────────────────────────────────────── */
function wireToggle(groupId, paramKey) {
  document.getElementById(groupId).addEventListener('click', e => {
    const opt = e.target.closest('.cfg-opt');
    if (!opt) return;
    document.querySelectorAll(`#${groupId} .cfg-opt`).forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    load(paramKey);
  });
}
wireToggle('cfg-aggregate', 'aggregate');
wireToggle('cfg-best-only', 'best_only');

document.getElementById('stats-reload').addEventListener('click', () => load('filter'));

document.getElementById('cfg-round').addEventListener('change', () => {
  refreshPoolOptions();
  applyPoolDefaults();
  loadContext();
  load('filter');
});
document.getElementById('cfg-pool').addEventListener('change', () => {
  applyPoolDefaults();
  loadContext();
  load('filter');
});

/* ── plot zoom modal ─────────────────────────────────────────── */
const plotModal = document.getElementById('plot-modal');
const plotModalImg = document.getElementById('plot-modal-img');
const plotModalClose = plotModal.querySelector('.plot-modal-close');
const plotModalOverlay = plotModal.querySelector('.plot-modal-overlay');

document.addEventListener('click', e => {
  const img = e.target.closest('.plot-block[data-clickable] .plot-img');
  if (!img) return;
  e.preventDefault();
  const hiresSrc = img.src.replace(/format=png/, 'format=hires');
  plotModalImg.src = hiresSrc;
  plotModalImg.alt = img.alt;
  plotModal.hidden = false;
});

function closePlotModal() { plotModal.hidden = true; plotModalImg.src = ''; }
plotModalClose.addEventListener('click', closePlotModal);
plotModalOverlay.addEventListener('click', closePlotModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !plotModal.hidden) closePlotModal(); });

/* ── boot ────────────────────────────────────────────────────── */
loadFilterOptions().then(() => { applyPoolDefaults(); loadContext(); load('filter'); });
