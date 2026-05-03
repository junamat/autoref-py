'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';
import { renderStrip } from './strip.js';
import { renderMode } from './mode.js';
import { renderMappool } from './mappool.js';
import { renderTimeline } from './timeline.js';
import { renderPlayers } from './players.js';
import { renderPhase } from './phase.js';
import { renderCmds } from './cmds.js';
import { renderSettings } from './settings.js';
import { renderAssistedBanner } from './assisted.js';

function renderRefPill() {
  const pill = $('ref-pill');
  if (appState.ref_name) {
    pill.textContent = `ref: ${appState.ref_name}`;
    pill.hidden = false;
  } else {
    pill.hidden = true;
  }
}

function updateMatchInfo() {
  const teams = (appState.team_names || []).join(' vs ');
  const roomId = appState.room_id ? `#mp_${appState.room_id}` : '';
  if (appState.qualifier) {
    const total = appState.total_maps || 0;
    const done = appState.maps_played || 0;
    const parts = [teams, `${done}/${total} maps`, roomId].filter(Boolean);
    $('match-info').textContent = parts.join(' · ') || 'connected';
  } else {
    const bo = appState.best_of ? `BO${appState.best_of}` : '';
    const phase = appState.phase || '';
    const parts = [phase, teams, bo, roomId].filter(Boolean);
    $('match-info').textContent = parts.join(' · ') || 'connected';
  }
}

function updateChatHead() {
  const roomId = appState.room_id ? ` — #mp_${appState.room_id}` : '';
  $('chat-head-label').textContent = `lobby chat${roomId}`;
}

export function handleState(s) {
  Object.assign(appState, s);
  renderStrip();
  renderMode();
  renderMappool();
  renderTimeline();
  renderPlayers();
  renderSettings();
  renderPhase();
  renderCmds();
  renderRefPill();
  renderAssistedBanner();
  updateMatchInfo();
  updateChatHead();
}
