import { $, esc } from '/static/shared/util.js';
import { modColor } from '/static/shared/modColors.js';
import { state } from '../state.js';
import { fmtTime } from '../utils.js';
import { totalMaps, totalLen, removeNode, findNode, isDescendant } from '../tree.js';
import { rerender } from './index.js';
import { addMapToPool, moveNodeBy } from '../ops.js';

export function updateStats() {
  $('pb-stat-maps').textContent = totalMaps(state.tree);
  $('pb-stat-time').textContent = fmtTime(totalLen(state.tree));
}

export function renderTree() {
  const container = $('pb-tree');
  container.innerHTML = '';
  renderNodes(state.tree, container, 0);
  if (state.tree.length) {
    const endStrip = document.createElement('div');
    endStrip.className = 'pb-tree-end-drop';
    wireEndDrop(endStrip);
    container.appendChild(endStrip);
  }
  updateStats();
}

function clearDropClasses(row) {
  row.classList.remove('drop-before', 'drop-inside', 'drop-after');
}

function clearAllDropClasses() {
  for (const r of document.querySelectorAll('.pb-tree-row, .pb-tree-end-drop')) {
    r.classList.remove('drop-before', 'drop-inside', 'drop-after', 'dragging');
    delete r.dataset.dropPos;
  }
}

function computeDropPos(e, row, node, draggedId) {
  const rect = row.getBoundingClientRect();
  const offset = e.clientY - rect.top;
  const h = rect.height || 1;
  let pos;
  if (node.type === 'map') {
    pos = offset < h / 2 ? 'before' : 'after';
  } else {
    if      (offset < h / 3)     pos = 'before';
    else if (offset < 2 * h / 3) pos = 'inside';
    else                          pos = 'after';
  }
  if (pos === 'inside' && draggedId) {
    const dragged = findNode(state.tree, draggedId);
    if (dragged && isDescendant(dragged, node.id)) {
      pos = offset < h / 2 ? 'before' : 'after';
    }
  }
  return pos;
}

function wireDrag(row, node) {
  row.draggable = true;

  row.addEventListener('dragstart', e => {
    e.stopPropagation();
    e.dataTransfer.setData('text/plain', node.id);
    e.dataTransfer.effectAllowed = 'move';
    row.classList.add('dragging');
  });

  row.addEventListener('dragend', () => {
    clearAllDropClasses();
  });

  row.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const draggingRow = document.querySelector('.pb-tree-row.dragging');
    const draggedId = draggingRow ? draggingRow.dataset.id : null;
    const pos = computeDropPos(e, row, node, draggedId);
    clearDropClasses(row);
    row.classList.add(`drop-${pos}`);
    row.dataset.dropPos = pos;
  });

  row.addEventListener('dragleave', e => {
    if (e.target === row) clearDropClasses(row);
  });

  row.addEventListener('drop', e => {
    e.preventDefault();
    e.stopPropagation();
    const draggedId = e.dataTransfer.getData('text/plain');
    const pos = row.dataset.dropPos || 'after';
    clearAllDropClasses();
    if (draggedId) moveNodeBy(draggedId, node.id, pos);
  });
}

function wireEndDrop(strip) {
  strip.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    strip.classList.add('drop-after');
  });
  strip.addEventListener('dragleave', () => strip.classList.remove('drop-after'));
  strip.addEventListener('drop', e => {
    e.preventDefault();
    const draggedId = e.dataTransfer.getData('text/plain');
    clearAllDropClasses();
    if (!draggedId || !state.tree.length) return;
    const last = state.tree[state.tree.length - 1];
    if (last.id === draggedId) return;
    moveNodeBy(draggedId, last.id, 'after');
  });
}

function renderNodes(nodes, container, depth) {
  for (const node of nodes) {
    const isPool = node.type !== 'map';
    const isSelected = node.id === state.selectedId;
    const defaultPoolColor = node.type === 'modpool' ? 'var(--yellow)' : 'var(--blue)';
    const poolColor = node.color || defaultPoolColor;
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
      ? `<span class="node-badge" style="border:1px solid ${modColor(node.mods)}44;color:${modColor(node.mods)}">${esc(node.mods)}</span>`
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
      <button class="row-del" title="delete" tabindex="-1">✕</button>
    `;

    row.addEventListener('click', e => {
      if (e.target.classList.contains('row-del')) return;
      if (isPool) {
        node.open = !node.open;
      }
      state.selectedId = node.id;
      rerender();
    });

    row.querySelector('.row-del').addEventListener('click', e => {
      e.stopPropagation();
      removeNode(state.tree, node.id);
      if (state.selectedId === node.id) state.selectedId = null;
      rerender();
    });

    wireDrag(row, node);

    container.appendChild(row);

    if (isPool && node.open && node.children) {
      renderNodes(node.children, container, depth + 1);

      const hint = document.createElement('div');
      hint.className = 'pb-add-hint';
      hint.style.paddingLeft = `${8 + indent + 16}px`;
      hint.style.padding = `2px 8px 2px ${8 + indent + 16}px`;
      hint.innerHTML = `<span>+ add map</span>`;
      hint.addEventListener('click', () => addMapToPool(node.id));
      container.appendChild(hint);
    }
  }
}
