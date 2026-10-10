export interface LyricsDocument {
  text: string
  cues: { seconds: number; text: string }[]
  notes: string[]
  offsetMs: number
  synchronized: boolean
}
export function parseLyrics(text: string, format: string | null): LyricsDocument {
  const doc: LyricsDocument = { text, cues: [], notes: [], offsetMs: 0, synchronized: false }
  if (format?.toLowerCase() !== 'lrc') return doc
  for (const line of text.split(/\r?\n/)) {
    for (const offset of line.matchAll(/\[offset:([+-]?\d+)\]/gi)) {
      const value = Number(offset[1])
      if (Number.isSafeInteger(value)) doc.offsetMs = value
    }
    const times = [...line.matchAll(/\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]/g)]
    const readable = line.replace(/\[\d+:[0-5]\d(?:[.:]\d{1,3})?\]/g, '').trim()
    if (times.length) {
      for (const time of times) {
        const seconds = Number(time[1]) * 60 + Number(time[2]) + Number(`0.${time[3] || '0'}`)
        if (Number.isFinite(seconds)) doc.cues.push({ seconds, text: readable })
      }
    } else if (line.trim() && !/^\[(?:ar|al|ti|au|by|re|ve|length|offset):[^\]]*\]$/i.test(line.trim())) doc.notes.push(line)
  }
  doc.cues.sort((a, b) => a.seconds - b.seconds) // Stable sort preserves source order for ties.
  doc.synchronized = doc.cues.length > 0
  return doc
}
export function activeCue(document: LyricsDocument, seconds: number | null): number[] {
  if (seconds === null || !Number.isFinite(seconds) || !document.synchronized) return []
  const adjusted = seconds + document.offsetMs / 1000
  let latest: number | null = null
  for (const cue of document.cues) { if (cue.seconds > adjusted) break; latest = cue.seconds }
  return latest === null ? [] : document.cues.flatMap((cue, index) => cue.seconds === latest ? [index] : [])
}
