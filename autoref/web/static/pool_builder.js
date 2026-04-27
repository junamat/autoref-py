'use strict';

/* ── utils ───────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function fmtTime(s) {
  if (!s) return '0:00';
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function getAdjustedLength(baseLength, mods) {
  if (!mods) return baseLength;
  const modsUpper = mods.toUpperCase();
  if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
    return Math.round(baseLength / 1.5);
  }
  if (modsUpper.includes('HT')) {
    return Math.round(baseLength / 0.75);
  }
  return baseLength;
}

function getAdjustedAR(baseAR, mods) {
  if (!mods) return baseAR;
  const modsUpper = mods.toUpperCase();
  let ar = baseAR;
  
  // Apply EZ/HR as simple multipliers
  if (modsUpper.includes('EZ')) ar *= 0.5;
  if (modsUpper.includes('HR')) ar = Math.min(10, ar * 1.4);
  
  // For DT/HT, calculate "perceived AR" through ms conversion
  if (modsUpper.includes('DT') || modsUpper.includes('NC') || modsUpper.includes('HT')) {
    // Calculate preempt time in ms
    let ms;
    if (ar > 5) {
      ms = 1200 - (ar - 5) * 150;
    } else {
      ms = 1200 + (5 - ar) * 120;
    }
    
    // Apply speed mods to timing
    if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
      ms *= (2/3);
    } else if (modsUpper.includes('HT')) {
      ms *= (4/3);
    }
    
    // Convert back to "perceived AR"
    if (ms < 300) {
      ar = 11;
    } else if (ms < 1200) {
      ar = 5 + (1200 - ms) / 150;
    } else {
      ar = 5 - (ms - 1200) / 120;
    }
  }
  
  return Math.round(ar * 100) / 100;
}

function getAdjustedOD(baseOD, mods) {
  if (!mods) return baseOD;
  const modsUpper = mods.toUpperCase();
  let od = baseOD;
  
  if (modsUpper.includes('HR')) od = Math.min(10, od * 1.4);
  if (modsUpper.includes('EZ')) od *= 0.5;
  
  if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
    const ms = 79 - od * 6 + 0.5;
    const adjustedMs = ms * (2/3) + 0.33;
    od = (79 - adjustedMs + 0.5) / 6;
  }
  if (modsUpper.includes('HT')) {
    const ms = 79 - od * 6 + 0.5;
    const adjustedMs = ms * (4/3) + 0.66;
    od = (79 - adjustedMs + 0.5) / 6;
  }
  
  return Math.floor(Math.max(0, Math.min(10, od)) * 10) / 10;
}

function getAdjustedCS(baseCS, mods) {
  if (!mods) return baseCS;
  const modsUpper = mods.toUpperCase();
  let cs = baseCS;
  
  if (modsUpper.includes('HR')) cs = Math.min(10, cs * 1.3);
  if (modsUpper.includes('EZ')) cs *= 0.5;
  
  return Math.floor(Math.max(0, Math.min(10, cs)) * 10) / 10;
}

function getAdjustedHP(baseHP, mods) {
  if (!mods) return baseHP;
  const modsUpper = mods.toUpperCase();
  let hp = baseHP;
  
  if (modsUpper.includes('HR')) hp = Math.min(10, hp * 1.4);
  if (modsUpper.includes('EZ')) hp *= 0.5;
  
  return Math.floor(Math.max(0, Math.min(10, hp)) * 10) / 10;
}

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
$('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});
function uid() {
  return Math.random().toString(36).slice(2, 9);
}

/* ── theme ───────────────────────────────────────────────────── */
if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');

/* ── state ───────────────────────────────────────────────────── */
// Tree: array of nodes. Each node: { id, type:'pool'|'modpool'|'map', name, open, mods, winCon, children?, code?, bid?, title?, diff?, len?, stars?, tb?, disallowed? }
let tree = [];
let selectedId = null;

const WIN_CONDITIONS = ['score_v2', 'score', 'accuracy', 'combo'];
const MOD_OPTIONS    = ['None', 'HD', 'HR', 'DT', 'FL', 'EZ', 'FM', 'HDHR', 'HDDT'];

/* ── tree helpers ────────────────────────────────────────────── */
function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n;
    if (n.children) {
      const found = findNode(n.children, id);
      if (found) return found;
    }
  }
  return null;
}

