import { $, esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { fmtTime } from '../utils.js';
import { totalMaps, totalLen } from '../tree.js';
import { rerender } from './index.js';
import { addMapToPool } from '../ops.js';

export function updateStats() {
  $('pb-stat-maps').textContent = totalMaps(state.tree);
  $('pb-stat-time').textContent = fmtTime(totalLen(state.tree));
}

export function renderTree() {
  const container = $('pb-tree');
  container.innerHTML = '';
  renderNodes(state.tree, container, 0);
  updateStats();
}

function renderNodes(nodes, container, depth) {
  for (const node of nodes) {
    const isPool = node.type !== 'map';
    const isSelected = node.id === state.selectedId;
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
        node.open = !node.open;
      }
      state.selectedId = node.id;
      rerender();
    });

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
