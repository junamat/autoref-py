import { $ } from '/static/shared/util.js';
import { state } from '../state.js';
import { findNodeByName } from '../tree.js';
import { inferModsFromName } from '../constants.js';
import { uid } from '../utils.js';
import { rerender } from '../render/index.js';

export function wireImport() {
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
      const urlMatch = line.match(/\/b(?:eatmaps)?\/(\d+)/);
      const parts = line.split(/\s+/);
      const bid = urlMatch ? urlMatch[1] : parts[0].replace(/\D/g, '');
      const pool = parts[1] || defaultPool;
      return { bid, pool };
    }).filter(e => e.bid);

    const beatmapData = {};
    for (const { bid } of entries) {
      if (beatmapData[bid]) continue;
      try {
        const res = await fetch(`/api/beatmap/${bid}`);
        if (res.ok) {
          beatmapData[bid] = await res.json();
        }
      } catch (e) {
        console.error(`Failed to fetch beatmap ${bid}:`, e);
      }
    }

    for (const { bid, pool: poolName } of entries) {
      let poolNode = findNodeByName(state.tree, poolName);
      if (!poolNode) {
        const inferredMods = inferModsFromName(poolName);
        poolNode = {
          id: uid(),
          type: inferredMods ? 'modpool' : 'pool',
          name: poolName,
          mods: inferredMods || '',
          winCon: 'score_v2', open: true, children: [],
        };
        state.tree.push(poolNode);
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

    rerender();
    $('pb-import-overlay').classList.add('hidden');
    $('pb-import-textarea').value = '';
    btn.textContent = 'lookup & import';
    btn.disabled = false;
  });
}
