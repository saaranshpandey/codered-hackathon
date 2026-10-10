import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { timeline } from '../lib/text'
import type { Caption, Message, State } from '../lib/types'
import { useMedbridge } from '../lib/useMedbridge'
import { Disclaimer, Icon, StatusPill, Waveform, Wordmark, sourceLabel } from './ui'

type Send = (msg: Record<string, unknown>) => void
const time = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export function DoctorView() {
  const { state, connected, fps, level, send } = useMedbridge('doctor')
  return (
    <div className="grain flex h-full min-h-[760px] flex-col bg-paper text-graphite">
      <header className="flex items-center justify-between px-10 pt-7">
        <Wordmark role="Clinician" tone="light" />
        <div className="flex items-center gap-4">
          {state && <AsrPill asr={state.asr.state} />}
          <Waveform level={level} color="#14150f" />
          {state && (
            <button onClick={() => send({ type: state.asr.state === 'paused' ? 'asr.resume' : 'asr.pause' })}
              className="flex items-center gap-2 rounded-full border border-graphite/20 px-4 py-2 text-sm font-bold hover:bg-graphite/5">
              <Icon name={state.asr.state === 'paused' ? 'play' : 'pause'} size={15} />
              {state.asr.state === 'paused' ? 'Resume captions' : 'Pause captions'}
            </button>
          )}
          {!connected && <StatusPill tone="warn" label="Reconnecting" pulse />}
        </div>
      </header>
      {state ? (
        <main className="grid min-h-0 flex-1 grid-cols-12 gap-8 px-10 py-7">
          <section className="col-span-8 flex min-h-0 flex-col">
            <Timeline state={state} send={send} />
          </section>
          <aside className="col-span-4 flex min-h-0 flex-col gap-5 overflow-y-auto">
            <LiveLane state={state} />
            <Readouts state={state} fps={fps} send={send} />
          </aside>
        </main>
      ) : (
        <div className="grid flex-1 place-items-center font-serif text-3xl italic text-graphite/50">Connecting…</div>
      )}
      <Disclaimer tone="light" />
    </div>
  )
}

function AsrPill({ asr }: { asr: State['asr']['state'] }) {
  if (asr === 'speech') return <StatusPill tone="live" label="Hearing you" pulse />
  if (asr === 'paused') return <StatusPill tone="idle" label="Captions paused" />
  if (asr === 'loading') return <StatusPill tone="warn" label="Loading speech model" pulse />
  return <StatusPill tone="ok" label="Listening" />
}

function Timeline({ state, send }: { state: State; send: Send }) {
  const scroller = useRef<HTMLDivElement>(null)
  const entries = timeline(state.captions, state.messages)
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [entries.length, state.interim?.text])
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-[28px] border border-paper-line bg-paper-raised">
      <div className="flex items-center justify-between border-b border-paper-line px-7 py-4">
        <span className="eyebrow text-graphite/50">Conversation</span>
        <span className="eyebrow text-graphite/40">Click your caption to correct it</span>
      </div>
      <div ref={scroller} className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-7 py-6">
        {entries.length === 0 && !state.interim && (
          <p className="m-auto max-w-md text-center font-serif text-3xl italic leading-snug text-graphite/35">
            Speak normally. Your words appear on the patient's screen as captions.
          </p>
        )}
        <AnimatePresence initial={false}>
          {entries.map((e) => e.kind === 'doctor'
            ? <DoctorLine key={`d${e.item.id}`} caption={e.item} send={send} />
            : <PatientLine key={`p${e.item.id}`} msg={e.item} />)}
        </AnimatePresence>
        {state.interim && (
          <div className="ml-auto max-w-[75%] text-right">
            <p className="shimmer shimmer-light text-[20px] leading-snug">{state.interim.text}</p>
          </div>
        )}
      </div>
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
            className="flex-1 rounded-xl border border-signal/50 bg-paper px-3 py-2 text-[18px] outline-none" />
          <button onClick={save} className="rounded-full bg-graphite px-4 py-2 text-sm font-bold text-paper">Save</button>
        </div>
      ) : (
        <button onClick={() => { setText(caption.text); setEditing(true) }}
          className="group inline-flex items-start gap-2 rounded-2xl bg-graphite px-5 py-3 text-left text-[19px] leading-snug text-paper">
          <span>{caption.text}</span>
          <span className="mt-1 opacity-0 transition-opacity group-hover:opacity-60"><Icon name="edit" size={15} /></span>
        </button>
      )}
      {caption.original && <p className="mt-1.5 text-sm text-graphite/40 line-through">{caption.original}</p>}
    </motion.div>
  )
}

