import { $ } from '/static/shared/util.js';
import { state } from './state.js';
import { hydrateTreeFromCache } from './hydrate.js';
import { rerender } from './render/index.js';

export function bootFromQuery() {
  (async () => {
    const id = new URLSearchParams(location.search).get('id');
    if (!id) return;
    try {
      const pools = await fetch('/api/pools').then(r => r.json());
      const pool = pools.find(p => p.id === id);
      if (!pool) return;
      state.currentPoolId = pool.id;
      $('pb-pool-name').value = pool.name || '';
      state.tree = pool.tree || [];
      state.currentStatsDefaults = pool.stats_defaults || {};
      const hydrated = await hydrateTreeFromCache(state.tree);
      rerender();
  
      if (hydrated) {
        const payload = { name: pool.name, tree: state.tree, id: state.currentPoolId, stats_defaults: state.currentStatsDefaults };
        await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      }
    } catch (_) {}
  })();
}

export function wireSave() {
  $('pb-save-btn').addEventListener('click', async () => {
    const name = $('pb-pool-name').value.trim() || 'Untitled Pool';
    const btn = $('pb-save-btn');
    btn.textContent = 'saving…';
    btn.disabled = true;
    try {
      const payload = { name, tree: state.tree, stats_defaults: state.currentStatsDefaults, ...(state.currentPoolId ? { id: state.currentPoolId } : {}) };
      const res  = await fetch('/api/pools', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.status);
      state.currentPoolId = data.id;
      history.replaceState(null, '', `?id=${encodeURIComponent(data.id)}`);
      btn.textContent = 'saved ✓';
      setTimeout(() => { btn.textContent = 'save pool'; btn.disabled = false; }, 1500);
    } catch (e) {
      alert('Save failed: ' + e.message);
      btn.textContent = 'save pool';
      btn.disabled = false;
    }
  });
}
