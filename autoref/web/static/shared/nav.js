'use strict';

export async function initNav({ active = null } = {}) {
  if (localStorage.getItem('theme') === 'light') document.body.classList.add('light');
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('light');
      localStorage.setItem('theme', document.body.classList.contains('light') ? 'light' : 'dark');
    });
  }

  const account = await fetch('/api/account').then(r => r.ok ? r.json() : null).catch(() => null);
  const role = account?.role ?? null;
  const isPriv = role === 'host' || role === 'ref';
  const isHost = role === 'host';

  const container = document.getElementById('nav-links');
  if (!container) return { role, account };

  const parts = [];
  if (active !== 'stats')
    parts.push('<a href="/" class="ghost-btn" style="text-decoration:none">stats</a>');
  if (isPriv) {
    if (active !== 'ref')
      parts.push('<a href="/ref" class="ghost-btn" style="text-decoration:none">ref</a>');
    if (active !== 'pool-builder')
      parts.push('<a href="/pool-builder" class="ghost-btn" style="text-decoration:none">pool builder</a>');
    if (active !== 'settings')
      parts.push('<a href="/settings" class="ghost-btn" style="text-decoration:none">settings</a>');
    if (isHost && active !== 'users')
      parts.push('<a href="/users" class="ghost-btn" style="text-decoration:none">users</a>');
  }
  if (account) {
    if (active !== 'account')
      parts.push('<a href="/account" class="ghost-btn" style="text-decoration:none">account</a>');
  }

  container.innerHTML = parts.join('');
  return { role, account };
}
