'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';
import { sendWS } from '../ws.js';

export function renderAssistedBanner() {
  const banner = $('assisted-banner');
  const p = appState.pending_proposal;
  if (!p || appState.mode !== 'assisted') { banner.hidden = true; return; }
  const team = (appState.team_names || [])[p.team_index] || `team ${p.team_index}`;
  const step = (p.step || 'action').toLowerCase();
  const map = p.map || '?';
  $('assisted-desc').textContent = `${team} typed ${map} — ${step} this map?`;
  $('assisted-confirm').textContent = `✓ confirm ${map} ${step}`;
  banner.hidden = false;
}

export function wireAssisted() {
  $('assisted-confirm').addEventListener('click', () => {
    const p = appState.pending_proposal;
    if (p) sendWS(`>next ${p.map}`);
  });

  let changeMode = false;
  $('assisted-change').addEventListener('click', () => {
    changeMode = !changeMode;
    $('assisted-input').hidden = !changeMode;
    $('assisted-input-send').hidden = !changeMode;
    if (changeMode) $('assisted-input').focus();
  });
  $('assisted-input-send').addEventListener('click', () => {
    const val = $('assisted-input').value.trim();
    if (val) {
      sendWS(`>next ${val}`);
      $('assisted-input').value = '';
      changeMode = false;
      $('assisted-input').hidden = true;
      $('assisted-input-send').hidden = true;
    }
  });
  $('assisted-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') $('assisted-input-send').click();
  });
  $('assisted-dismiss').addEventListener('click', () => sendWS('>dismiss'));
}
