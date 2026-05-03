'use strict';

export const appState = {
  mode: 'off', phase: null, wins: [0, 0],
  team_names: ['Team A', 'Team B'], teams: [],
  best_of: 1, maps: [], events: [],
  pending_proposal: null, ref_name: null,
  room_id: null,
};

export const nav = { currentMatchId: null };

export const sockets = { ws: null, landingWs: null };
