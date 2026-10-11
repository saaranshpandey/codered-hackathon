import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
// Glow (bloom) is disabled for now. To re-enable, restore these imports and the composer block below.
// import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
// import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
// import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
// import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { createCougar } from '../lib/cougar'
import type { SignedWord, Signing } from '../lib/types'
import { Icon } from './ui'

// Motion layout from the backend (medbridge/text2sign.py): 178 points x (x, y, z), image axes, shoulder width = 1.
const P = 178
const DEPTH = 0.22 // MediaPipe depth is noisy and exaggerated; compress it for display
const SMOOTH = 0.55 // per-frame smoothing of landmark jitter (1 = none)
// `done` is false while later batches of a long caption are still being prepared; `key` names one build of one caption.
type Motion = {
  key: string; captionId: number; fps: number; frames: number; data: Float32Array; words: NonNullable<Signing['words']>; done: boolean
}
const motionKey = (captionId: number, build?: number) => `${captionId}:${build ?? 0}`

function decode(b64: string) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Float32Array(bytes.buffer)
}

/** `onWord` reports the caption word being signed right now (null when none); pass a stable function. */
export function SigningStage({ signing, onWord }: { signing: Signing | null; onWord: (word: SignedWord | null) => void }) {
  const mount = useRef<HTMLDivElement>(null)
  const motionRef = useRef<Motion | null>(null)
  const clock = useRef({ t: 0, playing: false, speed: 1 })
  const [speed, setSpeed] = useState(1)
  const [loaded, setLoaded] = useState<Motion | null>(null)

  // Fetch the motion for the newest caption. A long caption arrives in batches: playback starts with the first
  // batch, and each later batch is fetched from where the last one ended and appended.
  const latest = useRef(signing)
  const fetching = useRef(false)
  useEffect(() => {
    latest.current = signing
    // The motion is complete once the server says the caption is done and every frame of it is here.
    const settle = () => {
      const s = latest.current, m = motionRef.current
      if (s && m && m.key === motionKey(s.caption_id, s.build) && s.done !== false && m.frames >= s.frames) m.done = true
    }
    settle()
    if (fetching.current) return
    fetching.current = true
    const pump = async () => {
      try {
        for (;;) {
          const s = latest.current
          if (!s || s.status !== 'ready') break
          const key = motionKey(s.caption_id, s.build)
          const have = motionRef.current?.key === key ? motionRef.current.frames : 0
          if (s.frames <= have) break
          const r = await fetch(`/api/signing/${s.caption_id}?start=${have}`)
          if (!r.ok) break
          const body = await r.json()
          const chunk = decode(body.data)
          const start: number = body.start ?? 0, bodyKey = motionKey(body.caption_id, body.build)
          const m = motionRef.current
          if (m && m.key === bodyKey && start === m.frames) {
            const data = new Float32Array(m.data.length + chunk.length)
            data.set(m.data); data.set(chunk, m.data.length)
            motionRef.current = { ...m, data, frames: m.frames + body.frames, words: body.words, done: false }
          } else if (start === 0) {
            motionRef.current = { key: bodyKey, captionId: body.caption_id, fps: body.fps, frames: body.frames, data: chunk, words: body.words, done: false }
            clock.current = { t: 0, playing: true, speed: clock.current.speed }
          } else break // a batch for something we no longer hold: the next state update starts over
          settle()
          setLoaded(motionRef.current)
        }
      } catch { /* network hiccup: the next state update tries again */ } finally { fetching.current = false }
    }
    void pump()
  }, [signing?.caption_id, signing?.build, signing?.status, signing?.frames, signing?.done]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { clock.current.speed = speed }, [speed])

  // Three.js scene: built once, driven every animation frame from motionRef.
  useEffect(() => {
    const el = mount.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) // see-through: the stage colours are CSS (theme.css)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50)
    // Glow (bloom) disabled for now:
    // const composer = new EffectComposer(renderer)
    // composer.addPass(new RenderPass(scene, camera))
    // const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.7, 0.45, 0.2)
    // composer.addPass(bloom)
    // composer.addPass(new OutputPass())

    scene.add(new THREE.HemisphereLight('#fff3e2', '#3a2a1e', 1.6))
    const key = new THREE.DirectionalLight('#ffffff', 2.2)
    key.position.set(2.5, 3, 4)
    const rim = new THREE.DirectionalLight('#ffb27a', 1.4)
    rim.position.set(-3, 2, -3)
    scene.add(key, rim)
    // soft contact shadow under the mascot
    const shadowCanvas = document.createElement('canvas')
    shadowCanvas.width = shadowCanvas.height = 128
    const sctx = shadowCanvas.getContext('2d')!
    const grad = sctx.createRadialGradient(64, 64, 0, 64, 64, 64)
    grad.addColorStop(0, 'rgba(0,0,0,0.55)'); grad.addColorStop(1, 'rgba(0,0,0,0)')
    sctx.fillStyle = grad; sctx.fillRect(0, 0, 128, 128)
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.3), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(shadowCanvas), transparent: true, depthWrite: false }))
    shadow.rotation.x = -Math.PI / 2
    shadow.position.set(0, -1.75, 0)
    scene.add(shadow)

    const cougar = createCougar(scene)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const smooth = new Float32Array(P * 3).fill(NaN)
    const getter = (f: Float32Array, base: number) => (i: number, out: THREE.Vector3) => {
      const k = base + i * 3
      const x = f[k], y = f[k + 1], z = f[k + 2]
      if (Number.isNaN(x) || Number.isNaN(y)) { smooth[i * 3] = NaN; return false }
      const tz = Math.max(-1, Math.min(1, -(Number.isNaN(z) ? 0 : z) * DEPTH))
      const j = i * 3
      if (Number.isNaN(smooth[j])) { smooth[j] = x; smooth[j + 1] = -y; smooth[j + 2] = tz }
      else { smooth[j] += (x - smooth[j]) * SMOOTH; smooth[j + 1] += (-y - smooth[j + 1]) * SMOOTH; smooth[j + 2] += (tz - smooth[j + 2]) * SMOOTH }
      out.set(smooth[j], smooth[j + 1], smooth[j + 2])
      return true
    }

    const resize = () => {
      const { clientWidth: W, clientHeight: H } = el
      renderer.setSize(W, H)
      camera.aspect = W / H; camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    // ?frame=N freezes the animation on one frame (for checking the rendering).
    const pinned = Number(new URLSearchParams(location.search).get('frame') ?? NaN)
    let raf = 0, last = performance.now(), wall = 0, shownWord = '', lastFrame = -1
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now; wall += dt
      const m = motionRef.current
      const c = clock.current
      let fi = -1
      if (m && m.frames > 0) {
        if (c.playing) {
          c.t += dt * c.speed
          if (!m.done) c.t = Math.min(c.t, m.frames / m.fps)           // the next batch is not here yet: wait on the last pose
          else if (c.t * m.fps >= m.frames + m.fps) c.playing = false // hold the last pose for 1 s
        }
        fi = Number.isFinite(pinned) ? Math.min(m.frames - 1, pinned) : Math.min(m.frames - 1, Math.floor(c.t * m.fps))
      }
      const vis = fi >= 0
      cougar.setVisible(vis)
      if (vis && fi !== lastFrame) {
        lastFrame = fi
        cougar.update(getter(m!.data, fi * P * 3))
      }
      shadow.visible = cougar.visible
      // The word being signed, for the caption highlight. The move into a sign counts as that sign, so the highlight
      // does not blink between words. None after the last frame, or while a word without a sign is held.
      const signingNow = vis && (Number.isFinite(pinned) || (c.playing && c.t * m!.fps < m!.frames))
      const next = signingNow ? m!.words.findIndex((x) => fi < x.end) : -1
      const wi = next >= 0 && m!.words[next].source !== 'none' ? next : -1
      const key = wi < 0 ? '' : `${m!.captionId}:${wi}`
      if (key !== shownWord) { shownWord = key; onWord(wi < 0 ? null : { captionId: m!.captionId, index: wi }) }
      const yaw = reduce ? 0 : Math.sin(wall * 0.18) * 0.3
      camera.position.set(Math.sin(yaw) * 4.6, 0.35, Math.cos(yaw) * 4.6)
      camera.lookAt(0, 0.1, 0)
      renderer.render(scene, camera) // composer.render() when glow is re-enabled
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); renderer.dispose(); el.removeChild(renderer.domElement); onWord(null) }
  }, [onWord])

  const replay = () => { clock.current.t = 0; clock.current.playing = true }
  const building = signing?.status === 'building'
  const noSigns = !!loaded && loaded.words.every((x) => x.source === 'none')

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-[28px] border border-ink-line bg-[radial-gradient(ellipse_at_50%_30%,color-mix(in_srgb,var(--color-stage)_78%,white)_0%,var(--color-stage)_80%)]">
      {loaded && !noSigns && (
        <div className="absolute right-6 top-5 z-20 flex items-center gap-2">
          <button onClick={() => setSpeed((s) => (s === 1 ? 0.6 : 1))} className="eyebrow rounded-md border border-bone/20 px-3 py-1.5 text-bone/70 hover:bg-bone/10">
            {speed === 1 ? '1×' : '0.6×'}
          </button>
          <button onClick={replay} className="flex items-center gap-1.5 rounded-md border border-bone/20 px-3 py-1.5 text-[13px] font-bold hover:bg-bone/10">
            <Icon name="retry" size={14} /> Replay
          </button>
        </div>
      )}
      <div ref={mount} className="relative min-h-[200px] flex-1 [&>canvas]:block">
        <AnimatePresence>
          {building && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="shimmer absolute inset-x-0 bottom-4 text-center text-[15px] font-bold">Preparing signs…</motion.p>
          )}
        </AnimatePresence>
        {!loaded && !building && (
          <p className="absolute inset-0 z-20 grid place-items-center px-10 text-center font-serif text-2xl italic text-bone/30">
            When the doctor speaks, their words are signed here.
          </p>
        )}
      </div>
    </div>
  )
}
