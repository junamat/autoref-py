'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';

export function renderSettings() {
  const s = appState;
  $('cfg-mode').textContent = s.mode || '—';
  $('cfg-bo').textContent = s.best_of ? `BO${s.best_of}` : '—';
  $('cfg-teams').textContent = (s.team_names || []).join(' vs ') || '—';
  const phaseRow = $('cfg-phase').closest('.setting-row');
  if (s.phase) { $('cfg-phase').textContent = s.phase; phaseRow.hidden = false; }
  else { phaseRow.hidden = true; }
}
