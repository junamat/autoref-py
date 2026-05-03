export const WIN_CONDITIONS = ['score_v2', 'score', 'accuracy', 'combo'];
export const MOD_OPTIONS    = ['NM', 'HD', 'HR', 'DT', 'FL', 'EZ', 'FM', 'HDHR', 'HDDT'];
export const MOD_PREFIXES   = { NM: 'NM', HD: 'HD', HR: 'HR', DT: 'DT', FL: 'FL', EZ: 'EZ', FM: 'FM' };

export function inferModsFromName(name) {
  if (!name) return null;
  const prefix = name.slice(0, 2).toUpperCase();
  return MOD_PREFIXES[prefix] || null;
}
