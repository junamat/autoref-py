import { $, esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { findNode } from '../tree.js';
import { rerender } from '../render/index.js';

export function loadSeparateList() {
  const list = $('pb-separate-list');
  list.innerHTML = '';
  
  for (const node of state.tree) {
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
      if (state.selectedNodes.has(node.id)) {
        state.selectedNodes.delete(node.id);
        item.classList.remove('selected');
      } else {
        state.selectedNodes.add(node.id);
        item.classList.add('selected');
      }
    });
    
    list.appendChild(item);
  }
}

export function wireSeparate() {
  $('pb-separate-btn').addEventListener('click', () => {
    if (state.tree.length === 0) {
      alert('No pools to separate');
      return;
    }
    $('pb-separate-overlay').classList.remove('hidden');
    state.selectedNodes.clear();
    loadSeparateList();
  });

  $('pb-separate-extract').addEventListener('click', async () => {
    if (state.selectedNodes.size === 0) {
      alert('Select at least one pool to extract');
      return;
    }
    
    const btn = $('pb-separate-extract');
    btn.textContent = 'extracting…';
    btn.disabled = true;
    
    try {
      const poolName = $('pb-pool-name').value.trim() || 'Untitled Pool';
      const count = state.selectedNodes.size;
      
      for (const nodeId of state.selectedNodes) {
        const node = findNode(state.tree, nodeId);
        if (!node) continue;
        
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
      
      state.tree = state.tree.filter(n => !state.selectedNodes.has(n.id));
      
      rerender();
      $('pb-separate-overlay').classList.add('hidden');
      state.selectedNodes.clear();
      
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
}
