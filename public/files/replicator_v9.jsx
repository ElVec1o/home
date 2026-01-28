import React, { useState, useEffect, useCallback, useRef } from 'react';

/*
 * REPLICATOR v9
 * - Working cargo haulers
 * - Tutorial hints
 * - Better graphics
 * - File-based save/load
 */

// ═══════════════════════════════════════════════════════════════════════════════
// STYLES
// ═══════════════════════════════════════════════════════════════════════════════

const CSS = `
  html, body, #root { background: #04060a !important; margin: 0; min-height: 100vh; }
  * { box-sizing: border-box; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
  @keyframes glow { 0%,100% { box-shadow: 0 0 10px currentColor; } 50% { box-shadow: 0 0 20px currentColor; } }
  @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .pulse { animation: pulse 2s ease-in-out infinite; }
  .glow { animation: glow 2s ease-in-out infinite; }
  .float { animation: float 3s ease-in-out infinite; }
  .spin { animation: spin 10s linear infinite; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0a0e14; }
  ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
`;

// ═══════════════════════════════════════════════════════════════════════════════
// AUDIO
// ═══════════════════════════════════════════════════════════════════════════════

const audio = {
  ctx: null,
  init() {
    if (this.ctx) return;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.12;
    this.master.connect(this.ctx.destination);
  },
  play(freq, type = 'sine', dur = 0.1) {
    if (!this.ctx) this.init();
    const o = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    o.type = type;
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.1, this.ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
    o.connect(g).connect(this.master);
    o.start();
    o.stop(this.ctx.currentTime + dur);
  },
  click() { this.play(800, 'square', 0.03); },
  success() { [523, 659, 784].forEach((f, i) => setTimeout(() => this.play(f, 'sine', 0.2), i * 80)); },
  launch() { this.play(100, 'sawtooth', 0.4); setTimeout(() => this.play(200, 'sawtooth', 0.3), 100); },
  error() { this.play(200, 'square', 0.15); },
};

// ═══════════════════════════════════════════════════════════════════════════════
// PLANET SVG COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function Planet({ color, size = 48, rings, status, glow, children }) {
  const id = useRef(`p${Math.random().toString(36).slice(2)}`).current;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48">
      <defs>
        <radialGradient id={`${id}-grad`} cx="35%" cy="35%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.3" />
          <stop offset="40%" stopColor={color} />
          <stop offset="100%" stopColor="#000" stopOpacity="0.5" />
        </radialGradient>
        <filter id={`${id}-glow`}>
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        {/* Surface texture */}
        <pattern id={`${id}-texture`} width="8" height="8" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1" fill="#000" opacity="0.1" />
          <circle cx="6" cy="6" r="1.5" fill="#000" opacity="0.08" />
        </pattern>
      </defs>
      
      {/* Glow effect */}
      {glow && <circle cx="24" cy="24" r="22" fill={color} opacity="0.3" filter={`url(#${id}-glow)`} />}
      
      {/* Status ring */}
      <circle cx="24" cy="24" r="21" fill="none" strokeWidth="2"
        stroke={status === 'colony' ? '#22c55e' : status === 'surveyed' ? '#eab308' : '#1e3a5f'}
        strokeDasharray={status === 'unknown' ? '4,4' : 'none'} />
      
      {/* Planet body */}
      <circle cx="24" cy="24" r="18" fill={`url(#${id}-grad)`} />
      <circle cx="24" cy="24" r="18" fill={`url(#${id}-texture)`} />
      
      {/* Atmosphere rim */}
      <circle cx="24" cy="24" r="18" fill="none" stroke="#fff" strokeWidth="1" opacity="0.2" />
      
      {/* Saturn rings */}
      {rings && (
        <g>
          <ellipse cx="24" cy="24" rx="26" ry="6" fill="none" stroke={color} strokeWidth="4" opacity="0.4" />
          <ellipse cx="24" cy="24" rx="24" ry="5" fill="none" stroke="#fff" strokeWidth="1" opacity="0.3" />
        </g>
      )}
      
      {/* Status indicator */}
      {status === 'colony' && (
        <g>
          <circle cx="36" cy="12" r="7" fill="#04060a" />
          <circle cx="36" cy="12" r="5" fill="#22c55e" className="pulse" />
          <text x="36" y="15" textAnchor="middle" fontSize="8" fill="#fff">⌂</text>
        </g>
      )}
      {status === 'surveyed' && (
        <g>
          <circle cx="36" cy="12" r="5" fill="#eab308" />
          <text x="36" y="15" textAnchor="middle" fontSize="7" fill="#000">✓</text>
        </g>
      )}
      
      {children}
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SHIP SVG COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function ShipIcon({ type, size = 32, color = '#22d3ee' }) {
  const ships = {
    probe: (
      <svg width={size} height={size} viewBox="0 0 32 32">
        <defs>
          <linearGradient id="probe-grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <path d="M16 4 L8 24 L12 24 L14 18 L18 18 L20 24 L24 24 Z" fill="url(#probe-grad)" />
        <circle cx="16" cy="12" r="3" fill={color} opacity="0.8" />
        <circle cx="16" cy="12" r="1.5" fill="#fff" />
        <path d="M10 24 L12 28 M22 24 L20 28" stroke={color} strokeWidth="2" />
      </svg>
    ),
    hauler: (
      <svg width={size} height={size} viewBox="0 0 32 32">
        <defs>
          <linearGradient id="hauler-grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.2" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <rect x="6" y="10" width="20" height="12" rx="2" fill="url(#hauler-grad)" />
        <rect x="10" y="6" width="12" height="6" rx="1" fill={color} opacity="0.8" />
        <rect x="9" y="13" width="6" height="6" rx="1" fill="#04060a" opacity="0.5" />
        <rect x="17" y="13" width="6" height="6" rx="1" fill="#04060a" opacity="0.5" />
        <circle cx="10" cy="24" r="2" fill={color} />
        <circle cx="22" cy="24" r="2" fill={color} />
      </svg>
    ),
    seeder: (
      <svg width={size} height={size} viewBox="0 0 32 32">
        <defs>
          <linearGradient id="seeder-grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#fff" stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <path d="M16 2 L8 12 L8 24 L16 30 L24 24 L24 12 Z" fill="url(#seeder-grad)" />
        <path d="M16 6 L12 12 L12 20 L16 24 L20 20 L20 12 Z" fill={color} opacity="0.4" />
        <circle cx="16" cy="15" r="4" fill="#04060a" opacity="0.5" />
        <circle cx="16" cy="15" r="2" fill={color} />
      </svg>
    ),
  };
  return ships[type] || null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// STRUCTURE ICONS
// ═══════════════════════════════════════════════════════════════════════════════

function StructIcon({ type, size = 28 }) {
  const c = '#14b8a6';
  const icons = {
    solar: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <rect x="2" y="8" width="24" height="14" rx="1" fill={c} />
        <path d="M6 8 V22 M11 8 V22 M17 8 V22 M23 8 V22" stroke="#04060a" strokeWidth="0.5" opacity="0.3" />
        <rect x="12" y="22" width="4" height="4" fill={c} opacity="0.7" />
        <circle cx="14" cy="4" r="2" fill="#fbbf24" className="pulse" />
      </svg>
    ),
    drill: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <path d="M14 2 L10 10 L18 10 Z" fill={c} />
        <rect x="8" y="10" width="12" height="10" rx="1" fill={c} />
        <path d="M11 20 L14 28 L17 20" fill={c} opacity="0.8" />
        <circle cx="14" cy="15" r="2" fill="#04060a" opacity="0.4" />
      </svg>
    ),
    refinery: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <path d="M8 4 L8 10 L6 12 L6 24 L22 24 L22 12 L20 10 L20 4 Z" fill={c} />
        <ellipse cx="14" cy="5" rx="5" ry="2" fill={c} opacity="0.6" />
        <rect x="10" y="14" width="8" height="6" rx="1" fill="#04060a" opacity="0.3" />
      </svg>
    ),
    foundry: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <rect x="2" y="12" width="24" height="14" rx="1" fill={c} />
        <path d="M4 12 V6 L10 6 V12 M18 12 V6 L24 6 V12" fill={c} opacity="0.8" />
        <rect x="8" y="16" width="12" height="6" rx="1" fill="#04060a" opacity="0.3" />
        <circle cx="20" cy="8" r="2" fill="#f97316" className="pulse" />
      </svg>
    ),
    habitat: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <ellipse cx="14" cy="18" rx="12" ry="8" fill={c} />
        <path d="M2 18 Q14 4 26 18" fill={c} opacity="0.8" />
        <ellipse cx="14" cy="16" rx="4" ry="3" fill="#04060a" opacity="0.3" />
        <ellipse cx="14" cy="15" rx="2" ry="1.5" fill="#67e8f9" opacity="0.5" />
      </svg>
    ),
    reactor: (
      <svg width={size} height={size} viewBox="0 0 28 28">
        <circle cx="14" cy="14" r="12" fill={c} />
        <circle cx="14" cy="14" r="8" fill={c} opacity="0.6" />
        <circle cx="14" cy="14" r="4" fill="#22c55e" className="pulse" />
        <path d="M14 0 V6 M14 22 V28 M0 14 H6 M22 14 H28" stroke={c} strokeWidth="2" opacity="0.5" />
      </svg>
    ),
  };
  return icons[type] || null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// TUTORIAL HINTS
