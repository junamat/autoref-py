'use strict';

import { state } from '/static/stats/state.js';
import { loadFilterOptions, refreshPoolOptions } from '/static/stats/filters.js';
import { applyPoolDefaults } from '/static/stats/methods.js';
import { load } from '/static/stats/tabs/performances.js';
import { loadExtras } from '/static/stats/tabs/extras.js';
import { loadStandings } from '/static/stats/tabs/standings.js';
import { loadResults } from '/static/stats/tabs/results.js';
import { loadTeamPerformances } from '/static/stats/tabs/teamPerf.js';

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
  load();
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
  });
});

/* ── config toggles ──────────────────────────────────────────── */
function wireToggle(groupId) {
  document.getElementById(groupId).addEventListener('click', e => {
    const opt = e.target.closest('.cfg-opt');
    if (!opt) return;
    document.querySelectorAll(`#${groupId} .cfg-opt`).forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    load();
  });
}
wireToggle('cfg-failed');
wireToggle('cfg-aggregate');

document.getElementById('stats-reload').addEventListener('click', load);

document.getElementById('cfg-round').addEventListener('change', () => {
  refreshPoolOptions();
  applyPoolDefaults();
  load();
});
document.getElementById('cfg-pool').addEventListener('change', () => {
  applyPoolDefaults();
  load();
});

/* ── boot ────────────────────────────────────────────────────── */
loadFilterOptions().then(() => { applyPoolDefaults(); load(); });
