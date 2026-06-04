'use strict';

import {
  register,
  SECTION_MAP_ANALYSIS,
  SECTION_MATCHFLOW,
  SECTION_PLAYER,
  SECTION_TEAM,
  SECTION_META,
  SCOPE_QUALIFIERS,
  SCOPE_BRACKET,
} from './registry.js';
import { plotBlock } from './url.js';

register({
  name: 'tb_incidence',
  section: SECTION_MAP_ANALYSIS,
  scope: SCOPE_QUALIFIERS,
  condition: (context) => context.has_tb,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'tb_incidence', 'Tiebreaker incidence per pool');
  },
});

register({
  name: 'map_close_factor',
  section: SECTION_MAP_ANALYSIS,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'map_close_factor', 'Map closeness (blowout vs swing)');
  },
});

register({
  name: 'pick_and_win_rate',
  section: SECTION_MAP_ANALYSIS,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'pick_and_win_rate', 'Pick & win rate per map');
  },
});

register({
  name: 'first_pick_frequency',
  section: SECTION_MAP_ANALYSIS,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'first_pick_frequency', 'First-pick frequency (opener maps)');
  },
});

register({
  name: 'score_lead_trajectory',
  section: SECTION_MATCHFLOW,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'score_lead_trajectory', 'Score lead trajectory (drama envelope)');
  },
});

register({
  name: 'comeback_rate',
  section: SECTION_MATCHFLOW,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'comeback_rate', 'Comeback rate (trailing at half wins)');
  },
});

register({
  name: 'action_sankey',
  section: SECTION_MATCHFLOW,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'action_sankey', 'Action flow (top transitions)');
  },
});

register({
  name: 'player_mod_radar',
  section: SECTION_PLAYER,
  scope: SCOPE_QUALIFIERS,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'player_mod_radar', 'Player mod profile (mean z per bracket)');
  },
});

register({
  name: 'team_rank_distribution',
  section: SECTION_PLAYER,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'team_rank_distribution', 'Team rank distribution (carry vs support)');
  },
});

register({
  name: 'pp_vs_score_scatter',
  section: SECTION_PLAYER,
  scope: SCOPE_QUALIFIERS,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'pp_vs_score_scatter', 'PP vs score scatter (mod sanity)');
  },
});

register({
  name: 'pp_consistency_scatter',
  section: SECTION_PLAYER,
  scope: SCOPE_QUALIFIERS,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'pp_consistency_scatter', 'PP consistency scatter');
  },
});

register({
  name: 'team_pool_heatmap',
  section: SECTION_TEAM,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'team_pool_heatmap', 'Team x pool heatmap (strength matrix)');
  },
});

register({
  name: 'team_strategy_profile',
  section: SECTION_TEAM,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'team_strategy_profile', 'Team strategy profile (actions by mod)');
  },
});

register({
  name: 'team_score_variance',
  section: SECTION_TEAM,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'team_score_variance', 'Team score variance (streaky vs steady)');
  },
});

register({
  name: 'score_inflation_curve',
  section: SECTION_META,
  scope: SCOPE_QUALIFIERS,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'score_inflation_curve', 'Score inflation curve (meta progression)');
  },
});

register({
  name: 'mod_popularity_timeline',
  section: SECTION_META,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'mod_popularity_timeline', 'Mod popularity timeline (meta evolution)');
  },
});

register({
  name: 'fm_mod_combo_stack',
  section: SECTION_META,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'fm_mod_combo_stack', 'FM mod combo stack (choices per slot)');
  },
});

register({
  name: 'upset_rate_by_round',
  section: SECTION_META,
  scope: SCOPE_BRACKET,
  mount(host, ctx) {
    host.innerHTML = plotBlock(ctx, 'upset_rate_by_round', 'Upset rate by round (lower seed wins)');
  },
});
