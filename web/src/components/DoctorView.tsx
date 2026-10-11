import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { timeline } from '../lib/text'
import { themeColor } from '../lib/theme'
import type { Caption, Message, State } from '../lib/types'
import { useMedbridge } from '../lib/useMedbridge'
import { Icon, StatusPill, Waveform, Wordmark /* , sourceLabel */ } from './ui'

type Send = (msg: Record<string, unknown>) => void
const time = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const NO_MESSAGES: Message[] = []

export function DoctorView() {
  const { state, connected, /* fps, */ level, send } = useMedbridge('doctor')
  const speech = useSpeech(state?.messages ?? NO_MESSAGES)
  return (
    <div className="grain flex min-h-full flex-col bg-paper text-graphite lg:h-full lg:min-h-[760px]">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 lg:px-10 lg:pt-7">
        <Wordmark role="Clinician" tone="light" />
        <div className="flex flex-wrap items-center gap-3 lg:gap-4">
          {state && <AsrPill asr={state.asr.state} />}
          <Waveform level={level} color={themeColor('graphite')} />
          {state && (
            <button onClick={() => send({ type: state.asr.state === 'paused' ? 'asr.resume' : 'asr.pause' })}
              className="flex items-center gap-2 rounded-md border border-graphite/20 px-4 py-2 text-sm font-bold hover:bg-graphite/5">
              <Icon name={state.asr.state === 'paused' ? 'play' : 'pause'} size={15} />
              {state.asr.state === 'paused' ? 'Resume captions' : 'Pause captions'}
            </button>
          )}
          {speech.on && (
            <button onClick={speech.toggleAuto} role="switch" aria-checked={speech.auto}
              className={`flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-bold ${speech.auto ? 'border-doctor bg-doctor text-paper' : 'border-graphite/20 hover:bg-graphite/5'}`}>
              <Icon name="speaker" size={15} /> Auto audio {speech.auto ? 'on' : 'off'}
            </button>
          )}
          {state && (
            <button onClick={() => { if (confirm('End the session and clear the conversation from memory?')) send({ type: 'session.end' }) }}
              className="flex items-center gap-2 rounded-md border border-graphite/20 px-4 py-2 text-sm font-bold hover:bg-graphite/5">
              <Icon name="stop" size={14} /> End session
            </button>
          )}
          {!connected && <StatusPill tone="warn" label="Reconnecting" pulse />}
        </div>
      </header>
      {state ? (
        <main className="flex min-h-0 flex-1 flex-col px-5 py-5 lg:px-10 lg:py-7">
          <section className="flex min-h-[55vh] flex-1 flex-col lg:min-h-0">
            <Timeline state={state} send={send} speak={speech.on ? speech.play : null} />
          </section>
          {/* The side column (System readouts) is disabled for now; the conversation takes the full width.
          <aside className="contents lg:col-span-4 lg:flex lg:min-h-0 lg:flex-col lg:gap-5 lg:overflow-y-auto">
            <div className="order-3 lg:order-none"><Readouts state={state} fps={fps} send={send} /></div>
          </aside> */}
        </main>
      ) : (
        <div className="grid flex-1 place-items-center font-serif text-3xl italic text-graphite/50">Connecting…</div>
      )}
    </div>
  )
}

function AsrPill({ asr }: { asr: State['asr']['state'] }) {
  if (asr === 'speech') return <StatusPill tone="live" label="Hearing you" pulse />
  if (asr === 'paused') return <StatusPill tone="idle" label="Captions paused" />
  if (asr === 'loading') return <StatusPill tone="warn" label="Loading speech model" pulse />
  return <StatusPill tone="ok" label="Listening" />
}

const AUTO_AUDIO = 'medbridge.autoAudio' // this browser's "Auto audio" choice

/**
 * The patient's voice, when the server has one (ELEVENLABS_API_KEY). With "Auto audio" on, each confirmed patient
 * message that arrives while this page is open is spoken as soon as it arrives, one at a time; `play` speaks one
 * on request. Each play is fetched from the server, which mutes the microphone meanwhile.
 */
