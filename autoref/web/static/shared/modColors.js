'use strict';

const MOD_COLORS = {
  NM:   '#e2e8f0',
  HD:   '#fbbf24',
  HR:   '#ef4444',
  DT:   '#a78bfa',
  FL:   '#3b82f6',
  EZ:   '#22c55e',
  FM:   '#14b8a6',
  HDHR: '#f97316',
  HDDT: '#8b5cf6',
  TB:   '#f472b6',
  MISC: '#64748b',
};

let _customColors = {};

export function setCustomColors(colors) {
  _customColors = colors || {};
}

export function modGroup(code) {
  if (!code) return 'MISC';
  const s = String(code).toUpperCase();
  if (s === 'TB' || s.startsWith('TB')) return 'TB';
  for (const prefix of ['HDDT', 'HDHR']) {
    if (s.startsWith(prefix)) return prefix;
  }
  const two = s.slice(0, 2);
  return MOD_COLORS[two] ? two : 'MISC';
}

export function modsToGroup(mods) {
  if (!mods || !mods.length) return 'NM';
  const filtered = mods.filter(m => m.toUpperCase() !== 'NF');
  if (!filtered.length) return 'NM';
  const sorted = [...filtered].map(m => String(m).toUpperCase()).sort();
  const key = sorted.join('');
  if (key === 'HDDT' || key === 'DTHD') return 'HDDT';
  if (key === 'HDHR' || key === 'HRHD') return 'HDHR';
  if (sorted.length === 1) return sorted[0];
  return key || 'NM';
}

export function modColor(code, beatmapIdOrMods) {
  let beatmapId = null;
  let mods = null;
  if (Array.isArray(beatmapIdOrMods)) {
    mods = beatmapIdOrMods;
  } else {
    beatmapId = beatmapIdOrMods;
  }
  
  if (beatmapId != null && _customColors[String(beatmapId)]) {
    return _customColors[String(beatmapId)];
  }
  
  if (mods && mods.length) {
    const group = modsToGroup(mods);
    return MOD_COLORS[group] || MOD_COLORS.MISC;
  }
  
  if (code) {
    const group = modGroup(code);
    if (group !== 'MISC') {
      return MOD_COLORS[group] || MOD_COLORS.MISC;
    }
  }
  
  return MOD_COLORS.MISC;
}

export { MOD_COLORS };
