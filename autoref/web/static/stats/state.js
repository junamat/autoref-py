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
    performances: ['method', 'aggregate', 'filter'],
    mappool: ['filter'],
    results: ['method', 'aggregate', 'filter'],
    standings: ['best_only', 'filter'],
    extras: ['filter'],
    teamPerf: ['filter'],
  };
  const tabDeps = deps[tab] || [];
  return changed.some(c => tabDeps.includes(c));
}
