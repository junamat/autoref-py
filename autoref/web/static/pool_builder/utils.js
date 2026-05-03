export function fmtTime(s) {
  if (!s) return '0:00';
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function uid() {
  return Math.random().toString(36).slice(2, 9);
}

export function getAdjustedLength(baseLength, mods) {
  if (!mods) return baseLength;
  const modsUpper = mods.toUpperCase();
  if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
    return Math.round(baseLength / 1.5);
  }
  if (modsUpper.includes('HT')) {
    return Math.round(baseLength / 0.75);
  }
  return baseLength;
}

export function getAdjustedAR(baseAR, mods) {
  if (!mods) return baseAR;
  const modsUpper = mods.toUpperCase();
  let ar = baseAR;
  
  if (modsUpper.includes('EZ')) ar *= 0.5;
  if (modsUpper.includes('HR')) ar = Math.min(10, ar * 1.4);
  
  if (modsUpper.includes('DT') || modsUpper.includes('NC') || modsUpper.includes('HT')) {
    let ms;
    if (ar > 5) {
      ms = 1200 - (ar - 5) * 150;
    } else {
      ms = 1200 + (5 - ar) * 120;
    }
    
    if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
      ms *= (2/3);
    } else if (modsUpper.includes('HT')) {
      ms *= (4/3);
    }
    
    if (ms < 300) {
      ar = 11;
    } else if (ms < 1200) {
      ar = 5 + (1200 - ms) / 150;
    } else {
      ar = 5 - (ms - 1200) / 120;
    }
  }
  
  return Math.round(ar * 100) / 100;
}

export function getAdjustedOD(baseOD, mods) {
  if (!mods) return baseOD;
  const modsUpper = mods.toUpperCase();
  let od = baseOD;
  
  if (modsUpper.includes('HR')) od = Math.min(10, od * 1.4);
  if (modsUpper.includes('EZ')) od *= 0.5;
  
  if (modsUpper.includes('DT') || modsUpper.includes('NC')) {
    const ms = 79 - od * 6 + 0.5;
    const adjustedMs = ms * (2/3) + 0.33;
    od = (79 - adjustedMs + 0.5) / 6;
  }
  if (modsUpper.includes('HT')) {
    const ms = 79 - od * 6 + 0.5;
    const adjustedMs = ms * (4/3) + 0.66;
    od = (79 - adjustedMs + 0.5) / 6;
  }
  
  return Math.floor(Math.max(0, Math.min(10, od)) * 10) / 10;
}

export function getAdjustedCS(baseCS, mods) {
  if (!mods) return baseCS;
  const modsUpper = mods.toUpperCase();
  let cs = baseCS;
  
  if (modsUpper.includes('HR')) cs = Math.min(10, cs * 1.3);
  if (modsUpper.includes('EZ')) cs *= 0.5;
  
  return Math.floor(Math.max(0, Math.min(10, cs)) * 10) / 10;
}

export function getAdjustedHP(baseHP, mods) {
  if (!mods) return baseHP;
  const modsUpper = mods.toUpperCase();
  let hp = baseHP;
  
  if (modsUpper.includes('HR')) hp = Math.min(10, hp * 1.4);
  if (modsUpper.includes('EZ')) hp *= 0.5;
  
  return Math.floor(Math.max(0, Math.min(10, hp)) * 10) / 10;
}
