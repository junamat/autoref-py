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
};

export function invalidateTabs() {
  state.extrasLoaded = false;
  state.standingsLoaded = false;
  state.resultsLoaded = false;
  state.teamPerfLoaded = false;
}
