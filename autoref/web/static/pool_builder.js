'use strict';

import { $ } from '/static/shared/util.js';
import { rerender } from './pool_builder/render/index.js';
import { addTopLevelPool, addTopLevelMap } from './pool_builder/ops.js';
import { wireImport } from './pool_builder/modals/import.js';
import { wireExport } from './pool_builder/modals/export.js';
import { wireLoad } from './pool_builder/modals/load.js';
import { wireCompose } from './pool_builder/modals/compose.js';
import { wireSeparate } from './pool_builder/modals/separate.js';
import { wireStatsDefaults } from './pool_builder/modals/statsDefaults.js';
import { bootFromQuery, wireSave } from './pool_builder/save.js';

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
$('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

/* ── toolbar ─────────────────────────────────────────────────── */
$('pb-add-pool-btn').addEventListener('click', addTopLevelPool);
$('pb-add-map-btn').addEventListener('click', addTopLevelMap);

/* ── init ────────────────────────────────────────────────────── */
wireImport();
wireExport();
wireLoad();
wireCompose();
wireSeparate();
wireStatsDefaults();
wireSave();

rerender();
bootFromQuery();
