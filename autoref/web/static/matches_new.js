'use strict';

import { wireQuickstart, loadPools, loadSettings, loadTemplates } from '/static/app/landing/quickstart.js';

if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('light');
  localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
});

wireQuickstart({
  onSuccess(data) {
    if (data.status === 'scheduled') {
      location.href = '/';
    } else {
      location.href = '/match/' + data.id;
    }
  },
});

loadSettings();
loadPools();
loadTemplates();
