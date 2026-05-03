'use strict';

import { $ } from '/static/shared/util.js';
import { sockets, nav } from './state.js';
import { handleChat, handleReply, appendChatLine } from './match/chat.js';
import { handleState } from './match/render.js';
import { renderMatchList } from './landing/matchList.js';

export function sendWS(text) {
  if (sockets.ws && sockets.ws.readyState === WebSocket.OPEN) sockets.ws.send(text);
}

export function setConnected(on) {
  $('led').className = 'led' + (on ? ' on' : '');
  $('chat-led').className = 'led led-sm' + (on ? ' on' : '');
  if (!on) $('match-info').textContent = 'disconnected';
}

export function connectLanding() {
  if (sockets.landingWs) sockets.landingWs.close();
  sockets.landingWs = new WebSocket(`ws://${location.host}/ws/landing`);

  sockets.landingWs.onopen = () => {
    $('landing-led').className = 'led on';
  };

  sockets.landingWs.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'matches') renderMatchList(msg.matches || []);
    } catch (_) {}
  };

  sockets.landingWs.onclose = () => {
    $('landing-led').className = 'led';
    $('landing-status').textContent = 'disconnected';
    if (!nav.currentMatchId) setTimeout(connectLanding, 3000);
  };
}

export function connectMatch(matchId, onDone) {
  sockets.ws = new WebSocket(`ws://${location.host}/ws/${matchId}`);

  sockets.ws.onopen = () => {
    setConnected(true);
    $('chat-input').disabled = false;
    $('chat-send').disabled = false;
    $('chat-input').focus();
  };

  sockets.ws.onclose = () => {
    setConnected(false);
    $('chat-input').disabled = true;
    $('chat-send').disabled = true;
    if (nav.currentMatchId === matchId) setTimeout(() => connectMatch(matchId, onDone), 3000);
  };

  sockets.ws.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'chat') handleChat(msg);
      else if (msg.type === 'state') handleState(msg);
      else if (msg.type === 'reply') handleReply(msg);
      else if (msg.type === 'error') { appendChatLine('autoref', msg.message, 'out'); onDone(); }
      else if (msg.type === 'done') { nav.currentMatchId = null; onDone(); }
    } catch (_) {}
  };
}
