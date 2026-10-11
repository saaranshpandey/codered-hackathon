import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { signedWordSpans } from '../lib/text'
import { themeColor } from '../lib/theme'
import type { SignedWord, State } from '../lib/types'
import { useMedbridge } from '../lib/useMedbridge'
import { CameraPanel } from './CameraPanel'
import { SigningStage } from './SigningStage'
import { Icon, StatusPill, Waveform, Wordmark } from './ui'

type Send = (msg: Record<string, unknown>) => void

export function PatientView() {
  const { state, connected, landmarks, level, send } = useMedbridge('patient')
  // Natural signing is disabled for now. To re-enable, restore the commented lines in this component and the
  // ModeSwitch, NaturalControl and NaturalReply components below, then the engine in medbridge/server.py.
  // const [countdown, setCountdown] = useState<number | null>(null)
  const [signed, setSigned] = useState<SignedWord | null>(null)
  return (
    <div className="grain flex min-h-full flex-col bg-ink text-bone lg:h-full lg:min-h-[760px]">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 lg:px-10 lg:pt-7">
        <Wordmark role="Patient" tone="dark" />
        <div className="flex items-center gap-5">
          {state && <DoctorMic asr={state.asr.state} />}
          <Waveform level={level} color={themeColor('bone')} />
          {!connected && <StatusPill tone="warn" label="Reconnecting" pulse />}
        </div>
      </header>
      {state ? (
        // Wide screens: a 2 x 2 grid. Top row: the mascot, and the camera centred against it. Bottom row: the
        // captions, and the message box. Narrow screens: one column, in the order written here.
        <main className="grid min-h-0 flex-1 grid-cols-1 gap-5 px-5 py-5 lg:grid-cols-12 lg:grid-rows-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-x-10 lg:px-10 lg:py-7">
          <div className="flex h-[42vh] min-h-[260px] lg:col-span-8 lg:col-start-1 lg:row-start-1 lg:h-auto lg:min-h-0">
            <SigningStage signing={state.signing} onWord={setSigned} />
          </div>
          <div className="flex max-h-[34vh] min-h-[180px] flex-col lg:col-span-8 lg:col-start-1 lg:row-start-2 lg:max-h-none lg:min-h-0">
            <Captions state={state} signed={signed} />
          </div>
          <div className="flex flex-col justify-center lg:col-span-4 lg:col-start-9 lg:row-start-1 lg:min-h-0">
            {/* the camera itself is centred; the switch hangs just below it */}
            <div className="relative">
              <CameraPanel landmarks={landmarks} signState={state.sign.state} mode={state.sign.mode}
                enabled={state.sign.enabled !== false}
                compact={false /* !!state.natural || state.precise.length > 0: shrank the video to make room for the sign chips */}
                countdown={null /* countdown */} />
              {/* <ModeSwitch mode={state.sign.mode} send={send} /> */}
              {/* {state.sign.mode === 'natural' && <NaturalControl state={state} send={send} countdown={countdown} setCountdown={setCountdown} />} */}
              {/* {state.sign.mode === 'natural' ? <NaturalReply state={state} send={send} /> : <PreciseReply state={state} send={send} />} */}
              <div className="mt-4 lg:absolute lg:inset-x-0 lg:top-full">
                <PreciseReply state={state} send={send} />
              </div>
            </div>
          </div>
          <div className="flex flex-col justify-end lg:col-span-4 lg:col-start-9 lg:row-start-2 lg:min-h-0">
            <Composer state={state} send={send} />
          </div>
        </main>
      ) : (
        <div className="grid flex-1 place-items-center font-serif text-3xl italic text-bone/50">Connecting…</div>
      )}
    </div>
  )
}

function DoctorMic({ asr }: { asr: State['asr']['state'] }) {
  if (asr === 'speech') return <StatusPill tone="live" label="Doctor speaking" pulse />
  if (asr === 'paused') return <StatusPill tone="idle" label="Captions paused" />
  if (asr === 'loading') return <StatusPill tone="warn" label="Loading speech model" pulse />
  return <StatusPill tone="ok" label="Listening to doctor" />
}

const clock = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })

