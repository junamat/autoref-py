'use strict';

import { initNav } from '/static/shared/nav.js';

initNav();

const urlInput = document.getElementById('mi-url');
const previewBtn = document.getElementById('mi-preview');
const previewSection = document.getElementById('mi-preview-section');
const matchNameEl = document.getElementById('mi-match-name');
const matchMetaEl = document.getElementById('mi-match-meta');
const playerListEl = document.getElementById('mi-player-list');
const poolInput = document.getElementById('mi-pool');
const roundInput = document.getElementById('mi-round');
const cancelBtn = document.getElementById('mi-cancel');
const importBtn = document.getElementById('mi-import');
const statusEl = document.getElementById('mi-status');

let currentPreview = null;

function showStatus(message, type = 'loading') {
  statusEl.textContent = message;
  statusEl.className = `mi-status ${type}`;
  statusEl.classList.remove('mi-hidden');
}

function hideStatus() {
  statusEl.classList.add('mi-hidden');
}

function renderPlayers(players) {
  playerListEl.innerHTML = '';
  for (const player of players) {
    const div = document.createElement('div');
    div.className = 'mi-player' + (player.enabled ? '' : ' disabled');
    div.innerHTML = `
      <input type="checkbox" class="mi-player-check" ${player.enabled ? 'checked' : ''}>
      <div class="mi-player-name"><input type="text" value="${escapeHtml(player.username)}"></div>
      <div class="mi-player-team">team ${player.team_index}</div>
    `;

    const check = div.querySelector('.mi-player-check');
    const nameInput = div.querySelector('.mi-player-name input');

    check.addEventListener('change', () => {
      player.enabled = check.checked;
      div.className = 'mi-player' + (player.enabled ? '' : ' disabled');
    });

    nameInput.addEventListener('input', () => {
      player.username = nameInput.value;
    });

    playerListEl.appendChild(div);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function fetchPreview() {
  const url = urlInput.value.trim();
  if (!url) {
    showStatus('please enter an mp link', 'error');
    return;
  }

  previewBtn.disabled = true;
  showStatus('fetching match data...', 'loading');

  try {
    const res = await fetch('/api/mp/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();

    if (!res.ok) {
      showStatus(`error: ${data.error || 'unknown error'}`, 'error');
      return;
    }

    currentPreview = data;
    matchNameEl.textContent = data.name || `Match ${data.match_id}`;
    matchMetaEl.textContent = `${data.num_games} games · ${data.players.length} players · ${data.match_type}`;
    renderPlayers(data.players);
    previewSection.classList.remove('mi-hidden');
    hideStatus();
  } catch (err) {
    showStatus(`failed to fetch: ${err.message}`, 'error');
  } finally {
    previewBtn.disabled = false;
  }
}

async function doImport() {
  if (!currentPreview) return;

  const enabledPlayers = currentPreview.players.filter(p => p.enabled);
  if (enabledPlayers.length === 0) {
    showStatus('at least one player must be selected', 'error');
    return;
  }

  importBtn.disabled = true;
  showStatus('importing match...', 'loading');

  try {
    const res = await fetch('/api/mp/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: urlInput.value.trim(),
        players: currentPreview.players,
        pool_id: poolInput.value.trim() || null,
        round_name: roundInput.value.trim() || null,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      showStatus(`import failed: ${data.error || 'unknown error'}`, 'error');
      return;
    }

    showStatus(`imported ${data.num_games} games with ${data.num_players} players (match id: ${data.match_id})`, 'success');
    previewSection.classList.add('mi-hidden');
    urlInput.value = '';
    poolInput.value = '';
    roundInput.value = '';
    currentPreview = null;
  } catch (err) {
    showStatus(`import failed: ${err.message}`, 'error');
  } finally {
    importBtn.disabled = false;
  }
}

function cancelPreview() {
  previewSection.classList.add('mi-hidden');
  currentPreview = null;
  hideStatus();
}

previewBtn.addEventListener('click', fetchPreview);
importBtn.addEventListener('click', doImport);
cancelBtn.addEventListener('click', cancelPreview);

urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    fetchPreview();
  }
});

// ── Imported matches list ─────────────────────────────────────────────────────

const importedListEl = document.getElementById('mi-imported-list');

async function loadImportedMatches() {
  try {
    const res = await fetch('/api/stats/filters');
    if (!res.ok) {
      importedListEl.innerHTML = '<div class="mi-status error">failed to load matches</div>';
      return;
    }

    // Get match history from stats endpoint
    const histRes = await fetch('/api/stats/matches');
    if (!histRes.ok) {
      importedListEl.innerHTML = '<div class="mi-status error">failed to load matches</div>';
      return;
    }

    const matches = await histRes.json();
    if (!matches.matches || matches.matches.length === 0) {
      importedListEl.innerHTML = '<div class="mi-status loading">no imported matches</div>';
      return;
    }

    importedListEl.innerHTML = '';
    for (const match of matches.matches) {
      const div = document.createElement('div');
      div.className = 'mi-player';
      div.innerHTML = `
        <div class="mi-player-name">
          <span style="font-weight:700">match ${match.match_id}</span>
          <span style="color:var(--muted);font-size:10px;margin-left:8px">${match.pool_id || ''} ${match.round_name || ''}</span>
        </div>
        <button class="mi-refresh-btn" data-match-id="${match.match_id}">refresh</button>
        <button class="mi-btn danger" style="padding:4px 10px;font-size:10px">delete</button>
      `;

      const refreshBtn = div.querySelector('.mi-refresh-btn');
      refreshBtn.addEventListener('click', () => openRefreshModal(match.match_id));

      const deleteBtn = div.querySelector('.mi-btn.danger');
      deleteBtn.addEventListener('click', async () => {
        if (!confirm(`Delete match ${match.match_id}? This cannot be undone.`)) return;

        deleteBtn.disabled = true;
        try {
          const res = await fetch(`/api/mp/imported/${match.match_id}`, { method: 'DELETE' });
          if (!res.ok) {
            const data = await res.json();
            alert(`Failed to delete: ${data.error || 'unknown error'}`);
            deleteBtn.disabled = false;
            return;
          }
          div.remove();
          if (importedListEl.children.length === 0) {
            importedListEl.innerHTML = '<div class="mi-status loading">no imported matches</div>';
          }
        } catch (err) {
          alert(`Failed to delete: ${err.message}`);
          deleteBtn.disabled = false;
        }
      });

      importedListEl.appendChild(div);
    }
  } catch (err) {
    importedListEl.innerHTML = `<div class="mi-status error">failed to load: ${err.message}</div>`;
  }
}

// Load imported matches on page load
loadImportedMatches();

// Refresh after successful import
const originalDoImport = doImport;
doImport = async function() {
  await originalDoImport();
  if (!statusEl.classList.contains('mi-hidden') && statusEl.classList.contains('success')) {
    loadImportedMatches();
  }
};
