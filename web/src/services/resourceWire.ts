import type { SongList } from '../types/resources'
import { parseSong, parseArtwork, WireError } from './wire'
export { parseSong } from './wire'
export function parseSongResource(value: unknown, path: string) {
  const song = parseSong(value)
  if (path !== `/api/library/songs/${encodeURIComponent(song.song_id ?? '')}`) throw new WireError('Song identity does not match resource')
  return song
}
export function parseSongList(value: unknown): SongList {
  if (value === null || typeof value !== 'object' || !('items' in value) || !('count' in value) ||
    !Array.isArray(value.items) || typeof value.count !== 'number' || !Number.isSafeInteger(value.count) || value.count < 0) {
    throw new WireError('Invalid SongList')
  }
  return { items: value.items.map(parseSong), count: value.count }
}

export function parsePlaylist(value: unknown): import('../types/resources').Playlist {
  if (value === null || typeof value !== 'object') throw new WireError('Invalid Playlist')
  const p = value as Record<string, unknown>
  if (typeof p.playlist_id !== 'string' || !p.playlist_id || typeof p.name !== 'string' ||
      typeof p.created_at !== 'string' || !Number.isFinite(Date.parse(p.created_at)) ||
      typeof p.updated_at !== 'string' || !Number.isFinite(Date.parse(p.updated_at)) || typeof p.is_system !== 'boolean' ||
      !Array.isArray(p.song_ids) || !p.song_ids.every(id => typeof id === 'string' && id.length > 0)) throw new WireError('Invalid Playlist')
  return { playlist_id: p.playlist_id, name: p.name, created_at: p.created_at, updated_at: p.updated_at, is_system: p.is_system, song_ids: [...p.song_ids] }
}
export function parsePlaylistList(value: unknown): import('../types/resources').PlaylistList {
  if (value === null || typeof value !== 'object') throw new WireError('Invalid PlaylistList')
  const p = value as Record<string, unknown>
  if (!Array.isArray(p.items) || typeof p.count !== 'number' || !Number.isSafeInteger(p.count) || p.count < 0) throw new WireError('Invalid PlaylistList')
  return { items: p.items.map(parsePlaylist), count: p.count }
}
export function parseNoContent(value: unknown): void {
  if (value !== undefined) throw new WireError('Expected empty response')
}

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new WireError('Invalid resource object')
  return value as Record<string, unknown>
}
function text(value: unknown): string {
  if (typeof value !== 'string') throw new WireError('Invalid resource text')
  return value
}
function identity(value: unknown): string {
  const id = text(value); if (!id) throw new WireError('Missing resource identity'); return id
}
function natural(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new WireError('Invalid resource count')
  return value
}
function strings(value: unknown): string[] {
  if (!Array.isArray(value)) throw new WireError('Invalid resource list')
  return value.map(text)
}
export function parseCategoryList(value: unknown, kind: import('../types/resources').CategoryKind): import('../types/resources').CategoryList {
  const root = object(value)
  if (!Array.isArray(root.items)) throw new WireError('Invalid category list')
  const count = natural(root.count)
  const items = root.items.map(value => {
    const item = object(value)
    const id = identity(item[{ albums: 'album_id', artists: 'artist_id', genres: 'genre_id', years: 'source_id', tags: 'tag_id' }[kind]])
    let year: number | null = null
    if (kind === 'years' || kind === 'albums') {
      const raw = kind === 'years' ? item.value : item.year
      if (raw !== null && (typeof raw !== 'number' || !Number.isSafeInteger(raw))) throw new WireError('Invalid category year')
      year = raw as number | null
    }
    return { id, name: kind === 'years' ? year === null ? '未知年代' : String(year) : text(kind === 'albums' ? item.title : item.name),
      song_count: natural(item.song_count), year, album_artists: kind === 'albums' ? strings(item.album_artists) : [],
      artwork: kind === 'albums' && item.artwork !== null ? parseArtwork(item.artwork) : null }
  })
  if (new Set(items.map(item => item.id)).size !== items.length || count !== items.length) throw new WireError('Invalid category membership')
  return { kind, items, count }
}
export function parseCollection(value: unknown): import('../types/resources').Collection {
  const c = object(value), source_type = text(c.source_type)
  if (!['ALBUM', 'ARTIST', 'GENRE', 'YEAR', 'TAG', 'SEARCH', 'PLAYLIST', 'FAVORITES', 'LIBRARY', 'SONGS'].includes(source_type)) throw new WireError('Invalid Collection source')
  const source_id = c.source_id === null ? null : identity(c.source_id)
  if (['ALBUM', 'ARTIST', 'GENRE', 'YEAR', 'TAG', 'PLAYLIST'].includes(source_type) && source_id === null) throw new WireError('Missing Collection source')
  const random_seed = c.random_seed === null ? null : natural(c.random_seed)
  return { source_type, source_id, song_ids: strings(c.song_ids), unavailable_song_ids: strings(c.unavailable_song_ids), random_seed }
}
export function parseLibraryResource(value: unknown, path: string): import('../types/resources').LibraryResource {
  if (path.startsWith('/api/library/search/results?')) return parseSearchResults(value)
  if (path.startsWith('/api/library/search?')) {
    const collection = parseCollection(value)
    if (collection.source_type !== 'SEARCH' || new Set(collection.song_ids).size !== collection.song_ids.length) throw new WireError('Invalid Search Collection')
    return collection
  }
  if (/^\/api\/library\/songs\/[^/]+$/.test(path)) return parseSongResource(value, path)
  if (path === '/api/library/songs' || /^\/api\/library\/(albums|artists|genres|years|tags)\/[^/]+\/songs$/.test(path)) return parseSongList(value)
  const kind = path.slice('/api/library/'.length)
  if (kind === 'albums' || kind === 'artists' || kind === 'genres' || kind === 'years' || kind === 'tags') return parseCategoryList(value, kind)
  throw new WireError('Unsupported Library resource')
}

