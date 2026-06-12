'use strict';

import { initNav } from '/static/shared/nav.js';

initNav();

const matchIdInput = document.getElementById('se-match-id');
const loadBtn = document.getElementById('se-load');
const scoresSection = document.getElementById('se-scores-section');
const matchInfoEl = document.getElementById('se-match-info');
const scoreListEl = document.getElementById('se-score-list');
const statusEl = document.getElementById('se-status');

const newUserIdInput = document.getElementById('se-new-user-id');
const newUsernameInput = document.getElementById('se-new-username');
const newTurnInput = document.getElementById('se-new-turn');
const newBeatmapInput = document.getElementById('se-new-beatmap');
const newTeamInput = document.getElementById('se-new-team');
const newScoreInput = document.getElementById('se-new-score');
const newAccInput = document.getElementById('se-new-acc');
const newComboInput = document.getElementById('se-new-combo');
const newMissInput = document.getElementById('se-new-miss');
const newRankInput = document.getElementById('se-new-rank');
const newModsInput = document.getElementById('se-new-mods');
const newPassedInput = document.getElementById('se-new-passed');
const addScoreBtn = document.getElementById('se-add-score');

let currentMatchId = null;

function showStatus(message, type = 'loading') {
  statusEl.textContent = message;
  statusEl.className = `se-status ${type}`;
  statusEl.classList.remove('se-hidden');
}

function hideStatus() {
  statusEl.classList.add('se-hidden');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

function formatScore(score) {
  return score.toLocaleString();
}

function renderScores(scores) {
  scoreListEl.innerHTML = '';

  if (scores.length === 0) {
    scoreListEl.innerHTML = '<div class="se-status loading">no scores in this match</div>';
    return;
  }

  const byTurn = {};
  for (const s of scores) {
    if (!byTurn[s.turn]) byTurn[s.turn] = [];
    byTurn[s.turn].push(s);
  }

  const sortedTurns = Object.keys(byTurn).map(Number).sort((a, b) => a - b);

  for (const turn of sortedTurns) {
    const turnScores = byTurn[turn].sort((a, b) => b.score - a.score);

    const turnHeader = document.createElement('div');
    turnHeader.className = 'se-section-title';
    turnHeader.style.marginTop = '12px';
    turnHeader.textContent = `turn ${turn} — beatmap ${turnScores[0].beatmap_id}`;
    scoreListEl.appendChild(turnHeader);

    for (const s of turnScores) {
      const div = document.createElement('div');
      div.className = 'se-score';
      div.dataset.scoreId = s.id;
      div.innerHTML = `
        <div class="se-score-info">
          <div class="se-score-name">${escapeHtml(s.username || `user ${s.user_id}`)}</div>
          <div class="se-score-meta">
            team ${s.team_index ?? '?'} · ${s.accuracy?.toFixed(2) ?? '?'}% · ${s.max_combo ?? 0}x · ${s.passed ? 'pass' : 'fail'}
            ${s.mods?.length ? ' · ' + escapeHtml(s.mods.join(',')) : ''}
          </div>
        </div>
        <div class="se-score-value">${formatScore(s.score)}</div>
        <button class="se-btn danger small">delete</button>
      `;

      const deleteBtn = div.querySelector('.se-btn.danger');
      deleteBtn.addEventListener('click', () => deleteScore(s.id, div));

      scoreListEl.appendChild(div);
    }
  }
}

async function loadMatch() {
  const matchId = parseInt(matchIdInput.value);
  if (!matchId) {
    showStatus('please enter a match id', 'error');
    return;
  }

  loadBtn.disabled = true;
  showStatus('loading match...', 'loading');

  try {
    const res = await fetch(`/api/scores/${matchId}`);
    const data = await res.json();

    if (!res.ok) {
      showStatus(`error: ${data.error || 'unknown error'}`, 'error');
      return;
    }

    currentMatchId = matchId;
    matchInfoEl.textContent = `(${data.scores.length} scores)`;
    renderScores(data.scores);
    scoresSection.classList.remove('se-hidden');
    hideStatus();

    newBeatmapInput.value = data.scores[0]?.beatmap_id || '';
  } catch (err) {
    showStatus(`failed to load: ${err.message}`, 'error');
  } finally {
    loadBtn.disabled = false;
  }
}

async function deleteScore(scoreId, element) {
  if (!confirm('delete this score? this cannot be undone and will affect stats.')) {
    return;
  }

  const btn = element.querySelector('.se-btn.danger');
  btn.disabled = true;

  try {
    const res = await fetch(`/api/scores/${scoreId}`, { method: 'DELETE' });
    const data = await res.json();

    if (!res.ok) {
      showStatus(`failed to delete: ${data.error || 'unknown error'}`, 'error');
      btn.disabled = false;
      return;
    }

    element.remove();
    showStatus('score deleted', 'success');
    setTimeout(hideStatus, 2000);

    const count = scoreListEl.querySelectorAll('.se-score').length;
    matchInfoEl.textContent = `(${count} scores)`;
  } catch (err) {
    showStatus(`failed to delete: ${err.message}`, 'error');
    btn.disabled = false;
  }
}

async function addScore() {
  if (!currentMatchId) {
    showStatus('load a match first', 'error');
    return;
  }

  const userId = parseInt(newUserIdInput.value);
  const score = parseInt(newScoreInput.value);
  const accuracy = parseFloat(newAccInput.value);
  const maxCombo = parseInt(newComboInput.value);
  const turn = parseInt(newTurnInput.value);
  const beatmapId = parseInt(newBeatmapInput.value);

  if (!userId || !score || isNaN(accuracy) || isNaN(maxCombo) || !turn || !beatmapId) {
    showStatus('please fill in all required fields', 'error');
    return;
  }

  addScoreBtn.disabled = true;
  showStatus('adding score...', 'loading');

  const mods = newModsInput.value
    .split(',')
    .map(m => m.trim().toUpperCase())
    .filter(m => m);

  try {
    const res = await fetch('/api/scores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        match_id: currentMatchId,
        turn,
        beatmap_id: beatmapId,
        user_id: userId,
        username: newUsernameInput.value || null,
        team_index: parseInt(newTeamInput.value) || 0,
        score,
        accuracy,
        max_combo: maxCombo,
        mods,
        passed: newPassedInput.value === 'true',
        perfect: false,
        rank: newRankInput.value || null,
        nmiss: parseInt(newMissInput.value) || 0,
        n50: 0,
        n100: 0,
        n300: 0,
        ngeki: 0,
        nkatu: 0,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      showStatus(`failed to add: ${data.error || 'unknown error'}`, 'error');
      return;
    }

    showStatus(`score added (id: ${data.score_id})`, 'success');
    setTimeout(hideStatus, 2000);

    await loadMatch();
  } catch (err) {
    showStatus(`failed to add: ${err.message}`, 'error');
  } finally {
    addScoreBtn.disabled = false;
  }
}

loadBtn.addEventListener('click', loadMatch);
addScoreBtn.addEventListener('click', addScore);

matchIdInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    loadMatch();
  }
});
