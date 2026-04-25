'use strict';

/* ── state ───────────────────────────────────────────────────── */
let appState = {
  mode: 'off', phase: null, wins: [0, 0],
  team_names: ['Team A', 'Team B'], teams: [],
  best_of: 1, maps: [], events: [],
  pending_proposal: null, ref_name: null,
  room_id: null,
};
let ws = null;
let landingWs = null;
let currentMatchId = null;

/* ── DOM shortcuts ───────────────────────────────────────────── */
const $ = id => document.getElementById(id);
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ── Theme ───────────────────────────────────────────────────── */
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'light') document.body.classList.add('light');

$('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

/* ── Page switching ──────────────────────────────────────────── */
function showLanding() {
  currentMatchId = null;
  $('landing-page').hidden = false;
  $('match-view').hidden   = true;
  if (ws) { ws.close(); ws = null; }
  connectLanding();
}

function showMatch(matchId) {
  currentMatchId = matchId;
  $('landing-page').hidden = true;
  $('match-view').hidden   = false;
  if (landingWs) { landingWs.close(); landingWs = null; }
  connectMatch(matchId);
}

/* ── Landing WebSocket ───────────────────────────────────────── */
function connectLanding() {
  if (landingWs) landingWs.close();
  landingWs = new WebSocket(`ws://${location.host}/ws/landing`);

  landingWs.onopen = () => {
    $('landing-led').className = 'led on';
  };

  landingWs.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'matches') renderMatchList(msg.matches || []);
    } catch (_) {}
  };

  landingWs.onclose = () => {
    $('landing-led').className = 'led';
    $('landing-status').textContent = 'disconnected';
    if (!currentMatchId) setTimeout(connectLanding, 3000);
  };
}

function renderMatchList(matches) {
  const list  = $('match-list');
  const noMsg = $('no-matches-msg');

  list.querySelectorAll('.match-card').forEach(c => c.remove());

  const count = matches.length;
  $('landing-status').textContent = count
    ? `connected · ${count} active match${count !== 1 ? 'es' : ''}`
    : 'connected · no active matches';

  if (!count) { noMsg.hidden = false; return; }
  noMsg.hidden = true;

  for (const data of matches) {
    const isQuals   = !!data.qualifier;
    const mode      = data.mode || 'off';
    const connected = data.connected || false;
    const title     = isQuals
      ? `Qualifiers${data.phase ? ' · ' + data.phase : ''}`
      : (data.team_names || []).join(' vs ') || 'Bracket match';
    const meta = isQuals
      ? `${data.maps_played ?? '?'}/${data.total_maps ?? '?'} maps played`
      : `BO${data.best_of || '?'}`;
    const step = data.phase || (isQuals ? 'MAP' : '');
    const refs = data.refs || (data.ref_name ? [data.ref_name] : []);

    const refsHtml = refs.length
      ? refs.map(r => `<span class="match-ref-tag mono">${esc(r)}</span>`).join('')
      : `<span class="muted mono xs">no refs connected</span>`;

    const card = document.createElement('div');
    card.className = 'match-card mono' + (isQuals ? ' quals' : '');
    card.innerHTML = `
      <div class="match-card-accent"></div>
      <div class="match-card-body">
        <div class="match-card-status">
          <span class="match-card-badge badge-${esc(mode)}">${esc(mode.toUpperCase())}</span>
          ${step ? `<span class="match-card-step">${esc(step)}</span>` : ''}
        </div>
        <div class="match-card-info">
          <div class="match-card-title">${esc(title)}</div>
          <div class="match-card-meta">${esc(meta)}</div>
          <div class="match-card-refs">${refsHtml}</div>
        </div>
        <div class="match-card-actions"></div>
      </div>
    `;

    const btn = document.createElement('button');
    btn.className = connected ? 'rejoin-btn' : 'join-btn';
    btn.textContent = connected ? '→ rejoin' : '→ join';
    btn.addEventListener('click', () => showMatch(data.id));
    card.querySelector('.match-card-actions').appendChild(btn);

    list.appendChild(card);
  }
}

/* ── Quick-start toggle opts ─────────────────────────────────── */
document.querySelectorAll('.qs-toggle').forEach(toggle => {
  toggle.addEventListener('click', e => {
    const opt = e.target.closest('.qs-opt');
    if (!opt) return;
    toggle.querySelectorAll('.qs-opt').forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
  });
});

