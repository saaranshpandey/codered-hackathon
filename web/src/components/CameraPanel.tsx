import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState, type RefObject } from 'react'
import type { Landmarks, SignState } from '../lib/types'

const HAND_EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]]
const BODY_EDGES = [[1, 2], [1, 3], [3, 5], [2, 4], [4, 6]] // shoulders, elbows, wrists

const RING: Record<SignState, { border: string; glow: string }> = {
  idle: { border: 'rgb(242 238 230 / 0.12)', glow: '0 0 0 0 rgb(0 0 0 / 0)' },
  loading: { border: 'rgb(242 238 230 / 0.12)', glow: '0 0 0 0 rgb(0 0 0 / 0)' },
  no_camera: { border: 'rgb(255 176 32 / 0.6)', glow: '0 0 0 0 rgb(0 0 0 / 0)' },
  hands: { border: 'rgb(61 220 151 / 0.7)', glow: '0 0 40px -8px rgb(61 220 151 / 0.45)' },
  signing: { border: 'rgb(255 90 31 / 0.95)', glow: '0 0 64px -6px rgb(255 90 31 / 0.6)' },
  translating: { border: 'rgb(255 176 32 / 0.9)', glow: '0 0 48px -8px rgb(255 176 32 / 0.5)' },
  recognizing: { border: 'rgb(255 176 32 / 0.9)', glow: '0 0 48px -8px rgb(255 176 32 / 0.5)' },
}

function caption(state: SignState, mode: string) {
  switch (state) {
    case 'loading': return 'Loading sign models…'
    case 'no_camera': return 'Camera unavailable'
    case 'hands': return 'Hands detected'
    case 'signing': return mode === 'natural' ? 'Recording — tap Done when you finish' : 'Signing — lower your hands after the sign'
    case 'translating': return 'Translating your sentence…'
    case 'recognizing': return 'Recognizing sign…'
    default: return mode === 'natural' ? 'Ready — tap Start signing' : 'Ready — one sign at a time'
  }
}

export function CameraPanel({ landmarks, signState, mode, fps, compact, countdown }: {
  landmarks: RefObject<Landmarks | null>; signState: SignState; mode: string; fps: number | null; compact: boolean
  countdown: number | null
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [imgKey, setImgKey] = useState(0)
  const [camOk, setCamOk] = useState(false)
  const [camError, setCamError] = useState(false)
  const signing = signState === 'signing'

  useEffect(() => {
    let raf = 0
    const draw = () => {
      const c = canvas.current
      if (c) {
        const ctx = c.getContext('2d')!
        const dpr = window.devicePixelRatio || 1
        const W = c.clientWidth, H = c.clientHeight
        if (c.width !== W * dpr) { c.width = W * dpr; c.height = H * dpr }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        ctx.clearRect(0, 0, W, H)
        const lm = landmarks.current
        if (lm && performance.now() - lm.at < 500) {
          const color = signing ? '#ff5a1f' : '#3ddc97'
          const seg = (pts: number[][], edges: number[][], width: number, alpha: number) => {
            ctx.globalAlpha = alpha
            ctx.lineWidth = width
            for (const [a, b] of edges) {
              const p = pts[a], q = pts[b]
              if (!p || !q || (!p[0] && !p[1]) || (!q[0] && !q[1])) continue
              ctx.beginPath(); ctx.moveTo(p[0] * W, p[1] * H); ctx.lineTo(q[0] * W, q[1] * H); ctx.stroke()
            }
          }
          ctx.lineCap = 'round'
          ctx.strokeStyle = '#f2eee6'
          seg(lm.body, BODY_EDGES, 2, 0.35)
          ctx.strokeStyle = color
          ctx.shadowColor = color
          ctx.shadowBlur = 14
          for (const hand of lm.hands) seg(hand, HAND_EDGES, 2.4, 0.95)
          ctx.shadowBlur = 0
          ctx.fillStyle = '#f2eee6'
          ctx.globalAlpha = 0.9
          for (const hand of lm.hands) for (const [x, y] of hand) {
            ctx.beginPath(); ctx.arc(x * W, y * H, 2.2, 0, Math.PI * 2); ctx.fill()
          }
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [landmarks, signing])

  const ring = RING[signState] ?? RING.idle
  return (
    <motion.div layout className="relative mx-auto w-full" style={{ maxWidth: compact ? 'calc(22vh * 16 / 9)' : 'calc(34vh * 16 / 9)' }}
      transition={{ type: 'spring', stiffness: 260, damping: 32 }}>
      <motion.div
        className="relative aspect-video overflow-hidden rounded-[28px] border-2 bg-ink-raised"
        animate={{ borderColor: ring.border, boxShadow: ring.glow }}
        transition={{ duration: 0.35 }}
      >
        {/* Mirrored like a mirror for the signer; the model sees the unmirrored frame. */}
        <div className="absolute inset-0 -scale-x-100">
          <img key={imgKey} src={`/video.mjpg?k=${imgKey}`} alt=""
            className={`h-full w-full object-cover transition-opacity duration-500 ${camOk ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => { setCamOk(true); setCamError(false) }}
            onError={() => { setCamOk(false); setCamError(true); setTimeout(() => setImgKey((k) => k + 1), 2000) }} />
          <canvas ref={canvas} className="absolute inset-0 h-full w-full" />
        </div>
        {(camError || signState === 'no_camera') && (
          <div className="absolute inset-0 grid place-items-center p-10 text-center">
            <div>
              <p className="font-serif text-3xl">Camera unavailable</p>
              <p className="mt-3 text-sm text-bone/60">Check that the webcam is connected and that the app running the
                server is allowed under System Settings → Privacy &amp; Security → Camera.</p>
            </div>
          </div>
        )}
        <AnimatePresence>
          {countdown !== null && (
            <motion.div key={countdown} className="absolute inset-0 grid place-items-center bg-ink/40"
              initial={{ opacity: 0, scale: 1.4 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.7 }}
              transition={{ duration: 0.35 }}>
              <span className="font-serif text-[120px] leading-none text-bone">{countdown}</span>
            </motion.div>
          )}
        </AnimatePresence>
        {signState === 'translating' && (
          <motion.div className="pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-amber/20 to-transparent"
            initial={{ x: '-100%' }} animate={{ x: '300%' }} transition={{ duration: 1.3, repeat: Infinity, ease: 'easeInOut' }} />
        )}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-ink/85 to-transparent px-5 pb-4 pt-10">
          <span className="text-[15px] font-bold">{caption(signState, mode)}</span>
          {fps !== null && <span className="eyebrow text-bone/50">{fps.toFixed(0)} fps</span>}
        </div>
      </motion.div>
    </motion.div>
  )
}
