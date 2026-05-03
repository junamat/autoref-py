import { esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { MOD_OPTIONS, WIN_CONDITIONS } from '../constants.js';
import { findParent, getEffectiveMods } from '../tree.js';
import { rerender } from './index.js';

export function makeModsSection(node, title, noneLabel) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="pb-field-label">${title}</div>`;

  const input = document.createElement('input');
  input.className = 'pb-field-val';
  input.placeholder = noneLabel ? 'inherit (leave blank)' : 'e.g. HD, HDHR, DT';
  input.value = node.mods || '';
  input.style.marginBottom = '5px';
  input.addEventListener('change', async () => {
    node.mods = input.value.trim().toUpperCase();
    rerender();
    if (node.type === 'map' && node.bid) {
      const effectiveMods = getEffectiveMods(node, state.tree);
      if (effectiveMods) {
        try {
          const res = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
          if (res.ok) {
            const attrs = await res.json();
            node.stars = attrs.star_rating;
            rerender();
          }
        } catch (e) {
          console.error('Failed to fetch modded attributes:', e);
        }
      }
    }
  });
  wrap.appendChild(input);

  const chips = document.createElement('div');
  chips.className = 'pb-toggle-row';
  const quickOpts = noneLabel ? ['', ...MOD_OPTIONS] : MOD_OPTIONS;
  for (const m of quickOpts) {
    const btn = document.createElement('div');
    btn.className = 'pb-toggle-opt';
    btn.textContent = m || (noneLabel ? 'Clear' : 'NM');
    btn.addEventListener('click', async () => {
      node.mods = m;
      input.value = m;
      rerender();
      if (node.type === 'map' && node.bid) {
        const effectiveMods = getEffectiveMods(node, state.tree);
        if (effectiveMods) {
          try {
            const res = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
            if (res.ok) {
              const attrs = await res.json();
              node.stars = attrs.star_rating;
              rerender();
            }
          } catch (e) {
            console.error('Failed to fetch modded attributes:', e);
          }
        }
      }
    });
    chips.appendChild(btn);
  }
  wrap.appendChild(chips);

  if (noneLabel) {
    const parent = findParent(state.tree, node.id);
    const hint = document.createElement('div');
    hint.className = 'pb-inherit-hint';
    hint.textContent = `inherits from parent: ${parent ? parent.name + (parent.mods ? ` (${parent.mods})` : ' (NM)') : 'NM'}`;
    wrap.appendChild(hint);
  } else {
    const hint = document.createElement('div');
    hint.className = 'pb-inherit-hint';
    hint.textContent = 'maps in this pool inherit these mods unless overridden';
    wrap.appendChild(hint);
  }

  return wrap;
}

export function makeWinConSection(node, title, allowInherit) {
  const wrap = document.createElement('div');
  const opts = allowInherit ? ['inherit', ...WIN_CONDITIONS] : WIN_CONDITIONS;
  const activeVal = node.winCon || (allowInherit ? 'inherit' : 'score_v2');

  wrap.innerHTML = `<div class="pb-field-label">${title}</div>`;
  const row = document.createElement('div');
  row.className = 'pb-toggle-row';

  for (const w of opts) {
    const btn = document.createElement('div');
    btn.className = 'pb-toggle-opt' + (w === activeVal ? ' active-blue' : '');
    btn.textContent = w;
    btn.addEventListener('click', () => {
      node.winCon = w;
      rerender();
    });
    row.appendChild(btn);
  }
  wrap.appendChild(row);

  if (allowInherit) {
    const parent = findParent(state.tree, node.id);
    const hint = document.createElement('div');
    hint.className = 'pb-inherit-hint';
    hint.textContent = `inherits from parent pool: ${parent ? parent.name + ' → ' + (parent.winCon || 'score_v2') : 'score_v2'}`;
    wrap.appendChild(hint);
  }

  return wrap;
}

export function makeMultipliersSection(node, title, hint) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="pb-field-label">${title}</div>`;

  const list = document.createElement('div');
  list.style.cssText = 'display:flex;flex-direction:column;gap:4px;margin-bottom:5px';
  wrap.appendChild(list);

  function commit() {
    const out = {};
    list.querySelectorAll('.pb-mult-row').forEach(row => {
      const k = row.querySelector('.pb-mult-key').value.trim().toUpperCase();
      const v = parseFloat(row.querySelector('.pb-mult-val').value);
      if (k && Number.isFinite(v)) out[k] = v;
    });
    if (Object.keys(out).length) node.score_multipliers = out;
    else delete node.score_multipliers;
  }

  function addRow(k = '', v = '') {
    const row = document.createElement('div');
    row.className = 'pb-mult-row';
    row.style.cssText = 'display:flex;gap:4px;align-items:center';
    row.innerHTML = `
      <input class="pb-field-val pb-mult-key" placeholder="MOD (e.g. EZ, HDHR)" value="${esc(k)}" style="flex:1">
      <input class="pb-field-val pb-mult-val" placeholder="multiplier" type="number" step="0.01" value="${esc(v)}" style="width:90px">
      <button class="ghost-btn pb-mult-rm" title="remove" style="padding:2px 6px">✕</button>
    `;
    row.querySelector('.pb-mult-key').addEventListener('change', commit);
    row.querySelector('.pb-mult-val').addEventListener('change', commit);
    row.querySelector('.pb-mult-rm').addEventListener('click', () => {
      row.remove();
      commit();
    });
    list.appendChild(row);
  }

  const existing = node.score_multipliers || {};
  for (const [k, v] of Object.entries(existing)) addRow(k, v);

  const addBtn = document.createElement('button');
  addBtn.className = 'ghost-btn xs';
  addBtn.textContent = '+ add multiplier';
  addBtn.addEventListener('click', () => addRow());
  wrap.appendChild(addBtn);

  if (hint) {
    const h = document.createElement('div');
    h.className = 'pb-inherit-hint';
    h.textContent = hint;
    wrap.appendChild(h);
  }

  return wrap;
}

export function makeCheckbox(label, checked, onChange) {
  const wrap = document.createElement('div');
  wrap.className = 'pb-checkbox-row';
  const box = document.createElement('div');
  box.className = 'pb-checkbox' + (checked ? ' checked' : '');
  if (checked) box.textContent = '✓';
  const lbl = document.createElement('span');
  lbl.textContent = label;
  wrap.appendChild(box);
  wrap.appendChild(lbl);
  wrap.addEventListener('click', () => {
    const newVal = !box.classList.contains('checked');
    box.classList.toggle('checked', newVal);
    box.textContent = newVal ? '✓' : '';
    onChange(newVal);
  });
  return wrap;
}
