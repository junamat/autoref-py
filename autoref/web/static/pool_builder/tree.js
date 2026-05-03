export function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n;
    if (n.children) {
      const found = findNode(n.children, id);
      if (found) return found;
    }
  }
  return null;
}

export function findParent(nodes, id, parent = null) {
  for (const n of nodes) {
    if (n.id === id) return parent;
    if (n.children) {
      const found = findParent(n.children, id, n);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

export function getEffectiveMods(node, stateTree) {
  if (node.type !== 'map') return node.mods || '';
  if (node.mods && node.mods !== 'inherit' && node.mods !== '') return node.mods;
  const parent = findParent(stateTree, node.id);
  return parent?.mods || '';
}

export function removeNode(nodes, id) {
  for (let i = 0; i < nodes.length; i++) {
    if (nodes[i].id === id) { nodes.splice(i, 1); return true; }
    if (nodes[i].children && removeNode(nodes[i].children, id)) return true;
  }
  return false;
}

export function countMaps(node) {
  if (node.type === 'map') return 1;
  return (node.children || []).reduce((s, c) => s + countMaps(c), 0);
}

export function sumLen(node) {
  if (node.type === 'map') return node.len || 0;
  return (node.children || []).reduce((s, c) => s + sumLen(c), 0);
}

export function totalMaps(tree) { return tree.reduce((s, n) => s + countMaps(n), 0); }
export function totalLen(tree)  { return tree.reduce((s, n) => s + sumLen(n), 0); }

export function findNodeByName(nodes, name) {
  for (const n of nodes) {
    if (n.name === name) return n;
    if (n.children) {
      const found = findNodeByName(n.children, name);
      if (found) return found;
    }
  }
  return null;
}
