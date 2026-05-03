export async function hydrateTreeFromCache(nodes, parentMods = '') {
  const promises = [];
  let didFetch = false;
  
  for (const node of nodes) {
    const isPool = node.type === 'pool' || node.type === 'modpool';
    
    if (node.type === 'map' && node.bid) {
      const needsHydration = node.ar === undefined;
      const mods = node.mods || parentMods;
      const modsKey = mods || 'NM';
      
      if (!node.srCache) node.srCache = {};
      
      const needsModdedSR = mods && mods !== 'NM' && !node.srCache[modsKey];
      
      if (needsHydration || needsModdedSR) {
        didFetch = true;
        promises.push((async () => {
          try {
            if (needsHydration) {
              const data = await fetch(`/api/beatmap/${node.bid}`).then(r => r.json());
              node.title = data.title || node.title;
              node.diff = data.diff || node.diff;
              node.len = data.len || node.len;
              node.ar = data.ar ?? 0;
              node.od = data.od ?? 0;
              node.cs = data.cs ?? 0;
              node.setId = data.beatmapset_id;
              node.srCache['NM'] = data.stars;
            }
            
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
