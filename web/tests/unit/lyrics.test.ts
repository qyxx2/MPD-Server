import { expect, it } from 'vitest'
import { activeCue, parseLyrics } from '../../src/components/player/lyrics'
it('parses decimal and colon fractions, expands multiple tags and stably groups simultaneous cues', () => {
  const doc = parseLyrics('[ar:测试]\n[00:02.12][00:01]复唱\n[00:02:120]同刻\n[00:02.1]较早\n[00:03.123]末行', 'lrc')
  expect(doc.cues).toEqual([{ seconds: 1, text: '复唱' }, { seconds: 2.1, text: '较早' }, { seconds: 2.12, text: '复唱' }, { seconds: 2.12, text: '同刻' }, { seconds: 3.123, text: '末行' }])
  expect(activeCue(doc, 0.9)).toEqual([])
  expect(activeCue(doc, 2.12)).toEqual([2, 3])
  expect(activeCue(doc, null)).toEqual([])
})
it('last legal integer offset advances display matching and invalid offsets cannot overwrite it', () => {
  const doc = parseLyrics('[offset:-500]\n[offset:1000]\n[offset:1.5]\n[00:02]提前', 'LRC')
  expect(activeCue(doc, 1)).toEqual([0])
  expect(activeCue(doc, 0.9)).toEqual([])
  expect(activeCue(parseLyrics('[offset:-1000]\n[00:02]延后', 'lrc'), 2)).toEqual([])
})
it('preserves non-time text and malformed tags without inventing cues; no valid cue falls back to raw plain text', () => {
  const raw = '[ar:作者]\n[00:99]坏秒\n[00:01.1234]坏小数\n普通文本 <b>不解释</b>'
  const doc = parseLyrics(raw, 'lrc')
  expect(doc.cues).toEqual([]); expect(doc.text).toBe(raw); expect(doc.synchronized).toBe(false)
  const mixed = parseLyrics('[00:01]有效\n说明文字\n[bad]异常', 'lrc')
  expect(mixed.notes).toEqual(['说明文字', '[bad]异常'])
  expect(parseLyrics('[00:01]原样', 'plain').synchronized).toBe(false)
  expect(activeCue(doc, 100)).toEqual([])
})