function PatientLine({ msg }: { msg: Message }) {
  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      className="max-w-[75%] rounded-2xl border border-mint-deep/25 bg-mint/10 py-3.5 pl-5 pr-6">
      <p className="eyebrow mb-1.5 flex items-center gap-1.5 text-mint-deep">
        <Icon name="check" size={13} /> Confirmed by patient · {time(msg.t)}
      </p>
      <p className="text-[24px] font-bold leading-snug">{msg.text}</p>
      <p className="eyebrow mt-2 text-graphite/45">
        {sourceLabel[msg.source] ?? msg.source}{msg.edited ? ' · edited by patient' : ''}
        {msg.glosses.length > 0 && ` · signs: ${msg.glosses.join(' · ')}`}
      </p>
    </motion.div>
  )
}

const signStateLabel: Record<string, string> = {
  idle: 'Waiting', hands: 'Hands raised', signing: 'Signing…', translating: 'Translating…', recognizing: 'Recognizing…',
  loading: 'Loading models…', no_camera: 'Camera unavailable',
}

function LiveLane({ state }: { state: State }) {
  const n = state.natural
  const active = ['signing', 'translating', 'recognizing'].includes(state.sign.state)
  return (
    <div className="rounded-[28px] border border-paper-line bg-paper-raised p-6">
      <div className="mb-4 flex items-center justify-between">
        <span className="eyebrow text-graphite/50">Live from patient</span>
        <StatusPill tone={active ? 'live' : state.sign.state === 'no_camera' ? 'warn' : 'idle'}
          label={signStateLabel[state.sign.state] ?? state.sign.state} pulse={active} />
      </div>
      <p className="eyebrow mb-3 text-graphite/40">Mode · {state.sign.mode === 'natural' ? 'natural signing' : 'one sign at a time'}</p>
      {n || state.precise.length > 0 || state.draft.text ? (
        <div className="rounded-2xl border-2 border-dashed border-amber/70 bg-amber/8 p-4">
          <p className="eyebrow mb-3 text-amber-deep">Unconfirmed AI output — not yet confirmed by patient</p>
          {n && (
            <ul className="flex flex-col gap-2">
              {n.candidates.map((c, i) => (
                <li key={i} className={`flex items-baseline justify-between gap-3 ${n.selected === i ? 'font-bold' : 'text-graphite/55'}`}>
                  <span className="text-[16px] leading-snug">{n.selected === i ? '▸ ' : ''}{c.text}</span>
                  <span className="font-mono text-xs text-graphite/45">{Math.round(c.rel_score * 100)}%</span>
                </li>
              ))}
              {n.low_confidence && <li className="text-sm font-bold text-amber-deep">Model confidence is low for this sentence.</li>}
            </ul>
          )}
          {state.precise.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {state.precise.map((p) => (
                <span key={p.seg_id} className={`rounded-full px-3 py-1 text-sm font-bold ${p.uncertain ? 'border border-dashed border-amber-deep text-amber-deep' : 'bg-graphite/8'}`}>
                  {p.chosen ?? '?'} <span className="font-mono text-xs font-normal opacity-60">{Math.round((p.topk[0]?.p ?? 0) * 100)}%</span>
                </span>
              ))}
            </div>
          )}
          {state.draft.text && !n && <p className="mt-3 text-[17px] italic">“{state.draft.text}”</p>}
        </div>
      ) : (
        <p className="text-graphite/45">Nothing pending. Confirmed replies appear in the conversation.</p>
      )}
    </div>
  )
}

function Readouts({ state, fps, send }: { state: State; fps: number | null; send: Send }) {
  const lastPrecise = state.precise[state.precise.length - 1]
  const rows: [string, string][] = [
    ['Camera', fps === null ? '—' : `${fps.toFixed(0)} fps`],
    ['Sentence translation', state.natural?.latency_ms != null ? `${state.natural.latency_ms} ms` : '—'],
    ['Sign recognition', lastPrecise?.latency_ms != null ? `${lastPrecise.latency_ms} ms` : '—'],
    ['Confirmed replies', String(state.messages.length)],
  ]
  return (
    <div className="rounded-[28px] border border-paper-line bg-paper-raised p-6">
      <span className="eyebrow text-graphite/50">System</span>
      <dl className="mt-3 divide-y divide-paper-line">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between py-2.5">
            <dt className="text-[15px] text-graphite/60">{k}</dt>
            <dd className="font-mono text-[14px]">{v}</dd>
          </div>
        ))}
      </dl>
      <button onClick={() => { if (confirm('End the session and clear the conversation from memory?')) send({ type: 'session.end' }) }}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-full border border-graphite/20 py-2.5 text-sm font-bold hover:bg-graphite/5">
        <Icon name="stop" size={14} /> End session
      </button>
    </div>
  )
}
