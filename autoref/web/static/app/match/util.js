'use strict';

export function formatEta(seconds) {
  if (seconds == null || seconds === 0) return '—';
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
