'use strict';

import { esc } from '/static/shared/util.js';
import { state } from './state.js';
import { currentPoolDefaults } from './filters.js';

export function buildMethodToggle(methods, onChange) {
  const toggle = document.getElementById('cfg-calc');
  const crown = currentPoolDefaults().qualifier_method;
  toggle.innerHTML = methods.map(m =>
    `<div class="cfg-opt${m.key === state.currentMethod ? ' active' : ''}" data-val="${esc(m.key)}">${m.key === crown ? '👑 ' : ''}${esc(m.label)}</div>`
  ).join('');
  toggle.addEventListener('click', e => {
    const opt = e.target.closest('.cfg-opt');
    if (!opt) return;
    toggle.querySelectorAll('.cfg-opt').forEach(o => o.classList.remove('active'));
    opt.classList.add('active');
    state.currentMethod = opt.dataset.val;
    onChange();
  });
}

export function rebuildCrown() {
  if (!state.methodsReady || !state.filterOptions) return;
  const toggle = document.getElementById('cfg-calc');
  const crown = currentPoolDefaults().qualifier_method;
  toggle.querySelectorAll('.cfg-opt').forEach(opt => {
    const key = opt.dataset.val;
    const label = opt.textContent.replace(/^👑\s*/, '');
    opt.textContent = (key === crown ? '👑 ' : '') + label;
  });
}

export function applyPoolDefaults() {
  const poolId = document.getElementById('cfg-pool')?.value || '';
  if (poolId === state.lastDefaultsPool) return false;
  state.lastDefaultsPool = poolId;
  const d = currentPoolDefaults();
  let changed = false;
  if (d.method && d.method !== state.currentMethod) {
    state.currentMethod = d.method;
    changed = true;
    if (state.methodsReady) {
      document.querySelectorAll('#cfg-calc .cfg-opt').forEach(o => {
        o.classList.toggle('active', o.dataset.val === state.currentMethod);
      });
    }
  }
  const setToggle = (groupId, val) => {
    if (val === undefined || val === null) return;
    const target = document.querySelector(`#${groupId} .cfg-opt[data-val="${val}"]`);
    if (!target || target.classList.contains('active')) return;
    document.querySelectorAll(`#${groupId} .cfg-opt`).forEach(o => o.classList.remove('active'));
    target.classList.add('active');
    changed = true;
  };
  if (d.count_failed !== undefined) setToggle('cfg-failed', String(d.count_failed));
  if (d.aggregate) setToggle('cfg-aggregate', d.aggregate);
  rebuildCrown();
  return changed;
}
