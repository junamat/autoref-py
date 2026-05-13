'use strict';

import { $, esc } from '/static/shared/util.js';

let qsTeams = [{ name: 'Blue', players: [] }, { name: 'Red', players: [] }];
let _defaultVs = 1;
let _defaultTs = 1;
let _defaultVsTeam = 2;

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
  val.split(',').map(s => s.trim()).filter(Boolean).forEach(u => {
    if (!qsTeams[teamIdx].players.includes(u)) qsTeams[teamIdx].players.push(u);
  });
  if (inp) inp.value = '';
  renderQsTeams();
}

function addQsTeam() {
  const val = $('qs-team-input').value.trim();
  if (!val) return;
  qsTeams.push({ name: val, players: [] });
  $('qs-team-input').value = '';
  renderQsTeams();
}

export async function loadSettings() {
  try {
    const s = await fetch('/api/settings').then(r => r.ok ? r.json() : {});
    _defaultVs = s.default_vs ?? 1;
    _defaultTs = s.default_ts ?? 1;
    _defaultVsTeam = s.default_vs_team ?? 2;
    _applyPlayerMode();
  } catch (_) {}
}

function _applyPlayerMode() {
  const playerMode = _defaultTs === 1;
  const isQuals = $('qs-type')?.querySelector('.active')?.dataset.val === 'qualifiers';
  const teamSection = $('qs-team-list')?.closest('.qs-field');
  const teamAddRow = $('qs-team-input')?.parentElement;

  // Non-player-mode OR quals: use team builder (dynamic, add as needed)
  if (!playerMode || isQuals) {
    if (teamSection) teamSection.hidden = false;
    if (teamAddRow) teamAddRow.hidden = false;
    $('qs-player-inputs')?.remove();
    return;
  }

  // Bracket + player mode: one fixed input per team slot
  if (teamSection) teamSection.hidden = true;
  if (teamAddRow) teamAddRow.hidden = true;

  let playerInputs = $('qs-player-inputs');
  if (!playerInputs) {
    playerInputs = document.createElement('div');
    playerInputs.id = 'qs-player-inputs';
    playerInputs.className = 'qs-field';
    const label = document.createElement('div');
    label.className = 'qs-label';
    label.textContent = 'players';
    playerInputs.appendChild(label);
    $('quickstart-form').insertBefore(playerInputs, teamSection ?? $('qs-team-list')?.closest('.qs-field') ?? null);
  }

  const sideCount = _defaultVsTeam;
  while (playerInputs.querySelectorAll('input').length < sideCount) {
    const idx = playerInputs.querySelectorAll('input').length;
    const inp = document.createElement('input');
    inp.className = 'qs-input';
    inp.id = `qs-player-${idx}`;
    inp.placeholder = `player ${idx + 1} username`;
    inp.style.marginTop = '3px';
    playerInputs.appendChild(inp);
  }
  playerInputs.querySelectorAll('input').forEach((inp, i) => {
    if (i >= sideCount) inp.remove();
  });
}

function _buildTeamsFromPlayerInputs() {
  const inputs = document.querySelectorAll('#qs-player-inputs input');
  return [...inputs].map(inp => {
    const name = inp.value.trim() || inp.placeholder;
    return { name, players: [name] };
  });
}

