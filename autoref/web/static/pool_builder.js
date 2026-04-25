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
const MOD_OPTIONS    = ['NM', 'HD', 'HR', 'DT', 'FL', 'EZ', 'FM', 'HDHR', 'HDDT'];

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
  card.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">
      <div>
        <div class="pb-beatmap-title">${esc(node.title || '—')}</div>
        <div class="pb-beatmap-sub">${esc(node.diff || '—')} · ${fmtTime(node.len)}</div>
      </div>
      <span class="pb-stars">★${node.stars || '?'}</span>
    </div>
    <div class="pb-beatmap-bid">beatmap #${esc(node.bid || '—')}</div>
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
    <button class="ghost-btn" id="det-move-btn" style="flex:1">move to pool…</button>
    <button class="ghost-btn" id="det-remove-btn" style="border-color:var(--red);color:var(--red)">remove</button>
  `;
  body.appendChild(actions);

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
  input.addEventListener('change', () => { node.mods = input.value.trim().toUpperCase(); renderTree(); });
  wrap.appendChild(input);

  // quick-pick chips
  const chips = document.createElement('div');
  chips.className = 'pb-toggle-row';
  const quickOpts = noneLabel ? ['', ...MOD_OPTIONS] : MOD_OPTIONS;
  for (const m of quickOpts) {
    const btn = document.createElement('div');
    btn.className = 'pb-toggle-opt';
    btn.textContent = m || 'NM';
    btn.addEventListener('click', () => {
      node.mods = m;
      input.value = m;
      renderTree();
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

  // Group by pool name, create pools if needed, add maps
  for (const { bid, pool: poolName } of entries) {
    let poolNode = findNodeByName(tree, poolName);
    if (!poolNode) {
      poolNode = { id: uid(), type: 'pool', name: poolName, mods: '', winCon: 'score_v2', open: true, children: [] };
      tree.push(poolNode);
    }
    const mapNode = {
      id: uid(), type: 'map',
      code: `${poolName}${(poolNode.children || []).length + 1}`,
      bid,
      title: `beatmap #${bid}`, diff: '', len: 0, stars: 0,
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
  function collectMaps(nodes) {
    for (const n of nodes) {
      if (n.type === 'map') {
        if (n.bid) lines.push(`${n.bid} ${n.code || ''}`);
      } else if (n.children) {
        collectMaps(n.children);
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
    renderTree();
    renderDetail();
  } catch (_) {}
})();

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