function Captions({ state, signed }: { state: State; signed: SignedWord | null }) {
  const captions = state.captions
  const newest = captions[captions.length - 1]
  // The caption words the mascot is signing right now are shown in a stronger colour.
  const signing = signed && state.signing?.caption_id === signed.captionId ? state.signing.words : null
  // The list follows the newest caption unless the patient has scrolled up to read back.
  // Only the patient's own upward scroll pauses following: scroll events the browser fires while the
  // layout shifts (interim line leaving, captions animating in, the signing panel resizing) must not.
  const scroller = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const follow = useRef(true)
  useEffect(() => {
    const el = scroller.current
    if (el && follow.current) el.scrollTop = el.scrollHeight
  }, [captions, state.interim]) // every snapshot: a correction to an older caption can change the height too
  useEffect(() => {
    const el = scroller.current, inner = content.current
    if (!el || !inner) return
    const ro = new ResizeObserver(() => { if (follow.current) el.scrollTop = el.scrollHeight })
    ro.observe(el)
    ro.observe(inner)
    return () => ro.disconnect()
  }, [])
  const pause = () => { follow.current = false }
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <motion.div ref={scroller} layoutScroll tabIndex={-1}
        onScroll={(e) => { const el = e.currentTarget; if (el.scrollHeight - el.scrollTop - el.clientHeight < 48) follow.current = true }}
        onWheel={(e) => { if (e.deltaY < 0) pause() }}
        onTouchMove={pause}
        onKeyDown={(e) => { if (['ArrowUp', 'PageUp', 'Home'].includes(e.key)) pause() }}
        onPointerDown={(e) => { if (e.target === e.currentTarget) pause() /* scrollbar drag */ }}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto pb-4 pr-2 outline-none [scrollbar-color:color-mix(in_srgb,var(--color-bone)_25%,transparent)_transparent] [scrollbar-width:thin]">
        <div ref={content} className="mt-auto flex flex-col gap-6">
          {captions.length === 0 && !state.interim && (
            <p className="font-serif text-5xl italic leading-tight text-bone/30">The doctor's words will appear here as they speak.</p>
          )}
          <AnimatePresence initial={false}>
            {captions.map((c) => {
              const latest = c === newest
              const now = signing && c.id === signed!.captionId ? signedWordSpans(c.text, signing.map((w) => w.word))[signed!.index] ?? [] : []
              return (
                <motion.div key={c.id} layout initial={{ opacity: 0, y: 24, filter: 'blur(8px)' }}
                  animate={{ opacity: latest ? 1 : 0.55, y: 0, filter: 'blur(0px)' }}
                  transition={{ type: 'spring', stiffness: 260, damping: 30 }}>
                  <time className="eyebrow mb-1.5 block text-bone/50">{clock(c.t)}</time>
                  <p className={`font-bold leading-[1.12] tracking-[-0.01em] ${latest ? 'text-[clamp(30px,2.6vw,44px)]' : 'text-[clamp(20px,1.6vw,26px)]'}`}>
                    {c.text.split(/\s+/).filter(Boolean).map((word, k) => (
                      <span key={k}>
                        <span className={`-mx-[0.1em] rounded-[0.18em] px-[0.1em] transition-colors duration-150 ${now.includes(k) ? 'bg-signal' : ''}`}>{word}</span>{' '}
                      </span>
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
      </motion.div>
    </div>
  )
}

// function ModeSwitch({ mode, send }: { mode: string; send: Send }) {
//   const options = [['natural', 'Natural signing'], ['precise', 'One sign at a time']] as const
//   return (
//     <div className="grid grid-cols-2 rounded-full border border-ink-line bg-ink-raised p-1">
//       {options.map(([value, label]) => (
//         <button key={value} onClick={() => mode !== value && send({ type: 'mode.set', mode: value })}
//           className={`relative rounded-full py-2.5 text-[15px] font-bold transition-colors ${mode === value ? 'text-ink' : 'text-bone/60 hover:text-bone'}`}>
//           {mode === value && <motion.span layoutId="mode-pill" className="absolute inset-0 rounded-full bg-bone"
//             transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
//           <span className="relative">{label}</span>
//         </button>
//       ))}
//     </div>
//   )
// }
//
// /** Natural signing is recorded between an explicit Start (3-2-1 countdown) and Done. Space does the same. */
// function NaturalControl({ state, send, countdown, setCountdown }: {
//   state: State; send: Send; countdown: number | null; setCountdown: (n: number | null) => void
// }) {
//   const signing = state.sign.state === 'signing'
//   const busy = state.sign.state === 'translating' || state.sign.state === 'loading'
//   const [elapsed, setElapsed] = useState(0)
//
//   const start = () => {
//     if (signing || busy || countdown !== null) return
//     let n = 3
//     setCountdown(n)
//     const t = setInterval(() => {
//       n -= 1
//       if (n > 0) { setCountdown(n); return }
//       clearInterval(t)
//       setCountdown(null)
//       send({ type: 'sign.start' })
//     }, 1000)
//   }
//   const done = () => { if (signing) send({ type: 'sign.done' }) }
//
//   useEffect(() => {
//     if (!signing) { setElapsed(0); return }
//     const t0 = Date.now()
//     const t = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 250)
//     return () => clearInterval(t)
//   }, [signing])
//
//   useEffect(() => {
//     const onKey = (e: KeyboardEvent) => {
//       const tag = (e.target as HTMLElement)?.tagName
//       if (e.code !== 'Space' || tag === 'TEXTAREA' || tag === 'INPUT') return
//       e.preventDefault()
//       if (signing) done(); else start()
//     }
//     window.addEventListener('keydown', onKey)
//     return () => window.removeEventListener('keydown', onKey)
//   })
//
//   if (signing) {
//     return (
//       <motion.button onClick={done} whileTap={{ scale: 0.97 }}
//         className="relative flex items-center justify-between overflow-hidden rounded-3xl bg-signal px-7 py-5 text-left text-ink">
//         <motion.span className="absolute inset-0 bg-white/20" animate={{ opacity: [0, 0.6, 0] }} transition={{ duration: 1.6, repeat: Infinity }} />
//         <span className="relative">
//           <span className="block text-[22px] font-bold">Done</span>
//           <span className="text-[14px] opacity-80">Tap or press Space when you finish your sentence</span>
//         </span>
//         <span className="relative font-mono text-[28px]">0:{String(elapsed).padStart(2, '0')}</span>
//       </motion.button>
//     )
//   }
//   return (
//     <button onClick={start} disabled={busy || countdown !== null}
//       className="flex items-center justify-between rounded-3xl border border-bone/25 bg-ink-raised px-7 py-5 text-left transition-colors hover:border-bone/50 disabled:opacity-40">
//       <span>
//         <span className="block text-[22px] font-bold">{busy ? 'Translating…' : countdown !== null ? 'Get ready…' : 'Start signing'}</span>
//         <span className="text-[14px] text-bone/55">Tap or press Space, sign your sentence, then tap Done</span>
//       </span>
//       <Icon name="hand" size={30} />
//     </button>
//   )
// }
//
// function NaturalReply({ state, send }: { state: State; send: Send }) {
//   const n = state.natural
//   if (!n) return null
//   return (
//     <div>
//       <div className="mb-3 flex items-center justify-between">
//         <span className="eyebrow text-bone/45">Closest ER phrases — choose what you meant</span>
//         {n.latency_ms !== null && <span className="eyebrow text-bone/35">translated in {n.latency_ms} ms</span>}
//       </div>
//       {n.low_confidence && (
//         <p className="mb-3 rounded-2xl bg-amber/12 px-4 py-3 text-[15px] text-amber">
//           Low confidence. None of these may be right — retry, or switch to one sign at a time.
//         </p>
//       )}
//       <div className="flex flex-col gap-2.5">
//         {n.candidates.map((c, i) => (
//           <motion.button key={`${n.seg_id}-${i}`} onClick={() => send({ type: 'candidate.pick', index: i })}
//             initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.07 }}
//             className={`group flex items-center gap-4 rounded-2xl border px-5 py-4 text-left transition-colors ${n.selected === i ? 'border-mint bg-mint/10' : 'border-ink-line bg-ink-raised hover:border-bone/30'}`}>
//             <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border ${n.selected === i ? 'border-mint bg-mint text-ink' : 'border-bone/25'}`}>
//               {n.selected === i && <Icon name="check" size={14} />}
//             </span>
//             <span className="flex-1">
//               <span className="eyebrow block text-bone/40">{c.kind === 'free' ? 'Free translation' : 'ER phrase'}</span>
//               <span className="text-[19px] leading-snug">{c.text}</span>
//             </span>
//             <span className="flex w-16 flex-col items-end gap-1">
//               <span className="font-mono text-xs text-bone/50">{Math.round(c.rel_score * 100)}%</span>
//               <span className="h-1 w-full overflow-hidden rounded-full bg-bone/10">
//                 <span className="block h-full rounded-full bg-bone/60" style={{ width: `${c.rel_score * 100}%` }} />
//               </span>
//             </span>
//           </motion.button>
//         ))}
//       </div>
//     </div>
//   )
// }

function Switch({ on, label, onToggle }: { on: boolean; label: string; onToggle: () => void }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={onToggle}
      className={`eyebrow flex items-center gap-2 transition-colors ${on ? 'text-bone' : 'text-bone/45 hover:text-bone'}`}>
      <span className={`relative h-[18px] w-8 rounded-[5px] transition-colors ${on ? 'bg-mint' : 'bg-bone/20'}`}>
        <span className={`absolute top-[3px] h-3 w-3 rounded-[3px] bg-on-go transition-[left] ${on ? 'left-[17px]' : 'left-[3px]'}`} />
      </span>
      {on ? 'On' : 'Off'}
    </button>
  )
}

function PreciseReply({ state, send }: { state: State; send: Send }) {
  // The sign chips are disabled for now: recognized signs go straight into "Your message to the doctor".
  // To re-enable, restore the commented lines in this component and the `compact` value on CameraPanel above.
  // const [open, setOpen] = useState<number | null>(null)
  // const openItem = state.precise.find((i) => i.seg_id === open)
  const on = state.sign.enabled !== false // a server from before the switch existed sends no value: treat as on
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="flex items-center gap-3">
          <span className="eyebrow text-bone/45">Sign recognition</span>
          <Switch on={on} label="Sign recognition" onToggle={() => send({ type: 'sign.enable', on: !on })} />
        </span>
      </div>
      {/* Hint box and sign chips (one per recognized sign, with a confidence bar, a remove button and a top-5 picker).
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
      */}
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
    <div className="mt-auto rounded-2xl border border-ink-line bg-ink-raised p-4">
      {editing ? (
        <textarea autoFocus value={text} onChange={(e) => setText(e.target.value)} rows={2}
          className="w-full resize-none rounded-lg bg-ink px-3 py-2 text-[20px] leading-snug outline-none ring-1 ring-bone/20 focus:ring-mint" />
      ) : (
        <p className={`max-h-[4.2em] min-h-[1.4em] overflow-y-auto text-[20px] font-bold leading-[1.4] ${draft.text ? '' : 'font-normal text-bone/30'}`}>
          {draft.text || 'Nothing yet'}
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {editing ? (
          <button onClick={saveEdit} className="flex items-center gap-1.5 rounded-md border border-bone/25 px-3 py-2 text-sm font-bold hover:bg-bone/10"><Icon name="check" size={15} /> Save</button>
        ) : (
          <button onClick={startEdit} className="flex items-center gap-1.5 rounded-md border border-bone/25 px-3 py-2 text-sm font-bold hover:bg-bone/10"><Icon name="edit" size={15} /> Edit</button>
        )}
        <button onClick={() => { send({ type: 'draft.clear' }); setEditing(false) }}
          className="flex items-center gap-1.5 rounded-md border border-bone/25 px-3 py-2 text-sm font-bold hover:bg-bone/10"><Icon name="retry" size={15} /> Retry</button>
        <motion.button whileTap={{ scale: 0.96 }} disabled={!draft.text.trim() || editing}
          onClick={() => send({ type: 'draft.confirm' })}
          className="ml-auto flex items-center gap-1.5 rounded-md bg-mint-deep px-4 py-2 text-[15px] font-bold text-on-go transition-opacity disabled:opacity-25">
          <Icon name="check" size={16} /> Confirm &amp; send
        </motion.button>
      </div>
      <AnimatePresence>
        {sent && (
          <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="mt-3 flex items-center gap-2 text-[15px] text-bone/80"><Icon name="check" size={16} /> Sent to the doctor: “{sent}”</motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
