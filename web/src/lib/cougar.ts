import * as THREE from 'three'

/**
 * Toon cougar mascot, posed every frame directly from the motion landmarks (no rig retargeting):
 * limbs are segments between joints, paws follow all 21 hand points, and the head is oriented from
 * face points (eye corners, forehead, chin) with jaw, brows and eyelids driven by the signer's face.
 *
 * Point layout matches medbridge/text2sign.py: body 0-7, face 8-135 (FACE_IDX order), hands 136/157.
 */
export const LS = 0, RS = 1, LE = 2, RE = 3, LW = 4, RW = 5, LHIP = 6, RHIP = 7, FACE = 8, LH = 136, RH = 157
const FACE_IDX = [0, 7, 10, 13, 14, 17, 21, 33, 37, 39, 40, 46, 52, 53, 54, 55, 58, 61, 63, 65, 66, 67, 70, 78, 80, 81, 82, 84,
  87, 88, 91, 93, 95, 103, 105, 107, 109, 127, 132, 133, 136, 144, 145, 146, 148, 149, 150, 152, 153, 154, 155,
  157, 158, 159, 160, 161, 162, 163, 172, 173, 176, 178, 181, 185, 191, 234, 246, 249, 251, 263, 267, 269, 270,
  276, 282, 283, 284, 285, 288, 291, 293, 295, 296, 297, 300, 308, 310, 311, 312, 314, 317, 318, 321, 323, 324,
  332, 334, 336, 338, 356, 361, 362, 365, 373, 374, 375, 377, 378, 379, 380, 381, 382, 384, 385, 386, 387, 388,
  389, 390, 397, 398, 400, 402, 405, 409, 415, 454, 466]
const F = (meshIndex: number) => FACE + FACE_IDX.indexOf(meshIndex)
const EYE_R_OUT = F(33), EYE_L_OUT = F(263), FOREHEAD = F(10), CHIN = F(152), LIP_UP = F(13), LIP_LO = F(14)
const BROW_R = F(105), BROW_L = F(334), LID_R_UP = F(159), LID_R_LO = F(145), LID_L_UP = F(386), LID_L_LO = F(374)
const FINGERS = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]]

const C = {
  fur: '#c98f55', furLight: '#f4e4c9', marking: '#3b2416', nose: '#d4847c', jersey: '#c8102e', trim: '#f6f1e7',
  eye: '#ffffff', iris: '#e0a82e', pupil: '#120c08', earInner: '#e9b4a4', mouth: '#4a1d1a', outline: '#1d140e', pad: '#dfae86',
  logo: '#ffffff',
}

type Getter = (i: number, out: THREE.Vector3) => boolean

function toonGradient() {
  const tex = new THREE.DataTexture(new Uint8Array([90, 175, 255]), 3, 1, THREE.RedFormat)
  tex.minFilter = tex.magFilter = THREE.NearestFilter
  tex.generateMipmaps = false
  tex.needsUpdate = true
  return tex
}

// University of Houston interlocking "UH": outlines from the logo's SVG on Wikimedia Commons (489 x 465 units).
const UH_OUTER = 'M0,0H171V91H145V157H239V91.00H213.51V0H384V91H357V157H489V248H462V374H489V465H319V375H344V358H252V375H278V465H107V375H134V302H79L27.5 255V91H0Z'
const UH_KEYLINE = 'M13 13H158V78H132V170H252V78H226.5V13H371.5V78H344V170H476V235.5H449V387.5H476.5V452.5H331.5V387.5H357V345H239V387.5H265V452.5H119.5V387.5H147V287.5H83L40.50 251V78H13Z'
const UH_LETTERS = 'M25 25H146V66H120V235H147.5V277H90L53 245V66H25ZM239 25H359V66H332V245L294 277H238V235H264V66H239V25ZM344 183H464V223H437V400H464V440H344V400H370V333H227V400H252V440H132V400H160V223H132V182.5H252.5V223H227V289H369.5V223.5H344ZM317 276L356 241V276Z'

/** The UH logo as it appears on red (white, with a keyline in the jersey's own red), as an alpha mask.
 *  Drawn on a canvas so no image file is needed. */
function jerseyLogo() {
  const canvas = document.createElement('canvas')
  canvas.width = 512; canvas.height = 488
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.translate(12, 12)                                             // clear margin, so the patch edge stays transparent
  ctx.scale((canvas.width - 24) / 489, (canvas.height - 24) / 465)
  for (const [d, color] of [[UH_OUTER, '#fff'], [UH_KEYLINE, '#000'], [UH_LETTERS, '#fff']]) {
    ctx.fillStyle = color
    ctx.fill(new Path2D(d))
  }
  const tex = new THREE.CanvasTexture(canvas)
  tex.anisotropy = 4
  return tex
}

