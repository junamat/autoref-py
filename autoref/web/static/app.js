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
  history.pushState(null, '', '/');
  connectLanding();
  loadPools();
}

function showMatch(matchId) {
  currentMatchId = matchId;
  $('landing-page').hidden = true;
  $('match-view').hidden   = false;
  if (landingWs) { landingWs.close(); landingWs = null; }
  history.pushState(null, '', `/match/${matchId}`);
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
    const pending   = data.status === 'pending';
    const isQuals   = !!data.qualifier;
    const mode      = data.mode || 'off';
    const connected = data.connected || false;
    const title     = isQuals
      ? `Qualifiers${data.phase ? ' · ' + data.phase : ''}`
      : (data.team_names || []).join(' vs ') || 'Bracket match';
    const meta = pending
      ? 'pending — not started'
      : isQuals
        ? `${data.maps_played ?? '?'}/${data.total_maps ?? '?'} maps played`
        : `BO${data.best_of || '?'}`;
    const step = data.phase || '';
    const refs = data.refs || (data.ref_name ? [data.ref_name] : []);

    const refsHtml = !pending && refs.length
      ? refs.map(r => `<span class="match-ref-tag mono">${esc(r)}</span>`).join('')
      : '';

    const card = document.createElement('div');
    card.className = 'match-card mono' + (isQuals ? ' quals' : '') + (pending ? ' pending' : '');
    card.innerHTML = `
      <div class="match-card-accent"></div>
      <div class="match-card-body">
        <div class="match-card-status">
          <span class="match-card-badge badge-${esc(mode)}">${esc(mode.toUpperCase())}</span>
          ${step && !pending ? `<span class="match-card-step">${esc(step)}</span>` : ''}
          ${pending ? `<span class="match-card-step" style="color:var(--muted)">PENDING</span>` : ''}
        </div>
        <div class="match-card-info">
          <div class="match-card-title">${esc(title)}</div>
          <div class="match-card-meta">${esc(meta)}</div>
          ${refsHtml ? `<div class="match-card-refs">${refsHtml}</div>` : ''}
        </div>
        <div class="match-card-actions" style="display:flex;gap:5px"></div>
      </div>
    `;

    const actions = card.querySelector('.match-card-actions');

    if (pending) {
      const startBtn = document.createElement('button');
      startBtn.className = 'join-btn';
      startBtn.textContent = '▶ start';
      startBtn.addEventListener('click', async () => {
        startBtn.disabled = true;
        startBtn.textContent = '…';
        const res = await fetch(`/api/matches/${data.id}/start`, { method: 'POST' });
        const d = await res.json();
        if (res.ok) showMatch(d.id);
        else { alert('Error: ' + (d.error || res.status)); startBtn.disabled = false; startBtn.textContent = '▶ start'; }
      });
      actions.appendChild(startBtn);

      const delBtn = document.createElement('button');
      delBtn.className = 'ghost-btn';
      delBtn.textContent = '✕';
      delBtn.style.color = 'var(--red)';
      delBtn.style.borderColor = 'var(--red)';
      delBtn.addEventListener('click', async () => {
        await fetch(`/api/matches/${data.id}`, { method: 'DELETE' });
      });
      actions.appendChild(delBtn);
    } else {
      const btn = document.createElement('button');
      btn.className = connected ? 'rejoin-btn' : 'join-btn';
      btn.textContent = connected ? '→ rejoin' : '→ join';
      btn.addEventListener('click', () => showMatch(data.id));
      actions.appendChild(btn);
    }

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

// hide BO/bans for qualifiers
$('qs-type').addEventListener('click', () => {
  const isQuals = $('qs-type').querySelector('.active')?.dataset.val === 'qualifiers';
  $('qs-bo-field').hidden   = isQuals;
  $('qs-bans-field').hidden = isQuals;
});

/* ── Dynamic team list ───────────────────────────────────────── */
let qsTeams = [{ name: 'Blue', players: [] }, { name: 'Red', players: [] }];

function renderQsTeams() {
  const list = $('qs-team-list');
  list.innerHTML = qsTeams.map((team, i) => `
    <div class="qs-team-block" data-i="${i}">
      <div class="pool-map-row mono" style="padding:2px 0">
        <span style="flex:1;font-size:10px;font-weight:700">${esc(team.name)}</span>
        <span class="muted xs" style="margin-right:6px">${team.players.length} player${team.players.length !== 1 ? 's' : ''}</span>
        <button class="pool-del" data-i="${i}">✕</button>
      </div>
      <div style="padding:2px 0 4px 8px;display:flex;flex-direction:column;gap:2px">
        ${team.players.map((p, j) => `
          <div style="display:flex;align-items:center;gap:4px;font-size:10px">
            <span style="flex:1" class="mono">${esc(p)}</span>
            <button class="pool-del" data-team="${i}" data-player="${j}">✕</button>
          </div>`).join('')}
        <div style="display:flex;gap:4px;margin-top:2px">
          <input class="qs-input qs-player-input" data-team="${i}" placeholder="username" style="flex:1;font-size:10px">
          <button class="ghost-btn xs qs-player-add" data-team="${i}">+ player</button>
        </div>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.pool-del[data-i]').forEach(btn => {
    btn.addEventListener('click', () => { qsTeams.splice(parseInt(btn.dataset.i), 1); renderQsTeams(); });
  });
  list.querySelectorAll('.pool-del[data-player]').forEach(btn => {
    btn.addEventListener('click', () => {
      qsTeams[parseInt(btn.dataset.team)].players.splice(parseInt(btn.dataset.player), 1);
      renderQsTeams();
    });
  });
  list.querySelectorAll('.qs-player-add').forEach(btn => {
    btn.addEventListener('click', () => addPlayer(parseInt(btn.dataset.team)));
  });
  list.querySelectorAll('.qs-player-input').forEach(inp => {
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') addPlayer(parseInt(inp.dataset.team)); });
  });
}

function addPlayer(teamIdx) {
  const inp = $('qs-team-list').querySelector(`.qs-player-input[data-team="${teamIdx}"]`);
  const val = inp?.value.trim();
  if (!val) return;
  // support comma-separated
  val.split(',').map(s => s.trim()).filter(Boolean).forEach(u => {
    if (!qsTeams[teamIdx].players.includes(u)) qsTeams[teamIdx].players.push(u);
  });
  if (inp) inp.value = '';
  renderQsTeams();
}

renderQsTeams();

function addQsTeam() {
  const val = $('qs-team-input').value.trim();
  if (!val) return;
  qsTeams.push({ name: val, players: [] });
  $('qs-team-input').value = '';
  renderQsTeams();
}
$('qs-team-add').addEventListener('click', addQsTeam);
$('qs-team-input').addEventListener('keydown', e => { if (e.key === 'Enter') addQsTeam(); });

/* ── Create match (pending) ──────────────────────────────────── */
async function loadPools() {
  try {
    const pools = await fetch('/api/pools').then(r => r.json());
    const sel = $('qs-pool');
    sel.innerHTML = '<option value="">— no pool —</option>';
    for (const p of pools) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      sel.appendChild(opt);
    }
  } catch (_) {}
}

$('qs-submit').addEventListener('click', async () => {
  const type  = $('qs-type').querySelector('.active')?.dataset.val || 'bracket';
  const mode  = $('qs-mode').querySelector('.active')?.dataset.val || 'off';
  const name  = $('qs-name').value.trim() || 'autoref match';
  const bo    = parseInt($('qs-bo').value)  || 1;
  const bans  = parseInt($('qs-bans').value) || 0;
  const poolId = $('qs-pool').value || null;

  const payload = {
    type, mode, room_name: name,
    best_of: bo, bans_per_team: bans,
    teams: qsTeams,
    ...(poolId ? { pool_id: poolId } : {}),
  };

  $('qs-submit').textContent = 'creating…';
  $('qs-submit').disabled = true;
  try {
    const res = await fetch('/api/matches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) alert('Error: ' + (data.error || res.status));
    // landing WS will push the updated list automatically
  } catch (e) {
    alert('Failed: ' + e.message);
  } finally {
    $('qs-submit').textContent = 'create';
    $('qs-submit').disabled = false;
  }
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
      else if (msg.type === 'error') { appendChatLine('autoref', msg.message, 'out'); showLanding(); }
      else if (msg.type === 'done')  { currentMatchId = null; showLanding(); }
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
  renderPhase();
  renderCmds();
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
    const teamIdx = (appState.team_names || []).indexOf(e.team);
    const teamClass = teamIdx === 0 ? 'blue' : teamIdx === 1 ? 'red' : 'muted';
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
    const headClass = i === 0 ? 'blue' : i === 1 ? 'red' : 'muted';
    const name = team.name || appState.team_names?.[i] || `Team ${i}`;
  const rows = (team.players || []).map(p => {
      const absent   = p.present === false;
      const ledClass = absent ? 'led led-sm red' : (p.ready ? 'led led-sm on' : 'led led-sm');
      const label    = absent ? 'not in lobby' : (!p.ready ? 'not ready' : '');
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
setInterval(updatePlayersAge, 5000);

$('players-refresh-btn').addEventListener('click', () => {
  sendWS('>refresh');
});

/* ── phase tab ───────────────────────────────────────────────── */
const PHASE_ORDER_BRACKET = ['ROLL','ORDER','PROTECT','BAN_1','PICK','TB','DONE'];
const PHASE_COLORS = {
  ROLL:'#a78bfa', ORDER:'#a78bfa',
  PROTECT:'var(--yellow)', BAN_1:'var(--red)',
  PICK:'var(--blue)', TB:'var(--orange)', DONE:'var(--green)',
};
const PHASE_ACTION = {
  ROLL:    'Waiting for team rolls. Ref can override with >roll.',
  ORDER:   'Roll winner chooses a scheme. Use >order <n>.',
  PROTECT: 'Protect phase active — 120s timer.',
  BAN_1:   'Ban phase active — 120s timer.',
  PICK:    'Pick phase active — 120s timer.',
  TB:      'Tiebreaker triggered! TB map queued.',
  DONE:    'Match complete.',
};

function renderPhase() {
  const el = $('phase-content');
  if (!el) return;
  const s = appState;

  if (s.qualifier) {
    renderQualsPhase(el, s);
  } else {
    renderBracketPhase(el, s);
  }
}

function renderBracketPhase(el, s) {
  const phase = (s.phase || 'PICK').toUpperCase();
  const cur   = PHASE_ORDER_BRACKET.indexOf(phase);
  const nodeState = name => {
    const idx = PHASE_ORDER_BRACKET.indexOf(name);
    return idx < cur ? 'done' : idx === cur ? 'active' : 'upcoming';
  };
  const activeColor = PHASE_COLORS[phase] || 'var(--text)';

  const nodes = [
    { key:'ROLL',    label:'ROLL', sub: nodeState('ROLL')==='done' ? 'done' : null },
    { key:'ORDER',   label:'ORDER', sub: nodeState('ORDER')==='done' ? 'done' : null },
    { key:'PROTECT', label:'PROT', sub: null },
    { key:'BAN_1',   label:'BAN',  sub: null },
    { key:'PICK',    label:'PICK', sub: `${(s.wins||[0,0]).reduce((a,b)=>a+b,0)} played` },
    { key:'TB',      label:'TB',   sub: null },
    { key:'DONE',    label:'DONE', sub: null },
  ];

  const pipelineHtml = nodes.map((n, i) => {
    const ns    = nodeState(n.key);
    const color = PHASE_COLORS[n.key] || 'var(--text)';
    const borderColor = ns === 'active' ? color : ns === 'done' ? 'var(--muted)' : 'var(--border)';
    const textColor   = ns === 'active' ? color : ns === 'done' ? 'var(--muted)' : 'var(--border)';
    const bgStyle     = ns === 'active' ? `background:${color}22;box-shadow:0 0 8px ${color}55;` : '';
    const opacityStyle = ns === 'upcoming' ? 'opacity:0.4;' : '';
    const check = ns === 'done' ? `<span class="phase-node-check">✓</span>` : '';
    const sub   = n.sub ? `<span class="phase-node-sub">${esc(n.sub)}</span>` : '';
    const arrow = i < nodes.length - 1
      ? `<div class="phase-arrow${nodeState(nodes[i+1].key) !== 'upcoming' ? ' active' : ''}">
           <div class="phase-arrow-line"></div><div class="phase-arrow-head"></div>
         </div>`
      : '';
    return `
      <div class="phase-node">
        <div class="phase-node-box ${ns}" style="border-color:${borderColor};${bgStyle}${opacityStyle}">
          ${check}
          <span class="phase-node-label" style="color:${textColor}">${n.label}</span>
          ${sub}
        </div>
      </div>${arrow}`;
  }).join('');

  const [w0, w1] = s.wins || [0, 0];
  const need = s.best_of ? Math.ceil(s.best_of / 2) : '?';
  const [n0, n1] = s.team_names || ['Team A', 'Team B'];

  const schemeHtml = s.scheme ? `
    <div class="phase-scheme">
      <div class="phase-scheme-title">scheme — ${esc(s.scheme)}</div>
      ${(s.scheme_orders || []).map(([k,v]) =>
        `<div class="phase-scheme-row"><span class="phase-scheme-key">${esc(k)}</span><span>${esc(v)}</span></div>`
      ).join('')}
    </div>` : '';

  el.innerHTML = `
    <div class="phase-pipeline"><div class="phase-pipeline-inner">${pipelineHtml}</div></div>
    <div class="phase-current-box" style="border-color:${activeColor}33;border-left-color:${activeColor}">
      <div class="phase-current-label" style="color:${activeColor}">CURRENT — ${esc(phase)}</div>
      <div class="phase-current-desc">${esc(PHASE_ACTION[phase] || '—')}</div>
    </div>
    <div class="phase-stats">
      <div class="phase-stat"><div class="phase-stat-val blue">${w0}</div><div class="phase-stat-key">${esc(n0)} wins</div></div>
      <div class="phase-stat"><div class="phase-stat-val red">${w1}</div><div class="phase-stat-key">${esc(n1)} wins</div></div>
      <div class="phase-stat"><div class="phase-stat-val muted">${need}</div><div class="phase-stat-key">needed</div></div>
    </div>
    ${schemeHtml}
    <div class="phase-hint">&gt;phase — show raw cursors &nbsp;·&nbsp; &gt;undo — step back</div>
  `;
}

function renderQualsPhase(el, s) {
  const maps    = s.maps || [];
  const played  = maps.filter(m => m.state === 'played').length;
  const remaining = maps.filter(m => m.state === 'upcoming' || m.state === 'current').length;
  const eta     = formatEta(s.eta_seconds);

  const icons = { played: '✓', current: '▶', upcoming: '·' };
  const rowsHtml = maps.map(m => {
    const isActive = m.state === 'current';
    const isDone   = m.state === 'played';
    const col = isActive ? 'var(--blue)' : isDone ? 'var(--green)' : 'var(--border)';
    const nowBadge = isActive ? `<span class="quals-phase-now">NOW</span>` : '';
    const meta = isDone ? 'done' : (m.length ? formatEta(m.length) : '—');
    return `<div class="quals-phase-row${isActive ? ' current' : ''}">
      <span class="quals-phase-icon" style="color:${col}">${icons[m.state] || '·'}</span>
      <span class="quals-phase-code" style="color:${col};font-weight:${isActive?700:400}">${esc(m.code)}</span>
      <span class="quals-phase-meta">${esc(meta)}</span>
      ${nowBadge}
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="phase-stats">
      <div class="phase-stat"><div class="phase-stat-val green">${played}</div><div class="phase-stat-key">played</div></div>
      <div class="phase-stat"><div class="phase-stat-val">${remaining}</div><div class="phase-stat-key">remaining</div></div>
      <div class="phase-stat"><div class="phase-stat-val yellow">${eta}</div><div class="phase-stat-key">ETA</div></div>
    </div>
    <div style="display:flex;flex-direction:column;gap:1px">${rowsHtml}</div>
    <div class="phase-hint">auto-advancing · &gt;abort to replay · &gt;startmap to force-start</div>
  `;
}

/* ── commands tab ────────────────────────────────────────────── */
function renderCmds() {
  const el = $('cmds-content');
  if (!el) return;
  const isQuals = !!appState.qualifier;
  const cmds = (appState.commands || []).filter(c => !isQuals || !c.bracket_only);

  // group by section preserving order
  const sections = [];
  const seen = {};
  for (const c of cmds) {
    if (!seen[c.section]) { seen[c.section] = []; sections.push(c.section); }
    seen[c.section].push(c);
  }

  const scopeClass = { ref: '', anyone: 'green' };

  el.innerHTML = sections.map(sec => `
    <div class="cmd-section">
      <div class="cmd-section-title">${esc(sec)}</div>
      <div class="cmd-section-btns">
        ${seen[sec].map(c => `
          <button class="cmd-btn${c.scope === 'anyone' ? ' green' : ''}" data-cmd="${esc((c.noprefix ? '' : '>') + c.name)}">
            <span>${esc(c.label)}</span>
            ${c.desc ? `<span class="cmd-btn-desc">${esc(c.desc)}</span>` : ''}
          </button>`).join('')}
      </div>
    </div>`).join('') +
    `<div class="cmd-footer">ref prefix: &gt; &nbsp;|&nbsp; green = anyone</div>`;

  el.querySelectorAll('.cmd-btn[data-cmd]').forEach(b => {
    b.addEventListener('click', () => sendWS(b.dataset.cmd));
  });
}

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
const _pathMatch = location.pathname.match(/^\/match\/([^/]+)/);
if (_pathMatch) {
  showMatch(_pathMatch[1]);
} else {
  showLanding();
}
