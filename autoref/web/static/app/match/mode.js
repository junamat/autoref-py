'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';

export function renderMode() {
  const mode = appState.mode || 'off';
  const labels = {
    auto: 'auto mode — fully automatic',
    assisted: 'assisted — awaiting ref confirm',
    off: 'off — ref is driving',
  };
  document.querySelectorAll('.mode-btn').forEach(btn => {
    const m = btn.dataset.mode;
    btn.className = 'mode-btn' + (m === mode ? ` mode-${m}-active` : '');
  });
  $('mode-label').textContent = labels[mode] || mode;
  $('mode-led').className = 'led led-sm' + (mode !== 'off' ? ' on' : '');
  $('mode-label').className = 'mono xs ' + (
    mode === 'auto' ? 'green' : mode === 'assisted' ? 'yellow' : 'muted'
  );
}
