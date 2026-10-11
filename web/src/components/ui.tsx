import { useEffect, useRef, type RefObject } from 'react'

export function Wordmark({ role, tone }: { role: string; tone: 'dark' | 'light' }) {
  return (
    <div className="flex items-baseline gap-3 select-none">
      <svg width="30" height="22" viewBox="0 0 30 22" aria-hidden className="translate-y-[3px]">
        <path d="M2 17C5 6 25 6 28 17" fill="none" className="stroke-mint" strokeWidth="2.6" strokeLinecap="round" />
        <path d="M2 17v4M28 17v4M15 10v11M8.5 12.5v8.5M21.5 12.5v8.5" className={tone === 'dark' ? 'stroke-bone' : 'stroke-graphite'} strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <span className="font-serif text-[28px] leading-none tracking-tight">
        Med<span className="italic">bridge</span>
      </span>
      <span className="eyebrow opacity-50">{role}</span>
    </div>
  )
}

type PillTone = 'live' | 'ok' | 'warn' | 'idle'
const pillDot: Record<PillTone, string> = {
  live: 'bg-mint', ok: 'bg-mint', warn: 'bg-amber', idle: 'bg-current opacity-40', // live differs from ok by its pulse
}

/** A status line: a small dot and a label. (The name is from when it was drawn as a pill.) */
export function StatusPill({ tone, label, pulse = false }: { tone: PillTone; label: string; pulse?: boolean }) {
  return (
    <span className="eyebrow inline-flex items-center gap-2">
      <span className="relative flex h-2 w-2">
        {pulse && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${pillDot[tone]}`} />}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${pillDot[tone]}`} />
      </span>
      {label}
    </span>
  )
}

/** Rolling bar graph of the real microphone RMS. */
export function Waveform({ level, color, width = 140, height = 28 }: {
  level: RefObject<number>; color: string; width?: number; height?: number
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const bars: number[] = new Array(36).fill(0)
    let raf = 0
    let frame = 0
    const draw = () => {
      const c = canvas.current
      if (c) {
        const ctx = c.getContext('2d')!
        const dpr = window.devicePixelRatio || 1
        if (c.width !== width * dpr) { c.width = width * dpr; c.height = height * dpr }
        if (frame++ % 2 === 0) { bars.shift(); bars.push(Math.min(1, Math.sqrt(level.current ?? 0) * 4)) }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        ctx.clearRect(0, 0, width, height)
        ctx.fillStyle = color
        const w = width / bars.length
        bars.forEach((v, i) => {
          const h = Math.max(2, v * height)
          ctx.globalAlpha = 0.35 + 0.65 * (i / bars.length)
          ctx.beginPath()
          ctx.roundRect(i * w + 1, (height - h) / 2, w - 2, h, 1.5)
          ctx.fill()
        })
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [level, color, width, height])
  return <canvas ref={canvas} style={{ width, height }} aria-label="Doctor microphone level" />
}

export function Icon({ name, size = 18 }: { name: 'check' | 'edit' | 'retry' | 'x' | 'hand' | 'mic' | 'pause' | 'play' | 'stop' | 'send' | 'speaker'; size?: number }) {
  const paths: Record<string, string> = {
    check: 'M4 12.5l5 5L20 6.5',
    edit: 'M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4',
    retry: 'M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5',
    x: 'M6 6l12 12M18 6L6 18',
    hand: 'M8 13V5.5a1.5 1.5 0 0 1 3 0V12m0-1V4a1.5 1.5 0 0 1 3 0v7m0-5.5a1.5 1.5 0 0 1 3 0V13m0-4a1.5 1.5 0 0 1 3 0v5a7 7 0 0 1-7 7h-1a7 7 0 0 1-5.5-2.7L3.6 14.6a1.5 1.5 0 0 1 2.3-1.9L8 15',
    mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3',
    pause: 'M8 5v14M16 5v14',
    play: 'M7 5l12 7-12 7V5z',
    stop: 'M6 6h12v12H6z',
    send: 'M5 12h14M13 6l6 6-6 6',
    speaker: 'M4 9.5v5h3.5L12 18V6L7.5 9.5H4zM15.5 9a4 4 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11',
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={paths[name]} />
    </svg>
  )
}

export const sourceLabel: Record<string, string> = {
  natural: 'Natural signing · free translation',
  'natural-phrase': 'Natural signing · closest ER phrase',
  'precise-literal': 'One sign at a time · literal',
  'precise-llm': 'One sign at a time · rephrased by Claude',
  '': 'Typed by patient',
}
