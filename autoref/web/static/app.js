'use strict';

/* ── state ───────────────────────────────────────────────────── */
let appState = {
  mode: 'off',
  phase: null,
  wins: [0, 0],
  team_names: ['Team A', 'Team B'],
  teams: [],
  best_of: 1,
  maps: [],
  events: [],
};
let ws = null;

/* ── DOM shortcuts ───────────────────────────────────────────── */
const $ = id => document.getElementById(id);
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ── WebSocket ───────────────────────────────────────────────── */
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    setConnected(true);
    $('chat-input').disabled = false;
    $('chat-send').disabled = false;
    $('chat-input').focus();
  };

  ws.onclose = () => {
    setConnected(false);
    $('chat-input').disabled = true;
    $('chat-send').disabled = true;
    setTimeout(connect, 3000);
  };

  ws.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'chat') handleChat(msg);
      else if (msg.type === 'state') handleState(msg);
    } catch (_) {}
  };
}

function sendWS(text) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(text);
}

/* ── connection status ───────────────────────────────────────── */
function setConnected(on) {
  $('led').className       = 'led' + (on ? ' on' : '');
  $('chat-led').className  = 'led led-sm' + (on ? ' on' : '');
  if (!on) $('match-info').textContent = 'disconnected';
}

/* ── chat ────────────────────────────────────────────────────── */
function handleChat({ username, message, outgoing }) {
  const log = $('chat-log');
  const div = document.createElement('div');
  div.className = 'msg ' + (outgoing ? 'out' : 'in');
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
  updateMatchInfo();
}

function updateMatchInfo() {
  const teams = (appState.team_names || []).join(' vs ');
  if (appState.qualifier) {
    const total = appState.total_maps || 0;
    const done  = appState.maps_played || 0;
    $('match-info').textContent = [teams, `${done}/${total} maps`].filter(Boolean).join(' · ') || 'connected';
  } else {
    const bo = appState.best_of ? `BO${appState.best_of}` : '';
    $('match-info').textContent = [teams, bo].filter(Boolean).join(' · ') || 'connected';
  }
}

/* strip: bracket score vs qualifiers progress */
function renderStrip() {
  const isQuals = !!appState.qualifier;
  $('score-panel').hidden  = isQuals;
  $('quals-panel').hidden  = !isQuals;

  if (isQuals) {
    renderQuals();
  } else {
    renderScore();
  }
}

function renderScore() {
  const [n0, n1] = appState.team_names || ['—', '—'];
  const [w0, w1] = appState.wins || [0, 0];
  const bo       = appState.best_of || 1;
  const needed   = Math.floor(bo / 2) + 1;

  $('team0-name').textContent = n0 || '—';
  $('team1-name').textContent = n1 || '—';
  $('score-0').textContent    = w0;
  $('score-1').textContent    = w1;
  $('score-bo').textContent   = `BO${bo}`;
  $('score-need').textContent = `first to ${needed}`;
}

function renderQuals() {
  $('quals-remaining').textContent = appState.maps_remaining ?? '—';
  $('quals-played').textContent    = appState.maps_played    ?? '—';
  $('quals-eta').textContent       = formatEta(appState.eta_seconds);
}

function formatEta(seconds) {
  if (seconds == null || seconds === 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/* mode */
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

/* mappool */
const MAP_CLASS = {
  pickable:   'map-pickable',
  protected:  'map-protected',
  banned:     'map-banned',
  played:     'map-played',
  disallowed: 'map-disallowed',
  current:    'map-current',
  upcoming:   'map-upcoming',
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

/* timeline */
const STEP_CLASS = {
  BAN: 'step-ban', PICK: 'step-pick', WIN: 'step-win', PROTECT: 'step-protect',
};
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

/* players */
function renderPlayers() {
  const content = $('players-content');
  const teams = appState.teams || [];
  if (!teams.length) return;

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

/* settings */
function renderSettings() {
  const s = appState;
  $('cfg-mode').textContent  = s.mode || '—';
  $('cfg-bo').textContent    = s.best_of ? `BO${s.best_of}` : '—';
  $('cfg-teams').textContent = (s.team_names || []).join(' vs ') || '—';
  const phaseRow = $('cfg-phase').closest('.setting-row');
  if (s.phase) {
    $('cfg-phase').textContent = s.phase;
    phaseRow.hidden = false;
  } else {
    phaseRow.hidden = true;
  }
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

/* ── panic ───────────────────────────────────────────────────── */
$('panic-btn').addEventListener('click', () => sendWS('!panic'));

/* ── boot ────────────────────────────────────────────────────── */
connect();
