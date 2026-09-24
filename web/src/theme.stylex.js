import * as stylex from '@stylexjs/stylex'

export const tokens = stylex.defineVars({
  bg: '#f7f7f9',
  surface: '#ffffff',
  border: '#e5e7eb',
  borderStrong: '#d1d5db',
  text: '#111827',
  textDim: '#6b7280',
  textFaint: '#9ca3af',
  accent: '#4f46e5',
  accentSoft: '#eef2ff',
  accentText: '#4338ca',
  green: '#059669',
  greenSoft: '#ecfdf5',
  red: '#dc2626',
  redSoft: '#fef2f2',
  amber: '#d97706',
  amberSoft: '#fffbeb',
  blue: '#2563eb',
  radius: '10px',
  radiusSm: '6px',
  shadow: '0 1px 2px rgba(16,24,40,.06)',
  font: '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  mono: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
})

export const TEAM_COLORS = { teamA: '#2563eb', teamB: '#d97706', accent: '#4f46e5', muted: '#9ca3af' }

export const global = stylex.create({
  page: {
    fontFamily: tokens.font,
    backgroundColor: tokens.bg,
    color: tokens.text,
    minHeight: '100vh',
    fontSize: '14px',
    lineHeight: 1.5,
  },
  shell: { maxWidth: '1180px', margin: '0 auto', padding: '0 20px 48px' },
  card: {
    backgroundColor: tokens.surface,
    border: `1px solid ${tokens.border}`,
    borderRadius: tokens.radius,
    boxShadow: tokens.shadow,
    padding: '18px 20px',
  },
  cardTitle: { fontSize: '13px', fontWeight: 600, color: tokens.textDim, marginBottom: '10px', letterSpacing: '0.01em' },
  grid2: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '14px' },
  chip: {
    display: 'inline-flex', alignItems: 'center', gap: '5px',
    fontSize: '12px', fontWeight: 500, padding: '3px 10px',
    borderRadius: '999px', border: `1px solid ${tokens.border}`,
    backgroundColor: tokens.surface, color: tokens.textDim,
  },
})
