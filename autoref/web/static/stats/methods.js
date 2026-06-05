'use strict';

import { esc } from '/static/shared/util.js';
import { state } from './state.js';
import { currentPoolDefaults } from './filters.js';

export function buildMethodToggle(methods, onChange) {
  const select = document.getElementById('cfg-calc');
  const crown = currentPoolDefaults().qualifier_method;
  select.innerHTML = methods.map(m =>
    `<option value="${esc(m.key)}"${m.key === state.currentMethod ? ' selected' : ''}>${m.key === crown ? '👑 ' : ''}${esc(m.label)}</option>`
  ).join('');
  select.addEventListener('change', () => {
    state.currentMethod = select.value;
    onChange('method');
  });
}

export function rebuildCrown() {
  if (!state.methodsReady || !state.filterOptions) return;
  const select = document.getElementById('cfg-calc');
  const crown = currentPoolDefaults().qualifier_method;
  Array.from(select.options).forEach(opt => {
    const key = opt.value;
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
      const select = document.getElementById('cfg-calc');
      select.value = state.currentMethod;
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
  if (d.aggregate) setToggle('cfg-aggregate', d.aggregate);
  rebuildCrown();
  return changed;
}
