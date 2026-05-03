import { $, esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { findNode, getEffectiveMods, removeNode, countMaps } from '../tree.js';
import { getAdjustedLength, getAdjustedAR, getAdjustedOD, getAdjustedCS, fmtTime } from '../utils.js';
import { rerender } from './index.js';
import { makeModsSection, makeWinConSection, makeMultipliersSection, makeCheckbox } from './sections.js';
import { showMoveDialog, addSubPool, addMapToPool } from '../ops.js';

export function renderDetail() {
  const head  = $('pb-detail-head');
  const empty = $('pb-detail-empty');
  const body  = $('pb-detail-body');

  if (!state.selectedId) {
    head.textContent = 'select an item';
    empty.style.display = 'flex';
    body.style.display  = 'none';
    return;
  }

  const node = findNode(state.tree, state.selectedId);
  if (!node) { state.selectedId = null; renderDetail(); return; }

  empty.style.display = 'none';
  body.style.display  = 'flex';
  body.innerHTML = '';

  if (node.type === 'map') {
    renderMapDetail(body, node);
  } else {
    renderPoolDetail(body, node);
  }

  head.textContent = node.type === 'map'
    ? `map — ${node.code || node.name}`
    : `${node.type} — ${node.name}`;
}

export function renderMapDetail(body, node) {
  const card = document.createElement('div');
  card.className = 'pb-beatmap-card';
  const effectiveMods = getEffectiveMods(node, state.tree);
  const modsText = effectiveMods ? ` +${effectiveMods}` : '';
  const adjustedLen = getAdjustedLength(node.len, effectiveMods);
  const adjustedAR = getAdjustedAR(node.ar || 0, effectiveMods);
  const adjustedOD = getAdjustedOD(node.od || 0, effectiveMods);
  const adjustedCS = getAdjustedCS(node.cs || 0, effectiveMods);
  
  const modsKey = effectiveMods || 'NM';
  const displayStars = (node.srCache && node.srCache[modsKey]) || node.stars || '?';
  
  if (node.setId) {
    card.style.backgroundImage = `linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.85)), url(https://assets.ppy.sh/beatmaps/${node.setId}/covers/cover.jpg)`;
    card.style.backgroundSize = 'cover';
    card.style.backgroundPosition = 'center';
  }
  
  card.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
      <div>
        <div class="pb-beatmap-title">${esc(node.title || '—')}</div>
        <div class="pb-beatmap-sub">${esc(node.diff || '—')} · ${fmtTime(adjustedLen)}</div>
      </div>
      <span class="pb-stars" id="det-stars">★${displayStars}${modsText}</span>
    </div>
    <div class="pb-beatmap-bid">beatmap #${esc(node.bid || '—')}</div>
    <div style="display:flex;gap:12px;margin-top:6px;font-size:11px;color:var(--muted)">
      <span>CS ${adjustedCS.toFixed(1)}</span>
      <span>AR ${adjustedAR.toFixed(1)}</span>
      <span>OD ${adjustedOD.toFixed(1)}</span>
    </div>
  `;
  body.appendChild(card);

  const grid = document.createElement('div');
  grid.className = 'pb-grid-2';
  grid.innerHTML = `
    <div>
      <div class="pb-field-label">code / name</div>
      <input class="pb-field-val" id="det-code" value="${esc(node.code || '')}">
    </div>
    <div>
      <div class="pb-field-label">beatmap id</div>
      <input class="pb-field-val" id="det-bid" value="${esc(node.bid || '')}">
    </div>
  `;
  body.appendChild(grid);

  $('det-code').addEventListener('change', e => { node.code = e.target.value.trim(); rerender(); });
  $('det-bid').addEventListener('change', e => { node.bid = e.target.value.trim(); });

  body.appendChild(makeModsSection(node, 'mods override', 'inherit'));
  body.appendChild(makeWinConSection(node, 'win condition override', true));

  const flags = document.createElement('div');
  flags.style.cssText = 'display:flex;gap:12px';
  flags.appendChild(makeCheckbox('tiebreaker', node.tb, v => { node.tb = v; rerender(); }));
  flags.appendChild(makeCheckbox('disallowed', node.disallowed, v => { node.disallowed = v; rerender(); }));
  body.appendChild(flags);

  body.appendChild(makeMultipliersSection(node, 'score multipliers',
    'overrides parent pool/ruleset per mod. Exact-combo key (e.g. HDHR) wins; otherwise per-mod product.'));

  const actions = document.createElement('div');
  actions.className = 'pb-detail-actions';
  actions.innerHTML = `
    <button class="ghost-btn" id="det-refresh-btn" title="Refresh beatmap data from osu! API">🔄 refresh</button>
    <button class="ghost-btn" id="det-move-btn" style="flex:1">move to pool…</button>
    <button class="ghost-btn" id="det-remove-btn" style="border-color:var(--red);color:var(--red)">remove</button>
  `;
  body.appendChild(actions);

  $('det-refresh-btn').addEventListener('click', async () => {
    if (!node.bid) {
      alert('No beatmap ID set');
      return;
    }
    const btn = $('det-refresh-btn');
    btn.textContent = '⏳';
    btn.disabled = true;
    try {
      if (!node.srCache) node.srCache = {};
      
      const res = await fetch(`/api/beatmap/${node.bid}`);
      if (!res.ok) throw new Error('Failed to fetch beatmap data');
      const data = await res.json();
      node.title = `${data.artist} - ${data.title}`;
      node.diff = data.diff;
      node.len = data.len;
      node.ar = data.ar;
      node.od = data.od;
      node.cs = data.cs;
      node.setId = data.beatmapset_id;
      node.srCache['NM'] = data.stars;
      
      const effectiveMods = getEffectiveMods(node, state.tree);
      const modsKey = effectiveMods || 'NM';
      if (effectiveMods) {
        const attrsRes = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
        if (attrsRes.ok) {
          const attrs = await attrsRes.json();
          node.srCache[modsKey] = attrs.star_rating;
        }
      }
      
      node.stars = node.srCache[modsKey];
      
      rerender();
    } catch (e) {
      alert('Refresh failed: ' + e.message);
    } finally {
      btn.textContent = '🔄 refresh';
      btn.disabled = false;
    }
  });

  $('det-remove-btn').addEventListener('click', () => {
    removeNode(state.tree, node.id);
    state.selectedId = null;
    rerender();
  });

  $('det-move-btn').addEventListener('click', () => showMoveDialog(node));
}

export function renderPoolDetail(body, node) {
  const grid = document.createElement('div');
  grid.className = 'pb-grid-2';
  grid.innerHTML = `
    <div>
      <div class="pb-field-label">pool name</div>
      <input class="pb-field-val" id="det-pool-name" value="${esc(node.name)}">
    </div>
    <div>
      <div class="pb-field-label">type</div>
      <div class="pb-toggle-row" id="det-type-toggle">
        <div class="pb-toggle-opt${node.type === 'pool' ? ' active-blue' : ''}" data-val="pool">Pool</div>
        <div class="pb-toggle-opt${node.type === 'modpool' ? ' active-yellow' : ''}" data-val="modpool">ModdedPool</div>
      </div>
    </div>
  `;
  body.appendChild(grid);

  $('det-pool-name').addEventListener('change', e => { node.name = e.target.value.trim(); rerender(); });
  $('det-type-toggle').addEventListener('click', e => {
    const opt = e.target.closest('.pb-toggle-opt');
    if (!opt) return;
    node.type = opt.dataset.val;
    rerender();
  });

  if (node.type === 'modpool') {
    body.appendChild(makeModsSection(node, 'enforced mods', null));
  }

  body.appendChild(makeWinConSection(node, 'win condition', false));

  body.appendChild(makeMultipliersSection(node, 'score multipliers',
    'inherited by maps in this pool unless overridden. Exact-combo key (e.g. HDHR) wins.'));

  const contains = document.createElement('div');
  contains.className = 'pb-contains-box';
  const childCount = (node.children || []).length;
  const mapCount   = countMaps(node);
  contains.innerHTML = `
    <div class="pb-field-label" style="margin-bottom:4px">contains</div>
    <div style="font-size:11px"><strong>${childCount}</strong> <span class="muted">${childCount !== 1 ? 'children' : 'child'}</span></div>
    <div style="font-size:9px;color:var(--muted);margin-top:2px">${mapCount} map${mapCount !== 1 ? 's' : ''} total</div>
  `;
  body.appendChild(contains);

  const actions = document.createElement('div');
  actions.className = 'pb-detail-actions';
  actions.innerHTML = `
    <button class="ghost-btn" id="det-add-sub-btn" style="flex:1">add sub-pool</button>
    <button class="join-btn" id="det-add-map-here-btn" style="flex:1">add map here</button>
    <button class="ghost-btn" id="det-pool-remove-btn" style="border-color:var(--red);color:var(--red)">✕</button>
  `;
  body.appendChild(actions);

  $('det-add-sub-btn').addEventListener('click', () => addSubPool(node));
  $('det-add-map-here-btn').addEventListener('click', () => addMapToPool(node.id));
  $('det-pool-remove-btn').addEventListener('click', () => {
    removeNode(state.tree, node.id);
    state.selectedId = null;
    rerender();
  });
}
