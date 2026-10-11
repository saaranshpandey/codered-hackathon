export type Caption = { id: number; text: string; original: string | null; t: number }
export type Message = { id: number; text: string; source: string; edited: boolean; t: number; glosses: string[] }
export type Candidate = { text: string; score: number; rel_score: number; kind?: 'phrase' | 'free' }
export type TopK = { label: string; glosses: string[]; p: number }
export type PreciseItem = { seg_id: number; topk: TopK[]; uncertain: boolean; chosen: string | null; latency_ms: number | null }
export type SignState = 'idle' | 'hands' | 'signing' | 'translating' | 'recognizing' | 'loading' | 'no_camera'
export type State = {
  captions: Caption[]
  interim: { id: number; text: string } | null
  messages: Message[]
  asr: { state: 'listening' | 'speech' | 'paused' | 'loading' }
  sign: { mode: 'natural' | 'precise'; state: SignState; enabled: boolean } // enabled: the patient's on/off switch
  natural: { seg_id: number; candidates: Candidate[]; latency_ms: number | null; selected: number; low_confidence: boolean } | null
  precise: PreciseItem[]
  draft: { text: string; source: string; edited: boolean }
  signing: Signing | null
}
export type Signing = {
  caption_id: number; status: 'building' | 'ready' | 'empty' | 'error'; frames: number; fps: number
  words: { word: string; gloss: string | null; source: 'aslc' | 'signmt' | 'none'; start: number; end: number }[] | null
}
/** The word of a caption that the mascot is signing right now: an index into that caption's `Signing.words`. */
export type SignedWord = { captionId: number; index: number }
export type Landmarks ={ mode: string; hands: number[][][]; body: number[][]; at: number }
