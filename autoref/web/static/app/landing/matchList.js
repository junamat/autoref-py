'use strict';

import { $, esc } from '/static/shared/util.js';
import { showMatch } from '../router.js';

export function renderMatchList(matches) {
  const list = $('match-list');
  const noMsg = $('no-matches-msg');

  list.querySelectorAll('.match-card').forEach(c => c.remove());

  const count = matches.length;
  $('landing-status').textContent = count
    ? `connected · ${count} active match${count !== 1 ? 'es' : ''}`
    : 'connected · no active matches';

  if (!count) { noMsg.hidden = false; return; }
  noMsg.hidden = true;

  for (const data of matches) {
    const pending = data.status === 'pending';
    const isQuals = !!data.qualifier;
    const mode = data.mode || 'off';
    const connected = data.connected || false;
    const title = isQuals
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
