'use strict';

import { $ } from '/static/shared/util.js';
import { sockets, nav } from './state.js';
import { connectLanding, connectMatch } from './ws.js';
import { loadPools } from './landing/quickstart.js';

export function showLanding() {
  nav.currentMatchId = null;
  $('landing-page').hidden = false;
  $('match-view').hidden = true;
  if (sockets.ws) { sockets.ws.close(); sockets.ws = null; }
  history.pushState(null, '', '/');
  connectLanding();
  loadPools();
}

export function showMatch(matchId) {
  nav.currentMatchId = matchId;
  $('landing-page').hidden = true;
  $('match-view').hidden = false;
  if (sockets.landingWs) { sockets.landingWs.close(); sockets.landingWs = null; }
  history.pushState(null, '', `/match/${matchId}`);
  connectMatch(matchId, showLanding);
}