/* ── Match WebSocket ─────────────────────────────────────────── */
function connectMatch(matchId) {
  ws = new WebSocket(`ws://${location.host}/ws/${matchId}`);

  ws.onopen = () => {
    setConnected(true);
    $('chat-input').disabled = false;
    $('chat-send').disabled  = false;
    $('chat-input').focus();
  };

  ws.onclose = () => {
    setConnected(false);
    $('chat-input').disabled = true;
    $('chat-send').disabled  = true;
    if (currentMatchId === matchId) setTimeout(() => connectMatch(matchId), 3000);
  };

  ws.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if      (msg.type === 'chat')  handleChat(msg);
      else if (msg.type === 'state') handleState(msg);
      else if (msg.type === 'reply') handleReply(msg);
    } catch (_) {}
  };
}

function sendWS(text) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(text);
}

/* ── connection status ───────────────────────────────────────── */
function setConnected(on) {
  $('led').className      = 'led' + (on ? ' on' : '');
  $('chat-led').className = 'led led-sm' + (on ? ' on' : '');
  if (!on) $('match-info').textContent = 'disconnected';
}

/* ── chat ────────────────────────────────────────────────────── */
function handleChat({ username, message, outgoing }) {
  appendChatLine(username, message, outgoing ? 'out' : 'in');
}

function handleReply({ text }) {
  appendChatLine('autoref', text, 'out');
}

