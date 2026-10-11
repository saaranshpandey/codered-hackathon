/**
 * Theme colours for code that draws by hand (canvas, animated borders), where a Tailwind class cannot be used.
 * The colours themselves live in src/theme.css; this only reads them.
 */

/** Roles from theme.css (see its last block for what each one is). */
export type ThemeRole = 'ink' | 'bone' | 'paper' | 'graphite' | 'doctor' | 'mint' | 'mint-deep' | 'leaf' | 'signal' | 'stage' | 'amber'

const cache = new Map<ThemeRole, [number, number, number]>()

function rgb(role: ThemeRole) {
  let c = cache.get(role)
  if (!c) {
    const probe = document.createElement('span')
    probe.style.color = `var(--color-${role})`
    document.body.appendChild(probe)
    const computed = getComputedStyle(probe).color // "rgb(31, 32, 31)", or "color(srgb 0.12 0.13 0.12)"
    probe.remove()
    const n = (computed.match(/[\d.]+/g) ?? ['0', '0', '0']).map(Number)
    const scale = computed.startsWith('color(') ? 255 : 1 // that form gives 0 to 1
    c = [Math.round(n[0] * scale), Math.round(n[1] * scale), Math.round(n[2] * scale)]
    cache.set(role, c)
  }
  return c
}

/** A theme colour as a CSS string, e.g. themeColor('signal', 0.6) -> "rgba(177, 217, 238, 0.6)". */
export function themeColor(role: ThemeRole, alpha = 1) {
  const [r, g, b] = rgb(role)
  return alpha >= 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`
}
