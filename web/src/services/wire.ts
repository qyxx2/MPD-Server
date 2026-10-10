import type {
  Artwork, FullStateSnapshot, HistoryEvent, InvalidateFrame, Observation,
  PlaybackObservation, PlaybackState, QueueItem, RealtimeFrame, RestOutputSnapshot,
  Song, StateOutput, StateOutputRequest, StateOutputSnapshot,
} from '../types/api'

export class WireError extends Error { readonly name = 'WireError' }
type Decoder<T> = (value: unknown) => T
function fail(): never { throw new WireError('Invalid wire value') }
const text: Decoder<string> = value => typeof value === 'string' ? value : fail()
const nonempty: Decoder<string> = value => typeof value === 'string' && value.length > 0 ? value : fail()
const bool: Decoder<boolean> = value => typeof value === 'boolean' ? value : fail()
const number: Decoder<number> = value => typeof value === 'number' && Number.isFinite(value) ? value : fail()
const integer: Decoder<number> = value => typeof value === 'number' && Number.isInteger(value) ? value : fail()
const natural: Decoder<number> = value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : fail()
const nonnegative: Decoder<number> = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fail()
const timestamp: Decoder<string> = value => typeof value === 'string' && Number.isFinite(Date.parse(value)) ? value : fail()
function nullable<T>(decode: Decoder<T>): Decoder<T | null> { return value => value === null ? null : decode(value) }
function list<T>(decode: Decoder<T>): Decoder<T[]> { return value => Array.isArray(value) ? value.map(decode) : fail() }
function enumeration<const T extends readonly string[]>(...values: T): Decoder<T[number]> {
  return value => typeof value === 'string' && values.includes(value) ? value as T[number] : fail()
}
function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return fail()
  return value as Record<string, unknown>
}
function object<T>(fields: { [K in keyof T]: Decoder<T[K]> }): Decoder<T> {
  return value => {
    const source = record(value)
    const result = {} as T
    for (const key of Object.keys(fields) as (keyof T)[]) result[key] = fields[key](source[key as string])
    return result
  }
}
const optionalNullText = nullable(text)
const optionalInteger = nullable(integer)
const optionalTime = nullable(timestamp)
const freshness = enumeration('fresh', 'stale', 'unknown')
const revisions = object({ library: natural, playlist: natural })
const target = object({ queue_item_id: nonempty, token: nonempty })
const actual = object({ entry_id: nullable(integer), uri: optionalNullText, position: nullable(natural) })
const observationFields = { observed_at: optionalTime, freshness, error_code: optionalNullText, error_message: optionalNullText }
const observation = object<Observation>(observationFields)
const playbackObservation = object<PlaybackObservation>({
  ...observationFields,
  actual_state: nullable(enumeration('playing', 'paused', 'stopped')),
  actual_current: nullable(actual), actual_freshness: freshness, bound_queue_item_id: optionalNullText,
  control_target: nullable(target), sync_status: enumeration('CONFIRMED', 'UNBOUND', 'EXTERNAL_DRIFT', 'UNCONFIRMED_STOP', 'SYNC_FAILED', 'NO_CANDIDATES'),
  matches_current: nullable(bool), position_seconds: nullable(nonnegative), duration_seconds: nullable(nonnegative), reconciliation_required: bool,
})
const playback = object<PlaybackState>({
  song_id: optionalNullText, state: enumeration('PLAYING', 'PAUSED', 'STOPPED'), playback_context_id: optionalNullText,
  position_seconds: nullable(nonnegative), autoplay_enabled: bool, updated_at: timestamp,
})
const artwork = object<Artwork>({
  artwork_id: text, source: enumeration('EMBEDDED'), picture_index: integer, mime_type: optionalNullText,
  width: optionalInteger, height: optionalInteger, content_sha256: optionalNullText,
})
const song = object<Song>({
  song_id: optionalNullText, title: text, file_uri: text, artists: list(text), album_id: optionalNullText, album: optionalNullText,
  album_artists: list(text), track_number: optionalInteger, disc_number: optionalInteger, year: optionalInteger, date: optionalNullText,
  genres: list(text), tag_names: list(text), duration: nullable(number), lyrics: optionalNullText, lyrics_format: optionalNullText,
  lyrics_source: optionalNullText, lyrics_status: text, bit_depth: optionalInteger, sample_rate_hz: optionalInteger, channel_count: optionalInteger,
  codec: optionalNullText, metadata_status: optionalNullText, last_scanned_at: optionalTime, file_size: optionalInteger,
  file_mtime_ns: optionalInteger, content_hash: optionalNullText, availability_status: enumeration('AVAILABLE', 'MISSING', 'UNREADABLE'),
  last_seen_at: optionalTime, artwork: nullable(artwork),
})
const queueItem = object<QueueItem>({ queue_item_id: text, song_id: text, position: integer, source: enumeration('MANUAL', 'AUTOPLAY'), playback_context_id: optionalNullText })
const historyEvent = object<HistoryEvent>({ history_id: optionalInteger, song_id: text, started_at: timestamp, ended_at: optionalTime, reason: optionalNullText, session_id: optionalNullText })
const mode = enumeration('NAS_DAC', 'CLIENT_STREAM')
const outputState = object<StateOutput>({
  mode, status: enumeration('UNAVAILABLE', 'INACTIVE', 'ACTIVE'), target_client_id: optionalNullText, stream_url: optionalNullText,
  format: optionalNullText, sample_rate: optionalInteger, bit_depth: optionalInteger, channels: optionalInteger,
  error_code: optionalNullText, error_message: optionalNullText, updated_at: timestamp, stale: bool,
})
const outputRequest = object<StateOutputRequest>({
  mode, enabled: bool, status: enumeration('PREPARING', 'SUCCEEDED', 'SWITCH_FAILED'),
  error_code: optionalNullText, error_message: optionalNullText, updated_at: timestamp,
})
const output = object<StateOutputSnapshot>({ states: list(outputState), last_request: nullable(outputRequest) })
const snapshot = object<FullStateSnapshot>({
  epoch: nonempty, sequence: natural, captured_at: timestamp, revisions,
  playback: nullable(playback), current_song: nullable(song), queue: object({ revision: natural, items: list(queueItem) }),
  history: object({ has_entries: bool, active_event: nullable(historyEvent), session_id: optionalNullText }),
  output, playback_observation: playbackObservation, output_observation: observation,
})

