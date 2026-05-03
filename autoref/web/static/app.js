'use strict';

import { $ } from '/static/shared/util.js';
import { showLanding, showMatch } from '/static/app/router.js';
import { sendWS } from '/static/app/ws.js';
import { wireQuickstart } from '/static/app/landing/quickstart.js';
import { wireChat } from '/static/app/match/chat.js';
import { wirePlayers } from '/static/app/match/players.js';
import { wireAssisted } from '/static/app/match/assisted.js';

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
$('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

/* ── drawer tabs ─────────────────────────────────────────────── */
document.querySelectorAll('.drawer-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const name = tab.dataset.tab;
    document.querySelectorAll('.drawer-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name)
    );
    document.querySelectorAll('.tab-pane').forEach(p => {
      p.hidden = p.id !== `tab-${name}`;
    });
  });
});

/* ── mode buttons ────────────────────────────────────────────── */
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => sendWS(`>mode ${btn.dataset.mode}`));
});

/* ── panic / leave ───────────────────────────────────────────── */
$('panic-btn').addEventListener('click', () => sendWS('!panic'));
$('leave-btn').addEventListener('click', showLanding);

/* ── module wiring ───────────────────────────────────────────── */
wireQuickstart();
wireChat();
wirePlayers();
wireAssisted();

/* ── boot ────────────────────────────────────────────────────── */
const _pathMatch = location.pathname.match(/^\/match\/([^/]+)/);
if (_pathMatch) showMatch(_pathMatch[1]);
else showLanding();
