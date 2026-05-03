'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';
import { formatEta } from './util.js';

export function renderStrip() {
  const isQuals = !!appState.qualifier;
  $('score-panel').hidden = isQuals;
  $('quals-panel').hidden = !isQuals;
  isQuals ? renderQuals() : renderScore();
}

function renderScore() {
  const [n0, n1] = appState.team_names || ['—', '—'];
  const [w0, w1] = appState.wins || [0, 0];
  const bo = appState.best_of || 1;
  $('team0-name').textContent = n0 || '—';
  $('team1-name').textContent = n1 || '—';
  $('score-0').textContent = w0;
  $('score-1').textContent = w1;
  $('score-bo').textContent = `BO${bo}`;
  $('score-need').textContent = `first to ${Math.floor(bo / 2) + 1}`;
}

function renderQuals() {
  $('quals-remaining').textContent = appState.maps_remaining ?? '—';
  $('quals-played').textContent = appState.maps_played ?? '—';
  $('quals-eta').textContent = formatEta(appState.eta_seconds);
}
