// MANTIS Operator Dashboard — Theme constants (JS-side for inline styles)
// Matches CSS variables in global.css
export const T = {
  bg: {
    base: '#05070b',
    surface: '#0b1118',
    panel: '#0d1520',
    card: '#0f1923',
    elevated: '#121e2b',
  },
  border: {
    dim: '#0e2319',
    mid: '#143126',
    bright: '#1a4a35',
    glow: 'rgba(57, 255, 136, 0.18)',
  },
  green: {
    primary: '#39ff88',
    holo: '#00ffa6',
    soft: '#2adb76',
    dim: '#1a7a4a',
    muted: '#0e4a2e',
    glow: 'rgba(57, 255, 136, 0.15)',
    glowStrong: 'rgba(57, 255, 136, 0.3)',
  },
  status: {
    success: '#39ff88',
    warning: '#ffcc66',
    danger: '#ff5f5f',
    info: '#66d9ff',
  },
  text: {
    bright: '#e8fff0',
    main: '#d9ffe9',
    mid: '#8fc9a8',
    dim: '#5a8a70',
    muted: '#3a6a52',
    faint: '#2a4a3a',
  },
  accent: {
    cyan: '#00e5c8',
    gold: '#f0d060',
  },
  font: {
    mono: "'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace",
  },
} as const;
