import type { Caption, Message } from './types'

/** Words of `corrected`, flagged when they are not part of the longest common word run with `original`. */
export function wordDiff(original: string | null, corrected: string) {
  const b = corrected.split(/\s+/).filter(Boolean)
  if (!original) return b.map((word) => ({ word, changed: false }))
  const a = original.split(/\s+/).filter(Boolean)
  const lcs = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1])
  const out: { word: string; changed: boolean }[] = []
  let i = 0
  let j = 0
  while (j < b.length) {
    if (i < a.length && a[i] === b[j]) {
      out.push({ word: b[j], changed: false }); i++; j++
    } else if (i < a.length && lcs[i + 1][j] >= lcs[i][j + 1]) {
      i++
    } else {
      out.push({ word: b[j], changed: true }); j++
    }
  }
  return out
}

/**
 * For each signed word, in order, the indices of the caption's whitespace-separated words it covers.
 * Signed words come from the backend (medbridge/text2sign.py, text_to_glosses): lower-case runs of [a-z0-9'],
 * with unsigned words like "the" left out and pairs like "thank you" joined into one entry.
 */
export function signedWordSpans(text: string, signed: string[]) {
  const parts = text.split(/\s+/).filter(Boolean).flatMap((word, index) =>
    (word.toLowerCase().match(/[a-z0-9']+/g) ?? []).map((part) => ({ index, part: part.replace(/^'+|'+$/g, '') })))
  let from = 0
  return signed.map((word) => {
    const span: number[] = []
    for (const piece of word.split(' ')) {
      const at = parts.findIndex((p, k) => k >= from && p.part === piece)
      if (at < 0) continue
      from = at + 1
      if (!span.includes(parts[at].index)) span.push(parts[at].index)
    }
    return span
  })
}

export type TimelineEntry ={ kind: 'doctor'; item: Caption } | { kind: 'patient'; item: Message }

export function timeline(captions: Caption[], messages: Message[]): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    ...captions.map((item) => ({ kind: 'doctor' as const, item })),
    ...messages.map((item) => ({ kind: 'patient' as const, item })),
  ]
  return entries.sort((x, y) => x.item.t - y.item.t)
}
