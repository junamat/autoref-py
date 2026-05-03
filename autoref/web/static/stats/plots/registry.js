'use strict';

export const SECTION_MAPPOOL = 'mappool';
export const SECTION_PERF = 'perf';

const _plots = [];

export function register(spec) {
  _plots.push(spec);
}

export function bySection(section) {
  return _plots.filter(p => p.section === section);
}

export function all() {
  return [..._plots];
}
