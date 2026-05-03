import { $, esc } from '/static/shared/util.js';
import { state } from '../state.js';
import { hydrateTreeFromCache } from '../hydrate.js';
import { rerender } from '../render/index.js';

export async function loadPoolList() {
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
      
      item.addEventListener('click', async (e) => {
        if (e.target.classList.contains('pb-delete-pool')) return;
        state.currentPoolId = pool.id;
        $('pb-pool-name').value = pool.name || '';
        state.tree = pool.tree || [];
        state.currentStatsDefaults = pool.stats_defaults || {};
        const hydrated = await hydrateTreeFromCache(state.tree);
        rerender();
        history.replaceState(null, '', `?id=${encodeURIComponent(pool.id)}`);
        $('pb-load-overlay').classList.add('hidden');

        if (hydrated) {
          const payload = { name: pool.name, tree: state.tree, id: state.currentPoolId, stats_defaults: state.currentStatsDefaults };
          await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        }
      });
      
      const deleteBtn = item.querySelector('.pb-delete-pool');
      deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete pool "${pool.name || 'Untitled'}"?`)) return;
        
        deleteBtn.textContent = '⏳';
        deleteBtn.disabled = true;
        try {
          const res = await fetch(`/api/pools/${pool.id}`, { method: 'DELETE' });
          if (!res.ok) throw new Error('Delete failed');
          await loadPoolList();
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

export function wireLoad() {
  $('pb-load-btn').addEventListener('click', async () => {
    $('pb-load-overlay').classList.remove('hidden');
    await loadPoolList();
  });

  $('pb-load-close').addEventListener('click', () => {
    $('pb-load-overlay').classList.add('hidden');
  });
  
  $('pb-load-overlay').addEventListener('click', e => {
    if (e.target === $('pb-load-overlay')) $('pb-load-overlay').classList.add('hidden');
  });
}
