import React from 'react'
import * as stylex from '@stylexjs/stylex'
import { tokens, global as g } from './theme.stylex'

function Chip({ label, value, tone }) {
  const toneStyle = tone === 'good' ? st.good : tone === 'bad' ? st.bad : tone === 'warn' ? st.warn : null
  return (
    <span {...stylex.props(g.chip, toneStyle)}>{label} <b {...stylex.props(st.chipVal)}>{value}</b></span>
  )
}

export default function JevPanel({ result, row }) {
  const verdict = row?.sentiment?.interval_verdict
  const commentVerdicts = row?.sentiment?.verdicts ?? []
  const trace = result._trace ?? []
  const usage = result.jev_usage ?? {}
  const gateRows = result.intervals.filter(r => r.fill?.gate)
  const vetoes = trace.filter(e => (e.question_keys ?? []).includes('gate')
    && (e.answers_digest?.gate ?? 1) < 0.5).length

  return (
    <div {...stylex.props(g.card)}>
      <div {...stylex.props(g.cardTitle)}>Jev decisions</div>
      {usage.calls != null && (
        <div {...stylex.props(st.usage)}>
          {usage.calls} decide calls · {usage.questions} questions · ~{usage.input_tokens?.toLocaleString()} input tokens ·
          {' '}{usage.cache_hits} cache hits{vetoes ? ` · ${vetoes} gate vetoes` : ''}
        </div>
      )}

      {verdict ? (
        <div {...stylex.props(st.chipRow)}>
          <Chip label="regime" value={verdict.regime} tone={verdict.regime === 'tense' ? 'warn' : undefined} />
          <Chip label="signal quality" value={(verdict.signal_quality ?? 0).toFixed(2)} />
          <Chip label="odds stale" value={verdict.odds_stale != null ? verdict.odds_stale.toFixed(2) : '—'}
            tone={verdict.odds_stale > 0.5 ? 'bad' : undefined} />
          <Chip label="narrate" value={verdict.narrate != null ? verdict.narrate.toFixed(2) : '—'}
            tone={verdict.narrate > 0.5 ? 'good' : undefined} />
        </div>
      ) : (
        <div {...stylex.props(st.dim)}>No interval verdict (engine: {result.sentiment_source}).</div>
      )}

      {commentVerdicts.length > 0 && (
        <details {...stylex.props(st.details)}>
          <summary {...stylex.props(st.summary)}>{commentVerdicts.length} per-comment verdicts this interval</summary>
          <table {...stylex.props(st.table)}>
            <thead><tr>{['comment', 'relevant', 'team', 'bullish'].map(h => <th key={h} {...stylex.props(st.th)}>{h}</th>)}</tr></thead>
            <tbody>
              {commentVerdicts.map((v, i) => (
                <tr key={i}>
                  <td {...stylex.props(st.td, st.mono)}>#{v.index}</td>
                  <td {...stylex.props(st.td, st.mono)}>{v.relevant?.toFixed(2)}</td>
                  <td {...stylex.props(st.td)}>{v.team}</td>
                  <td {...stylex.props(st.td, st.mono)}>{v.bullish?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}

      {trace.length > 0 && (
        <details {...stylex.props(st.details)}>
          <summary {...stylex.props(st.summary)}>Decision trace — {trace.length} calls</summary>
          <table {...stylex.props(st.table)}>
            <thead><tr>{['#', 'questions', 'cache', 'input tokens', 'ms'].map(h => <th key={h} {...stylex.props(st.th)}>{h}</th>)}</tr></thead>
            <tbody>
              {trace.map((e, i) => (
                <tr key={i}>
                  <td {...stylex.props(st.td, st.mono)}>{i + 1}</td>
                  <td {...stylex.props(st.td, st.mono)}>{e.n_questions ?? (e.question_keys || []).length}</td>
                  <td {...stylex.props(st.td)}>{e.cache_hit ? 'hit' : 'api'}</td>
                  <td {...stylex.props(st.td, st.mono)}>{(e.input_tokens ?? 0).toLocaleString()}</td>
                  <td {...stylex.props(st.td, st.mono)}>{Math.round(e.latency_ms ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}

      {gateRows.length === 0 && usage.calls > 0 && (
        <div {...stylex.props(st.dim)}>No fills — every proposal was vetoed or blocked before the gate.</div>
      )}
    </div>
  )
}

const st = stylex.create({
  usage: { fontSize: '12.5px', color: tokens.textDim, marginBottom: '10px' },
  chipRow: { display: 'flex', gap: '6px', flexWrap: 'wrap' },
  chipVal: { color: tokens.text, fontWeight: 600, marginLeft: '2px' },
  good: { color: tokens.green, backgroundColor: tokens.greenSoft, borderColor: `${tokens.green}30` },
  bad: { color: tokens.red, backgroundColor: tokens.redSoft, borderColor: `${tokens.red}30` },
  warn: { color: tokens.amber, backgroundColor: tokens.amberSoft, borderColor: `${tokens.amber}30` },
  dim: { color: tokens.textFaint, fontSize: '12.5px', marginTop: '6px' },
  details: { marginTop: '10px' },
  summary: { cursor: 'pointer', fontSize: '12.5px', color: tokens.accentText, fontWeight: 500 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12.5px', marginTop: '8px' },
  th: { textAlign: 'left', padding: '6px 10px', backgroundColor: tokens.bg, color: tokens.textDim, fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: `1px solid ${tokens.border}` },
  td: { padding: '5px 10px', borderBottom: `1px solid ${tokens.border}` },
  mono: { fontFamily: tokens.mono, fontSize: '12px', fontVariantNumeric: 'tabular-nums' },
})
