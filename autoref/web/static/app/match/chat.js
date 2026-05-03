'use strict';

import { $, esc } from '/static/shared/util.js';
import { sendWS } from '../ws.js';

export function handleChat({ username, message, outgoing }) {
  appendChatLine(username, message, outgoing ? 'out' : 'in');
}

export function handleReply({ text }) {
  appendChatLine('autoref', text, 'out');
}

export function appendChatLine(username, message, cls) {
  const log = $('chat-log');
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.innerHTML =
    `<span class="user">${esc(username)}</span>` +
    `<span class="sep">»</span>` +
    `<span class="text">${esc(message)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function doSend() {
  const text = $('chat-input').value.trim();
  if (text) { sendWS(text); $('chat-input').value = ''; }
}

export function wireChat() {
  $('chat-send').addEventListener('click', doSend);
  $('chat-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });
}
