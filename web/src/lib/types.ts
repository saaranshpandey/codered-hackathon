export type Caption = { id: number; text: string; original: string | null; t: number }
export type Message = { id: number; text: string; source: string; edited: boolean; t: number; glosses: string[] }
export type Candidate = { text: string; score: number; rel_score: number }
export type TopK = { label: string; glosses: string[]; p: number }
export type PreciseItem = { seg_id: number; topk: TopK[]; uncertain: boolean; chosen: string | null; latency_ms: number | null }
export type SignState = 'idle' | 'hands' | 'signing' | 'translating' | 'recognizing' | 'loading' | 'no_camera'
export type State = {
  captions: Caption[]
  interim: { id: number; text: string } | null
  messages: Message[]
  asr: { state: 'listening' | 'speech' | 'paused' | 'loading' }
  sign: { mode: 'natural' | 'precise'; state: SignState }
  natural: { seg_id: number; candidates: Candidate[]; latency_ms: number | null; selected: number; low_confidence: boolean } | null
  precise: PreciseItem[]
  draft: { text: string; source: string; edited: boolean }
}
export type Landmarks = { mode: string; hands: number[][][]; body: number[][]; at: number }
