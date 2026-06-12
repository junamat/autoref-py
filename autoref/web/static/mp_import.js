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

async function openRefreshModal(matchId) {
  const btn = document.querySelector(`.mi-refresh-btn[data-match-id="${matchId}"]`);
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`/api/mp/refresh/${matchId}`);
    const data = await res.json();

    if (!res.ok) {
      alert(`Refresh failed: ${data.error || 'unknown error'}`);
      if (btn) btn.disabled = false;
      return;
    }

    const hasNewScores = data.new_games && data.new_games.length > 0;
    const hasNameChanges = data.name_changes && data.name_changes.length > 0;

    if (!hasNewScores && !hasNameChanges) {
      alert('No new scores or name changes found.');
      if (btn) btn.disabled = false;
      return;
    }

    let html = `
      <div class="mi-modal-overlay" id="mi-modal-overlay">
        <div class="mi-modal">
          <div class="mi-modal-header">
            <div class="mi-modal-title">refresh match ${matchId}</div>
            <button class="mi-modal-close" id="mi-modal-close">×</button>
          </div>
    `;

    if (hasNameChanges) {
      html += `
        <div class="mi-section-title">name changes (${data.name_changes.length})</div>
        <div class="mi-diff-game">
      `;
      for (const change of data.name_changes) {
        html += `
          <div class="mi-diff-score">
            <div class="mi-diff-name">user ${change.user_id}</div>
            <div style="text-decoration:line-through;color:var(--muted)">${escapeHtml(change.old_name)}</div>
            <div>→</div>
            <div class="mi-diff-name mi-diff-new">${escapeHtml(change.new_name)}</div>
          </div>
        `;
      }
      html += `</div>`;
    }

    if (hasNewScores) {
      html += `<div class="mi-section-title">new scores (${data.new_games.reduce((sum, g) => sum + g.scores.length, 0)})</div>`;
      for (const game of data.new_games) {
        html += `
          <div class="mi-diff-game">
            <div class="mi-diff-game-header">turn ${game.turn} — beatmap ${game.beatmap_id}</div>
        `;
        for (const score of game.scores) {
          html += `
            <div class="mi-diff-score">
              <div class="mi-diff-name">${escapeHtml(score.username || `user ${score.user_id}`)}</div>
              <div class="mi-diff-value mi-diff-new">${score.score.toLocaleString()}</div>
            </div>
          `;
        }
        html += `</div>`;
      }
    }

    html += `
          <div style="margin-top:1rem;display:flex;gap:8px;justify-content:flex-end">
            <button class="mi-btn secondary" id="mi-modal-cancel">cancel</button>
            <button class="mi-btn" id="mi-modal-apply">apply changes</button>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', html);

    const overlay = document.getElementById('mi-modal-overlay');
    const closeBtn = document.getElementById('mi-modal-close');
    const cancelBtn = document.getElementById('mi-modal-cancel');
    const applyBtn = document.getElementById('mi-modal-apply');

    const closeModal = () => overlay.remove();
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });

    applyBtn.addEventListener('click', async () => {
      applyBtn.disabled = true;
      try {
        const res = await fetch(`/api/mp/refresh/${matchId}/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            new_games: data.new_games || [],
            name_changes: data.name_changes || [],
          }),
        });

        const result = await res.json();
        if (!res.ok) {
          alert(`Failed to apply: ${result.error || 'unknown error'}`);
          applyBtn.disabled = false;
          return;
        }

        let msg = [];
        if (result.new_scores > 0) msg.push(`${result.new_scores} new scores`);
        if (result.name_changes > 0) msg.push(`${result.name_changes} name updates`);
        alert(`Applied: ${msg.join(', ')}`);
        closeModal();
        loadImportedMatches();
      } catch (err) {
        alert(`Failed to apply: ${err.message}`);
        applyBtn.disabled = false;
      }
    });

  } catch (err) {
    alert(`Refresh failed: ${err.message}`);
    if (btn) btn.disabled = false;
  }
}

// Refresh after successful import
const originalDoImport = doImport;
doImport = async function() {
  await originalDoImport();
  if (!statusEl.classList.contains('mi-hidden') && statusEl.classList.contains('success')) {
    loadImportedMatches();
  }
};
