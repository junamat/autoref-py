'use strict';

export const $ = (id) => document.getElementById(id);

export function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function fetchJson(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  return res.json();
}

export function activeVal(groupId) {
  return document.querySelector(`#${groupId} .active`)?.dataset.val;
}

export function isLightTheme() {
  return document.body.classList.contains('light');
}
