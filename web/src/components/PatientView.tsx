import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { wordDiff } from '../lib/text'
import type { State } from '../lib/types'
import { useMedbridge } from '../lib/useMedbridge'
import { CameraPanel } from './CameraPanel'
import { SigningStage } from './SigningStage'
import { Disclaimer, Icon, StatusPill, Waveform, Wordmark, sourceLabel } from './ui'

type Send = (msg: Record<string, unknown>) => void

export function PatientView() {
  const { state, connected, fps, landmarks, level, send } = useMedbridge('patient')
  const [countdown, setCountdown] = useState<number | null>(null)
  return (
    <div className="grain flex min-h-full flex-col bg-ink text-bone lg:h-full lg:min-h-[760px]">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 lg:px-10 lg:pt-7">
        <Wordmark role="Patient" tone="dark" />
        <div className="flex items-center gap-5">
          {state && <DoctorMic asr={state.asr.state} />}
          <Waveform level={level} color="#f2eee6" />
          {!connected && <StatusPill tone="warn" label="Reconnecting" pulse />}
        </div>
      </header>
      {state ? (
        <main className="grid min-h-0 flex-1 grid-cols-1 gap-6 px-5 py-5 lg:grid-cols-12 lg:gap-10 lg:px-10 lg:py-7">
          <section className="flex flex-col gap-5 lg:col-span-7 lg:min-h-0">
            <div className="flex h-[42vh] min-h-[260px] lg:h-auto lg:min-h-0 lg:flex-[1.15]">
              <SigningStage signing={state.signing} />
            </div>
            <div className="flex max-h-[34vh] min-h-[180px] flex-col lg:max-h-none lg:min-h-0 lg:flex-1">
              <Captions state={state} />
            </div>
          </section>
          <section className="flex min-h-0 flex-col gap-5 pb-2 lg:col-span-5 lg:overflow-y-auto">
            <CameraPanel landmarks={landmarks} signState={state.sign.state} mode={state.sign.mode} fps={fps}
              compact={!!state.natural || state.precise.length > 0} countdown={countdown} />
            <ModeSwitch mode={state.sign.mode} send={send} />
            {state.sign.mode === 'natural' && <NaturalControl state={state} send={send} countdown={countdown} setCountdown={setCountdown} />}
            {state.sign.mode === 'natural' ? <NaturalReply state={state} send={send} /> : <PreciseReply state={state} send={send} />}
            <Composer state={state} send={send} />
          </section>
        </main>
      ) : (
        <div className="grid flex-1 place-items-center font-serif text-3xl italic text-bone/50">Connecting…</div>
      )}
      <Disclaimer tone="dark" />
    </div>
  )
}

function DoctorMic({ asr }: { asr: State['asr']['state'] }) {
  if (asr === 'speech') return <StatusPill tone="live" label="Doctor speaking" pulse />
  if (asr === 'paused') return <StatusPill tone="idle" label="Captions paused" />
  if (asr === 'loading') return <StatusPill tone="warn" label="Loading speech model" pulse />
  return <StatusPill tone="ok" label="Listening to doctor" />
}

