import { $ } from '/static/shared/util.js';
import { state } from '../state.js';

export function wireExport() {
  $('pb-export-btn').addEventListener('click', () => {
    const name = $('pb-pool-name').value.trim() || 'pool';
    const lines = [];
    function collectMaps(nodes, poolName = '') {
      for (const n of nodes) {
        if (n.type === 'map') {
          if (n.bid) lines.push(`${n.bid} ${poolName}`);
        } else if (n.children) {
          collectMaps(n.children, n.name || poolName);
        }
      }
    }
    collectMaps(state.tree);
    const text = lines.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${name.replace(/\s+/g, '_')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  });
}
