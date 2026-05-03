'use strict';

import { $, esc } from '/static/shared/util.js';
import { appState } from '../state.js';

const STEP_CLASS = { BAN: 'step-ban', PICK: 'step-pick', WIN: 'step-win', PROTECT: 'step-protect' };

export function renderTimeline() {
  const list = $('timeline-list');
  const events = appState.events || [];
  if (!events.length) {
    list.innerHTML = '<span class="muted mono xs pad">no events yet</span>';
    return;
  }
  list.innerHTML = events.map(e => {
    const teamIdx = (appState.team_names || []).indexOf(e.team);
    const teamClass = teamIdx === 0 ? 'blue' : teamIdx === 1 ? 'red' : 'muted';
    return `<div class="event-row">
      <span class="event-step ${STEP_CLASS[e.step] || ''}">${esc(e.step)}</span>
      <span class="event-team ${teamClass}">${esc(e.team)}</span>
      <span class="event-map">${esc(e.map)}</span>
    </div>`;
  }).join('');
}