export async function loadPools() {
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

let _templates = [];

export async function loadTemplates() {
  try {
    _templates = await fetch('/api/match-templates').then(r => r.ok ? r.json() : []);
    const sel = $('qs-template');
    if (!sel) return;
    sel.innerHTML = '<option value="">— no template —</option>';
    for (const t of _templates) {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.name;
      sel.appendChild(opt);
    }
  } catch (_) {}
}

function _applyTemplate(payload) {
  if (!payload) return;

  if (payload.type) {
    $('qs-type').querySelectorAll('.qs-opt').forEach(o => {
      o.classList.toggle('active', o.dataset.val === payload.type);
    });
    const isQuals = payload.type === 'qualifiers';
    $('qs-bo-field').hidden = isQuals;
    $('qs-bans-field').hidden = isQuals;
  }
  if (payload.mode) {
    $('qs-mode').querySelectorAll('.qs-opt').forEach(o => {
      o.classList.toggle('active', o.dataset.val === payload.mode);
    });
  }
  if (payload.room_name) $('qs-name').value = payload.room_name;
  if (payload.best_of)   $('qs-bo').value   = payload.best_of;
  if (payload.bans_per_team !== undefined) $('qs-bans').value = payload.bans_per_team;
  if (payload.pool_id)   $('qs-pool').value  = payload.pool_id;
  if (payload.round_name) $('qs-round').value = payload.round_name;
  if (Array.isArray(payload.teams)) {
    qsTeams = payload.teams.map(t => ({
      name: t.name || '',
      players: Array.isArray(t.players) ? t.players : [],
    }));
    renderQsTeams();
  }
}

export function wireQuickstart({ onSuccess } = {}) {
  document.querySelectorAll('.qs-toggle').forEach(toggle => {
    toggle.addEventListener('click', e => {
      const opt = e.target.closest('.qs-opt');
      if (!opt) return;
      toggle.querySelectorAll('.qs-opt').forEach(o => o.classList.remove('active'));
      opt.classList.add('active');
    });
  });

  $('qs-type').addEventListener('click', () => {
    const isQuals = $('qs-type').querySelector('.active')?.dataset.val === 'qualifiers';
    $('qs-bo-field').hidden = isQuals;
    $('qs-bans-field').hidden = isQuals;
    _applyPlayerMode();
  });

  renderQsTeams();

  $('qs-team-add').addEventListener('click', addQsTeam);
  $('qs-team-input').addEventListener('keydown', e => { if (e.key === 'Enter') addQsTeam(); });

  $('qs-template-load')?.addEventListener('click', () => {
    const id = parseInt($('qs-template').value);
    const tmpl = _templates.find(t => t.id === id);
    if (tmpl) _applyTemplate(tmpl.payload);
  });

  $('qs-template-save')?.addEventListener('click', async () => {
    const name = prompt('Template name:')?.trim();
    if (!name) return;
    const type = $('qs-type').querySelector('.active')?.dataset.val || 'bracket';
    const mode = $('qs-mode').querySelector('.active')?.dataset.val || 'off';
    const payload = {
      type, mode,
      room_name: $('qs-name').value.trim() || 'autoref match',
      best_of: parseInt($('qs-bo').value) || 1,
      bans_per_team: parseInt($('qs-bans').value) || 0,
      teams: qsTeams,
      ...($('qs-pool').value ? { pool_id: $('qs-pool').value } : {}),
      ...($('qs-round')?.value.trim() ? { round_name: $('qs-round').value.trim() } : {}),
    };
    try {
      const res = await fetch('/api/match-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, payload }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert('Error: ' + (data.detail || res.status));
        return;
      }
      await loadTemplates();
      if (data.id) $('qs-template').value = data.id;
    } catch (e) {
      alert('Failed: ' + e.message);
    }
  });

  $('qs-submit').addEventListener('click', async () => {
    const type = $('qs-type').querySelector('.active')?.dataset.val || 'bracket';
    const mode = $('qs-mode').querySelector('.active')?.dataset.val || 'off';
    const name = $('qs-name').value.trim() || 'autoref match';
    const bo = parseInt($('qs-bo').value) || 1;
    const bans = parseInt($('qs-bans').value) || 0;
    const poolId = $('qs-pool').value || null;
    const round = $('qs-round')?.value.trim() || null;
    const scheduledAt = $('qs-scheduled-at')?.value || null;
    const isQuals = type === 'qualifiers';
    const playerMode = _defaultTs === 1;
    const teams = (playerMode && !isQuals) ? _buildTeamsFromPlayerInputs() : qsTeams;

    const payload = {
      type, mode, room_name: name,
      best_of: bo, bans_per_team: bans,
      teams,
      ...(playerMode ? { vs: _defaultVs, ts: _defaultTs } : {}),
      ...(poolId ? { pool_id: poolId } : {}),
      ...(round ? { round_name: round } : {}),
      ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
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
      if (!res.ok) { alert('Error: ' + (data.error || res.status)); return; }
      if (data.status === 'pending') {
        $('qs-submit').textContent = 'starting…';
        const startRes = await fetch(`/api/matches/${data.id}/start`, { method: 'POST' });
        const startData = await startRes.json().catch(() => ({}));
        if (!startRes.ok) { alert('Error starting match: ' + (startData.error || startRes.status)); return; }
        if (onSuccess) onSuccess(startData);
      } else {
        if (onSuccess) onSuccess(data);
      }
    } catch (e) {
      alert('Failed: ' + e.message);
    } finally {
      $('qs-submit').textContent = 'create';
      $('qs-submit').disabled = false;
    }
  });
}
