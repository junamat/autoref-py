'use strict';

export const state = {
  currentMethod: 'zscore',
  methodsReady: false,
  filterOptions: null,
  lastDefaultsPool: undefined,
  extrasLoaded: false,
  standingsLoaded: false,
  resultsLoaded: false,
  teamPerfLoaded: false,
  mappoolLoaded: false,
  context: null,
  lastParams: {},
};

export function invalidateTabs() {
  state.extrasLoaded = false;
  state.standingsLoaded = false;
  state.resultsLoaded = false;
  state.teamPerfLoaded = false;
  state.mappoolLoaded = false;
}

export function tabAffects(tab, changed) {
  const deps = {
    performances: ['method', 'count_failed', 'aggregate', 'filter'],
    mappool: ['count_failed', 'filter'],
    results: ['method', 'count_failed', 'aggregate', 'filter'],
    standings: ['count_failed', 'best_only', 'filter'],
    extras: ['count_failed', 'filter'],
    teamPerf: ['count_failed', 'filter'],
  };
  const tabDeps = deps[tab] || [];
  return changed.some(c => tabDeps.includes(c));
}