function useSpeech(messages: Message[]) {
  const [on, setOn] = useState(false)
  const [auto, setAuto] = useState(() => { try { return localStorage.getItem(AUTO_AUDIO) !== 'off' } catch { return true } })
  const handled = useRef<number | null>(null) // id of the newest message already spoken or skipped
  const missed = useRef<number | null>(null)  // a message the browser would not let us play
  const queue = useRef(Promise.resolve())
  useEffect(() => {
    fetch('/api/config').then((r) => (r.ok ? r.json() : null)).then((c) => setOn(!!c?.speech)).catch(() => {})
  }, [])
  const play = useCallback((id: number, automatic = false) => {
    queue.current = queue.current.then(async () => {
      try {
        const r = await fetch(`/api/speech/${id}`)
        if (!r.ok) return
        const url = URL.createObjectURL(await r.blob())
        const audio = new Audio(url)
        await new Promise<void>((done) => {
          audio.onended = audio.onerror = () => done()
          audio.play().catch((e) => {
            // A page that has not been clicked yet may not play sound. Show "Auto audio" as off: turning it on is the click.
            if (automatic && e?.name === 'NotAllowedError') { missed.current = id; setAuto(false) }
            done()
          })
        })
        URL.revokeObjectURL(url)
      } catch { /* no audio for this one */ }
    })
  }, [])
  useEffect(() => {
    const newest = messages.length ? messages[messages.length - 1].id : 0
    if (handled.current !== null && on && auto) for (const m of messages) if (m.id > handled.current) play(m.id, true)
    handled.current = Math.max(handled.current ?? 0, newest)
  }, [messages, on, auto, play])
  const toggleAuto = () => {
    const next = !auto
    setAuto(next)
    try { localStorage.setItem(AUTO_AUDIO, next ? 'on' : 'off') } catch { /* the choice lasts until reload */ }
    if (next && missed.current !== null) play(missed.current)
    missed.current = null
  }
  return { on, auto, toggleAuto, play: (id: number) => play(id) }
}

function Timeline({ state, send, speak }: { state: State; send: Send; speak: ((id: number) => void) | null }) {
  const scroller = useRef<HTMLDivElement>(null)
  const entries = timeline(state.captions, state.messages)
  const [typed, setTyped] = useState('')
  const sendTyped = () => {
    if (!typed.trim()) return
    send({ type: 'caption.add', text: typed })
    setTyped('')
  }
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [entries.length, state.interim?.text])
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-[28px] border border-paper-line bg-paper-raised">
      {/* <div className="flex items-center justify-between border-b border-paper-line px-7 py-4">
        <span className="eyebrow text-graphite/50">Conversation</span>
        <span className="eyebrow text-graphite/40">Click your caption to correct it</span>
      </div> */}
      <div ref={scroller} className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-7 py-6">
        {entries.length === 0 && !state.interim && (
          <p className="m-auto max-w-md text-center font-serif text-3xl italic leading-snug text-graphite/35">
            Speak normally. Your words appear on the patient's screen as captions.
          </p>
        )}
        <AnimatePresence initial={false}>
          {entries.map((e) => e.kind === 'doctor'
            ? <DoctorLine key={`d${e.item.id}`} caption={e.item} send={send} />
            : <PatientLine key={`p${e.item.id}`} msg={e.item} speak={speak} />)}
        </AnimatePresence>
        {state.interim && (
          <div className="ml-auto max-w-[75%] text-right">
            <p className="shimmer shimmer-light text-[20px] leading-snug">{state.interim.text}</p>
          </div>
        )}
      </div>
      {/* Typed lines reach the patient like spoken captions. */}
      <form onSubmit={(e) => { e.preventDefault(); sendTyped() }} className="flex items-center gap-2.5 border-t border-paper-line px-5 py-4">
        <input value={typed} onChange={(e) => setTyped(e.target.value)} maxLength={500} placeholder="Type a message"
          aria-label="Type a message to the patient"
          className="min-w-0 flex-1 rounded-md border border-graphite/15 bg-paper px-5 py-3 text-[17px] outline-none focus:border-mint/70" />
        <button type="submit" disabled={!typed.trim()} aria-label="Send"
          className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-doctor text-paper transition-opacity disabled:opacity-25">
          <Icon name="send" />
        </button>
      </form>
    </div>
  )
}