export function parseSearchResults(value: unknown): import('../types/resources').SearchResults {
  const root = object(value)
  if (!Array.isArray(root.groups)) throw new WireError('Invalid Search groups')
  const uniqueIds = (value: unknown) => {
    if (!Array.isArray(value)) throw new WireError('Invalid Search members')
    const ids = value.map(identity)
    if (new Set(ids).size !== ids.length) throw new WireError('Duplicate Search members')
    return ids
  }
  const groups = root.groups.map((value): import('../types/resources').SearchGroup => {
    const g = object(value), kind = text(g.kind)
    if (kind !== 'albums' && kind !== 'artists' && kind !== 'genres' && kind !== 'years' && kind !== 'tags') throw new WireError('Invalid Search category')
    return { kind, source_id: identity(g.source_id), name: text(g.name), song_ids: uniqueIds(g.song_ids) }
  })
  if (new Set(groups.map(g => `${g.kind}:${g.source_id}`)).size !== groups.length) throw new WireError('Duplicate Search category')
  const song_ids = uniqueIds(root.song_ids), grouped = new Set(groups.flatMap(g => g.song_ids))
  if (song_ids.some(id => grouped.has(id))) throw new WireError('Duplicate direct Search result')
  return { groups, song_ids }
}

export function parsePlaylistResource(value: unknown, path: string): import('../types/resources').PlaylistResource {
  if (path === '/api/favorites/members') {
    const ids = strings(object(value).song_ids)
    if (ids.some(id => !id) || new Set(ids).size !== ids.length) throw new WireError('Invalid Favorites membership')
    return { song_ids: ids }
  }
  if (path === '/api/playlists') return parsePlaylistList(value)
  if (/^\/api\/playlists\/[^/]+\/songs$/.test(path)) {
    const songs = parseSongList(value)
    if (songs.count !== songs.items.length || songs.items.some(song => !song.song_id) || new Set(songs.items.map(song => song.song_id)).size !== songs.items.length) throw new WireError('Invalid Playlist members')
    return songs
  }
  if (/^\/api\/playlists\/[^/]+$/.test(path)) {
    const playlist = parsePlaylist(value)
    if (path !== `/api/playlists/${encodeURIComponent(playlist.playlist_id)}` || new Set(playlist.song_ids).size !== playlist.song_ids.length) throw new WireError('Invalid Playlist identity or members')
    return playlist
  }
  throw new WireError('Unsupported Playlist resource')
}

export function parseMPDInfo(value: unknown): import('../types/resources').MPDInfo {
  function object(v: unknown): Record<string, unknown> { if (!v || typeof v !== 'object' || Array.isArray(v)) throw new WireError('Invalid MPDInfo'); return v as Record<string, unknown> }
  function number(v: unknown): number | null { if (v === null) return null; if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < 0) throw new WireError('Invalid MPD statistic'); return v }
  function boolean(v: unknown): boolean | null { if (v === null || typeof v === 'boolean') return v; throw new WireError('Invalid MPD boolean') }
  const p = object(value), s = object(p.stats), u = object(p.database_update_status), errors = object(p.errors)
  if (p.version !== null && typeof p.version !== 'string' || p.version_source !== null && p.version_source !== 'verified_capability' || typeof p.observed_at !== 'string' || !Number.isFinite(Date.parse(p.observed_at))) throw new WireError('Invalid MPDInfo')
  const parsedErrors: Record<string, { code: string; message: string }> = {}
  for (const [source, raw] of Object.entries(errors)) { const e = object(raw); if (!['CAPABILITY_UNVERIFIED', 'PLAYER_UNAVAILABLE', 'PLAYER_COMMAND_ERROR'].includes(String(e.code)) || typeof e.message !== 'string') throw new WireError('Invalid MPD error'); parsedErrors[source] = { code: String(e.code), message: e.message } }
  return { version: p.version, version_source: p.version_source, observed_at: p.observed_at, connected: boolean(p.connected), errors: parsedErrors,
    stats: { artists: number(s.artists), albums: number(s.albums), songs: number(s.songs), uptime: number(s.uptime), db_playtime: number(s.db_playtime), db_update: number(s.db_update), playtime: number(s.playtime) },
    database_update_status: { updating: boolean(u.updating), job_id: number(u.job_id) } }
}
export function parseMPDConnection(value: unknown): import('../types/resources').MPDConnection {
  function address(raw: unknown): import('../types/resources').MPDAddress {
    if (!raw || typeof raw !== 'object' || !('host' in raw) || typeof raw.host !== 'string' || !raw.host || !('port' in raw) || typeof raw.port !== 'number' || !Number.isInteger(raw.port) || raw.port < 1 || raw.port > 65535) throw new WireError('Invalid MPD address')
    return { host: raw.host, port: raw.port }
  }
  if (!value || typeof value !== 'object' || !('active' in value) || !('saved' in value) || !('restart_required' in value) || typeof value.restart_required !== 'boolean') throw new WireError('Invalid MPD connection')
  const active = address(value.active), saved = value.saved === null ? null : address(value.saved)
  if (value.restart_required !== Boolean(saved && (saved.host !== active.host || saved.port !== active.port))) throw new WireError('Invalid MPD restart state')
  return { active, saved, restart_required: value.restart_required }
}
