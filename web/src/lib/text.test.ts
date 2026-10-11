import { describe, expect, it } from 'vitest'
import { signedWordSpans, timeline, wordDiff } from './text'

describe('wordDiff', () => {
  it('marks only the words the doctor changed', () => {
    const out = wordDiff('Are you allergic to pencil in?', 'Are you allergic to penicillin?')
    expect(out.filter((w) => w.changed).map((w) => w.word)).toEqual(['penicillin?'])
    expect(out.map((w) => w.word).join(' ')).toBe('Are you allergic to penicillin?')
  })
  it('returns all words unchanged when there is no original', () => {
    expect(wordDiff(null, 'Hello there').every((w) => !w.changed)).toBe(true)
  })
})

describe('signedWordSpans', () => {
  it('finds each signed word in the caption, skipping the words that are not signed', () => {
    expect(signedWordSpans('Come to the belly.', ['come', 'belly'])).toEqual([[0], [3]])
  })
  it('keeps repeated words in order', () => {
    expect(signedWordSpans('Does it hurt here, or here?', ['hurt', 'here', 'or', 'here'])).toEqual([[2], [3], [4], [5]])
  })
  it('covers both caption words of a joined pair, and one caption word that holds several signed words', () => {
    expect(signedWordSpans('Thank you. One-to-ten?', ['thank you', 'one', 'ten'])).toEqual([[0, 1], [2], [2]])
  })
  it('returns an empty span for a signed word that is not in the caption', () => {
    expect(signedWordSpans('Hello', ['goodbye', 'hello'])).toEqual([[], [0]])
  })
})

describe('timeline', () => {
  it('interleaves doctor captions and confirmed patient messages by time', () => {
    const t = timeline(
      [{ id: 1, text: 'Hi', original: null, t: 10 }, { id: 3, text: 'When?', original: null, t: 30 }],
      [{ id: 2, text: 'My stomach hurts.', source: 'natural', edited: false, t: 20, glosses: [] }],
    )
    expect(t.map((e) => e.kind + ':' + e.item.id)).toEqual(['doctor:1', 'patient:2', 'doctor:3'])
  })
})
