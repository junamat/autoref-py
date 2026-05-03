import { $ } from '/static/shared/util.js';
import { state } from '../state.js';

export async function ensureMethodsLoaded() {
  if (state.availableMethods.length) return;
  try {
    const res = await fetch('/api/stats/filters');
    if (!res.ok) return;
    const data = await res.json();
    state.availableMethods = data.methods || [];
  } catch (_) {}
}

export function populateMethodSelect(selectId, current) {
  const sel = $(selectId);
  const head = sel.querySelector('option[value=""]');
  sel.innerHTML = '';
  if (head) sel.appendChild(head);
  for (const m of state.availableMethods) {
    const opt = document.createElement('option');
    opt.value = m.key;
    opt.textContent = m.label;
    if (m.key === current) opt.selected = true;
    sel.appendChild(opt);
  }
  if (!current) sel.value = '';
}

export function wireStatsDefaults() {
  $('pb-stats-cfg-btn').addEventListener('click', async () => {
    await ensureMethodsLoaded();
    const d = state.currentStatsDefaults || {};
    populateMethodSelect('pb-cfg-qualifier-method', d.qualifier_method || '');
    populateMethodSelect('pb-cfg-method', d.method || '');
    $('pb-cfg-count-failed').value = d.count_failed === undefined ? '' : String(d.count_failed);
    $('pb-cfg-aggregate').value = d.aggregate || '';
    $('pb-stats-cfg-overlay').classList.remove('hidden');
  });

  $('pb-stats-cfg-close').addEventListener('click', () => {
    $('pb-stats-cfg-overlay').classList.add('hidden');
  });

  $('pb-stats-cfg-apply').addEventListener('click', () => {
    const out = {};
    const qm = $('pb-cfg-qualifier-method').value;
    const m  = $('pb-cfg-method').value;
    const cf = $('pb-cfg-count-failed').value;
    const ag = $('pb-cfg-aggregate').value;
    if (qm) out.qualifier_method = qm;
    if (m)  out.method = m;
    if (cf !== '') out.count_failed = cf === 'true';
    if (ag) out.aggregate = ag;
    state.currentStatsDefaults = out;
    $('pb-stats-cfg-overlay').classList.add('hidden');
  });
}