function appendChatLine(username, message, cls) {
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
$('chat-send').addEventListener('click', doSend);
$('chat-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSend(); });

/* ── state updates ───────────────────────────────────────────── */
function handleState(s) {
  Object.assign(appState, s);
  renderStrip();
  renderMode();
  renderMappool();
  renderTimeline();
  renderPlayers();
  renderSettings();
  renderRefPill();
  renderAssistedBanner();
  updateMatchInfo();
  updateChatHead();
}

function updateMatchInfo() {
  const teams = (appState.team_names || []).join(' vs ');
  const roomId = appState.room_id ? `#mp_${appState.room_id}` : '';
  if (appState.qualifier) {
    const total = appState.total_maps || 0;
    const done  = appState.maps_played || 0;
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

/* ── ref pill ────────────────────────────────────────────────── */
function renderRefPill() {
  const pill = $('ref-pill');
  if (appState.ref_name) {
    pill.textContent = `ref: ${appState.ref_name}`;
    pill.hidden = false;
  } else {
    pill.hidden = true;
  }
}

/* ── assisted banner ─────────────────────────────────────────── */
function renderAssistedBanner() {
  const banner = $('assisted-banner');
  const p = appState.pending_proposal;
  if (!p || appState.mode !== 'assisted') { banner.hidden = true; return; }
  const team = (appState.team_names || [])[p.team_index] || `team ${p.team_index}`;
  const step = (p.step || 'action').toLowerCase();
  const map  = p.map || '?';
  $('assisted-desc').textContent = `${team} typed ${map} — ${step} this map?`;
  // include map name in confirm button
  $('assisted-confirm').textContent = `✓ confirm ${map} ${step}`;
  banner.hidden = false;
}

/* ── strip ───────────────────────────────────────────────────── */
function renderStrip() {
  const isQuals = !!appState.qualifier;
  $('score-panel').hidden = isQuals;
  $('quals-panel').hidden = !isQuals;
  isQuals ? renderQuals() : renderScore();
}

function renderScore() {
  const [n0, n1] = appState.team_names || ['—', '—'];
  const [w0, w1] = appState.wins || [0, 0];
  const bo       = appState.best_of || 1;
  $('team0-name').textContent = n0 || '—';
  $('team1-name').textContent = n1 || '—';
  $('score-0').textContent    = w0;
  $('score-1').textContent    = w1;
  $('score-bo').textContent   = `BO${bo}`;
  $('score-need').textContent = `first to ${Math.floor(bo / 2) + 1}`;
}

function renderQuals() {
  $('quals-remaining').textContent = appState.maps_remaining ?? '—';
  $('quals-played').textContent    = appState.maps_played    ?? '—';
  $('quals-eta').textContent       = formatEta(appState.eta_seconds);
}

function formatEta(seconds) {
  if (seconds == null || seconds === 0) return '—';
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/* ── mode ────────────────────────────────────────────────────── */
function renderMode() {
  const mode = appState.mode || 'off';
  const labels = {
    auto:     'auto mode — fully automatic',
    assisted: 'assisted — awaiting ref confirm',
    off:      'off — ref is driving',
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

/* ── mappool ─────────────────────────────────────────────────── */
const MAP_CLASS = {
  pickable: 'map-pickable', protected: 'map-protected', banned: 'map-banned',
  played: 'map-played', disallowed: 'map-disallowed',
  current: 'map-current', upcoming: 'map-upcoming',
};
function renderMappool() {
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

/* ── timeline ────────────────────────────────────────────────── */
const STEP_CLASS = { BAN:'step-ban', PICK:'step-pick', WIN:'step-win', PROTECT:'step-protect' };
function renderTimeline() {
  const list = $('timeline-list');
  const events = appState.events || [];
  if (!events.length) {
    list.innerHTML = '<span class="muted mono xs pad">no events yet</span>';
    return;
  }
  list.innerHTML = events.map(e => {
    const teamClass = e.team === appState.team_names?.[0] ? 'blue' : 'red';
    return `<div class="event-row">
      <span class="event-step ${STEP_CLASS[e.step] || ''}">${esc(e.step)}</span>
      <span class="event-team ${teamClass}">${esc(e.team)}</span>
      <span class="event-map">${esc(e.map)}</span>
    </div>`;
  }).join('');
}

/* ── players ─────────────────────────────────────────────────── */
let playersLastUpdated = null;

function renderPlayers() {
  const content = $('players-content');
  const teams = appState.teams || [];
  if (!teams.length) return;

  // show refresh row
  const refreshRow = $('players-refresh');
  refreshRow.hidden = false;
  playersLastUpdated = Date.now();
  updatePlayersAge();

  const cols = teams.map((team, i) => {
    const headClass = i === 0 ? 'blue' : 'red';
    const name = team.name || appState.team_names?.[i] || `Team ${i}`;
    const rows = (team.players || []).map(p =>
      `<div class="player-row">
        <div class="led led-sm${p.ready ? ' on' : ''}"></div>
        <span class="mono xs">${esc(p.username || p.name || '?')}</span>
        ${!p.ready ? '<span class="muted mono xs" style="margin-left:auto">not ready</span>' : ''}
      </div>`
    ).join('') || '<div class="player-row"><span class="muted mono xs">—</span></div>';
    return `<div class="team-col">
      <div class="team-head ${headClass}">${esc(name)}</div>
      ${rows}
    </div>`;
  }).join('');
  content.innerHTML = `<div class="teams-grid">${cols}</div>`;
}

function updatePlayersAge() {
  if (!playersLastUpdated) return;
  const secs = Math.round((Date.now() - playersLastUpdated) / 1000);
  $('players-refresh-label').textContent = `last updated ${secs}s ago`;
}
setInterval(updatePlayersAge, 5000);

$('players-refresh-btn').addEventListener('click', () => {
  sendWS('>refresh');
});

/* ── settings ────────────────────────────────────────────────── */
function renderSettings() {
  const s = appState;
  $('cfg-mode').textContent  = s.mode || '—';
  $('cfg-bo').textContent    = s.best_of ? `BO${s.best_of}` : '—';
  $('cfg-teams').textContent = (s.team_names || []).join(' vs ') || '—';
  const phaseRow = $('cfg-phase').closest('.setting-row');
  if (s.phase) { $('cfg-phase').textContent = s.phase; phaseRow.hidden = false; }
  else { phaseRow.hidden = true; }
}

/* ── drawer tabs ─────────────────────────────────────────────── */
document.querySelectorAll('.drawer-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const name = tab.dataset.tab;
    document.querySelectorAll('.drawer-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === name)
    );
    document.querySelectorAll('.tab-pane').forEach(p => {
      p.hidden = p.id !== `tab-${name}`;
    });
  });
});

/* ── mode buttons ────────────────────────────────────────────── */
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => sendWS(`>mode ${btn.dataset.mode}`));
});

/* ── panic / leave ───────────────────────────────────────────── */
$('panic-btn').addEventListener('click', () => sendWS('!panic'));
$('leave-btn').addEventListener('click', showLanding);

/* ── assisted banner ─────────────────────────────────────────── */
$('assisted-confirm').addEventListener('click', () => {
  const p = appState.pending_proposal;
  if (p) sendWS(`>next ${p.map}`);
});

let changeMode = false;
$('assisted-change').addEventListener('click', () => {
  changeMode = !changeMode;
  $('assisted-input').hidden      = !changeMode;
  $('assisted-input-send').hidden = !changeMode;
  if (changeMode) $('assisted-input').focus();
});
$('assisted-input-send').addEventListener('click', () => {
  const val = $('assisted-input').value.trim();
  if (val) {
    sendWS(`>next ${val}`);
    $('assisted-input').value = '';
    changeMode = false;
    $('assisted-input').hidden      = true;
    $('assisted-input-send').hidden = true;
  }
});
$('assisted-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') $('assisted-input-send').click();
});
$('assisted-dismiss').addEventListener('click', () => sendWS('>dismiss'));

/* ── boot ────────────────────────────────────────────────────── */
showLanding();
