import { $, esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { uid } from '../utils.js';
import { rerender } from '../render/index.js';

export async function loadComposeList() {
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
        if (state.selectedPools.has(pool.id)) {
          state.selectedPools.delete(pool.id);
          item.classList.remove('selected');
        } else {
          state.selectedPools.add(pool.id);
          item.classList.add('selected');
        }
      });
      
      list.appendChild(item);
    }
  } catch (e) {
    list.innerHTML = `<div class="mono xs muted">Error: ${esc(e.message)}</div>`;
  }
}

export function wireCompose() {
  $('pb-compose-btn').addEventListener('click', async () => {
    $('pb-compose-overlay').classList.remove('hidden');
    state.selectedPools.clear();
    await loadComposeList();
  });

  $('pb-compose-merge').addEventListener('click', async () => {
    if (state.selectedPools.size === 0) {
      alert('Select at least one pool to merge');
      return;
    }
    
    const btn = $('pb-compose-merge');
    btn.textContent = 'merging…';
    btn.disabled = true;
    
    try {
      const pools = await fetch('/api/pools').then(r => r.json());
      
      for (const poolId of state.selectedPools) {
        const pool = pools.find(p => p.id === poolId);
        if (!pool || !pool.tree) continue;
        
        for (const node of pool.tree) {
          const cloned = JSON.parse(JSON.stringify(node));
          cloned.id = uid();
          if (cloned.children) {
            cloned.children = cloned.children.map(c => ({ ...c, id: uid() }));
          }
          state.tree.push(cloned);
        }
      }
      
      rerender();
      $('pb-compose-overlay').classList.add('hidden');
      state.selectedPools.clear();
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
}