function findParent(nodes, id, parent = null) {
  for (const n of nodes) {
    if (n.id === id) return parent;
    if (n.children) {
      const found = findParent(n.children, id, n);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

function getEffectiveMods(node) {
  if (node.type !== 'map') return node.mods || '';
  if (node.mods && node.mods !== 'inherit' && node.mods !== '') return node.mods;
  const parent = findParent(tree, node.id);
  return parent?.mods || '';
}

function removeNode(nodes, id) {
  for (let i = 0; i < nodes.length; i++) {
    if (nodes[i].id === id) { nodes.splice(i, 1); return true; }
    if (nodes[i].children && removeNode(nodes[i].children, id)) return true;
  }
  return false;
}

function countMaps(node) {
  if (node.type === 'map') return 1;
  return (node.children || []).reduce((s, c) => s + countMaps(c), 0);
}

function sumLen(node) {
  if (node.type === 'map') return node.len || 0;
  return (node.children || []).reduce((s, c) => s + sumLen(c), 0);
}

function totalMaps() { return tree.reduce((s, n) => s + countMaps(n), 0); }
function totalLen()  { return tree.reduce((s, n) => s + sumLen(n), 0); }

/* ── stats bar ───────────────────────────────────────────────── */
function updateStats() {
  $('pb-stat-maps').textContent = totalMaps();
  $('pb-stat-time').textContent = fmtTime(totalLen());
}

/* ── tree rendering ──────────────────────────────────────────── */
function renderTree() {
  const container = $('pb-tree');
  container.innerHTML = '';
  renderNodes(tree, container, 0);
  updateStats();
}

function renderNodes(nodes, container, depth) {
  for (const node of nodes) {
    const isPool = node.type !== 'map';
    const isSelected = node.id === selectedId;
    const poolColor = node.type === 'modpool' ? 'var(--yellow)' : 'var(--blue)';
    const indent = depth * 16;

    const row = document.createElement('div');
    row.className = 'pb-tree-row' + (isSelected ? ' selected' : '');
    row.dataset.id = node.id;
    row.style.paddingLeft = `${8 + indent}px`;

    const expandIcon = isPool
      ? `<span class="expand-icon" style="color:${poolColor}">${node.open ? '▾' : '▸'}</span>`
      : `<span class="expand-icon" style="color:var(--muted)">♩</span>`;

    const nameColor = isSelected ? 'var(--blue)' : isPool ? poolColor : 'var(--text)';
    const nameWeight = isPool ? '700' : '400';
    const displayName = node.code || node.name;

    const modsBadge = node.mods
      ? `<span class="node-badge" style="border:1px solid rgba(251,191,36,.4);color:var(--yellow)">${esc(node.mods)}</span>`
      : '';
    const tbBadge = node.tb
      ? `<span class="node-badge" style="border:1px dashed var(--muted);color:var(--muted)">TB</span>`
      : '';
    const winBadge = (node.winCon && node.winCon !== 'score_v2' && node.winCon !== 'inherit')
      ? `<span class="node-badge" style="border:1px solid rgba(251,146,60,.4);color:var(--orange)">${esc(node.winCon.slice(0,3).toUpperCase())}</span>`
      : '';
    const lenBadge = node.len
      ? `<span class="node-len">${fmtTime(node.len)}</span>`
      : '';
    const countBadge = isPool
      ? `<span class="node-count">${(node.children || []).length}</span>`
      : '';

    row.innerHTML = `
      <span class="drag-handle">⠿</span>
      ${expandIcon}
      <span class="node-name" style="color:${nameColor};font-weight:${nameWeight}">${esc(displayName)}</span>
      ${modsBadge}${tbBadge}${winBadge}${lenBadge}${countBadge}
    `;

    row.addEventListener('click', e => {
      if (isPool) {
        // toggle expand on the expand icon click, select on name click
        node.open = !node.open;
      }
      selectedId = node.id;
      renderTree();
      renderDetail();
    });

    container.appendChild(row);

    if (isPool && node.open && node.children) {
      renderNodes(node.children, container, depth + 1);

      // add-to-pool hint
      const hint = document.createElement('div');
      hint.className = 'pb-add-hint';
      hint.style.paddingLeft = `${8 + indent + 16}px`;
      hint.style.padding = `2px 8px 2px ${8 + indent + 16}px`;
      hint.innerHTML = `<span>+ add map or sub-pool</span>`;
      hint.addEventListener('click', () => addMapToPool(node.id));
      container.appendChild(hint);
    }
  }
}

/* ── detail panel ────────────────────────────────────────────── */
function renderDetail() {
  const head  = $('pb-detail-head');
  const empty = $('pb-detail-empty');
  const body  = $('pb-detail-body');

  if (!selectedId) {
    head.textContent = 'select an item';
    empty.style.display = 'flex';
    body.style.display  = 'none';
    return;
  }

  const node = findNode(tree, selectedId);
  if (!node) { selectedId = null; renderDetail(); return; }

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

function renderMapDetail(body, node) {
  // beatmap card
  const card = document.createElement('div');
  card.className = 'pb-beatmap-card';
  const effectiveMods = getEffectiveMods(node);
  const modsText = effectiveMods ? ` +${effectiveMods}` : '';
  const adjustedLen = getAdjustedLength(node.len, effectiveMods);
  const adjustedAR = getAdjustedAR(node.ar || 0, effectiveMods);
  const adjustedOD = getAdjustedOD(node.od || 0, effectiveMods);
  const adjustedCS = getAdjustedCS(node.cs || 0, effectiveMods);
  
  // Get SR from cache based on effective mods
  const modsKey = effectiveMods || 'NM';
  const displayStars = (node.srCache && node.srCache[modsKey]) || node.stars || '?';
  
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

  // code + bid fields
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

  $('det-code').addEventListener('change', e => { node.code = e.target.value.trim(); renderTree(); renderDetail(); });
  $('det-bid').addEventListener('change', e => { node.bid = e.target.value.trim(); });

  // mods override
  body.appendChild(makeModsSection(node, 'mods override', 'inherit'));

  // win condition override
  body.appendChild(makeWinConSection(node, 'win condition override', true));

  // flags
  const flags = document.createElement('div');
  flags.style.cssText = 'display:flex;gap:12px';
  flags.appendChild(makeCheckbox('tiebreaker', node.tb, v => { node.tb = v; renderTree(); }));
  flags.appendChild(makeCheckbox('disallowed', node.disallowed, v => { node.disallowed = v; renderTree(); }));
  body.appendChild(flags);

  // actions
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
      // Initialize SR cache if needed
      if (!node.srCache) node.srCache = {};
      
      // Fetch base beatmap data
      const res = await fetch(`/api/beatmap/${node.bid}`);
      if (!res.ok) throw new Error('Failed to fetch beatmap data');
      const data = await res.json();
      node.title = `${data.artist} - ${data.title}`;
      node.diff = data.diff;
      node.len = data.len;
      node.ar = data.ar;
      node.od = data.od;
      node.cs = data.cs;
      node.srCache['NM'] = data.stars;
      
      // Fetch modded attributes if mods are set (including inherited)
      const effectiveMods = getEffectiveMods(node);
      const modsKey = effectiveMods || 'NM';
      if (effectiveMods) {
        const attrsRes = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
        if (attrsRes.ok) {
          const attrs = await attrsRes.json();
          node.srCache[modsKey] = attrs.star_rating;
        }
      }
      
      node.stars = node.srCache[modsKey];
      
      renderTree();
      renderDetail();
    } catch (e) {
      alert('Refresh failed: ' + e.message);
    } finally {
      btn.textContent = '🔄 refresh';
      btn.disabled = false;
    }
  });

  $('det-remove-btn').addEventListener('click', () => {
    removeNode(tree, node.id);
    selectedId = null;
    renderTree();
    renderDetail();
  });

  $('det-move-btn').addEventListener('click', () => showMoveDialog(node));
}

function renderPoolDetail(body, node) {
  // name + type
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

  $('det-pool-name').addEventListener('change', e => { node.name = e.target.value.trim(); renderTree(); renderDetail(); });
  $('det-type-toggle').addEventListener('click', e => {
    const opt = e.target.closest('.pb-toggle-opt');
    if (!opt) return;
    node.type = opt.dataset.val;
    renderTree();
    renderDetail();
  });

  // enforced mods (modpool only)
  if (node.type === 'modpool') {
    body.appendChild(makeModsSection(node, 'enforced mods', null));
  }

  // win condition
  body.appendChild(makeWinConSection(node, 'win condition', false));

  // contains summary
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

  // actions
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
    removeNode(tree, node.id);
    selectedId = null;
    renderTree();
    renderDetail();
  });
}

