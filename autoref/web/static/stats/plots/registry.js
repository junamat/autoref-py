'use strict';

export const SECTION_MAPPOOL = 'mappool';
export const SECTION_MAP_ANALYSIS = 'map_analysis';
export const SECTION_PERF = 'perf';
export const SECTION_MATCHFLOW = 'matchflow';
export const SECTION_PLAYER = 'player';
export const SECTION_TEAM = 'team';
export const SECTION_META = 'meta';

export const SCOPE_QUALIFIERS = 'qualifiers';
export const SCOPE_BRACKET = 'bracket';

const _plots = [];

export function register(spec) {
  _plots.push(spec);
}

export function bySection(section, scope = null) {
  return _plots.filter(p => {
    if (p.section !== section) return false;
    if (scope === null) return true;
    // qualifiers scope shows qualifiers plots
    // bracket scope shows both qualifiers and bracket plots
    if (scope === SCOPE_QUALIFIERS) return p.scope === SCOPE_QUALIFIERS;
    if (scope === SCOPE_BRACKET) return true;
    return true;
  });
}

export function all() {
  return [..._plots];
}
