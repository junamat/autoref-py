'use strict';

import { $ } from '/static/shared/util.js';
import { appState } from '../state.js';
import { formatEta } from './util.js';

const MAP_CLASS = {
  pickable: 'map-pickable', protected: 'map-protected', banned: 'map-banned',
  played: 'map-played', disallowed: 'map-disallowed',
  current: 'map-current', upcoming: 'map-upcoming',
};

export function renderMappool() {
  const grid = $('mappool-grid');
  grid.innerHTML = '';
  for (const m of appState.maps || []) {
    const tile = document.createElement('div');
    tile.className = 'map-tile ' + (MAP_CLASS[m.state] || 'map-pickable');
    if (m.tb) tile.classList.add('map-tb');
    tile.textContent = m.code;
    if (m.length) {
      const sub = document.createElement('div');
      sub.className = 'map-len';
      sub.textContent = formatEta(m.length);
      tile.appendChild(sub);
    }
    grid.appendChild(tile);
  }
}