/* ── detail helpers ──────────────────────────────────────────── */
function makeModsSection(node, title, noneLabel) {
  const wrap = document.createElement('div');
  wrap.innerHTML = `<div class="pb-field-label">${title}</div>`;

  // free-text input
  const input = document.createElement('input');
  input.className = 'pb-field-val';
  input.placeholder = noneLabel ? 'inherit (leave blank)' : 'e.g. HD, HDHR, DT';
  input.value = node.mods || '';
  input.style.marginBottom = '5px';
  input.addEventListener('change', async () => {
    node.mods = input.value.trim().toUpperCase();
    renderTree();
    // Auto-refresh stars for maps when mods change
    if (node.type === 'map' && node.bid) {
      const effectiveMods = getEffectiveMods(node);
      if (effectiveMods) {
        try {
          const res = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
          if (res.ok) {
            const attrs = await res.json();
            node.stars = attrs.star_rating;
            renderDetail();
          }
        } catch (e) {
          console.error('Failed to fetch modded attributes:', e);
        }
      }
    }
  });
  wrap.appendChild(input);

  // quick-pick chips
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
      renderTree();
      // Auto-refresh stars for maps when mods change
      if (node.type === 'map' && node.bid) {
        const effectiveMods = getEffectiveMods(node);
        if (effectiveMods) {
          try {
            const res = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(effectiveMods)}`);
            if (res.ok) {
              const attrs = await res.json();
              node.stars = attrs.star_rating;
              renderDetail();
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
    const parent = findParent(tree, node.id);
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

function makeWinConSection(node, title, allowInherit) {
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
      renderTree();
      renderDetail();
    });
    row.appendChild(btn);
  }
  wrap.appendChild(row);

  if (allowInherit) {
    const parent = findParent(tree, node.id);
    const hint = document.createElement('div');
    hint.className = 'pb-inherit-hint';
    hint.textContent = `inherits from parent pool: ${parent ? parent.name + ' → ' + (parent.winCon || 'score_v2') : 'score_v2'}`;
    wrap.appendChild(hint);
  }

  return wrap;
}

function makeCheckbox(label, checked, onChange) {
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

/* ── add / create helpers ────────────────────────────────────── */
function addTopLevelPool() {
  const node = { id: uid(), type: 'pool', name: 'New Pool', mods: '', winCon: 'score_v2', open: true, children: [] };
  tree.push(node);
  selectedId = node.id;
  renderTree();
  renderDetail();
}

function addSubPool(parentNode) {
  const node = { id: uid(), type: 'modpool', name: 'New Sub-Pool', mods: '', winCon: 'inherit', open: true, children: [] };
  parentNode.children = parentNode.children || [];
  parentNode.children.push(node);
  selectedId = node.id;
  renderTree();
  renderDetail();
}

function addMapToPool(poolId) {
  const pool = findNode(tree, poolId);
  if (!pool) return;
  const node = {
    id: uid(), type: 'map',
    code: `MAP${totalMaps() + 1}`,
    bid: '', title: 'New Map', diff: '', len: 0, stars: 0,
    ar: 0, od: 0, cs: 0,
    tb: false, disallowed: false, mods: '', winCon: 'inherit',
  };
  pool.children = pool.children || [];
  pool.children.push(node);
  selectedId = node.id;
  renderTree();
  renderDetail();
}

function addTopLevelMap() {
  // If there's a selected pool, add there; otherwise add to first pool or create one
  const sel = selectedId ? findNode(tree, selectedId) : null;
  const targetPool = sel && sel.type !== 'map' ? sel
    : tree.find(n => n.type !== 'map') || null;

  if (targetPool) {
    addMapToPool(targetPool.id);
  } else {
    // no pools yet — create a default one first
    const pool = { id: uid(), type: 'pool', name: 'NM', mods: '', winCon: 'score_v2', open: true, children: [] };
    tree.push(pool);
    addMapToPool(pool.id);
  }
}

/* ── move dialog (simple prompt) ─────────────────────────────── */
function showMoveDialog(node) {
  // Collect all pool/modpool names
  const pools = [];
  function collect(nodes) {
    for (const n of nodes) {
      if (n.type !== 'map' && n.id !== node.id) {
        pools.push({ id: n.id, name: n.name });
        if (n.children) collect(n.children);
      }
    }
  }
  collect(tree);
  if (!pools.length) { alert('No pools to move to.'); return; }
  const names = pools.map((p, i) => `${i + 1}. ${p.name}`).join('\n');
  const choice = prompt(`Move "${node.code || node.name}" to:\n${names}\n\nEnter number:`);
  const idx = parseInt(choice) - 1;
  if (isNaN(idx) || idx < 0 || idx >= pools.length) return;
  removeNode(tree, node.id);
  const target = findNode(tree, pools[idx].id);
  if (target) {
    target.children = target.children || [];
    target.children.push(node);
  }
  renderTree();
  renderDetail();
}

/* ── import ──────────────────────────────────────────────────── */
$('pb-import-btn').addEventListener('click', () => {
  $('pb-import-overlay').classList.remove('hidden');
  $('pb-import-textarea').focus();
});
$('pb-import-close').addEventListener('click', () => {
  $('pb-import-overlay').classList.add('hidden');
});
$('pb-import-overlay').addEventListener('click', e => {
  if (e.target === $('pb-import-overlay')) $('pb-import-overlay').classList.add('hidden');
});

$('pb-import-submit').addEventListener('click', async () => {
  const raw = $('pb-import-textarea').value.trim();
  if (!raw) return;
  const defaultPool = $('pb-import-default-pool').value.trim() || 'NM';
  const btn = $('pb-import-submit');
  btn.textContent = 'importing…';
  btn.disabled = true;

  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
  const entries = lines.map(line => {
    // extract beatmap id from URL or plain id
    const urlMatch = line.match(/\/b(?:eatmaps)?\/(\d+)/);
    const parts = line.split(/\s+/);
    const bid = urlMatch ? urlMatch[1] : parts[0].replace(/\D/g, '');
    const pool = parts[1] || defaultPool;
    return { bid, pool };
  }).filter(e => e.bid);

  // Fetch beatmap data for all entries
  const beatmapData = {};
  for (const { bid } of entries) {
    if (beatmapData[bid]) continue; // Skip duplicates
    try {
      const res = await fetch(`/api/beatmap/${bid}`);
      if (res.ok) {
        beatmapData[bid] = await res.json();
      }
    } catch (e) {
      console.error(`Failed to fetch beatmap ${bid}:`, e);
    }
  }

  // Group by pool name, create pools if needed, add maps
  for (const { bid, pool: poolName } of entries) {
    let poolNode = findNodeByName(tree, poolName);
    if (!poolNode) {
      poolNode = { id: uid(), type: 'pool', name: poolName, mods: '', winCon: 'score_v2', open: true, children: [] };
      tree.push(poolNode);
    }
    
    const data = beatmapData[bid];
    const mapNode = {
      id: uid(), type: 'map',
      code: `${poolName}${(poolNode.children || []).length + 1}`,
      bid,
      title: data ? `${data.artist} - ${data.title}` : `beatmap #${bid}`,
      diff: data?.diff || '',
      len: data?.len || 0,
      stars: data?.stars || 0,
      ar: data?.ar || 0,
      od: data?.od || 0,
      cs: data?.cs || 0,
      hp: data?.hp || 0,
      tb: false, disallowed: false, mods: '', winCon: 'inherit',
    };
    poolNode.children = poolNode.children || [];
    poolNode.children.push(mapNode);
  }

  renderTree();
  renderDetail();
  $('pb-import-overlay').classList.add('hidden');
  $('pb-import-textarea').value = '';
  btn.textContent = 'lookup & import';
  btn.disabled = false;
});

