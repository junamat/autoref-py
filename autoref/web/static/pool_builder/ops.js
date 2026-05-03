import { state } from './state.js';
import { uid } from './utils.js';
import { findNode, removeNode, totalMaps } from './tree.js';
import { rerender } from './render/index.js';

export function addTopLevelPool() {
  const node = { id: uid(), type: 'pool', name: 'New Pool', mods: '', winCon: 'score_v2', open: true, children: [] };
  state.tree.push(node);
  state.selectedId = node.id;
  rerender();
}

export function addSubPool(parentNode) {
  const node = { id: uid(), type: 'modpool', name: 'New Sub-Pool', mods: '', winCon: 'inherit', open: true, children: [] };
  parentNode.children = parentNode.children || [];
  parentNode.children.push(node);
  state.selectedId = node.id;
  rerender();
}

export function addMapToPool(poolId) {
  const pool = findNode(state.tree, poolId);
  if (!pool) return;
  const node = {
    id: uid(), type: 'map',
    code: `MAP${totalMaps(state.tree) + 1}`,
    bid: '', title: 'New Map', diff: '', len: 0, stars: 0,
    ar: 0, od: 0, cs: 0,
    tb: false, disallowed: false, mods: '', winCon: 'inherit',
  };
  pool.children = pool.children || [];
  pool.children.push(node);
  state.selectedId = node.id;
  rerender();
}

export function addTopLevelMap() {
  const sel = state.selectedId ? findNode(state.tree, state.selectedId) : null;
  const targetPool = sel && sel.type !== 'map' ? sel
    : state.tree.find(n => n.type !== 'map') || null;

  if (targetPool) {
    addMapToPool(targetPool.id);
  } else {
    const pool = { id: uid(), type: 'pool', name: 'NM', mods: '', winCon: 'score_v2', open: true, children: [] };
    state.tree.push(pool);
    addMapToPool(pool.id);
  }
}

export function showMoveDialog(node) {
  const pools = [];
  function collect(nodes) {
    for (const n of nodes) {
      if (n.type !== 'map' && n.id !== node.id) {
        pools.push({ id: n.id, name: n.name });
        if (n.children) collect(n.children);
      }
    }
  }
  collect(state.tree);
  if (!pools.length) { alert('No pools to move to.'); return; }
  const names = pools.map((p, i) => `${i + 1}. ${p.name}`).join('\n');
  const choice = prompt(`Move "${node.code || node.name}" to:\n${names}\n\nEnter number:`);
  const idx = parseInt(choice) - 1;
  if (isNaN(idx) || idx < 0 || idx >= pools.length) return;
  removeNode(state.tree, node.id);
  const target = findNode(state.tree, pools[idx].id);
  if (target) {
    target.children = target.children || [];
    target.children.push(node);
  }
  rerender();
}
