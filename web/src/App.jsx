import React, { useEffect, useMemo, useState } from 'react'
import * as stylex from '@stylexjs/stylex'
import { tokens, global as g, TEAM_COLORS as C } from './theme.stylex'
import LineChart from './LineChart'
import JevPanel from './JevPanel'

const api = {
  matches: () => fetch('/api/matches').then(r => r.json()),
  analyze: (match, sentiment, narrative, bankroll, trace) =>
    fetch(`/api/analyze?match=${match}&sentiment=${sentiment}&narrative=${narrative}&bankroll=${bankroll}&trace=${trace}`)
      .then(r => { if (!r.ok) throw new Error(`analyze failed: ${r.status}`); return r.json() }),
}

function Metric({ label, value, sub, tone }) {
  return (
    <div {...stylex.props(st.metric, tone === 'good' && st.metricGood, tone === 'bad' && st.metricBad)}>
      <div {...stylex.props(st.metricLabel)}>{label}</div>
      <div {...stylex.props(st.metricValue)}>{value}</div>
      {sub && <div {...stylex.props(st.metricSub)}>{sub}</div>}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div {...stylex.props(st.stat)}>
      <span {...stylex.props(st.statLabel)}>{label}</span>
      <span {...stylex.props(st.mono)}>{value}</span>
    </div>
  )
}

