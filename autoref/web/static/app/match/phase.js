'use strict';

import { $, esc } from '/static/shared/util.js';
import { appState } from '../state.js';
import { formatEta } from './util.js';

const PHASE_ORDER_BRACKET = ['ROLL', 'ORDER', 'PROTECT', 'BAN_1', 'PICK', 'TB', 'DONE'];
const PHASE_COLORS = {
  ROLL: '#a78bfa', ORDER: '#a78bfa',
  PROTECT: 'var(--yellow)', BAN_1: 'var(--red)',
  PICK: 'var(--blue)', TB: 'var(--orange)', DONE: 'var(--green)',
};
const PHASE_ACTION = {
  ROLL: 'Waiting for team rolls. Ref can override with >roll.',
  ORDER: 'Roll winner chooses a scheme. Use >order <n>.',
  PROTECT: 'Protect phase active — 120s timer.',
  BAN_1: 'Ban phase active — 120s timer.',
  PICK: 'Pick phase active — 120s timer.',
  TB: 'Tiebreaker triggered! TB map queued.',
  DONE: 'Match complete.',
};

export function renderPhase() {
  const el = $('phase-content');
  if (!el) return;
  const s = appState;
  if (s.qualifier) renderQualsPhase(el, s);
  else renderBracketPhase(el, s);
}

function renderBracketPhase(el, s) {
  const phase = (s.phase || 'PICK').toUpperCase();
  const cur = PHASE_ORDER_BRACKET.indexOf(phase);
  const nodeState = name => {
    const idx = PHASE_ORDER_BRACKET.indexOf(name);
    return idx < cur ? 'done' : idx === cur ? 'active' : 'upcoming';
  };
  const activeColor = PHASE_COLORS[phase] || 'var(--text)';

  const nodes = [
    { key: 'ROLL', label: 'ROLL', sub: nodeState('ROLL') === 'done' ? 'done' : null },
    { key: 'ORDER', label: 'ORDER', sub: nodeState('ORDER') === 'done' ? 'done' : null },
    { key: 'PROTECT', label: 'PROT', sub: null },
    { key: 'BAN_1', label: 'BAN', sub: null },
    { key: 'PICK', label: 'PICK', sub: `${(s.wins || [0, 0]).reduce((a, b) => a + b, 0)} played` },
    { key: 'TB', label: 'TB', sub: null },
    { key: 'DONE', label: 'DONE', sub: null },
  ];

  const pipelineHtml = nodes.map((n, i) => {
    const ns = nodeState(n.key);
    const color = PHASE_COLORS[n.key] || 'var(--text)';
    const borderColor = ns === 'active' ? color : ns === 'done' ? 'var(--muted)' : 'var(--border)';
    const textColor = ns === 'active' ? color : ns === 'done' ? 'var(--muted)' : 'var(--border)';
    const bgStyle = ns === 'active' ? `background:${color}22;box-shadow:0 0 8px ${color}55;` : '';
    const opacityStyle = ns === 'upcoming' ? 'opacity:0.4;' : '';
    const check = ns === 'done' ? `<span class="phase-node-check">✓</span>` : '';
    const sub = n.sub ? `<span class="phase-node-sub">${esc(n.sub)}</span>` : '';
    const arrow = i < nodes.length - 1
      ? `<div class="phase-arrow${nodeState(nodes[i + 1].key) !== 'upcoming' ? ' active' : ''}">
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
      ${(s.scheme_orders || []).map(([k, v]) =>
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
  const maps = s.maps || [];
  const played = maps.filter(m => m.state === 'played').length;
  const remaining = maps.filter(m => m.state === 'upcoming' || m.state === 'current').length;
  const eta = formatEta(s.eta_seconds);

  const icons = { played: '✓', current: '▶', upcoming: '·' };
  const rowsHtml = maps.map(m => {
    const isActive = m.state === 'current';
    const isDone = m.state === 'played';
    const col = isActive ? 'var(--blue)' : isDone ? 'var(--green)' : 'var(--border)';
    const nowBadge = isActive ? `<span class="quals-phase-now">NOW</span>` : '';
    const meta = isDone ? 'done' : (m.length ? formatEta(m.length) : '—');
    return `<div class="quals-phase-row${isActive ? ' current' : ''}">
      <span class="quals-phase-icon" style="color:${col}">${icons[m.state] || '·'}</span>
      <span class="quals-phase-code" style="color:${col};font-weight:${isActive ? 700 : 400}">${esc(m.code)}</span>
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
