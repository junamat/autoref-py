'use strict';

import { $, esc } from '/static/shared/util.js';
import { appState } from '../state.js';
import { sendWS } from '../ws.js';

export function renderCmds() {
  const el = $('cmds-content');
  if (!el) return;
  const isQuals = !!appState.qualifier;
  const cmds = (appState.commands || []).filter(c => !isQuals || !c.bracket_only);

  const sections = [];
  const seen = {};
  for (const c of cmds) {
    if (!seen[c.section]) { seen[c.section] = []; sections.push(c.section); }
    seen[c.section].push(c);
  }

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
