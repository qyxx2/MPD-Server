export type Freshness = 'fresh' | 'stale' | 'unknown'
export interface PlaybackControlTarget { queue_item_id: string; token: string }
export interface PlaybackState {
  song_id: string | null
  state: 'PLAYING' | 'PAUSED' | 'STOPPED'
  playback_context_id: string | null
  position_seconds: number | null
  autoplay_enabled: boolean
  updated_at: string
}
export interface Artwork {
  artwork_id: string; source: 'EMBEDDED'; picture_index: number
  mime_type: string | null; width: number | null; height: number | null; content_sha256: string | null
}
export interface Song {
  song_id: string | null; title: string; file_uri: string; artists: string[]
  album_id: string | null; album: string | null; album_artists: string[]
  track_number: number | null; disc_number: number | null; year: number | null; date: string | null
  genres: string[]; tag_names: string[]; duration: number | null
  lyrics: string | null; lyrics_format: string | null; lyrics_source: string | null; lyrics_status: string
  bit_depth: number | null; sample_rate_hz: number | null; channel_count: number | null; codec: string | null
  metadata_status: string | null; last_scanned_at: string | null; file_size: number | null
  file_mtime_ns: number | null; content_hash: string | null
  availability_status: 'AVAILABLE' | 'MISSING' | 'UNREADABLE'; last_seen_at: string | null; artwork: Artwork | null
}
export interface QueueItem {
  queue_item_id: string; song_id: string; position: number; source: 'MANUAL' | 'AUTOPLAY'; playback_context_id: string | null
}
export interface HistoryEvent {
  history_id: number | null; song_id: string; started_at: string; ended_at: string | null; reason: string | null; session_id: string | null
}
export interface Observation {
  observed_at: string | null; freshness: Freshness; error_code: string | null; error_message: string | null
}
export interface PlaybackObservation extends Observation {
  actual_state: 'playing' | 'paused' | 'stopped' | null
  actual_current: { entry_id: number | null; uri: string | null; position: number | null } | null
  actual_freshness: Freshness; bound_queue_item_id: string | null; control_target: PlaybackControlTarget | null
  sync_status: 'CONFIRMED' | 'UNBOUND' | 'EXTERNAL_DRIFT' | 'UNCONFIRMED_STOP' | 'SYNC_FAILED' | 'NO_CANDIDATES'
  matches_current: boolean | null; position_seconds: number | null; duration_seconds: number | null; reconciliation_required: boolean
}
export type OutputMode = 'NAS_DAC' | 'CLIENT_STREAM'
export interface StateOutput {
  mode: OutputMode; status: 'UNAVAILABLE' | 'INACTIVE' | 'ACTIVE'
  target_client_id: string | null; stream_url: string | null; format: string | null
  sample_rate: number | null; bit_depth: number | null; channels: number | null
  error_code: string | null; error_message: string | null; updated_at: string; stale: boolean
}
export interface StateOutputRequest {
  mode: OutputMode; enabled: boolean; status: 'PREPARING' | 'SUCCEEDED' | 'SWITCH_FAILED'
  error_code: string | null; error_message: string | null; updated_at: string
}
export interface StateOutputSnapshot { states: StateOutput[]; last_request: StateOutputRequest | null }
export interface RestOutputState {
  mode: OutputMode; status: StateOutput['status']; targetClientId: string | null; streamUrl: string | null; format: string | null
  sampleRate: number | null; bitDepth: number | null; channels: number | null
  errorCode: string | null; errorMessage: string | null; updatedAt: string; stale: boolean
}
export interface RestOutputRequest {
  mode: OutputMode; enabled: boolean; status: StateOutputRequest['status']
  errorCode: string | null; errorMessage: string | null; updatedAt: string
}
// The outer REST field remains snake_case; only nested models use aliases.
export interface RestOutputSnapshot { states: RestOutputState[]; last_request: RestOutputRequest | null }
export interface Revisions { library: number; playlist: number }
export interface FullStateSnapshot {
  epoch: string; sequence: number; captured_at: string; revisions: Revisions
  playback: PlaybackState | null; current_song: Song | null
  queue: { revision: number; items: QueueItem[] }
  history: { has_entries: boolean; active_event: HistoryEvent | null; session_id: string | null }
  output: StateOutputSnapshot; playback_observation: PlaybackObservation; output_observation: Observation
}
export interface SnapshotFrame { type: 'snapshot'; protocol_version: 1; epoch: string; sequence: number; state: FullStateSnapshot }
export type Domain = 'playback' | 'queue' | 'history' | 'library' | 'playlist' | 'output'
export interface InvalidateFrame { type: 'invalidate'; protocol_version: 1; epoch: string; sequence: number; domains: Domain[]; revisions: Revisions }
export type RealtimeFrame = SnapshotFrame | InvalidateFrame
export interface ApiErrorBody { code: string; message: string; details: unknown }
export type MutationMethod = 'POST' | 'PUT' | 'PATCH' | 'DELETE'
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }
export interface MutationIntent {
  readonly key: string; readonly method: MutationMethod; readonly path: string
  readonly payload: JsonValue | undefined; readonly canonicalPayload: string | undefined
}

export class ApiError extends Error {
  readonly name = 'ApiError'
  constructor(
    readonly kind: 'http' | 'network' | 'wire', readonly status: number | null,
    readonly code: string, message: string, readonly details: unknown = null,
  ) { super(message) }
}