function findNodeByName(nodes, name) {
  for (const n of nodes) {
    if (n.name === name) return n;
    if (n.children) {
      const found = findNodeByName(n.children, name);
      if (found) return found;
    }
  }
  return null;
}

/* ── export ──────────────────────────────────────────────────── */
$('pb-export-btn').addEventListener('click', () => {
  const name = $('pb-pool-name').value.trim() || 'pool';
  const lines = [];
  function collectMaps(nodes, poolName = '') {
    for (const n of nodes) {
      if (n.type === 'map') {
        if (n.bid) lines.push(`${n.bid} ${poolName}`);
      } else if (n.children) {
        collectMaps(n.children, n.name || poolName);
      }
    }
  }
  collectMaps(tree);
  const text = lines.join('\n');
  const blob = new Blob([text], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `${name.replace(/\s+/g, '_')}.txt`;
  a.click();
  URL.revokeObjectURL(url);
});

/* ── load ────────────────────────────────────────────────────── */
$('pb-load-btn').addEventListener('click', async () => {
  $('pb-load-overlay').classList.remove('hidden');
  await loadPoolList();
});

async function loadPoolList() {
  const list = $('pb-load-list');
  list.innerHTML = '<div class="mono xs muted">loading…</div>';
  
  try {
    const pools = await fetch('/api/pools').then(r => r.json());
    if (!pools.length) {
      list.innerHTML = '<div class="mono xs muted">No saved pools found</div>';
      return;
    }
    
    list.innerHTML = '';
    for (const pool of pools) {
      const item = document.createElement('div');
      item.className = 'pb-load-item';
      item.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px">
          <div style="flex:1">
            <div style="font-weight:500">${esc(pool.name || 'Untitled')}</div>
            <div class="mono xs muted">${pool.tree?.length || 0} pools</div>
          </div>
          <button class="ghost-btn xs pb-delete-pool" data-id="${esc(pool.id)}" title="delete">🗑</button>
        </div>
      `;
      
      // Load pool on click (but not on delete button)
      item.addEventListener('click', async (e) => {
        if (e.target.classList.contains('pb-delete-pool')) return;
        currentPoolId = pool.id;
        $('pb-pool-name').value = pool.name || '';
        tree = pool.tree || [];
        const hydrated = await hydrateTreeFromCache(tree);
        renderTree();
        renderDetail();
        history.replaceState(null, '', `?id=${encodeURIComponent(pool.id)}`);
        $('pb-load-overlay').classList.add('hidden');
        
        // Auto-save if hydration added data
        if (hydrated) {
          const payload = { name: pool.name, tree, id: currentPoolId };
          await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        }
      });
      
      // Delete button
      const deleteBtn = item.querySelector('.pb-delete-pool');
      deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete pool "${pool.name || 'Untitled'}"?`)) return;
        
        deleteBtn.textContent = '⏳';
        deleteBtn.disabled = true;
        try {
          const res = await fetch(`/api/pools/${pool.id}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('Delete failed');
          await loadPoolList(); // Refresh list
        } catch (err) {
          alert('Delete failed: ' + err.message);
          deleteBtn.textContent = '🗑';
          deleteBtn.disabled = false;
        }
      });
      
      list.appendChild(item);
    }
  } catch (e) {
    list.innerHTML = `<div class="mono xs muted">Error: ${esc(e.message)}</div>`;
  }
}

$('pb-load-close').addEventListener('click', () => {
  $('pb-load-overlay').classList.add('hidden');
});
$('pb-load-overlay').addEventListener('click', e => {
  if (e.target === $('pb-load-overlay')) $('pb-load-overlay').classList.add('hidden');
});

/* ── compose ──────────────────────────────────────────────────── */
let selectedPools = new Set();

$('pb-compose-btn').addEventListener('click', async () => {
  $('pb-compose-overlay').classList.remove('hidden');
  selectedPools.clear();
  await loadComposeList();
});

async function loadComposeList() {
  const list = $('pb-compose-list');
  list.innerHTML = '<div class="mono xs muted">loading…</div>';
  
  try {
    const pools = await fetch('/api/pools').then(r => r.json());
    if (!pools.length) {
      list.innerHTML = '<div class="mono xs muted">No saved pools found</div>';
      return;
    }
    
    list.innerHTML = '';
    for (const pool of pools) {
      const item = document.createElement('div');
      item.className = 'pb-compose-item';
      item.dataset.id = pool.id;
      item.innerHTML = `
        <div class="pb-compose-checkbox"></div>
        <div style="flex:1">
          <div style="font-weight:500">${esc(pool.name || 'Untitled')}</div>
          <div class="mono xs muted">${pool.tree?.length || 0} pools</div>
        </div>
      `;
      
      item.addEventListener('click', () => {
        if (selectedPools.has(pool.id)) {
          selectedPools.delete(pool.id);
          item.classList.remove('selected');
        } else {
          selectedPools.add(pool.id);
          item.classList.add('selected');
        }
      });
      
      list.appendChild(item);
    }
  } catch (e) {
    list.innerHTML = `<div class="mono xs muted">Error: ${esc(e.message)}</div>`;
  }
}

$('pb-compose-merge').addEventListener('click', async () => {
  if (selectedPools.size === 0) {
    alert('Select at least one pool to merge');
    return;
  }
  
  const btn = $('pb-compose-merge');
  btn.textContent = 'merging…';
  btn.disabled = true;
  
  try {
    const pools = await fetch('/api/pools').then(r => r.json());
    
    for (const poolId of selectedPools) {
      const pool = pools.find(p => p.id === poolId);
      if (!pool || !pool.tree) continue;
      
      // Deep clone and merge the tree
      for (const node of pool.tree) {
        const cloned = JSON.parse(JSON.stringify(node));
        // Regenerate IDs to avoid conflicts
        cloned.id = uid();
        if (cloned.children) {
          cloned.children = cloned.children.map(c => ({ ...c, id: uid() }));
        }
        tree.push(cloned);
      }
    }
    
    renderTree();
    renderDetail();
    $('pb-compose-overlay').classList.add('hidden');
    selectedPools.clear();
  } catch (e) {
    alert('Merge failed: ' + e.message);
  } finally {
    btn.textContent = 'merge selected';
    btn.disabled = false;
  }
});

$('pb-compose-close').addEventListener('click', () => {
  $('pb-compose-overlay').classList.add('hidden');
});
$('pb-compose-overlay').addEventListener('click', e => {
  if (e.target === $('pb-compose-overlay')) $('pb-compose-overlay').classList.add('hidden');
});

/* ── separate ─────────────────────────────────────────────────── */
let selectedNodes = new Set();

$('pb-separate-btn').addEventListener('click', () => {
  if (tree.length === 0) {
    alert('No pools to separate');
    return;
  }
  $('pb-separate-overlay').classList.remove('hidden');
  selectedNodes.clear();
  loadSeparateList();
});

function loadSeparateList() {
  const list = $('pb-separate-list');
  list.innerHTML = '';
  
  for (const node of tree) {
    const item = document.createElement('div');
    item.className = 'pb-separate-item';
    item.dataset.id = node.id;
    
    const mapCount = node.children?.length || 0;
    item.innerHTML = `
      <div class="pb-separate-checkbox"></div>
      <div style="flex:1">
        <div style="font-weight:500">${esc(node.name || 'Unnamed')}</div>
        <div class="mono xs muted">${mapCount} maps</div>
      </div>
    `;
    
    item.addEventListener('click', () => {
      if (selectedNodes.has(node.id)) {
        selectedNodes.delete(node.id);
        item.classList.remove('selected');
      } else {
        selectedNodes.add(node.id);
        item.classList.add('selected');
      }
    });
    
    list.appendChild(item);
  }
}

$('pb-separate-extract').addEventListener('click', async () => {
  if (selectedNodes.size === 0) {
    alert('Select at least one pool to extract');
    return;
  }
  
  const btn = $('pb-separate-extract');
  btn.textContent = 'extracting…';
  btn.disabled = true;
  
  try {
    const poolName = $('pb-pool-name').value.trim() || 'Untitled Pool';
    const count = selectedNodes.size;
    
    for (const nodeId of selectedNodes) {
      const node = findNode(tree, nodeId);
      if (!node) continue;
      
      // Create a new saved pool with just this node
      const newPool = {
        name: `${poolName} - ${node.name || 'Unnamed'}`,
        tree: [JSON.parse(JSON.stringify(node))]
      };
      
      const res = await fetch('/api/pools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPool)
      });
      
      if (!res.ok) throw new Error('Failed to save extracted pool');
    }
    
    // Remove extracted nodes from current tree
    tree = tree.filter(n => !selectedNodes.has(n.id));
    
    renderTree();
    renderDetail();
    $('pb-separate-overlay').classList.add('hidden');
    selectedNodes.clear();
    
    alert(`Extracted ${count} pool(s) and saved separately`);
  } catch (e) {
    alert('Extract failed: ' + e.message);
  } finally {
    btn.textContent = 'extract selected';
    btn.disabled = false;
  }
});

$('pb-separate-close').addEventListener('click', () => {
  $('pb-separate-overlay').classList.add('hidden');
});
$('pb-separate-overlay').addEventListener('click', e => {
  if (e.target === $('pb-separate-overlay')) $('pb-separate-overlay').classList.add('hidden');
});


/* ── save ────────────────────────────────────────────────────── */
let currentPoolId = null;

// load pool from ?id= query param if present
(async () => {
  const id = new URLSearchParams(location.search).get('id');
  if (!id) return;
  try {
    const pools = await fetch('/api/pools').then(r => r.json());
    const pool = pools.find(p => p.id === id);
    if (!pool) return;
    currentPoolId = pool.id;
    $('pb-pool-name').value = pool.name || '';
    tree = pool.tree || [];
    const hydrated = await hydrateTreeFromCache(tree);
    renderTree();
    renderDetail();
    
    // Auto-save if hydration added data
    if (hydrated) {
      const payload = { name: pool.name, tree, id: currentPoolId };
      await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    }
  } catch (_) {}
})();

async function hydrateTreeFromCache(nodes, parentMods = '') {
  const promises = [];
  let didFetch = false;
  
  for (const node of nodes) {
    const isPool = node.type === 'pool' || node.type === 'modpool';
    
    if (node.type === 'map' && node.bid) {
      const needsHydration = node.ar === undefined;
      const mods = node.mods || parentMods;
      const modsKey = mods || 'NM';
      
      // Initialize SR cache if needed
      if (!node.srCache) node.srCache = {};
      
      // Only fetch if we don't have the SR cached
      const needsModdedSR = mods && mods !== 'NM' && !node.srCache[modsKey];
      
      if (needsHydration || needsModdedSR) {
        didFetch = true;
        promises.push((async () => {
          try {
            // Fetch base data if needed
            if (needsHydration) {
              const data = await fetch(`/api/beatmap/${node.bid}`).then(r => r.json());
              node.title = data.title || node.title;
              node.diff = data.diff || node.diff;
              node.len = data.len || node.len;
              node.ar = data.ar ?? 0;
              node.od = data.od ?? 0;
              node.cs = data.cs ?? 0;
              node.srCache['NM'] = data.stars;
            }
            
            // Fetch modded SR if not cached
            if (needsModdedSR) {
              const attrsRes = await fetch(`/api/beatmap/${node.bid}/attributes?mods=${encodeURIComponent(mods)}`);
              if (attrsRes.ok) {
                const attrs = await attrsRes.json();
                node.srCache[modsKey] = attrs.star_rating;
              }
            }
          } catch (e) {
            console.error(`Hydration error for ${node.bid}:`, e);
          }
        })());
      }
      
      // Always set stars from cache (or use existing if cache empty)
      if (node.srCache[modsKey]) {
        node.stars = node.srCache[modsKey];
      } else if (!node.stars && node.srCache['NM']) {
        node.stars = node.srCache['NM'];
      }
    }
    
    if (node.children) {
      const mods = isPool ? (node.mods || parentMods) : parentMods;
      const childResult = hydrateTreeFromCache(node.children, mods);
      promises.push(childResult);
      childResult.then(fetched => { if (fetched) didFetch = true; });
    }
  }
  
  await Promise.all(promises);
  return didFetch;
}

$('pb-save-btn').addEventListener('click', async () => {
  const name = $('pb-pool-name').value.trim() || 'Untitled Pool';
  const btn = $('pb-save-btn');
  btn.textContent = 'saving…';
  btn.disabled = true;
  try {
    const payload = { name, tree, ...(currentPoolId ? { id: currentPoolId } : {}) };
    const res  = await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.status);
    currentPoolId = data.id;
    history.replaceState(null, '', `?id=${encodeURIComponent(data.id)}`);
    btn.textContent = 'saved ✓';
    setTimeout(() => { btn.textContent = 'save pool'; btn.disabled = false; }, 1500);
  } catch (e) {
    alert('Save failed: ' + e.message);
    btn.textContent = 'save pool';
    btn.disabled = false;
  }
});

/* ── toolbar buttons ─────────────────────────────────────────── */
$('pb-add-pool-btn').addEventListener('click', addTopLevelPool);
$('pb-add-map-btn').addEventListener('click', addTopLevelMap);

/* ── init ────────────────────────────────────────────────────── */
renderTree();
renderDetail();
