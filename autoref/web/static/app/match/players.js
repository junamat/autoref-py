'use strict';

import { $, esc } from '/static/shared/util.js';
import { appState } from '../state.js';
import { sendWS } from '../ws.js';

let playersLastUpdated = null;

export function renderPlayers() {
  const content = $('players-content');
  const teams = appState.teams || [];
  if (!teams.length) return;

  const refreshRow = $('players-refresh');
  refreshRow.hidden = false;
  playersLastUpdated = Date.now();
  updatePlayersAge();

  const cols = teams.map((team, i) => {
    const headClass = i === 0 ? 'blue' : i === 1 ? 'red' : 'muted';
    const name = team.name || appState.team_names?.[i] || `Team ${i}`;
    const rows = (team.players || []).map(p => {
      const absent = p.present === false;
      const ledClass = absent ? 'led led-sm red' : (p.ready ? 'led led-sm on' : 'led led-sm');
      const label = absent ? 'not in lobby' : (!p.ready ? 'not ready' : '');
      return `<div class="player-row">
        <div class="${ledClass}"></div>
        <span class="mono xs">${esc(p.username || p.name || '?')}</span>
        ${label ? `<span class="muted mono xs" style="margin-left:auto">${label}</span>` : ''}
      </div>`;
    }).join('') || '<div class="player-row"><span class="muted mono xs">—</span></div>';
    return `<div class="team-col">
      <div class="team-head ${headClass}">${esc(name)}</div>
      ${rows}
    </div>`;
  }).join('');
  content.innerHTML = `<div class="teams-grid" style="grid-template-columns:repeat(${teams.length},1fr)">${cols}</div>`;
}

function updatePlayersAge() {
  if (!playersLastUpdated) return;
  const secs = Math.round((Date.now() - playersLastUpdated) / 1000);
  $('players-refresh-label').textContent = `last updated ${secs}s ago`;
}

export function wirePlayers() {
  setInterval(updatePlayersAge, 5000);
  $('players-refresh-btn').addEventListener('click', () => sendWS('>refresh'));
}