export default function App() {
  const [matches, setMatches] = useState([])
  const [matchId, setMatchId] = useState(74)
  const [engine, setEngine] = useState('auto')
  const [narrative, setNarrative] = useState(false)
  const [trace, setTrace] = useState(true)
  const [bankroll, setBankroll] = useState(1000)
  const [result, setResult] = useState(null)
  const [cursor, setCursor] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.matches().then(rows => {
      setMatches(rows)
      if (rows.length && !rows.some(r => r.match_id === 74)) setMatchId(rows[0].match_id)
    }).catch(e => setError(`API unreachable — start the backend with \`ipl-ui\`. (${e})`))
  }, [])

  const run = () => {
    setLoading(true); setError(null)
    api.analyze(matchId, engine, narrative, bankroll, trace)
      .then(r => { setResult(r); setCursor(1) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }

  const ivs = result?.intervals ?? []
  const row = ivs[cursor - 1]
  const a = result?.team_a, b = result?.team_b
  const aAbbr = result?.team_a_abbr, bAbbr = result?.team_b_abbr

  return (
    <div {...stylex.props(g.page)}>
      <header {...stylex.props(st.topbar)}>
        <div {...stylex.props(st.topInner)}>
          <div {...stylex.props(st.brand)}>IPL 2024 paper book <span {...stylex.props(st.brandTag)}>Jev</span></div>
          <div {...stylex.props(st.controls)}>
            <select {...stylex.props(st.select)} value={matchId} onChange={e => setMatchId(+e.target.value)}>
              {matches.map(m => <option key={m.match_id} value={m.match_id}>{m.label}</option>)}
            </select>
            <select {...stylex.props(st.select)} value={engine} onChange={e => setEngine(e.target.value)}>
              {['auto', 'jev', 'vader', 'none'].map(o => <option key={o}>{o}</option>)}
            </select>
            <label {...stylex.props(st.check)}><input type="checkbox" checked={narrative} onChange={e => setNarrative(e.target.checked)} /> Narrate</label>
            <label {...stylex.props(st.check)}><input type="checkbox" checked={trace} onChange={e => setTrace(e.target.checked)} /> Trace</label>
            <button {...stylex.props(st.runBtn)} onClick={run} disabled={loading}>
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>
        </div>
      </header>

      <div {...stylex.props(g.shell)}>
        {error && <div {...stylex.props(st.errorCard)}>{error}</div>}
        {!result && !error && (
          <div {...stylex.props(st.empty)}>
            <div {...stylex.props(st.emptyTitle)}>Pick a frozen match, press Analyze.</div>
            <p>Replayed IPL 2024 paper trading. Jev types every judgment — crowd read, regime, gate vetoes —
               while de-vig, Kelly sizing and settlement stay deterministic. VADER works fully offline.</p>
          </div>
        )}

        {result && (
          <>
            <div {...stylex.props(g.card)}>
              <div {...stylex.props(st.titleRow)}>
                <h1 {...stylex.props(st.h1)}>{a} vs {b}</h1>
                <div {...stylex.props(st.chips)}>
                  {[result.round, result.date, result.venue].filter(Boolean).map((t, i) =>
                    <span key={i} {...stylex.props(g.chip)}>{t}</span>)}
                  <span {...stylex.props(g.chip, st.accentChip)}>engine: {result.sentiment_source}</span>
                  {result.narrative_provider && <span {...stylex.props(g.chip)}>narrator: {result.narrative_provider}</span>}
                </div>
              </div>
              <div {...stylex.props(st.metrics)}>
                <Metric label={`${aAbbr} fair p*`} value={row?.market ? `${(row.market.p_fair[a] * 100).toFixed(1)}%` : '—'} />
                <Metric label={`${bAbbr} fair p*`} value={row?.market ? `${(row.market.p_fair[b] * 100).toFixed(1)}%` : '—'} />
                <Metric label="Overround" value={row?.market ? `${(row.market.overround * 100).toFixed(2)}%` : '—'}
                  sub={row?.market?.is_carry_forward ? 'carried forward' : undefined} />
                <Metric label="Equity" value={row ? row.ledger.equity.toFixed(1) : '—'}
                  sub={`cash ${row ? row.ledger.cash.toFixed(1) : '—'}`} />
                <Metric label="Open exposure" value={row ? row.ledger.exposure.toFixed(1) : '—'} />
              </div>
              <div {...stylex.props(st.sliderRow)}>
                <input type="range" min={1} max={ivs.length} value={cursor}
                  onChange={e => setCursor(+e.target.value)} {...stylex.props(st.slider)} />
                <span {...stylex.props(st.mono)}>{row?.name} · {row?.start_time?.slice(11, 16)}–{row?.end_time?.slice(11, 16)}</span>
              </div>
            </div>

            <div {...stylex.props(g.grid2)}>
              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>On the field</div>
                {row && !row.is_pregame && row.cricket?.batting_team ? (
                  <>
                    <div {...stylex.props(st.score)}>
                      {row.cricket.batting_team} <b>{row.cricket.innings_runs}/{row.cricket.innings_wickets}</b>
                      <span {...stylex.props(st.overs)}> {Math.floor(row.cricket.innings_legal_balls / 6)}.{row.cricket.innings_legal_balls % 6} ov</span>
                    </div>
                    <Stat label="Run rate" value={row.cricket.run_rate.toFixed(2)} />
                    <Stat label="Dot ball %" value={(row.cricket.dot_ball_pct * 100).toFixed(1)} />
                    <Stat label="Boundary %" value={(row.cricket.boundary_ball_pct * 100).toFixed(1)} />
                    <Stat label="Partnership" value={`${row.cricket.partnership_runs} (${row.cricket.partnership_legal_balls}b)`} />
                  </>
                ) : <div {...stylex.props(st.dim)}>{row?.is_pregame ? 'Pregame — no balls yet.' : 'No balls in this interval.'}</div>}
              </div>

              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>Paper signal</div>
                {row && <>
                  <Stat label="Reason" value={row.signal.reason} />
                  {row.signal.p_view_a != null && <>
                    <Stat label="p* market" value={`${(row.signal.p_market_a * 100).toFixed(1)}%`} />
                    <Stat label="p_sent" value={`${(row.signal.p_sent_a * 100).toFixed(1)}%`} />
                    <Stat label="p_view" value={`${(row.signal.p_view_a * 100).toFixed(1)}%`} />
                    <Stat label="edge" value={`${(row.signal.edge_a * 100).toFixed(1)}%`} />
                    <Stat label="α (shrink)" value={row.signal.alpha.toFixed(2)} />
                  </>}
                  {row.fill ? (
                    <div {...stylex.props(st.fillBox)}>
                      Fill — back <b>{row.fill.team}</b> @ {row.fill.decimal_odds.toFixed(2)} for {row.fill.stake.toFixed(2)}
                      {row.fill.gate && <div {...stylex.props(st.dim)}>gate p_genuine {row.fill.gate.p_genuine.toFixed(2)}</div>}
                    </div>
                  ) : <div {...stylex.props(st.dim)}>No fill this interval.</div>}
                </>}
              </div>

              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>Crowd ({row?.sentiment.source})</div>
                {row && <>
                  <Stat label={aAbbr} value={`${row.sentiment.team_a.mean >= 0 ? '+' : ''}${row.sentiment.team_a.mean.toFixed(3)} · n=${row.sentiment.team_a.volume} · eff ${(row.sentiment.team_a.effective_volume ?? 0).toFixed(0)}`} />
                  <Stat label={bAbbr} value={`${row.sentiment.team_b.mean >= 0 ? '+' : ''}${row.sentiment.team_b.mean.toFixed(3)} · n=${row.sentiment.team_b.volume} · eff ${(row.sentiment.team_b.effective_volume ?? 0).toFixed(0)}`} />
                  {[...(row.sentiment.team_a.sample_positive || []), ...(row.sentiment.team_b.sample_negative || [])].slice(0, 3).map((q, i) =>
                    <div key={i} {...stylex.props(st.quote)}>“{q}”</div>)}
                </>}
              </div>

              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>Narrative</div>
                {row?.narrative ? <div {...stylex.props(st.narrative)}>“{row.narrative}”</div>
                  : <div {...stylex.props(st.dim)}>No narration for this interval (Jev said skip, or narrator off).</div>}
              </div>
            </div>

            <div {...stylex.props(g.card)}>
              <div {...stylex.props(g.cardTitle)}>Market p* vs sentiment view — click to replay</div>
              <LineChart pct yMin={0} yMax={100} cursor={cursor} onPick={i => setCursor(i + 1)} series={[
                { name: `${aAbbr} p*`, color: C.teamA, values: ivs.map(r => r.market ? r.market.p_fair[a] * 100 : null) },
                { name: `${bAbbr} p*`, color: C.teamB, values: ivs.map(r => r.market ? r.market.p_fair[b] * 100 : null) },
                { name: 'p_view', color: C.accent, width: 1.8, dash: '5 4', values: ivs.map(r => r.signal.p_view_a == null ? null : r.signal.p_view_a * 100) },
              ]} />
              <div {...stylex.props(st.legend)}>
                <span><i {...stylex.props(st.dot, { backgroundColor: C.teamA })} />{aAbbr} fair</span>
                <span><i {...stylex.props(st.dot, { backgroundColor: C.teamB })} />{bAbbr} fair</span>
                <span><i {...stylex.props(st.dot, { backgroundColor: C.accent })} />p_view (sentiment)</span>
              </div>
            </div>

            <div {...stylex.props(g.grid2)}>
              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>Crowd lean (−1 to +1)</div>
                <LineChart yMin={-1} yMax={1} cursor={cursor} onPick={i => setCursor(i + 1)} series={[
                  { name: aAbbr, color: C.teamA, values: ivs.map(r => r.sentiment.team_a.mean) },
                  { name: bAbbr, color: C.teamB, values: ivs.map(r => r.sentiment.team_b.mean) },
                ]} />
              </div>
              <div {...stylex.props(g.card)}>
                <div {...stylex.props(g.cardTitle)}>Equity (cash + MTM)</div>
                <LineChart cursor={cursor} onPick={i => setCursor(i + 1)} series={[
                  { name: 'equity', color: C.accent, width: 2.2, values: ivs.map(r => r.ledger.equity) },
                  { name: 'cash', color: C.muted, width: 1.4, dash: '4 3', values: ivs.map(r => r.ledger.cash) },
                  { name: 'fills', color: C.green, points: true, width: 0,
                    values: ivs.map(r => r.fill ? r.ledger.equity : null) },
                ]} />
              </div>
            </div>

            <JevPanel result={result} row={row} />

            <div {...stylex.props(g.card)}>
              <div {...stylex.props(g.cardTitle)}>Ledger</div>
              <div {...stylex.props(st.metrics)}>
                <Metric label="Settled PnL" value={`${result.realized_pnl >= 0 ? '+' : ''}${result.realized_pnl.toFixed(2)}`}
                  tone={result.realized_pnl > 0 ? 'good' : result.realized_pnl < 0 ? 'bad' : undefined} />
                <Metric label="Fills" value={String(result.n_fills)} />
                <Metric label="Hit rate" value={result.hit_rate == null ? '—' : `${(result.hit_rate * 100).toFixed(0)}%`} />
                <Metric label="Max drawdown" value={`${(result.max_drawdown * 100).toFixed(1)}%`} />
              </div>
              <div {...stylex.props(st.tableWrap)}>
                <table {...stylex.props(st.table)}>
                  <thead><tr>{['#', 'interval', 'cash', 'exposure', 'equity', 'fill', 'gate p'].map(h =>
                    <th key={h} {...stylex.props(st.th)}>{h}</th>)}</tr></thead>
                  <tbody>
                    {ivs.map((r, i) => (
                      <tr key={i} {...stylex.props(i === cursor - 1 && st.trActive)} onClick={() => setCursor(i + 1)}>
                        <td {...stylex.props(st.td)}>{i + 1}</td>
                        <td {...stylex.props(st.td)}>{r.name}</td>
                        <td {...stylex.props(st.td, st.mono)}>{r.ledger.cash.toFixed(2)}</td>
                        <td {...stylex.props(st.td, st.mono)}>{r.ledger.exposure.toFixed(2)}</td>
                        <td {...stylex.props(st.td, st.mono)}>{r.ledger.equity.toFixed(2)}</td>
                        <td {...stylex.props(st.td)}>{r.fill ? `${r.fill.team} @ ${r.fill.decimal_odds.toFixed(2)}` : ''}</td>
                        <td {...stylex.props(st.td, st.mono)}>{r.fill?.gate ? r.fill.gate.p_genuine.toFixed(2) : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div {...stylex.props(st.dim)}>cash + exposure = bankroll + realized PnL (fees 0). Final interval settles on frozen winner {result.winner ? `(${result.winner})` : ''} — never visible to live features.</div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

const st = stylex.create({
  topbar: { position: 'sticky', top: 0, zIndex: 10, backgroundColor: 'rgba(255,255,255,.92)', backdropFilter: 'blur(8px)', borderBottom: `1px solid ${tokens.border}` },
  topInner: { maxWidth: '1180px', margin: '0 auto', padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' },
  brand: { fontSize: '15px', fontWeight: 700, letterSpacing: '-0.01em' },
  brandTag: { marginLeft: '6px', fontSize: '11px', fontWeight: 600, color: tokens.accentText, backgroundColor: tokens.accentSoft, borderRadius: '999px', padding: '2px 8px', verticalAlign: '2px' },
  controls: { display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
  select: { fontFamily: tokens.font, fontSize: '13px', padding: '7px 10px', borderRadius: tokens.radiusSm, border: `1px solid ${tokens.borderStrong}`, backgroundColor: tokens.surface, color: tokens.text, maxWidth: '300px' },
  check: { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '13px', color: tokens.textDim, cursor: 'pointer' },
  runBtn: { fontFamily: tokens.font, fontSize: '13px', fontWeight: 600, color: '#fff', backgroundColor: { default: tokens.accent, ':disabled': tokens.textFaint }, border: 'none', borderRadius: tokens.radiusSm, padding: '8px 16px', cursor: { default: 'pointer', ':disabled': 'default' } },
  errorCard: { backgroundColor: tokens.redSoft, border: `1px solid ${tokens.red}30`, color: tokens.red, borderRadius: tokens.radius, padding: '14px 18px', marginTop: '16px', fontSize: '13px' },
  empty: { ...{ padding: '64px 20px', textAlign: 'center', color: tokens.textDim } },
  emptyTitle: { fontSize: '18px', fontWeight: 600, color: tokens.text, marginBottom: '8px' },
  titleRow: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '14px' },
  h1: { fontSize: '22px', fontWeight: 700, margin: 0, letterSpacing: '-0.02em' },
  chips: { display: 'flex', gap: '6px', flexWrap: 'wrap' },
  accentChip: { color: tokens.accentText, backgroundColor: tokens.accentSoft, borderColor: `${tokens.accent}30` },
  metrics: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' },
  metric: { padding: '10px 14px', borderRadius: tokens.radiusSm, backgroundColor: tokens.bg, border: `1px solid ${tokens.border}` },
  metricGood: { backgroundColor: tokens.greenSoft, borderColor: `${tokens.green}30` },
  metricBad: { backgroundColor: tokens.redSoft, borderColor: `${tokens.red}30` },
  metricLabel: { fontSize: '11px', fontWeight: 600, color: tokens.textDim, textTransform: 'uppercase', letterSpacing: '0.04em' },
  metricValue: { fontSize: '19px', fontWeight: 700, fontVariantNumeric: 'tabular-nums' },
  metricSub: { fontSize: '11px', color: tokens.textFaint },
  sliderRow: { display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' },
  slider: { flex: 1, accentColor: tokens.accent },
  mono: { fontFamily: tokens.mono, fontSize: '12px', fontVariantNumeric: 'tabular-nums' },
  score: { fontSize: '15px', marginBottom: '8px' },
  overs: { color: tokens.textDim, fontSize: '13px' },
  stat: { display: 'flex', justifyContent: 'space-between', gap: '12px', padding: '5px 0', borderBottom: `1px dashed ${tokens.border}` },
  statLabel: { color: tokens.textDim, fontSize: '13px' },
  dim: { color: tokens.textFaint, fontSize: '12.5px', marginTop: '6px' },
  fillBox: { marginTop: '10px', padding: '10px 12px', borderRadius: tokens.radiusSm, backgroundColor: tokens.accentSoft, color: tokens.accentText, fontSize: '13px' },
  quote: { fontSize: '12px', color: tokens.textDim, fontStyle: 'italic', borderLeft: `2px solid ${tokens.borderStrong}`, paddingLeft: '8px', marginTop: '7px' },
  narrative: { fontSize: '14px', lineHeight: 1.6, color: tokens.text },
  legend: { display: 'flex', gap: '16px', marginTop: '8px', fontSize: '12px', color: tokens.textDim },
  dot: { display: 'inline-block', width: '9px', height: '9px', borderRadius: '999px', marginRight: '5px' },
  tableWrap: { maxHeight: '300px', overflow: 'auto', marginTop: '12px', border: `1px solid ${tokens.border}`, borderRadius: tokens.radiusSm },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '12.5px' },
  th: { textAlign: 'left', padding: '8px 10px', position: 'sticky', top: 0, backgroundColor: tokens.bg, color: tokens.textDim, fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: `1px solid ${tokens.border}` },
  td: { padding: '6px 10px', borderBottom: `1px solid ${tokens.border}` },
  trActive: { backgroundColor: tokens.accentSoft },
})
