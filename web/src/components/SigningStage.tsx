import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import type { Signing } from '../lib/types'
import { Icon } from './ui'

// Motion layout from the backend (medbridge/text2sign.py): 178 points x (x, y, z), image axes, shoulder width = 1.
const P = 178
const LS = 0, RS = 1, LE = 2, RE = 3, LW = 4, RW = 5, LHIP = 6, RHIP = 7, FACE = 8, LH = 136, RH = 157
const HAND = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]]
const DEPTH = 0.22 // MediaPipe depth is noisy and exaggerated; compress it for display

type Bone = { a: number; b: number; mesh: THREE.Mesh }
type Motion = { fps: number; frames: number; data: Float32Array; words: NonNullable<Signing['words']> }

function decode(b64: string) {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Float32Array(bytes.buffer)
}

const SOURCE: Record<string, { dot: string; label: string }> = {
  aslc: { dot: 'bg-mint', label: 'Deaf signer (ASL Citizen)' },
  signmt: { dot: 'bg-amber', label: 'sign.mt' },
  none: { dot: 'border border-dashed border-bone/50', label: 'text only' },
}

export function SigningStage({ signing }: { signing: Signing | null }) {
  const mount = useRef<HTMLDivElement>(null)
  const motionRef = useRef<Motion | null>(null)
  const clock = useRef({ t: 0, playing: false, speed: 1 })
  const [word, setWord] = useState(-1)
  const [speed, setSpeed] = useState(1)
  const [loaded, setLoaded] = useState<Motion | null>(null)

  // Fetch the motion for the newest caption once it is ready.
  useEffect(() => {
    if (!signing || signing.status !== 'ready') return
    let cancelled = false
    fetch(`/api/signing/${signing.caption_id}`).then((r) => (r.ok ? r.json() : null)).then((body) => {
      if (!body || cancelled) return
      const m: Motion = { fps: body.fps, frames: body.frames, data: decode(body.data), words: body.words }
      motionRef.current = m
      clock.current = { t: 0, playing: true, speed: clock.current.speed }
      setLoaded(m)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [signing?.caption_id, signing?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { clock.current.speed = speed }, [speed])

  // Three.js scene: built once, driven every animation frame from motionRef.
  useEffect(() => {
    const el = mount.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#121310') // opaque: bloom on a transparent canvas turns grey
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50)
    const composer = new EffectComposer(renderer)
    composer.addPass(new RenderPass(scene, camera))
    const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.7, 0.45, 0.2)
    composer.addPass(bloom)
    composer.addPass(new OutputPass())

    const cyl = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true)
    const mat = (color: string, opacity = 1) => new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity })
    const bones: Bone[] = []
    const addBone = (a: number, b: number, m: THREE.Material, r: number) => {
      const mesh = new THREE.Mesh(cyl, m)
      mesh.userData.r = r
      scene.add(mesh)
      bones.push({ a, b, mesh })
    }
    const body = mat('#a8a39a', 0.5)
    for (const [a, b] of [[LS, RS], [LS, LE], [LE, LW], [RS, RE], [RE, RW], [LS, LHIP], [RS, RHIP], [LHIP, RHIP]]) addBone(a, b, body, 0.035)
    const left = mat('#5cf0b0'), right = mat('#ff8a4c')
    for (const [a, b] of HAND) { addBone(LH + a, LH + b, left, 0.024); addBone(RH + a, RH + b, right, 0.024) }
    addBone(LW, LH, left, 0.028); addBone(RW, RH, right, 0.028)

    const joint = new THREE.SphereGeometry(1, 12, 12)
    const joints = new THREE.InstancedMesh(joint, mat('#ffffff'), 50)
    scene.add(joints)
    const jointIdx = [LS, RS, LE, RE, LW, RW, LHIP, RHIP, ...Array.from({ length: 21 }, (_, i) => LH + i), ...Array.from({ length: 21 }, (_, i) => RH + i)]

    const face = new THREE.BufferGeometry()
    const facePos = new Float32Array(128 * 3)
    face.setAttribute('position', new THREE.BufferAttribute(facePos, 3))
    scene.add(new THREE.Points(face, new THREE.PointsMaterial({ color: '#f2eee6', size: 0.018, transparent: true, opacity: 0.55 })))
    const head = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 24), new THREE.MeshBasicMaterial({ color: '#f2eee6', transparent: true, opacity: 0.035 }))
    scene.add(head)
    const halo = new THREE.Mesh(new THREE.TorusGeometry(1, 0.012, 8, 96), mat('#ff5a1f', 0.5))
    halo.rotation.x = Math.PI / 2
    scene.add(halo)

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const v = new THREE.Vector3(), w = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0), m4 = new THREE.Matrix4()
    const pt = (f: Float32Array, base: number, i: number, out: THREE.Vector3) => {
      const k = base + i * 3
      const x = f[k], y = f[k + 1], z = f[k + 2]
      if (Number.isNaN(x) || Number.isNaN(y)) return false
      out.set(x, -y, Math.max(-1, Math.min(1, -(Number.isNaN(z) ? 0 : z) * DEPTH)))
      return true
    }

    const resize = () => {
      const { clientWidth: W, clientHeight: H } = el
      renderer.setSize(W, H); composer.setSize(W, H); bloom.setSize(W, H)
      camera.aspect = W / H; camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)
    resize()

    // ?frame=N freezes the animation on one frame (for checking the rendering).
    const pinned = Number(new URLSearchParams(location.search).get('frame') ?? NaN)
    let raf = 0, last = performance.now(), wall = 0, shownWord = -1
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now; wall += dt
      const m = motionRef.current
      const c = clock.current
      let fi = -1
      if (m && m.frames > 0) {
        if (c.playing) {
          c.t += dt * c.speed
          if (c.t * m.fps >= m.frames + m.fps) c.playing = false // hold the last pose for 1 s
        }
        fi = Number.isFinite(pinned) ? Math.min(m.frames - 1, pinned) : Math.min(m.frames - 1, Math.floor(c.t * m.fps))
      }
      const vis = fi >= 0
      if (vis) {
        const base = fi * P * 3
        const f = m!.data
        for (const bone of bones) {
          const ok = pt(f, base, bone.a, v) && pt(f, base, bone.b, w)
          bone.mesh.visible = ok
          if (!ok) continue
          const len = v.distanceTo(w)
          bone.mesh.position.copy(v).add(w).multiplyScalar(0.5)
          bone.mesh.quaternion.setFromUnitVectors(up, w.clone().sub(v).normalize())
          bone.mesh.scale.set(bone.mesh.userData.r, len, bone.mesh.userData.r)
        }
        let n = 0
        for (const i of jointIdx) {
          if (!pt(f, base, i, v)) continue
          const r = i >= LH ? ((i - LH) % 21 % 4 === 0 && (i - LH) % 21 > 0 ? 0.038 : 0.026) : 0.04
          joints.setMatrixAt(n++, m4.compose(v, new THREE.Quaternion(), new THREE.Vector3(r, r, r)))
        }
        joints.count = n
        joints.instanceMatrix.needsUpdate = true
        let fx = 0, fy = 0, fz = 0, fn = 0
        for (let i = 0; i < 128; i++) {
          if (pt(f, base, FACE + i, v)) { facePos.set([v.x, v.y, v.z], i * 3); fx += v.x; fy += v.y; fz += v.z; fn++ }
          else facePos.set([0, -99, 0], i * 3)
        }
        face.attributes.position.needsUpdate = true
        if (fn) head.position.set(fx / fn, fy / fn, fz / fn - 0.05)
        else if (pt(f, base, LS, v) && pt(f, base, RS, w)) head.position.copy(v).add(w).multiplyScalar(0.5).add(new THREE.Vector3(0, 0.95, 0))
        head.scale.set(0.34, 0.46, 0.34)
        halo.position.set(0, -1.35, 0)
        halo.scale.setScalar(1.15 + Math.sin(wall * 1.6) * 0.04)
        const wi = m!.words.findIndex((x) => fi >= x.start && fi < x.end)
        if (wi !== shownWord) { shownWord = wi; setWord(wi) }
      }
      for (const b of bones) b.mesh.visible = b.mesh.visible && vis
      joints.visible = vis; head.visible = vis; halo.visible = vis
      const yaw = reduce ? 0 : Math.sin(wall * 0.18) * 0.35
      camera.position.set(Math.sin(yaw) * 3.9, 0.25, Math.cos(yaw) * 3.9)
      camera.lookAt(0, 0.05, 0)
      composer.render()
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); renderer.dispose(); el.removeChild(renderer.domElement) }
  }, [])

  const replay = () => { clock.current.t = 0; clock.current.playing = true }
  const words = loaded?.words ?? []
  const building = signing?.status === 'building'

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-[28px] border border-ink-line bg-[radial-gradient(ellipse_at_50%_30%,#22231d_0%,#0e0f0c_70%)]">
      <div className="flex items-start justify-between px-6 pt-5">
        <div>
          <span className="eyebrow text-bone/45">The doctor's words, signed</span>
          <p className="mt-1 text-[12px] text-bone/35">Word-by-word preview · not full ASL grammar · captions below are the reference</p>
        </div>
        {loaded && (
          <div className="flex items-center gap-2">
            <button onClick={() => setSpeed((s) => (s === 1 ? 0.6 : 1))} className="eyebrow rounded-full border border-bone/20 px-3 py-1.5 text-bone/70 hover:bg-bone/10">
              {speed === 1 ? '1×' : '0.6×'}
            </button>
            <button onClick={replay} className="flex items-center gap-1.5 rounded-full border border-bone/20 px-3 py-1.5 text-[13px] font-bold hover:bg-bone/10">
              <Icon name="retry" size={14} /> Replay
            </button>
          </div>
        )}
      </div>
      <div ref={mount} className="relative min-h-[200px] flex-1 [&>canvas]:block">
        <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(ellipse_at_center,transparent_45%,#0e0f0c_100%)]" />
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
      {words.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-6 pb-5">
          {words.map((x, i) => (
            <span key={i} title={SOURCE[x.source]?.label}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-[14px] transition-colors ${i === word ? 'bg-bone text-ink' : 'bg-bone/8 text-bone/70'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${SOURCE[x.source]?.dot}`} />{x.word}
            </span>
          ))}
          <span className="eyebrow ml-auto flex gap-3 text-bone/30">
            {Object.entries(SOURCE).map(([k, s]) => <span key={k} className="flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />{s.label}</span>)}
          </span>
        </div>
      )}
    </div>
  )
}