function Captions({ state }: { state: State }) {
  const recent = state.captions.slice(-4)
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="eyebrow flex items-center gap-3 text-bone/45">
        <span className="h-px w-8 bg-bone/30" /> The doctor said
      </div>
      <div className="flex min-h-0 flex-1 flex-col justify-end gap-6 overflow-hidden pb-4">
        {recent.length === 0 && !state.interim && (
          <p className="font-serif text-5xl italic leading-tight text-bone/30">The doctor's words will appear here as they speak.</p>
        )}
        <AnimatePresence initial={false}>
          {recent.map((c, i) => {
            const latest = i === recent.length - 1
            const age = recent.length - 1 - i
            return (
              <motion.div key={c.id} layout initial={{ opacity: 0, y: 24, filter: 'blur(8px)' }}
                animate={{ opacity: latest ? 1 : Math.max(0.22, 0.6 - age * 0.13), y: 0, filter: 'blur(0px)' }}
                transition={{ type: 'spring', stiffness: 260, damping: 30 }}>
                {c.original && <span className="eyebrow mb-2 inline-block rounded-full bg-amber/15 px-2.5 py-1 text-amber">Corrected by doctor</span>}
                <p className={`font-bold leading-[1.12] tracking-[-0.01em] ${latest ? 'text-[clamp(30px,2.6vw,44px)]' : 'text-[clamp(20px,1.6vw,26px)]'}`}>
                  {wordDiff(c.original, c.text).map((w, k) => (
                    <span key={k} className={w.changed ? 'text-amber underline decoration-amber/60 decoration-2 underline-offset-8' : ''}>{w.word} </span>
                  ))}
                </p>
              </motion.div>
            )
          })}
          {state.interim && (
            <motion.p key={`interim-${state.interim.id}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="shimmer text-[clamp(30px,2.6vw,44px)] font-bold leading-[1.12]">
              {state.interim.text}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

function ModeSwitch({ mode, send }: { mode: string; send: Send }) {
  const options = [['natural', 'Natural signing'], ['precise', 'One sign at a time']] as const
  return (
    <div className="grid grid-cols-2 rounded-full border border-ink-line bg-ink-raised p-1">
      {options.map(([value, label]) => (
        <button key={value} onClick={() => mode !== value && send({ type: 'mode.set', mode: value })}
          className={`relative rounded-full py-2.5 text-[15px] font-bold transition-colors ${mode === value ? 'text-ink' : 'text-bone/60 hover:text-bone'}`}>
          {mode === value && <motion.span layoutId="mode-pill" className="absolute inset-0 rounded-full bg-bone"
            transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
          <span className="relative">{label}</span>
        </button>
      ))}
    </div>
  )
}

/** Natural signing is recorded between an explicit Start (3-2-1 countdown) and Done. Space does the same. */
function NaturalControl({ state, send, countdown, setCountdown }: {
  state: State; send: Send; countdown: number | null; setCountdown: (n: number | null) => void
}) {
  const signing = state.sign.state === 'signing'
  const busy = state.sign.state === 'translating' || state.sign.state === 'loading'
  const [elapsed, setElapsed] = useState(0)

  const start = () => {
    if (signing || busy || countdown !== null) return
    let n = 3
    setCountdown(n)
    const t = setInterval(() => {
      n -= 1
      if (n > 0) { setCountdown(n); return }
      clearInterval(t)
      setCountdown(null)
      send({ type: 'sign.start' })
    }, 1000)
  }
  const done = () => { if (signing) send({ type: 'sign.done' }) }

  useEffect(() => {
    if (!signing) { setElapsed(0); return }
    const t0 = Date.now()
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 250)
    return () => clearInterval(t)
  }, [signing])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (e.code !== 'Space' || tag === 'TEXTAREA' || tag === 'INPUT') return
      e.preventDefault()
      if (signing) done(); else start()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (signing) {
    return (
      <motion.button onClick={done} whileTap={{ scale: 0.97 }}
        className="relative flex items-center justify-between overflow-hidden rounded-3xl bg-signal px-7 py-5 text-left text-ink">
        <motion.span className="absolute inset-0 bg-white/20" animate={{ opacity: [0, 0.6, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />
        <span className="relative">
          <span className="block text-[22px] font-bold">Done</span>
          <span className="text-[14px] opacity-80">Tap or press Space when you finish your sentence</span>
        </span>
        <span className="relative font-mono text-[28px]">0:{String(elapsed).padStart(2, '0')}</span>
      </motion.button>
    )
  }
  return (
    <button onClick={start} disabled={busy || countdown !== null}
      className="flex items-center justify-between rounded-3xl border border-bone/25 bg-ink-raised px-7 py-5 text-left transition-colors hover:border-bone/50 disabled:opacity-40">
      <span>
        <span className="block text-[22px] font-bold">{busy ? 'Translating…' : countdown !== null ? 'Get ready…' : 'Start signing'}</span>
        <span className="text-[14px] text-bone/55">Tap or press Space, sign your sentence, then tap Done</span>
      </span>
      <Icon name="hand" size={30} />
    </button>
  )
}

function NaturalReply({ state, send }: { state: State; send: Send }) {
  const n = state.natural
  if (!n) return null
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="eyebrow text-bone/45">Closest ER phrases — choose what you meant</span>
        {n.latency_ms !== null && <span className="eyebrow text-bone/35">translated in {n.latency_ms} ms</span>}
      </div>
      {n.low_confidence && (
        <p className="mb-3 rounded-2xl bg-amber/12 px-4 py-3 text-[15px] text-amber">
          Low confidence. None of these may be right — retry, or switch to one sign at a time.
        </p>
      )}
      <div className="flex flex-col gap-2.5">
        {n.candidates.map((c, i) => (
          <motion.button key={`${n.seg_id}-${i}`} onClick={() => send({ type: 'candidate.pick', index: i })}
            initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.07 }}
            className={`group flex items-center gap-4 rounded-2xl border px-5 py-4 text-left transition-colors ${n.selected === i ? 'border-mint bg-mint/10' : 'border-ink-line bg-ink-raised hover:border-bone/30'}`}>
            <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${n.selected === i ? 'border-mint bg-mint text-ink' : 'border-bone/25'}`}>
              {n.selected === i && <Icon name="check" size={14} />}
            </span>
            <span className="flex-1">
              <span className="eyebrow block text-bone/40">{c.kind === 'free' ? 'Free translation' : 'ER phrase'}</span>
              <span className="text-[19px] leading-snug">{c.text}</span>
            </span>
            <span className="flex w-16 flex-col items-end gap-1">
              <span className="font-mono text-xs text-bone/50">{Math.round(c.rel_score * 100)}%</span>
              <span className="h-1 w-full overflow-hidden rounded-full bg-bone/10">
                <span className="block h-full rounded-full bg-bone/60" style={{ width: `${c.rel_score * 100}%` }} />
              </span>
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}

function PreciseReply({ state, send }: { state: State; send: Send }) {
  const [open, setOpen] = useState<number | null>(null)
  const [vocab, setVocab] = useState<string[] | null>(null)
  const [showVocab, setShowVocab] = useState(false)
  useEffect(() => { fetch('/api/vocab').then((r) => r.json()).then(setVocab).catch(() => setVocab([])) }, [])
  const openItem = state.precise.find((i) => i.seg_id === open)
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="eyebrow text-bone/45">Your signs</span>
        <button onClick={() => setShowVocab((v) => !v)} className="eyebrow text-bone/45 hover:text-bone">
          Signs I can recognize {vocab ? `(${vocab.length})` : ''}
        </button>
      </div>
      {state.precise.length === 0 ? (
        <p className="rounded-3xl border border-dashed border-ink-line px-6 py-5 text-bone/60">Sign one word, lower your hands, then sign the next.</p>
      ) : (
        <div className="flex flex-wrap gap-2.5">
          <AnimatePresence>
            {state.precise.map((item) => (
              <motion.div key={item.seg_id} layout initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.6, opacity: 0 }} transition={{ type: 'spring', stiffness: 420, damping: 26 }}
                className={`flex items-center overflow-hidden rounded-2xl border ${item.uncertain ? 'border-dashed border-amber text-amber' : 'border-bone/20 bg-ink-raised'}`}>
                <button onClick={() => setOpen(open === item.seg_id ? null : item.seg_id)} className="flex flex-col items-start px-4 py-2.5">
                  <span className="text-[18px] font-bold">{item.chosen ?? 'Not sure — pick'}</span>
                  <span className="mt-1 h-1 w-16 overflow-hidden rounded-full bg-bone/10">
                    <span className="block h-full bg-mint" style={{ width: `${(item.topk[0]?.p ?? 0) * 100}%` }} />
                  </span>
                </button>
                <button onClick={() => send({ type: 'sign.remove', seg_id: item.seg_id })} aria-label="Remove sign"
                  className="self-stretch border-l border-current/15 px-2.5 opacity-60 hover:opacity-100"><Icon name="x" size={14} /></button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
      <AnimatePresence>
        {openItem && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-3 rounded-2xl border border-ink-line bg-ink-raised p-2">
            <p className="eyebrow px-3 pb-1 pt-2 text-bone/45">Did you mean</p>
            {openItem.topk.map((t) => (
              <button key={t.label} onClick={() => { send({ type: 'sign.pick', seg_id: openItem.seg_id, label: t.label }); setOpen(null) }}
                className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left hover:bg-bone/5">
                <span className="text-[17px]">{t.label}</span>
                <span className="font-mono text-xs text-bone/50">{Math.round(t.p * 100)}%</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence>
        {showVocab && vocab && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-3 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto rounded-2xl border border-ink-line p-3">
              {vocab.map((v) => <span key={v} className="rounded-full bg-bone/8 px-2.5 py-1 text-[13px] text-bone/75">{v}</span>)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Composer({ state, send }: { state: State; send: Send }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const draft = state.draft
  const last = state.messages[state.messages.length - 1]
  const seenId = useRef(last?.id)

  useEffect(() => {
    if (!last || last.id === seenId.current) return
    seenId.current = last.id
    setSent(last.text)
    const t = setTimeout(() => setSent(null), 3500)
    return () => clearTimeout(t)
  }, [last?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const startEdit = () => { setText(draft.text); setEditing(true) }
  const saveEdit = () => { send({ type: 'draft.edit', text }); setEditing(false) }

  return (
    <div className="sticky bottom-0 z-10 mt-auto rounded-3xl border border-ink-line bg-ink-raised p-5 shadow-[0_-24px_40px_-12px_rgb(14_15_12)]">
      <div className="mb-2 flex items-center justify-between">
        <span className="eyebrow text-bone/45">Your message to the doctor</span>
        {(draft.text || draft.edited) && (
          <span className="eyebrow text-bone/40">{sourceLabel[draft.source] ?? draft.source}{draft.edited ? ' · edited' : ''}</span>
        )}
      </div>
      {editing ? (
        <textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} rows={2}
          className="w-full resize-none rounded-xl bg-ink px-3 py-2 text-[24px] leading-snug outline-none ring-1 ring-bone/20 focus:ring-mint" />
      ) : (
        <p className={`leading-snug ${draft.source === 'natural' && !draft.edited ? 'line-clamp-2 text-[17px] text-bone/75' : 'min-h-[34px] text-[24px]'} ${draft.text ? '' : 'text-bone/30'}`}>
          {draft.text || 'Nothing yet'}
        </p>
      )}
      <div className="mt-4 flex items-center gap-2.5">
        {editing ? (
          <button onClick={saveEdit} className="flex items-center gap-2 rounded-full border border-bone/25 px-4 py-2.5 font-bold hover:bg-bone/10"><Icon name="check" /> Save</button>
        ) : (
          <button onClick={startEdit} className="flex items-center gap-2 rounded-full border border-bone/25 px-4 py-2.5 font-bold hover:bg-bone/10"><Icon name="edit" /> Edit</button>
        )}
        <button onClick={() => { send({ type: 'draft.clear' }); setEditing(false) }}
          className="flex items-center gap-2 rounded-full border border-bone/25 px-4 py-2.5 font-bold hover:bg-bone/10"><Icon name="retry" /> Retry</button>
        <motion.button whileTap={{ scale: 0.96 }} disabled={!draft.text.trim() || editing}
          onClick={() => send({ type: 'draft.confirm' })}
          className="ml-auto flex items-center gap-2 rounded-full bg-mint px-6 py-3 text-[17px] font-bold text-ink transition-opacity disabled:opacity-25">
          <Icon name="check" /> Confirm &amp; send
        </motion.button>
      </div>
      <AnimatePresence>
        {sent && (
          <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-3 flex items-center gap-2 text-[15px] text-mint"><Icon name="check" size={16} /> Sent to the doctor: “{sent}”</motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