// ═══════════════════════════════════════════════════════════════════════════════

function getHint(state) {
  const { colonies, fleet, survey, sel } = state;
  const col = sel && colonies[sel];
  const ships = fleet.filter(s => !s.moving);
  const probes = ships.filter(s => s.type === 'probe');
  const haulers = ships.filter(s => s.type === 'hauler');
  const seeders = ships.filter(s => s.type === 'seeder');
  const surveyed = Object.entries(survey).filter(([_, v]) => v === 'surveyed');
  const colonyCount = Object.keys(colonies).length;

  if (!col) return null;

  // Power deficit
  const pwr = (col.bld.solar || 0) * 25 + (col.bld.reactor || 0) * 100;
  const use = Object.entries(col.bld).reduce((s, [k, v]) => {
    const costs = { drill: 10, refinery: 15, foundry: 20, habitat: 5 };
    return s + (costs[k] || 0) * v;
  }, 0);
  if (pwr < use) return { type: 'warning', text: '⚡ Power deficit! Build more Solar Arrays or a Reactor.' };

  // No drills
  if (!col.bld.drill) return { type: 'tip', text: '⛏ Build an Extractor to mine local resources.' };

  // No foundry
  if (!col.bld.foundry) return { type: 'tip', text: '🏭 Build a Foundry to construct spacecraft.' };

  // Has foundry but no ships
  if (col.bld.foundry && ships.length === 0) return { type: 'tip', text: '🚀 Build a Probe to explore unknown worlds!' };

  // Has probe, nothing surveyed yet
  if (probes.length > 0 && surveyed.length === 0) return { type: 'tip', text: '🔭 Launch your Probe to survey another planet or moon!' };

  // Has surveyed worlds but no seeder
  if (surveyed.length > 0 && seeders.length === 0 && colonyCount === 1) {
    return { type: 'tip', text: '🌱 Build a Seeder ship to colonize a surveyed world!' };
  }

  // Has seeder and surveyed worlds
  if (seeders.length > 0 && surveyed.length > 0) {
    return { type: 'tip', text: '🏠 Launch your Seeder to establish a new colony!' };
  }

  // Multiple colonies but no hauler
  if (colonyCount > 1 && haulers.length === 0) {
    return { type: 'tip', text: '📦 Build a Hauler to transport resources between colonies!' };
  }

  // Has hauler
  if (haulers.length > 0 && colonyCount > 1) {
    return { type: 'tip', text: '📦 Load cargo on your Hauler and send it to another colony!' };
  }

  return null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DATA
// ═══════════════════════════════════════════════════════════════════════════════

const WORLDS = [
  { id: 'mercury', name: 'Mercury', order: 1, col: '#a08070', res: ['fe', 'ti'], desc: 'Scorched world rich in metals' },
  { id: 'venus', name: 'Venus', order: 2, col: '#d4a030', res: ['c', 's'], desc: 'Toxic atmosphere, carbon-rich' },
  { id: 'earth', name: 'Earth', order: 3, col: '#4080b0', dead: true, desc: 'Destroyed by asteroid, 2247' },
  { id: 'moon', name: 'Luna', parent: 'earth', col: '#b0b0b0', res: ['fe', 'si', 'al', 'ti'], home: true, desc: 'Humanity\'s last foothold' },
  { id: 'mars', name: 'Mars', order: 4, col: '#d04020', res: ['fe', 'c', 'h2o'], desc: 'The red planet, water ice present' },
  { id: 'phobos', name: 'Phobos', parent: 'mars', col: '#705040', res: ['c', 'fe'], desc: 'Captured asteroid moon' },
  { id: 'deimos', name: 'Deimos', parent: 'mars', col: '#806050', res: ['c', 'si'], desc: 'Small outer moon' },
  { id: 'ceres', name: 'Ceres', order: 5, col: '#909090', res: ['h2o', 'c', 'pt'], desc: 'Dwarf planet, water-rich' },
  { id: 'jupiter', name: 'Jupiter', order: 6, col: '#d0a050', gas: true, desc: 'Gas giant - colonize moons' },
  { id: 'io', name: 'Io', parent: 'jupiter', col: '#e0c030', res: ['s', 'fe'], desc: 'Volcanic moon, sulfur deposits' },
  { id: 'europa', name: 'Europa', parent: 'jupiter', col: '#c0c0b0', res: ['h2o', 'si'], desc: 'Subsurface ocean world' },
  { id: 'ganymede', name: 'Ganymede', parent: 'jupiter', col: '#706050', res: ['fe', 'h2o', 'ti'], desc: 'Largest moon in system' },
  { id: 'callisto', name: 'Callisto', parent: 'jupiter', col: '#504540', res: ['h2o', 'c', 'fe'], desc: 'Ancient cratered surface' },
  { id: 'saturn', name: 'Saturn', order: 7, col: '#e0c070', gas: true, rings: true, desc: 'Ringed giant - colonize moons' },
  { id: 'titan', name: 'Titan', parent: 'saturn', col: '#d07020', res: ['c', 'n', 'ch4'], desc: 'Thick atmosphere, methane lakes' },
  { id: 'enceladus', name: 'Enceladus', parent: 'saturn', col: '#f0f0f0', res: ['h2o', 'n'], desc: 'Ice geysers, subsurface ocean' },
  { id: 'uranus', name: 'Uranus', order: 8, col: '#70c0c0', gas: true, desc: 'Ice giant - colonize moons' },
  { id: 'miranda', name: 'Miranda', parent: 'uranus', col: '#909090', res: ['h2o', 'c', 'u'], desc: 'Extreme terrain, uranium deposits' },
  { id: 'neptune', name: 'Neptune', order: 9, col: '#4060d0', gas: true, desc: 'Ice giant - colonize moons' },
  { id: 'triton', name: 'Triton', parent: 'neptune', col: '#a09080', res: ['n', 'ch4', 'u'], desc: 'Retrograde orbit, nitrogen geysers' },
  { id: 'pluto', name: 'Pluto', order: 10, col: '#c0b090', res: ['n', 'pt', 'u'], desc: 'Distant dwarf, platinum deposits' },
];

const RES = {
  fe: { n: 'Iron', c: '#e09050' },
  si: { n: 'Silicon', c: '#90a0b0' },
  al: { n: 'Aluminum', c: '#c0c8d0' },
  ti: { n: 'Titanium', c: '#60b0b0' },
  c: { n: 'Carbon', c: '#909090' },
  h2o: { n: 'Water', c: '#50a0e0' },
  n: { n: 'Nitrogen', c: '#80c0e0' },
  s: { n: 'Sulfur', c: '#e0b020' },
  ch4: { n: 'Methane', c: '#70e070' },
  pt: { n: 'Platinum', c: '#e0e0e8' },
  u: { n: 'Uranium', c: '#40e060' },
};

const SHIPS = {
  probe: { n: 'Probe', d: 'Surveys unknown worlds', c: { fe: 8, si: 4 }, spd: 10, cargo: 0 },
  hauler: { n: 'Hauler', d: 'Transports 100 units of cargo', c: { fe: 25, al: 12 }, spd: 5, cargo: 100 },
  seeder: { n: 'Seeder', d: 'Establishes new colonies', c: { fe: 50, al: 25, si: 15 }, spd: 3, cargo: 0 },
};

const BLDG = {
  solar: { n: 'Solar Array', d: 'Generates +25 kW power', c: { si: 8, al: 6 }, pwr: 25, use: 0 },
  drill: { n: 'Extractor', d: 'Mines local resources (10 kW)', c: { fe: 12, si: 4 }, pwr: 0, use: 10 },
  refinery: { n: 'Refinery', d: 'Doubles mining output (15 kW)', c: { fe: 20, al: 8 }, pwr: 0, use: 15 },
  foundry: { n: 'Foundry', d: 'Builds spacecraft (20 kW)', c: { fe: 35, al: 18, si: 8 }, pwr: 0, use: 20 },
  habitat: { n: 'Habitat', d: 'Houses +100 colonists (5 kW)', c: { al: 20, si: 12 }, pwr: 0, use: 5 },
  reactor: { n: 'Reactor', d: 'Generates +100 kW (for outer system)', c: { fe: 45, ti: 15, u: 8 }, pwr: 100, use: 0 },
};

const W = id => WORLDS.find(w => w.id === id);
const moons = p => WORLDS.filter(w => w.parent === p);

// ═══════════════════════════════════════════════════════════════════════════════
// SAVE/LOAD MENU MODAL
// ═══════════════════════════════════════════════════════════════════════════════

function SaveMenu({ onSave, onExport, onImport, fileInputRef, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
         onClick={onClose}>
      <div style={{ background: '#0c1018', border: '2px solid #1e3a5f', borderRadius: 8, padding: 24, width: 340 }}
           onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ margin: 0, color: '#fff', fontSize: 18 }}>💾 Save / Load</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#607080', fontSize: 24, cursor: 'pointer', lineHeight: 1 }}>×</button>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Quick Save */}
          <button onClick={onSave} style={{ 
            padding: '14px 18px', background: 'linear-gradient(180deg, #0f766e, #0a5550)', 
            border: '1px solid #14b8a6', borderRadius: 6, color: '#d0fff0', fontSize: 13, 
            fontWeight: 600, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>⚡</span>
              <div>
                <div>Quick Save</div>
                <div style={{ fontSize: 10, color: '#5eead4', fontWeight: 400, marginTop: 2 }}>Save to browser storage</div>
              </div>
            </div>
          </button>
          
          {/* Export to File */}
          <button onClick={onExport} style={{ 
            padding: '14px 18px', background: 'linear-gradient(180deg, #1e3a5f, #152a45)', 
            border: '1px solid #3b82f6', borderRadius: 6, color: '#bfdbfe', fontSize: 13, 
            fontWeight: 600, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>📁</span>
              <div>
                <div>Export to File</div>
                <div style={{ fontSize: 10, color: '#60a5fa', fontWeight: 400, marginTop: 2 }}>Download .json save file</div>
              </div>
            </div>
          </button>
          
          {/* Import from File */}
          <button onClick={() => fileInputRef.current?.click()} style={{ 
            padding: '14px 18px', background: 'linear-gradient(180deg, #422006, #351c05)', 
            border: '1px solid #d97706', borderRadius: 6, color: '#fde68a', fontSize: 13, 
            fontWeight: 600, cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 18 }}>📂</span>
              <div>
                <div>Import from File</div>
                <div style={{ fontSize: 10, color: '#fbbf24', fontWeight: 400, marginTop: 2 }}>Load .json save file</div>
              </div>
            </div>
          </button>
        </div>
        
        <p style={{ color: '#405060', fontSize: 10, marginTop: 16, textAlign: 'center' }}>
          File saves can be shared or backed up externally
        </p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// RESOURCE INFO MODAL
// ═══════════════════════════════════════════════════════════════════════════════

function ResourceInfo({ resId, onClose, survey }) {
  const res = RES[resId];
  const worldsWithRes = WORLDS.filter(w => w.res?.includes(resId) && !w.gas && !w.dead);
  
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}
         onClick={onClose}>
      <div style={{ background: '#0c1018', border: `2px solid ${res.c}`, borderRadius: 8, padding: 24, width: 420, maxHeight: '80vh', overflow: 'auto' }}
           onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: res.c, opacity: 0.8 }} />
            <h3 style={{ margin: 0, color: res.c, fontSize: 20 }}>{res.n}</h3>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#607080', fontSize: 24, cursor: 'pointer', lineHeight: 1 }}>×</button>
        </div>
        
        <p style={{ color: '#a0b0c0', fontSize: 13, marginBottom: 20 }}>
          Found on {worldsWithRes.length} {worldsWithRes.length === 1 ? 'world' : 'worlds'}:
        </p>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {worldsWithRes.map(w => {
            const status = survey[w.id];
            return (
              <div key={w.id} style={{ 
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: '#080c12', padding: '12px 14px', borderRadius: 6,
                border: `1px solid ${status === 'colony' ? '#059669' : status === 'surveyed' ? '#b45309' : '#1a2a3a'}`
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 16, height: 16, borderRadius: '50%', background: w.col }} />
                  <div>
                    <span style={{ color: '#fff', fontWeight: 500 }}>{w.name}</span>
                    {w.parent && <span style={{ color: '#607080', fontSize: 11, marginLeft: 8 }}>({W(w.parent).name} moon)</span>}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '4px 10px', borderRadius: 4,
                  background: status === 'colony' ? '#064e3b' : status === 'surveyed' ? '#422006' : '#151a24',
                  color: status === 'colony' ? '#34d399' : status === 'surveyed' ? '#fbbf24' : '#607080',
                }}>
                  {status === 'colony' ? '● COLONY' : status === 'surveyed' ? '◐ SURVEYED' : '○ UNKNOWN'}
                </span>
              </div>
            );
          })}
        </div>
        
        {worldsWithRes.filter(w => survey[w.id] === 'unknown').length > 0 && (
          <p style={{ color: '#607080', fontSize: 11, marginTop: 16, fontStyle: 'italic' }}>
            💡 Send Probes to unknown worlds to confirm resource deposits.
          </p>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CARGO MODAL
// ═══════════════════════════════════════════════════════════════════════════════

function CargoModal({ ship, colony, onLoad, onClose }) {
  const [cargo, setCargo] = useState({});
  const capacity = SHIPS[ship.type].cargo;
  const used = Object.values(cargo).reduce((a, b) => a + b, 0);
  const remaining = capacity - used;

  const setAmount = (res, val) => {
    const max = Math.min(colony.res[res] || 0, remaining + (cargo[res] || 0));
    const amt = Math.max(0, Math.min(max, parseInt(val) || 0));
    setCargo(c => ({ ...c, [res]: amt || undefined }));
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ background: '#0c1018', border: '1px solid #1e3a5f', borderRadius: 8, padding: 24, width: 400 }}>
        <h3 style={{ margin: '0 0 8px', color: '#fff', fontSize: 18 }}>Load Cargo: {ship.name}</h3>
        <p style={{ color: '#a0b0c0', fontSize: 12, marginBottom: 16 }}>
          Capacity: <span style={{ color: '#22d3ee' }}>{used}/{capacity}</span> units
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
          {Object.entries(colony.res).filter(([_, v]) => v > 0).map(([r, v]) => (
            <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 12, background: '#0a0e14', padding: 10, borderRadius: 4 }}>
              <span style={{ color: RES[r].c, fontWeight: 600, width: 80 }}>{RES[r].n}</span>
              <span style={{ color: '#707080', fontSize: 12 }}>({Math.floor(v)} available)</span>
              <input
                type="number"
                min="0"
                max={Math.min(v, remaining + (cargo[r] || 0))}
                value={cargo[r] || ''}
                onChange={e => setAmount(r, e.target.value)}
                placeholder="0"
                style={{ width: 70, padding: '6px 8px', background: '#1a2030', border: '1px solid #2a3a50', borderRadius: 4, color: '#fff', fontSize: 14, textAlign: 'right' }}
              />
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={onClose} style={{ flex: 1, padding: '12px', background: '#1a2030', border: '1px solid #2a3a50', color: '#a0b0c0', fontSize: 13, cursor: 'pointer', borderRadius: 4 }}>
            Cancel
          </button>
          <button
            onClick={() => onLoad(cargo)}
            disabled={used === 0}
            style={{ flex: 1, padding: '12px', background: used > 0 ? '#0f766e' : '#1a2030', border: `1px solid ${used > 0 ? '#14b8a6' : '#2a3a50'}`, color: used > 0 ? '#a7f3d0' : '#505060', fontSize: 13, cursor: used > 0 ? 'pointer' : 'not-allowed', borderRadius: 4, fontWeight: 600 }}
          >
            Load {used} units
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN GAME
// ═══════════════════════════════════════════════════════════════════════════════

export default function Game() {
  const [phase, setPhase] = useState('menu');
  const [day, setDay] = useState(1);
  const [spd, setSpd] = useState(0);
  const [colonies, setColonies] = useState({});
  const [fleet, setFleet] = useState([]);
  const [survey, setSurvey] = useState({});
  const [sel, setSel] = useState(null);
  const [exp, setExp] = useState(null);
  const [launching, setLaunching] = useState(null);
  const [loadingCargo, setLoadingCargo] = useState(null);
  const [showResInfo, setShowResInfo] = useState(null);
  const [showSaveMenu, setShowSaveMenu] = useState(false);
  const fileInputRef = useRef(null);
  const [log, setLog] = useState([]);
  const [hasSave, setHasSave] = useState(false);

  useEffect(() => {
    (async () => { try { const r = await window.storage.get('rep9'); setHasSave(!!r?.value); } catch (e) { } })();
  }, []);

  const addLog = useCallback((m, type = 'info') => setLog(p => [...p.slice(-50), { text: m, type, day }]), [day]);

  const newGame = () => {
    const sv = {};
    WORLDS.forEach(w => { sv[w.id] = w.home ? 'colony' : 'unknown'; });
    setSurvey(sv);
    setColonies({
      moon: { n: 'Luna Prime', res: { fe: 200, si: 120, al: 80, ti: 30 }, bld: { solar: 4, drill: 2, foundry: 1, habitat: 1 }, pop: 120 }
    });
    setFleet([]);
    setDay(1);
    setSpd(1);
    setSel('moon');
    setExp('earth');
    setLog([{ text: 'Luna Prime online. Earth destroyed. Begin expansion protocol.', type: 'system', day: 1 }]);
    setPhase('game');
  };

  const save = async () => {
    try { await window.storage.set('rep9', JSON.stringify({ day, colonies, fleet, survey, log })); addLog('Game saved.', 'system'); audio.click(); } catch (e) { }
  };

  const load = async () => {
    try {
      const r = await window.storage.get('rep9');
      if (r?.value) {
        const d = JSON.parse(r.value);
        setDay(d.day); setColonies(d.colonies); setFleet(d.fleet); setSurvey(d.survey); setLog(d.log);
        setSel('moon'); setExp('earth'); setSpd(1); setPhase('game');
      }
    } catch (e) { }
  };

  const exportToFile = () => {
    const saveData = { 
      version: 9,
      timestamp: new Date().toISOString(),
      day, colonies, fleet, survey, log 
    };
    const blob = new Blob([JSON.stringify(saveData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `replicator-save-day${day}-${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    addLog('Game exported to file.', 'system');
    audio.click();
    setShowSaveMenu(false);
  };

  const importFromFile = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const d = JSON.parse(e.target.result);
        if (d.day && d.colonies && d.survey) {
          setDay(d.day); 
          setColonies(d.colonies); 
          setFleet(d.fleet || []); 
          setSurvey(d.survey); 
          setLog(d.log || []);
          setSel('moon'); 
          setExp('earth'); 
          setSpd(1); 
          setPhase('game');
          addLog('Game imported from file.', 'system');
          audio.success();
        } else {
          addLog('Invalid save file!', 'error');
          audio.error();
        }
      } catch (err) {
        addLog('Failed to read save file!', 'error');
        audio.error();
      }
    };
    reader.readAsText(file);
    event.target.value = '';
    setShowSaveMenu(false);
  };

  // Game tick
  useEffect(() => {
    if (phase !== 'game' || spd === 0) return;
    const tick = setInterval(() => {
      setDay(d => d + 1);
      
      // Move ships
      setFleet(p => p.map(s => {
        if (!s.moving) return s;
        if (s.eta <= 1) return { ...s, moving: false, at: s.to, eta: 0, arrived: true };
        return { ...s, eta: s.eta - 1 };
      }));

      // Production
      setColonies(p => {
        const n = JSON.parse(JSON.stringify(p));
        Object.entries(n).forEach(([id, c]) => {
          const w = W(id);
          const pwr = (c.bld.solar || 0) * 25 + (c.bld.reactor || 0) * 100;
          const use = (c.bld.drill || 0) * 10 + (c.bld.refinery || 0) * 15 + (c.bld.foundry || 0) * 20 + (c.bld.habitat || 0) * 5;
          if (pwr >= use && w?.res) {
            const mult = c.bld.refinery ? 2 : 1;
            w.res.forEach(r => { n[id].res[r] = (n[id].res[r] || 0) + (c.bld.drill || 0) * 0.5 * mult; });
          }
        });
        return n;
      });
    }, 600 / spd);
    return () => clearInterval(tick);
  }, [phase, spd]);

  // Handle arrivals
  useEffect(() => {
    fleet.filter(s => s.arrived && !s.handled).forEach(s => {
      const w = W(s.to);

      if (s.type === 'probe') {
        setSurvey(p => ({ ...p, [s.to]: 'surveyed' }));
        addLog(`Survey complete: ${w.name} — Found: ${w.res?.map(r => RES[r].n).join(', ') || 'nothing'}`, 'success');
        audio.success();
      }
      else if (s.type === 'seeder' && survey[s.to] === 'surveyed') {
        setColonies(p => ({
          ...p,
          [s.to]: { n: `${w.name} Colony`, res: { fe: 50, si: 25 }, bld: { solar: 1 }, pop: 30 }
        }));
        setSurvey(p => ({ ...p, [s.to]: 'colony' }));
        addLog(`Colony established: ${w.name}!`, 'success');
        audio.success();
      }
      else if (s.type === 'hauler' && s.cargo && Object.keys(s.cargo).length > 0) {
        // Deliver cargo
        setColonies(p => {
          if (!p[s.to]) return p;
          const n = { ...p };
          Object.entries(s.cargo).forEach(([r, amt]) => {
            n[s.to].res[r] = (n[s.to].res[r] || 0) + amt;
          });
          return n;
        });
        const total = Object.values(s.cargo).reduce((a, b) => a + b, 0);
        addLog(`Cargo delivered to ${w.name}: ${total} units`, 'success');
        audio.success();
      }

      setFleet(p => p.map(x => x.id === s.id ? { ...x, handled: true, cargo: {} } : x));
    });
  }, [fleet, survey, addLog]);

  const afford = (cost, res) => Object.entries(cost).every(([r, a]) => (res[r] || 0) >= a);

  const spend = (cost, cid) => setColonies(p => {
    const n = { ...p };
    Object.entries(cost).forEach(([r, a]) => { n[cid].res[r] -= a; });
    return n;
  });

  const build = (sid, cid) => {
    const c = colonies[cid];
    if (!afford(BLDG[sid].c, c.res)) { audio.error(); return; }
    spend(BLDG[sid].c, cid);
    setColonies(p => ({ ...p, [cid]: { ...p[cid], bld: { ...p[cid].bld, [sid]: (p[cid].bld[sid] || 0) + 1 } } }));
    addLog(`Built: ${BLDG[sid].n} at ${c.n}`, 'build');
    audio.click();
  };

  const buildShip = (type, cid) => {
    const c = colonies[cid];
    if (!c.bld.foundry) { addLog('Need a Foundry to build ships!', 'error'); audio.error(); return; }
    if (!afford(SHIPS[type].c, c.res)) { audio.error(); return; }
    spend(SHIPS[type].c, cid);
    setFleet(p => [...p, { id: Date.now(), type, name: `${SHIPS[type].n}-${p.length + 1}`, at: cid, moving: false, cargo: {} }]);
    addLog(`Built: ${SHIPS[type].n}`, 'build');
    audio.click();
  };

  const loadCargo = (shipId, cargo) => {
    const ship = fleet.find(s => s.id === shipId);
    if (!ship) return;

    // Remove from colony
    setColonies(p => {
      const n = { ...p };
      Object.entries(cargo).forEach(([r, amt]) => {
        if (amt > 0) n[ship.at].res[r] -= amt;
      });
      return n;
    });

    // Add to ship
    setFleet(p => p.map(s => s.id === shipId ? { ...s, cargo } : s));

    const total = Object.values(cargo).reduce((a, b) => a + b, 0);
    addLog(`Loaded ${total} units onto ${ship.name}`, 'info');
    setLoadingCargo(null);
    audio.click();
  };

  const launch = (sid, to) => {
    const s = fleet.find(x => x.id === sid);
    const fromOrd = W(s.at)?.order || W(W(s.at)?.parent)?.order || 3;
    const toOrd = W(to)?.order || W(W(to)?.parent)?.order || 5;
    const eta = Math.max(2, Math.ceil(Math.abs(toOrd - fromOrd) * 3 / SHIPS[s.type].spd));
    setFleet(p => p.map(x => x.id === sid ? { ...x, moving: true, to, eta, arrived: false, handled: false } : x));
    addLog(`Launch: ${s.name} → ${W(to).name} (ETA: ${eta} days)`, 'launch');
    setLaunching(null);
    audio.launch();
  };

  const col = sel && colonies[sel];
  const world = sel && W(sel);
  const pwr = col ? {
    g: (col.bld.solar || 0) * 25 + (col.bld.reactor || 0) * 100,
    u: (col.bld.drill || 0) * 10 + (col.bld.refinery || 0) * 15 + (col.bld.foundry || 0) * 20 + (col.bld.habitat || 0) * 5
  } : null;

  const hint = phase === 'game' ? getHint({ colonies, fleet, survey, sel }) : null;
  const planets = WORLDS.filter(w => w.order);

  // ═══════════════════════════════════════════════════════════════════════════
  // STYLES
  // ═══════════════════════════════════════════════════════════════════════════

  const S = {
    page: { minHeight: '100vh', background: '#04060a', color: '#e0e8f0', fontFamily: "'SF Mono', Consolas, monospace", fontSize: 13 },
    btn: (active, disabled) => ({
      padding: '10px 18px', fontSize: 12, fontWeight: 600, letterSpacing: '0.05em', cursor: disabled ? 'not-allowed' : 'pointer',
      background: disabled ? '#151a24' : active ? '#0d9488' : 'linear-gradient(180deg, #0f766e, #0a5550)',
      border: `1px solid ${disabled ? '#1e2a3a' : '#14b8a6'}`, color: disabled ? '#404858' : '#d0fff0',
      borderRadius: 4, transition: 'all 0.15s', fontFamily: 'inherit'
    }),
    card: { background: 'linear-gradient(180deg, #0c1218, #080c10)', border: '1px solid #1a2a3a', borderRadius: 6, padding: 18 },
    label: { fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', color: '#14b8a6', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 },
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════

  if (phase === 'menu') {
    return (
      <>
        <style>{CSS}</style>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={importFromFile} 
          accept=".json"
          style={{ display: 'none' }} 
        />
        <div style={{ ...S.page, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
          <div style={{ textAlign: 'center' }}>
            <div className="float">
              <Planet color="#4080b0" size={120} glow />
            </div>
            <h1 style={{ fontSize: 52, fontWeight: 900, color: '#fff', margin: '24px 0 0', letterSpacing: '-0.02em', textShadow: '0 0 60px rgba(20,184,166,0.5)' }}>
              REPLICATOR
            </h1>
            <p style={{ color: '#14b8a6', fontSize: 13, letterSpacing: '0.4em', marginTop: 8 }}>SOLAR SYSTEM COLONIZATION</p>
            <div style={{ marginTop: 48, display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
              <button onClick={() => { audio.init(); audio.click(); newGame(); }} style={{ ...S.btn(false, false), width: 220, padding: '16px 24px', fontSize: 14 }}>
                NEW MISSION
              </button>
              {hasSave && (
                <button onClick={() => { audio.init(); audio.click(); load(); }} style={{ ...S.btn(false, false), width: 220, padding: '16px 24px', fontSize: 14, background: '#151a24', borderColor: '#2a3a4a' }}>
                  CONTINUE
                </button>
              )}
              <button onClick={() => { audio.init(); fileInputRef.current?.click(); }} style={{ ...S.btn(false, false), width: 220, padding: '16px 24px', fontSize: 14, background: '#422006', borderColor: '#d97706', color: '#fde68a' }}>
                📂 IMPORT SAVE
              </button>
            </div>
            <p style={{ color: '#304050', fontSize: 11, marginTop: 64, letterSpacing: '0.15em' }}>INSPIRED BY MILLENNIUM 2.2 · 1989</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{CSS}</style>
      {loadingCargo && (
        <CargoModal
          ship={fleet.find(s => s.id === loadingCargo)}
          colony={colonies[fleet.find(s => s.id === loadingCargo)?.at]}
          onLoad={(cargo) => loadCargo(loadingCargo, cargo)}
          onClose={() => setLoadingCargo(null)}
        />
      )}
      {showResInfo && (
        <ResourceInfo 
          resId={showResInfo} 
          survey={survey}
          onClose={() => setShowResInfo(null)} 
        />
      )}
      {showSaveMenu && (
        <SaveMenu
          onSave={() => { save(); setShowSaveMenu(false); }}
          onExport={exportToFile}
          onImport={importFromFile}
          fileInputRef={fileInputRef}
          onClose={() => setShowSaveMenu(false)}
        />
      )}
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={importFromFile} 
        accept=".json"
        style={{ display: 'none' }} 
      />
      <div style={{ ...S.page, height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* HEADER */}
        <header style={{ height: 52, background: '#080c12', borderBottom: '1px solid #1a2a3a', padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <span style={{ color: '#14b8a6', fontWeight: 800, fontSize: 16 }}>REPLICATOR</span>
            <div style={{ height: 24, width: 1, background: '#1a2a3a' }} />
            <span style={{ color: '#c0c8d0' }}>DAY <span style={{ color: '#5eead4', fontWeight: 700 }}>{day}</span></span>
            <span style={{ color: '#405060' }}>│</span>
            <span style={{ color: '#c0c8d0' }}>COLONIES <span style={{ color: '#34d399', fontWeight: 600 }}>{Object.keys(colonies).length}</span></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ display: 'flex', border: '1px solid #1a2a3a', borderRadius: 4, overflow: 'hidden' }}>
              {[0, 1, 3, 10].map(s => (
                <button key={s} onClick={() => { setSpd(s); audio.click(); }}
                  style={{ width: 44, padding: '10px 0', fontSize: 12, fontWeight: spd === s ? 700 : 400, background: spd === s ? '#0f766e' : 'transparent', border: 'none', color: spd === s ? '#fff' : '#607080', cursor: 'pointer', fontFamily: 'inherit' }}>
                  {s === 0 ? '⏸' : s + '×'}
                </button>
              ))}
            </div>
            <button onClick={() => setShowSaveMenu(true)} style={{ ...S.btn(false, false), padding: '10px 14px', background: '#064e3b', borderColor: '#10b981' }}>SAVE</button>
            <button onClick={() => setPhase('menu')} style={{ ...S.btn(false, false), padding: '10px 14px', background: '#151a24', borderColor: '#2a3a4a' }}>EXIT</button>
          </div>
        </header>

        {/* HINT BAR */}
        {hint && (
          <div style={{ background: hint.type === 'warning' ? '#451a03' : '#042f2e', borderBottom: `1px solid ${hint.type === 'warning' ? '#92400e' : '#0f766e'}`, padding: '10px 20px', fontSize: 13, color: hint.type === 'warning' ? '#fcd34d' : '#5eead4' }}>
            {hint.text}
          </div>
        )}

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* NAV */}
          <nav style={{ width: 240, background: '#060a0e', borderRight: '1px solid #1a2a3a', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid #1a2a3a' }}>
              <span style={{ ...S.label, marginBottom: 0 }}>◆ SOLAR SYSTEM</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {planets.map(p => {
                const ms = moons(p.id);
                const isExp = exp === p.id;
                const st = survey[p.id];
                return (
                  <div key={p.id}>
                    <button onClick={() => { setSel(p.id); if (ms.length) setExp(isExp ? null : p.id); audio.click(); }}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px', background: sel === p.id ? '#0c1820' : 'transparent', border: 'none', borderLeft: sel === p.id ? '3px solid #14b8a6' : '3px solid transparent', color: '#e0e8f0', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}>
                      <Planet color={p.col} size={28} status={st} rings={p.rings} />
                      <span style={{ flex: 1, fontSize: 13, fontWeight: sel === p.id ? 600 : 400 }}>{p.name}</span>
                      {p.gas && <span style={{ fontSize: 9, color: '#fb923c', background: '#431407', padding: '2px 6px', borderRadius: 3 }}>GAS</span>}
                      {ms.length > 0 && <span style={{ color: '#405060', fontSize: 12 }}>{isExp ? '▾' : '▸'}</span>}
                    </button>
                    {isExp && ms.map(m => {
                      const mst = survey[m.id];
                      return (
                        <button key={m.id} onClick={() => { setSel(m.id); audio.click(); }}
                          style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 18px 8px 42px', background: sel === m.id ? '#0c1820' : 'transparent', border: 'none', borderLeft: sel === m.id ? '3px solid #14b8a6' : '3px solid transparent', color: '#a0b0c0', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}>
                          <Planet color={m.col} size={20} status={mst} />
                          <span style={{ fontSize: 12 }}>{m.name}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>

            {fleet.filter(s => s.moving).length > 0 && (
              <div style={{ borderTop: '1px solid #1a2a3a', padding: 16 }}>
                <div style={{ ...S.label }}>◆ IN TRANSIT</div>
                {fleet.filter(s => s.moving).map(s => (
                  <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ShipIcon type={s.type} size={20} />
                      <span style={{ color: '#c0c8d0', fontSize: 12 }}>{s.name}</span>
                    </div>
                    <span style={{ color: '#34d399', fontWeight: 600, fontSize: 12 }}>{s.eta}d</span>
                  </div>
                ))}
              </div>
            )}
          </nav>

          {/* MAIN */}
          <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#04060a' }}>
            {/* World header */}
            {world && (
              <div style={{ padding: 20, borderBottom: '1px solid #1a2a3a', background: 'linear-gradient(90deg, #0a0e14, #04060a)', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                  <Planet color={world.col} size={64} status={survey[world.id]} rings={world.rings} glow />
                  <div>
                    <h2 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: '#fff' }}>{world.name}</h2>
                    <p style={{ color: '#8090a0', fontSize: 12, margin: '4px 0 10px' }}>{world.desc}</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '5px 12px', borderRadius: 4,
                        background: survey[world.id] === 'colony' ? '#064e3b' : survey[world.id] === 'surveyed' ? '#422006' : '#151a24',
                        color: survey[world.id] === 'colony' ? '#34d399' : survey[world.id] === 'surveyed' ? '#fbbf24' : '#607080',
                        border: `1px solid ${survey[world.id] === 'colony' ? '#059669' : survey[world.id] === 'surveyed' ? '#b45309' : '#2a3a4a'}`
                      }}>
                        {(survey[world.id] || 'UNKNOWN').toUpperCase()}
                      </span>
                      {survey[world.id] !== 'unknown' && world.res?.length > 0 && (
                        <div style={{ display: 'flex', gap: 6 }}>
                          {world.res.map(r => (
                            <span key={r} onClick={() => setShowResInfo(r)} style={{ fontSize: 11, fontWeight: 600, padding: '4px 10px', borderRadius: 4, background: `${RES[r].c}20`, color: RES[r].c, cursor: 'pointer', transition: 'transform 0.1s' }}
                              onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
                              onMouseOut={e => e.target.style.transform = 'scale(1)'}
                              title={`Click to see all worlds with ${RES[r]?.n}`}>
                              {RES[r].n}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
              {col ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {/* Resources */}
                  <div style={S.card}>
                    <div style={S.label}>◆ STOCKPILE <span style={{ color: '#405060', fontSize: 9, fontWeight: 400, marginLeft: 8 }}>click to find more</span></div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                      {Object.entries(col.res).filter(([_, v]) => v > 0).map(([r, v]) => (
                        <div key={r} onClick={() => setShowResInfo(r)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#080c12', padding: '12px 14px', borderRadius: 4, borderLeft: `4px solid ${RES[r]?.c}`, cursor: 'pointer', transition: 'background 0.15s' }}
                          onMouseOver={e => e.currentTarget.style.background = '#0c1018'}
                          onMouseOut={e => e.currentTarget.style.background = '#080c12'}
                          title={`Click to see where to find more ${RES[r]?.n}`}>
                          <span style={{ color: RES[r]?.c, fontWeight: 600 }}>{RES[r]?.n}</span>
                          <span style={{ color: '#fff', fontWeight: 700, fontSize: 16 }}>{Math.floor(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Power */}
                  <div style={S.card}>
                    <div style={S.label}>◆ POWER GRID</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                      <span style={{ color: '#a0b0c0' }}>Output / Usage</span>
                      <span style={{ fontSize: 28, fontWeight: 700, color: pwr.g >= pwr.u ? '#34d399' : '#ef4444' }}>
                        {pwr.g}<span style={{ color: '#405060', fontSize: 18 }}>/{pwr.u}</span>
                        <span style={{ color: '#607080', fontSize: 13, marginLeft: 6 }}>kW</span>
                      </span>
                    </div>
                    <div style={{ height: 10, background: '#151a24', borderRadius: 5, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, pwr.g / Math.max(1, pwr.u) * 100)}%`, background: pwr.g >= pwr.u ? 'linear-gradient(90deg, #059669, #34d399)' : 'linear-gradient(90deg, #dc2626, #ef4444)', transition: 'width 0.3s' }} />
                    </div>
                    {pwr.g < pwr.u && <p style={{ color: '#ef4444', fontSize: 12, marginTop: 12 }} className="pulse">⚠ POWER DEFICIT — Mining halted!</p>}
                  </div>

                  {/* Structures */}
                  <div style={{ ...S.card, gridColumn: 'span 2' }}>
                    <div style={S.label}>◆ STRUCTURES <span style={{ color: '#405060', fontSize: 9, fontWeight: 400, marginLeft: 8 }}>click resources to find sources</span></div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                      {Object.entries(BLDG).map(([id, st]) => {
                        const ok = afford(st.c, col.res);
                        return (
                          <div key={id} style={{ background: '#080c12', borderRadius: 6, padding: 16, border: '1px solid #1a2a3a' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                              <StructIcon type={id} size={32} />
                              <div>
                                <span style={{ color: '#fff', fontWeight: 600 }}>{st.n}</span>
                                <span style={{ color: '#607080', marginLeft: 8 }}>×{col.bld[id] || 0}</span>
                              </div>
                            </div>
                            <p style={{ color: '#a0b0c0', fontSize: 11, margin: '0 0 12px' }}>{st.d}</p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 14 }}>
                              {Object.entries(st.c).map(([r, a]) => (
                                <span key={r} onClick={() => setShowResInfo(r)} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 3, background: (col.res[r] || 0) >= a ? '#064e3b' : '#450a0a', color: (col.res[r] || 0) >= a ? '#34d399' : '#ef4444', cursor: 'pointer', transition: 'transform 0.1s' }}
                                  onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
                                  onMouseOut={e => e.target.style.transform = 'scale(1)'}
                                  title={`Click to see where to find ${RES[r]?.n}`}>
                                  {a} {RES[r]?.n}
                                </span>
                              ))}
                            </div>
                            <button onClick={() => build(id, sel)} disabled={!ok} style={{ ...S.btn(false, !ok), width: '100%' }}>BUILD</button>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Shipyard */}
                  <div style={{ ...S.card, gridColumn: 'span 2' }}>
                    <div style={S.label}>◆ SHIPYARD {!col.bld.foundry && <span style={{ color: '#f97316', fontSize: 10, fontWeight: 400 }}>— Requires Foundry</span>}</div>
                    {col.bld.foundry ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                        {Object.entries(SHIPS).map(([id, sh]) => {
                          const ok = afford(sh.c, col.res);
                          return (
                            <div key={id} style={{ background: '#080c12', borderRadius: 6, padding: 16, border: '1px solid #1a2a3a' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                                <ShipIcon type={id} size={36} />
                                <span style={{ color: '#fff', fontWeight: 700, fontSize: 15 }}>{sh.n}</span>
                              </div>
                              <p style={{ color: '#a0b0c0', fontSize: 11, margin: '0 0 12px' }}>{sh.d}</p>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 14 }}>
                                {Object.entries(sh.c).map(([r, a]) => (
                                  <span key={r} onClick={() => setShowResInfo(r)} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 3, background: (col.res[r] || 0) >= a ? '#064e3b' : '#450a0a', color: (col.res[r] || 0) >= a ? '#34d399' : '#ef4444', cursor: 'pointer', transition: 'transform 0.1s' }}
                                    onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
                                    onMouseOut={e => e.target.style.transform = 'scale(1)'}
                                    title={`Click to see where to find ${RES[r]?.n}`}>
                                    {a} {RES[r]?.n}
                                  </span>
                                ))}
                              </div>
                              <button onClick={() => buildShip(id, sel)} disabled={!ok} style={{ ...S.btn(false, !ok), width: '100%', background: ok ? '#064e3b' : undefined, borderColor: ok ? '#10b981' : undefined }}>CONSTRUCT</button>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p style={{ color: '#607080' }}>Build a Foundry to unlock spacecraft construction.</p>
                    )}
                  </div>

                  {/* Hangar */}
                  <div style={{ ...S.card, gridColumn: 'span 2' }}>
                    <div style={S.label}>◆ HANGAR</div>
                    {fleet.filter(s => s.at === sel && !s.moving).length === 0 ? (
                      <p style={{ color: '#607080' }}>No spacecraft docked at this colony.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {fleet.filter(s => s.at === sel && !s.moving).map(s => {
                          const cargoAmt = Object.values(s.cargo || {}).reduce((a, b) => a + b, 0);
                          return (
                            <div key={s.id} style={{ background: '#080c12', borderRadius: 6, padding: 16, border: '1px solid #1a2a3a' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                  <ShipIcon type={s.type} size={28} />
                                  <div>
                                    <span style={{ color: '#fff', fontWeight: 600 }}>{s.name}</span>
                                    {s.type === 'hauler' && (
                                      <span style={{ color: '#607080', fontSize: 11, marginLeft: 10 }}>
                                        Cargo: <span style={{ color: cargoAmt > 0 ? '#fbbf24' : '#607080' }}>{cargoAmt}/{SHIPS.hauler.cargo}</span>
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: 8 }}>
                                  {s.type === 'hauler' && (
                                    <button onClick={() => setLoadingCargo(s.id)} style={{ ...S.btn(false, false), padding: '8px 14px', background: '#422006', borderColor: '#b45309' }}>
                                      LOAD CARGO
                                    </button>
                                  )}
                                  <button onClick={() => setLaunching(launching === s.id ? null : s.id)}
                                    style={{ ...S.btn(launching === s.id, false), padding: '8px 18px' }}>
                                    {launching === s.id ? 'CANCEL' : 'LAUNCH'}
                                  </button>
                                </div>
                              </div>

                              {/* Cargo display */}
                              {cargoAmt > 0 && (
                                <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                                  {Object.entries(s.cargo).filter(([_, v]) => v > 0).map(([r, v]) => (
                                    <span key={r} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 3, background: `${RES[r].c}20`, color: RES[r].c }}>
                                      {v} {RES[r].n}
                                    </span>
                                  ))}
                                </div>
                              )}

                              {/* Launch destinations */}
                              {launching === s.id && (
                                <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #1a2a3a' }}>
                                  <p style={{ color: '#a0b0c0', fontSize: 11, marginBottom: 10 }}>SELECT DESTINATION:</p>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                    {WORLDS.filter(w => w.id !== sel && !w.gas && !w.dead && (s.type !== 'seeder' || survey[w.id] === 'surveyed') && (s.type !== 'hauler' || survey[w.id] === 'colony')).map(w => (
                                      <button key={w.id} onClick={() => launch(s.id, w.id)}
                                        style={{
                                          padding: '8px 14px', fontSize: 11, borderRadius: 4, cursor: 'pointer',
                                          background: survey[w.id] === 'colony' ? '#064e3b' : survey[w.id] === 'surveyed' ? '#422006' : '#151a24',
                                          color: survey[w.id] === 'colony' ? '#34d399' : survey[w.id] === 'surveyed' ? '#fbbf24' : '#a0b0c0',
                                          border: `1px solid ${survey[w.id] === 'colony' ? '#059669' : survey[w.id] === 'surveyed' ? '#b45309' : '#2a3a4a'}`,
                                          fontFamily: 'inherit'
                                        }}>
                                        {w.name}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ ...S.card, textAlign: 'center', padding: 48 }}>
                    {survey[world?.id] === 'unknown' && !world?.gas && !world?.dead && (
                      <>
                        <ShipIcon type="probe" size={56} color="#607080" />
                        <p style={{ color: '#e0e8f0', marginTop: 16, marginBottom: 4, fontSize: 16 }}>Unknown World</p>
                        <p style={{ color: '#a0b0c0', fontSize: 13 }}>Build and launch a <span style={{ color: '#22d3ee' }}>Probe</span> to survey.</p>
                      </>
                    )}
                    {survey[world?.id] === 'surveyed' && (
                      <>
                        <ShipIcon type="seeder" size={56} color="#fbbf24" />
                        <p style={{ color: '#e0e8f0', marginTop: 16, marginBottom: 4, fontSize: 16 }}>Survey Complete</p>
                        <p style={{ color: '#a0b0c0', fontSize: 13 }}>Launch a <span style={{ color: '#a855f7' }}>Seeder</span> to establish a colony.</p>
                      </>
                    )}
                    {world?.gas && (
                      <>
                        <p style={{ color: '#e0e8f0', fontSize: 16, marginBottom: 4 }}>Gas Giant</p>
                        <p style={{ color: '#a0b0c0', fontSize: 13 }}>Cannot colonize directly — expand moons in the list.</p>
                      </>
                    )}
                    {world?.dead && (
                      <>
                        <p style={{ color: '#ef4444', fontSize: 16, marginBottom: 4 }}>Earth — Destroyed</p>
                        <p style={{ color: '#a0b0c0', fontSize: 13 }}>Lost to asteroid impact in 2247.</p>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Log */}
            <div style={{ height: 100, borderTop: '1px solid #1a2a3a', padding: 14, background: '#060a0e', flexShrink: 0 }}>
              <div style={{ ...S.label, marginBottom: 8 }}>◆ MISSION LOG</div>
              <div style={{ height: 54, overflowY: 'auto', fontSize: 11 }}>
                {log.slice().reverse().map((l, i) => (
                  <div key={i} style={{ color: l.type === 'error' ? '#ef4444' : l.type === 'success' ? '#34d399' : l.type === 'launch' ? '#22d3ee' : l.type === 'build' ? '#a78bfa' : '#a0b0c0', marginBottom: 3 }}>
                    <span style={{ color: '#405060' }}>[D{l.day}]</span> {l.text}
                  </div>
                ))}
              </div>
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