function DoctorLine({ caption, send }: { caption: Caption; send: Send }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(caption.text)
  const save = () => { send({ type: 'caption.correct', id: caption.id, text }); setEditing(false) }
  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="ml-auto max-w-[75%] text-right">
      <p className="eyebrow mb-1.5 text-graphite/40">You · {time(caption.t)}{caption.original ? ' · corrected' : ''}</p>
      {editing ? (
        <div className="flex items-center gap-2">
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false) }}
            className="flex-1 rounded-xl border border-mint/60 bg-paper px-3 py-2 text-[18px] outline-none" />
          <button onClick={save} className="rounded-md bg-doctor px-4 py-2 text-sm font-bold text-paper">Save</button>
        </div>
      ) : (
        <button onClick={() => { setText(caption.text); setEditing(true) }}
          className="group inline-flex items-start gap-2 rounded-2xl bg-doctor px-5 py-3 text-left text-[19px] leading-snug text-paper">
          <span>{caption.text}</span>
          <span className="mt-1 opacity-0 transition-opacity group-hover:opacity-60"><Icon name="edit" size={15} /></span>
        </button>
      )}
      {caption.original && <p className="mt-1.5 text-sm text-graphite/40 line-through">{caption.original}</p>}
    </motion.div>
  )
}

function PatientLine({ msg, speak }: { msg: Message; speak: ((id: number) => void) | null }) {
  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      className="w-fit max-w-[75%] self-start rounded-2xl border border-doctor/20 bg-leaf py-3.5 pl-5 pr-6">
      <p className="eyebrow mb-1.5 flex items-center gap-1.5 text-doctor">
        <Icon name="check" size={13} /> {time(msg.t)}
        {speak && (
          <button onClick={() => speak(msg.id)} aria-label="Play aloud" className="ml-1 opacity-60 hover:opacity-100">
            <Icon name="speaker" size={15} />
          </button>
        )}
      </p>
      <p className="text-[24px] font-bold leading-snug">{msg.text}</p>
      {/* Only the final text is shown for now; this line gave the source and the signs behind it.
      <p className="eyebrow mt-2 text-graphite/45">
        {sourceLabel[msg.source] ?? msg.source}{msg.edited ? ' · edited by patient' : ''}
        {msg.glosses.length > 0 && ` · signs: ${msg.glosses.join(' · ')}`}
      </p> */}
    </motion.div>
  )
}

// The System readouts (camera fps, latencies, reply count) are disabled for now, and End session moved to the header.
// To re-enable, restore this component, the side column in DoctorView (in a 12-column grid, conversation spanning 8)
// and `fps` from useMedbridge.
// function Readouts({ state, fps, send }: { state: State; fps: number | null; send: Send }) {
//   const lastPrecise = state.precise[state.precise.length - 1]
//   const rows: [string, string][] = [
//     ['Camera', fps === null ? '—' : `${fps.toFixed(0)} fps`],
//     ['Sentence translation', state.natural?.latency_ms != null ? `${state.natural.latency_ms} ms` : '—'],
//     ['Sign recognition', lastPrecise?.latency_ms != null ? `${lastPrecise.latency_ms} ms` : '—'],
//     ['Confirmed replies', String(state.messages.length)],
//   ]
//   return (
//     <div className="rounded-[28px] border border-paper-line bg-paper-raised p-6">
//       <span className="eyebrow text-graphite/50">System</span>
//       <dl className="mt-3 divide-y divide-paper-line">
//         {rows.map(([k, v]) => (
//           <div key={k} className="flex justify-between py-2.5">
//             <dt className="text-[15px] text-graphite/60">{k}</dt>
//             <dd className="font-mono text-[14px]">{v}</dd>
//           </div>
//         ))}
//       </dl>
//     </div>
//   )
// }
