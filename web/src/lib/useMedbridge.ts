import { useCallback, useEffect, useRef, useState } from 'react'
import type { Landmarks, State } from './types'

/** Live connection to the backend. State snapshots re-render; landmarks and mic level are kept in
 * refs so 30 fps streams drive canvases without re-rendering React. */
export function useMedbridge(role: 'patient' | 'doctor') {
  const [state, setState] = useState<State | null>(null)
  const [connected, setConnected] = useState(false)
  const [fps, setFps] = useState<number | null>(null)
  const landmarks = useRef<Landmarks | null>(null)
  const level = useRef(0)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    let stopped = false
    let retry = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const sock = new WebSocket(`${proto}://${location.host}/ws?role=${role}`)
      ws.current = sock
      sock.onopen = () => { retry = 0; setConnected(true) }
      sock.onmessage = (e) => {
        const m = JSON.parse(e.data)
        if (m.type === 'state') setState(m.state)
        else if (m.type === 'landmarks') landmarks.current = { ...m, at: performance.now() }
        else if (m.type === 'level') level.current = m.level
        else if (m.type === 'vision.fps') setFps(m.fps)
      }
      sock.onclose = () => {
        setConnected(false)
        if (!stopped) timer = setTimeout(connect, Math.min(4000, 300 * 2 ** retry++))
      }
    }
    connect()
    return () => { stopped = true; clearTimeout(timer); ws.current?.close() }
  }, [role])

  const send = useCallback((msg: Record<string, unknown>) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(msg))
  }, [])

  return { state, connected, fps, landmarks, level, send }
}
