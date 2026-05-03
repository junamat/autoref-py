'use strict';

import { esc, activeVal } from '/static/shared/util.js';
import { state } from '../state.js';
import { currentFilterParams } from '../filters.js';
import { renderPpTable, renderDiffTable, renderCarryTable } from '../tables/extras.js';

export async function loadExtras() {
  state.extrasLoaded = true;
  const countFailed = activeVal('cfg-failed') !== 'false';
  const params = new URLSearchParams({ count_failed: countFailed, ...currentFilterParams() });

  const closest = document.getElementById('extras-closest-wrap');
  const blowouts = document.getElementById('extras-blowouts-wrap');
  const carries = document.getElementById('extras-carries-wrap');
  const ppWrap = document.getElementById('extras-pp-wrap');
  const zppWrap = document.getElementById('extras-zpp-wrap');
  const wraps = [closest, blowouts, carries, ppWrap, zppWrap];
  wraps.forEach(w => { if (w) w.innerHTML = '<div class="empty-msg">loading…</div>'; });

  let data;
  try {
    const res = await fetch(`/api/stats/extras?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (e) {
    const msg = `<div class="empty-msg">error: ${esc(e.message)}</div>`;
    wraps.forEach(w => { if (w) w.innerHTML = msg; });
    return;
  }

  closest.innerHTML = renderDiffTable(data.closest_maps || [], 'closest');
  blowouts.innerHTML = renderDiffTable(data.biggest_blowouts || [], 'blowout');
  carries.innerHTML = renderCarryTable(data.biggest_carries || []);
  if (ppWrap) ppWrap.innerHTML = renderPpTable(data.highest_pp || [], 'pp');
  if (zppWrap) zppWrap.innerHTML = renderPpTable(data.highest_zpp || [], 'zpp');
}
