import React from 'react'
import * as stylex from '@stylexjs/stylex'
import { tokens } from './theme.stylex'

const PAD = { l: 42, r: 12, t: 10, b: 22 }

function niceTicks(lo, hi, n = 4) {
  if (lo === hi) { lo -= 1; hi += 1 }
  const step = (hi - lo) / n
  return Array.from({ length: n + 1 }, (_, i) => lo + step * i)
}

export default function LineChart({ series, height = 260, cursor = 0, onPick, yMin, yMax, pct = false }) {
  const W = 720, H = height
  const all = series.flatMap(s => s.values.filter(v => v != null))
  const lo = yMin ?? Math.min(...all, 0), hi = yMax ?? Math.max(...all, 1)
  const n = Math.max(...series.map(s => s.values.length))
  const x = i => PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * (W - PAD.l - PAD.r))
  const y = v => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b)
  const ticks = niceTicks(lo, hi)
  const path = vals => vals.map((v, i) => v == null ? null : `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .reduce((acc, p) => p ? acc + p : acc, '')
  const pathSegs = vals => {
    const segs = []; let cur = ''
    vals.forEach((v, i) => {
      if (v == null) { if (cur) segs.push(cur); cur = '' }
      else cur += (cur ? 'L' : 'M') + `${x(i).toFixed(1)},${y(v).toFixed(1)}`
    })
    if (cur) segs.push(cur)
    return segs
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} {...stylex.props(st.svg)}
      onClick={e => {
        if (!onPick) return
        const rect = e.currentTarget.getBoundingClientRect()
        const frac = (e.clientX - rect.left) / rect.width * W
        const i = Math.round((frac - PAD.l) / (W - PAD.l - PAD.r) * (n - 1))
        onPick(Math.min(n - 1, Math.max(0, i)))
      }}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} stroke={tokens.border} strokeWidth={1} />
          <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" {...stylex.props(st.tick)}>
            {pct ? `${t.toFixed(0)}%` : t.toFixed(2)}
          </text>
        </g>
      ))}
      {series.map((s, si) => pathSegs(s.values).map((d, di) => (
        <path key={`${si}-${di}`} d={d} fill="none" stroke={s.color} strokeWidth={s.width ?? 2}
          strokeDasharray={s.dash} strokeLinecap="round" />
      )))}
      {series.map((s, si) => s.points && s.values.map((v, i) => v == null ? null : (
        <circle key={`p${si}-${i}`} cx={x(i)} cy={y(v)} r={4} fill={s.color} />
      )))}
      {cursor > 0 && cursor <= n && (
        <line x1={x(cursor - 1)} x2={x(cursor - 1)} y1={PAD.t} y2={H - PAD.b}
          stroke={tokens.accent} strokeWidth={1.4} strokeDasharray="4 3" />
      )}
      <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke={tokens.borderStrong} />
    </svg>
  )
}

const st = stylex.create({
  svg: { width: '100%', height: 'auto', display: 'block', cursor: 'crosshair' },
  tick: { fontSize: '10px', fill: tokens.textFaint, fontFamily: tokens.mono },
})
