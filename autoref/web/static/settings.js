(async () => {
  const form = document.getElementById('settings-form');
  const msg  = document.getElementById('settings-msg');

  function showMsg(text, cls) {
    msg.textContent = text;
    msg.className = cls;
    setTimeout(() => { msg.textContent = ''; msg.className = ''; }, 4000);
  }

  async function load() {
    const res = await fetch('/api/settings');
    const cfg = await res.json();

    for (const [k, v] of Object.entries(cfg)) {
      if (k.endsWith('_set')) continue;
      const el = form.elements[k];
      if (!el) continue;
      if (k === 'default_refs') {
        el.value = Array.isArray(v) ? v.join(', ') : v;
      } else {
        el.value = v;
      }
    }

    for (const secret of ['bancho_password', 'osu_client_secret']) {
      if (cfg[`${secret}_set`]) {
        const el = form.elements[secret];
        if (el) el.placeholder = '••• set';
      }
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {};
    const fd = new FormData(form);

    for (const [k, v] of fd.entries()) {
      if (k === 'default_refs') {
        data[k] = v.split(',').map(s => s.trim()).filter(Boolean);
      } else if (['port', 'default_best_of', 'default_team_mode',
                  'default_vs', 'default_ts', 'default_vs_team',
                  'timer_pick', 'timer_ban', 'timer_protect', 'timer_ready_up',
                  'timer_start_map', 'timer_force_start', 'timer_between_maps', 'timer_closing'].includes(k)) {
        data[k] = Number(v);
      } else {
        data[k] = v;
      }
    }

    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const json = await res.json();
      if (!res.ok) {
        const errs = json.detail?.errors || [json.detail || 'error'];
        showMsg(errs.join('; '), 'err');
        return;
      }
      if (json.requires_restart) {
        showMsg('saved — restart required for host/port change', 'warn');
      } else {
        showMsg('saved', 'ok');
      }
      await load();
    } catch (err) {
      showMsg('network error', 'err');
    }
  });

  await load();
})();