export function createCougar(scene: THREE.Scene) {
  const gradientMap = toonGradient()
  const mats = new Map<string, THREE.Material>()
  const mat = (color: string) => {
    if (!mats.has(color)) mats.set(color, new THREE.MeshToonMaterial({ color, gradientMap }))
    return mats.get(color)!
  }
  const outlineMat = new THREE.MeshBasicMaterial({ color: C.outline, side: THREE.BackSide })
  const sphere = new THREE.SphereGeometry(1, 24, 16)
  const cyl = new THREE.CylinderGeometry(1, 1, 1, 16, 1)
  const cone = new THREE.ConeGeometry(1, 1, 20)

  /** Toon mesh with an inverted-hull outline child. */
  const part = (geo: THREE.BufferGeometry, color: string, outline = 1.08) => {
    const m = new THREE.Mesh(geo, mat(color))
    if (outline) {
      const o = new THREE.Mesh(geo, outlineMat)
      o.scale.setScalar(outline)
      m.add(o)
    }
    return m
  }

  const root = new THREE.Group()
  scene.add(root)

  // ---- limbs: cylinders between two points, spheres at joints ------------------------------------
  type Seg = { a: number; b: number; r: number; mesh: THREE.Mesh }
  const segs: Seg[] = []
  const seg = (a: number, b: number, r: number, color: string) => {
    const mesh = part(cyl, color, 0)
    const o = new THREE.Mesh(cyl, outlineMat)
    o.scale.set(1.18, 1, 1.18)
    mesh.add(o)
    root.add(mesh)
    segs.push({ a, b, r, mesh })
  }
  type Ball = { i: number; r: number; mesh: THREE.Mesh }
  const balls: Ball[] = []
  const ball = (i: number, r: number, color: string) => {
    const mesh = part(sphere, color, 1.14)
    root.add(mesh)
    balls.push({ i, r, mesh })
  }

  seg(LS, LE, 0.13, C.jersey); seg(RS, RE, 0.13, C.jersey)        // jersey sleeves
  seg(LE, LW, 0.1, C.fur); seg(RE, RW, 0.1, C.fur)                // furry forearms
  ball(LS, 0.16, C.jersey); ball(RS, 0.16, C.jersey); ball(LE, 0.11, C.fur); ball(RE, 0.11, C.fur)
  for (const H of [LH, RH]) {
    for (const f of FINGERS) {
      seg(H + f[0], H + f[1], f[0] === 1 ? 0.042 : 0.036, C.fur)
      seg(H + f[1], H + f[2], 0.033, C.fur)
      seg(H + f[2], H + f[3], 0.03, C.fur)
      for (const j of f) ball(H + j, j === f[3] ? 0.04 : 0.035, j === f[3] ? C.pad : C.fur)
    }
  }
  seg(LW, LH, 0.085, C.fur); seg(RW, RH, 0.085, C.fur)            // wrist into paw

  // palms: flattened ellipsoids spanning wrist and knuckles
  const palms = [LH, RH].map((H) => {
    const mesh = part(sphere, C.fur, 1.1)
    root.add(mesh)
    return { H, mesh }
  })
  // closed paws shown when a hand is not tracked in this frame
  const fists = [[LW, LH], [RW, RH]].map(([W, H]) => {
    const mesh = part(sphere, C.fur, 1.12)
    root.add(mesh)
    return { W, H, mesh }
  })

  // ---- torso (jersey) and neck --------------------------------------------------------------------
  const torso = part(sphere, C.jersey, 1.04)
  const collar = part(new THREE.TorusGeometry(1, 0.18, 12, 32), C.trim, 0)
  const neck = part(cyl, C.fur, 0)
  root.add(torso, collar, neck)
  // UH logo on the chest: a patch of sphere just above the jersey, so it follows the torso's shape and lean
  const logo = new THREE.Mesh(
    new THREE.SphereGeometry(1.02, 16, 12, Math.PI / 2 - 0.5, 1.0, 0.98, 0.62),
    new THREE.MeshToonMaterial({ color: C.logo, alphaMap: jerseyLogo(), gradientMap, transparent: true, depthWrite: false }),
  )
  torso.add(logo)

  // ---- head ---------------------------------------------------------------------------------------
  const head = new THREE.Group()
  root.add(head)
  const add = (m: THREE.Object3D, p: [number, number, number], s: [number, number, number], r: [number, number, number] = [0, 0, 0]) => {
    m.position.set(...p); m.scale.set(...s); m.rotation.set(...r); head.add(m); return m
  }
  add(part(sphere, C.fur, 1.04), [0, 0, 0], [1, 0.94, 0.9])                                   // skull
  add(part(sphere, C.furLight, 1.05), [0, -0.3, 0.62], [0.58, 0.42, 0.42])                    // muzzle
  add(part(sphere, C.nose, 1.08), [0, -0.12, 1.0], [0.17, 0.11, 0.1])                         // nose
  for (const s of [-1, 1]) {
    add(part(cone, C.fur, 1.08), [0.6 * s, 0.78, -0.05], [0.3, 0.42, 0.18], [0, 0, -0.45 * s])   // ears
    add(part(cone, C.earInner, 0), [0.6 * s, 0.75, 0.04], [0.18, 0.28, 0.08], [0, 0, -0.45 * s])
    add(part(cyl, C.marking, 0), [0.24 * s, -0.12, 0.84], [0.025, 0.36, 0.025], [0.15, 0, 0.35 * s]) // tear marks
    for (const k of [0, 1, 2]) add(part(sphere, C.marking, 0), [0.2 * s + 0.08 * s * k, -0.3 - 0.04 * k, 0.96], [0.022, 0.022, 0.022])
  }
  const eyes = [-1, 1].map((s) => {
    const g = new THREE.Group()
    add(g, [0.33 * s, 0.14, 0.72], [1, 1, 1])
    g.add(part(sphere, C.eye, 1.1))
    g.children[0].scale.set(0.2, 0.2, 0.14)
    const iris = part(sphere, C.iris, 0)
    iris.position.set(0, 0, 0.1); iris.scale.set(0.12, 0.13, 0.06)
    const pupil = part(sphere, C.pupil, 0)
    pupil.position.set(0, 0, 0.15); pupil.scale.set(0.04, 0.09, 0.03)
    g.add(iris, pupil)
    return g
  })
  const brows = [-1, 1].map((s) => add(part(cyl, C.marking, 0), [0.33 * s, 0.4, 0.8], [0.035, 0.26, 0.035], [0, 0, Math.PI / 2 - 0.22 * s]))
  const jaw = new THREE.Group()
  add(jaw, [0, -0.42, 0.45], [1, 1, 1])
  const mouthInside = part(sphere, C.mouth, 0)
  mouthInside.position.set(0, 0.02, 0.18); mouthInside.scale.set(0.3, 0.12, 0.2)
  const chinMesh = part(sphere, C.furLight, 1.06)
  chinMesh.position.set(0, -0.08, 0.2); chinMesh.scale.set(0.36, 0.17, 0.3)
  jaw.add(mouthInside, chinMesh)

  // ---- per-frame pose ----------------------------------------------------------------------------
  const P: THREE.Vector3[] = Array.from({ length: 178 }, () => new THREE.Vector3())
  const ok: boolean[] = new Array(178).fill(false)
  const up = new THREE.Vector3(0, 1, 0), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3(), basis = new THREE.Matrix4()
  let headR = 0.48, browBase = -1, lidBase = -1

  const place = (mesh: THREE.Object3D, a: THREE.Vector3, b: THREE.Vector3, r: number) => {
    const len = a.distanceTo(b)
    mesh.position.copy(a).add(b).multiplyScalar(0.5)
    mesh.quaternion.setFromUnitVectors(up, tmp.copy(b).sub(a).normalize())
    mesh.scale.set(r, len, r)
  }

  function update(get: Getter) {
    for (let i = 0; i < 178; i++) ok[i] = get(i, P[i])
    // Signing happens in front of the body; keep paws clear of the jersey even when depth is flat (sign.mt).
    for (const i of [LW, RW]) if (ok[i]) P[i].z = Math.max(P[i].z, 0) + 0.12
    for (let i = LH; i < LH + 42; i++) if (ok[i]) P[i].z = Math.max(P[i].z, 0) + 0.16
    root.visible = ok[LS] && ok[RS]
    if (!root.visible) return
    const shoulderMid = tmp2.copy(P[LS]).add(P[RS]).multiplyScalar(0.5).clone()
    const width = P[LS].distanceTo(P[RS])
    const hipMid = ok[LHIP] && ok[RHIP] ? P[LHIP].clone().add(P[RHIP]).multiplyScalar(0.5) : shoulderMid.clone().add(new THREE.Vector3(0, -1.5, 0))

    for (const s of segs) {
      s.mesh.visible = ok[s.a] && ok[s.b]
      if (s.mesh.visible) place(s.mesh, P[s.a], P[s.b], s.r)
    }
    for (const b of balls) {
      b.mesh.visible = ok[b.i]
      if (ok[b.i]) { b.mesh.position.copy(P[b.i]); b.mesh.scale.setScalar(b.r) }
    }
    for (const p of palms) {
      const H = p.H
      p.mesh.visible = ok[H] && ok[H + 5] && ok[H + 9] && ok[H + 17]
      if (!p.mesh.visible) continue
      const x = P[H + 5].clone().sub(P[H + 17]); const across = x.length(); x.normalize()
      const y = P[H + 9].clone().sub(P[H]); const along = y.length(); y.normalize()
      const z = new THREE.Vector3().crossVectors(x, y).normalize()
      y.crossVectors(z, x)
      p.mesh.quaternion.setFromRotationMatrix(basis.makeBasis(x, y, z))
      p.mesh.position.copy(P[H]).add(P[H + 5]).add(P[H + 9]).add(P[H + 17]).multiplyScalar(0.25)
      p.mesh.scale.set(across * 0.62, along * 0.6, 0.06)
    }
    for (const f of fists) {
      f.mesh.visible = ok[f.W] && !ok[f.H]
      if (f.mesh.visible) { f.mesh.position.copy(P[f.W]); f.mesh.scale.setScalar(0.12) }
    }

    // torso ellipsoid from shoulders down toward the hips
    const axis = shoulderMid.clone().sub(hipMid)
    torso.position.copy(hipMid).add(axis.clone().multiplyScalar(0.55)).add(new THREE.Vector3(0, 0, -0.12))
    torso.quaternion.setFromUnitVectors(up, axis.clone().normalize())
    torso.scale.set(width * 0.6, axis.length() * 0.62, width * 0.24)
    collar.position.copy(shoulderMid).add(new THREE.Vector3(0, 0.05, 0))
    collar.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), axis.clone().normalize())
    collar.scale.set(width * 0.22, width * 0.22, width * 0.22)

    // head orientation from the face; face-forward fallback above the shoulders
    const faceOk = ok[EYE_R_OUT] && ok[EYE_L_OUT] && ok[FOREHEAD] && ok[CHIN]
    let faceH = 0.5
    if (faceOk) {
      const x = P[EYE_L_OUT].clone().sub(P[EYE_R_OUT]).normalize()
      const yRaw = P[FOREHEAD].clone().sub(P[CHIN])
      faceH = yRaw.length()
      const y = yRaw.sub(x.clone().multiplyScalar(yRaw.dot(x))).normalize()
      const z = new THREE.Vector3().crossVectors(x, y)
      head.quaternion.slerp(new THREE.Quaternion().setFromRotationMatrix(basis.makeBasis(x, y, z)), 0.5)
      headR += (THREE.MathUtils.clamp(faceH * 0.95, 0.38, 0.62) - headR) * 0.2
      head.position.copy(P[FOREHEAD]).add(P[CHIN]).multiplyScalar(0.5).add(z.multiplyScalar(-0.15 * headR)).add(new THREE.Vector3(0, 0.12, 0))
    } else {
      head.position.copy(shoulderMid).add(new THREE.Vector3(0, 0.75, 0))
    }
    head.scale.setScalar(headR)
    place(neck, shoulderMid, head.position.clone().add(new THREE.Vector3(0, -headR * 0.6, 0)), width * 0.16)

    // expressions: jaw from lip gap, brows from brow-to-eyelid distance, eyelids from lid gap
    if (ok[LIP_UP] && ok[LIP_LO]) {
      const open = THREE.MathUtils.clamp((P[LIP_UP].distanceTo(P[LIP_LO]) / faceH - 0.015) * 7, 0, 1)
      jaw.rotation.x += (open * 0.5 - jaw.rotation.x) * 0.5
      mouthInside.visible = open > 0.08
    }
    if (ok[BROW_R] && ok[BROW_L] && ok[LID_R_UP] && ok[LID_L_UP]) {
      const d = (P[BROW_R].distanceTo(P[LID_R_UP]) + P[BROW_L].distanceTo(P[LID_L_UP])) / 2 / faceH
      browBase = browBase < 0 ? d : browBase + (d - browBase) * 0.02
      const raise = THREE.MathUtils.clamp((d - browBase) * 9, -0.6, 1)
      brows.forEach((b) => { b.position.y = 0.4 + raise * 0.14 })
    }
    if (ok[LID_R_UP] && ok[LID_R_LO] && ok[LID_L_UP] && ok[LID_L_LO]) {
      const g = (P[LID_R_UP].distanceTo(P[LID_R_LO]) + P[LID_L_UP].distanceTo(P[LID_L_LO])) / 2 / faceH
      lidBase = lidBase < 0 ? g : lidBase + (g - lidBase) * 0.02
      const open = THREE.MathUtils.clamp(g / Math.max(lidBase, 1e-3), 0.15, 1.2)
      eyes.forEach((e) => { e.scale.y = open })
    }
  }

  return { update, setVisible: (v: boolean) => { root.visible = v } }
}