export function parseSnapshot(value: unknown): FullStateSnapshot {
  const source = record(value)
  const observed = record(source.playback_observation)
  // Only explicitly additive legacy fields default. Mandatory domains fail closed.
  const normalized = { ...observed }
  const defaults = { actual_current: null, actual_freshness: 'unknown', bound_queue_item_id: null, control_target: null, sync_status: 'UNBOUND' }
  for (const [key, fallback] of Object.entries(defaults)) {
    if (!(key in normalized)) normalized[key] = fallback
  }
  return snapshot({ ...source, playback_observation: normalized })
}

export function parseRealtimeFrame(value: unknown): RealtimeFrame {
  if (typeof value === 'string') {
    try { value = JSON.parse(value) } catch { throw new WireError('Invalid frame JSON') }
  }
  const frame = record(value)
  if (frame.protocol_version !== 1) throw new WireError('Unsupported protocol version')
  const epoch = nonempty(frame.epoch)
  const sequence = natural(frame.sequence)
  if (frame.type === 'snapshot') {
    const state = parseSnapshot(frame.state)
    if (state.epoch !== epoch || state.sequence !== sequence) throw new WireError('Snapshot envelope disagrees with state')
    return { type: 'snapshot', protocol_version: 1, epoch, sequence, state }
  }
  if (frame.type === 'invalidate') {
    return object<InvalidateFrame>({
      type: enumeration('invalidate'), protocol_version: value => value === 1 ? 1 : fail(), epoch: nonempty, sequence: natural,
      domains: list(enumeration('playback', 'queue', 'history', 'library', 'playlist', 'output')), revisions,
    })(frame)
  }
  throw new WireError('Unknown frame type')
}

export function normalizeOutput(value: RestOutputSnapshot): StateOutputSnapshot {
  const source = record(value)
  if (!Array.isArray(source.states)) return fail()
  const request = source.last_request === null ? null : record(source.last_request)
  return output({
    states: source.states.map(value => {
      const s = record(value)
      return {
        mode: s.mode, status: s.status, target_client_id: s.targetClientId, stream_url: s.streamUrl,
        format: s.format, sample_rate: s.sampleRate, bit_depth: s.bitDepth, channels: s.channels,
        error_code: s.errorCode, error_message: s.errorMessage, updated_at: s.updatedAt, stale: s.stale,
      }
    }),
    last_request: request === null ? null : {
      mode: request.mode, enabled: request.enabled, status: request.status,
      error_code: request.errorCode, error_message: request.errorMessage, updated_at: request.updatedAt,
    },
  })
}

export const parsePlaybackState = playback
export function parseRestOutput(value: unknown): StateOutputSnapshot {
  // Runtime validation is performed by the explicit alias adapter.
  return normalizeOutput(value as RestOutputSnapshot)
}
