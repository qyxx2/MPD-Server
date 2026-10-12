import type { Song } from './api'
export interface SongList { items: Song[]; count: number }

export interface Playlist { playlist_id: string; name: string; created_at: string; updated_at: string; is_system: boolean; song_ids: string[] }
export interface PlaylistList { items: Playlist[]; count: number }

export type CategoryKind = 'albums' | 'artists' | 'genres' | 'years' | 'tags'
export interface Category { id: string; name: string; song_count: number; album_artists: string[]; year: number | null; artwork: import('./api').Artwork | null }
export interface CategoryList { kind: CategoryKind; items: Category[]; count: number }
export type LibraryResource = Song | SongList | CategoryList | Collection | SearchResults
export type LibrarySource = { source_type: 'LIBRARY' | 'FAVORITES' } | { source_type: 'ALBUM' | 'ARTIST' | 'GENRE' | 'YEAR' | 'TAG'; source_id: string }
export interface Collection { source_type: string; source_id: string | null; song_ids: string[]; unavailable_song_ids: string[]; random_seed: number | null }
export interface SearchGroup { kind: CategoryKind; source_id: string; name: string; song_ids: string[] }
export interface SearchResults { groups: SearchGroup[]; song_ids: string[] }
export interface FavoriteMembers { song_ids: string[] }
export type PlaylistResource = FavoriteMembers | Playlist | PlaylistList | SongList
export interface MPDInfo {
  version: string | null; version_source: 'verified_capability' | null
  stats: { artists: number | null; albums: number | null; songs: number | null; uptime: number | null; db_playtime: number | null; db_update: number | null; playtime: number | null }
  database_update_status: { updating: boolean | null; job_id: number | null }
  connected: boolean | null; errors: Record<string, { code: string; message: string }>; observed_at: string
}
export interface MPDAddress { host: string; port: number }
export interface MPDConnection { active: MPDAddress; saved: MPDAddress | null; restart_required: boolean }
