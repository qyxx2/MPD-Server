# Web/PWA Visual Design Spec

Status: **sole authoritative visual specification for Task 8 / Task 9 presentation**. It remains subordinate to the existing business/architecture Specs and Implementation Plan for all business and contract semantics.

Visual reference: [`../../ui/web-pwa-mobile-reference.png`](../../ui/web-pwa-mobile-reference.png).

This document defines stable presentation rules only. It does not replace or duplicate the existing Playback, Library/Playlist, Output, realtime, API, or architecture specifications.

## 1. Authority and non-goals

When sources disagree, use this order:

1. existing business/architecture Specs in `docs/superpowers/specs/`;
2. `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`;
3. this visual specification;
4. the concept image.

The concept image is a **visual and interaction-expression reference**, not a source of new business semantics. A control, tab, label, setting, entity type, or behavior shown in the image is not an implementation requirement unless an existing Spec/Plan already authorizes it.

In particular:

- the Account/login item shown in the concept is out of v0.1 scope;
- the concept's heart-shaped favorite affordance does not override the existing Favorites contract: song rows use the specified star affordance and its authoritative states;
- concept-only categories such as a Folder tab are not required unless the Library contract/API exposes them;
- sample music, artwork, text, status-bar chrome, device frame, clock, and exact mock data are not product requirements;
- this document does **not** freeze or redefine REST, WebSocket, store, transaction, reconnect, state-ordering, seek-confirmation, retry, or idempotency semantics. Task 8 Contract Audit remains responsible for those contracts.

## 2. Visual language

The Web/PWA uses a modern **dark glassmorphism** language consistent with the existing web shell and the concept image:

- a near-black/navy atmospheric base rather than pure black;
- translucent dark surfaces with restrained blur, subtle borders, and soft depth;
- cool blue/cyan accent for active navigation, focus, progress, and primary interactive emphasis;
- high-contrast near-white primary text with progressively quieter secondary/muted text;
- artwork may contribute a softly blurred ambient backdrop on the Player, but content contrast must remain stable and a neutral dark fallback must always exist;
- decorative glow is secondary to legibility. Glass, blur, shadow, or gradients must never obscure state or controls.

Do not reproduce the phone frame or iOS status bar from the reference. The application fills the browser/PWA viewport and respects safe-area insets where present.

## 3. Responsive composition

Design mobile-first. The narrow-screen hierarchy is the canonical hierarchy; larger screens may gain breathing room or a bounded multi-column arrangement without changing meaning or action priority.

- Prefer fluid sizing, `rem`, `clamp()`, intrinsic grids, flex/grid gaps, and content constraints over device-specific pixel coordinates.
- Avoid horizontal overflow for ordinary content. Long labels and metadata must truncate or wrap according to their importance.
- Keep primary actions reachable on touch screens and preserve clear focus treatment for keyboard input.
- On wider viewports, do not scale a phone mockup indefinitely. Bound reading width and artwork size, then use available space to improve grouping.
- Task 9 owns the responsive bottom navigation and Player-as-default application navigation defined by the Implementation Plan. Safe-area padding is part of that navigation shell.

Exact breakpoints, dimensions, and component metrics are implementation details unless accessibility or an existing Spec requires otherwise.

## 4. Player visual hierarchy — Task 8

The Player is Task 8's primary visual surface. Its information hierarchy is:

1. compact page/context header;
2. dominant media stage;
3. song identity;
4. technical metadata;
5. progress/time presentation;
6. primary playback controls;
7. output/connection presentation and secondary actions.

### 4.1 Media stage and artwork / lyrics

- Artwork is the dominant visual object and remains square when artwork is shown.
- Artwork and lyrics occupy the same primary media stage; switching between them should not create a second competing content hierarchy.
- Missing artwork uses a neutral, deliberate placeholder that preserves layout and contrast. Do not stretch low-information placeholders or fabricate cover art.
- LRC retains server-provided timestamps and may highlight the active line. Plain text lyrics remain plain text and must not imply synchronized timing.
- Lyrics should prioritize the current line while retaining nearby context. Text remains selectable/readable where practical.
- The visual spec does not define how playback time is predicted, confirmed, or reconciled; it only defines presentation once authoritative state is available.

### 4.2 Song identity and metadata

- Title is the strongest text below the media stage; artist is secondary; album/context is tertiary when present.
- Codec, bit depth, sample rate, and similar source-file metadata use compact secondary treatment such as chips or a concise inline group.
- Unknown metadata is omitted or represented as unknown only when the authoritative state explicitly requires that distinction. Never invent values or turn unknown into zero.
- File metadata must not be visually labelled as DAC/output format. Source-file specification and output state are separate concepts.
- Long titles/artists may wrap in the Player within a bounded number of lines; dense rows elsewhere prefer ellipsis. No automatic marquee is required.

### 4.3 Progress and controls

- Progress is visually prominent enough for touch interaction but subordinate to title/artwork.
- Elapsed/duration/remaining presentation must degrade cleanly when values are unavailable; unavailable data must not appear as a fabricated `0:00` fact.
- The exact seek request/confirmation lifecycle is outside this document and must be resolved by Task 8's contract work.
- The primary play/pause affordance receives the strongest control emphasis. Other controls use a consistent icon-button language and clear enabled/disabled/active states.
- The concept image does not define the required control set. Existing Playback Specs determine which actions exist and their semantics.

### 4.4 Output and status

- Output is a compact, lower-hierarchy status/control region: recognizable, readable, and not visually confused with source-file metadata.
- Unavailable, stale, unknown, disconnected, or error states use text/icon treatment in addition to color.
- This spec does not define output switching semantics or reconnection behavior; it only requires their existing authoritative states to be visually distinguishable.

## 5. Task 9 page mapping

The concept board contains Library, Queue, Search, Playlist, and Settings views. Task 9 may use their composition as the visual reference while keeping existing business rules authoritative.

- **Queue:** use the compact artwork/list-row language from the concept, while preserving the required Now Playing / Played / Up Next structure. Played is visually collapsible according to the Task 9 Plan. Reorder handles appear only where reorder is actually allowed.
- **Library:** use artwork-forward responsive grids/lists, restrained segmented filters, and clear collection hierarchy. The actual collection types/tabs come from existing Library contracts, not from every tab drawn in the concept.
- **Search:** place the query field prominently, with compact filters and predictable result rows. Empty query, no results, and unavailable/index-updating states must be visually different.
- **Playlists/Favorites:** use consistent list/card surfaces and overflow actions. Favorite state remains the business-Spec star control, independent from the SongRow playback action.
- **Settings:** use simple grouped glass rows. Only settings/features authorized by the Plan/Specs are shown. The concept's Account/login row is excluded from v0.1. `Settings → About` follows the existing MPD information contract and must preserve unknown/disconnected presentation.
- **Bottom navigation:** Task 9 provides the responsive app navigation with Player as the default view. The concept's exact labels/order are reference material, not a new routing contract.

## 6. Design-token principles

Implementation should expose semantic CSS variables/tokens rather than scattering one-off values.

### Color roles

At minimum distinguish: page background, ambient background, glass surface, raised surface, overlay surface, subtle border, primary/secondary/muted text, accent, focus, success, warning, error, and disabled states. Semantic status colors must remain understandable without color alone.

### Surface hierarchy

Use a small hierarchy rather than many visually unrelated cards:

- base/background;
- glass/content surface;
- raised/selected surface;
- overlay/menu/sheet surface.

Blur and transparency decrease gracefully when `backdrop-filter` is unavailable; the fallback remains an opaque/semi-opaque dark surface with sufficient contrast.

### Typography

Use the existing system-sans/Inter-style stack without requiring a network font. Establish semantic roles for page title, song title, section title, body, secondary metadata, compact label, and numeric/time text. Favor weight/size/contrast hierarchy over many font families.

### Spacing, radius, and depth

Use a small spacing rhythm and reusable radius tiers: tighter for chips/inputs, medium for rows/cards, larger for dominant artwork containers/sheets, pill radius only for pill-shaped controls. Shadows remain soft and low-contrast; border plus surface contrast should carry most grouping.

No token in this document is a pixel-perfect screenshot measurement.

## 7. Motion and reduced motion

Motion communicates continuity, not decoration.

Suitable motion includes short opacity/transform transitions for page/overlay changes, artwork↔lyrics switching, selection indicators, control state changes, and reorder feedback. Avoid continuous parallax, decorative looping motion, or large layout shifts.

With `prefers-reduced-motion: reduce`:

- remove nonessential transitions/animations and shimmer;
- avoid animated auto-scrolling; synchronized lyrics may update/highlight the active line and reposition without smooth travel;
- preserve all state changes and interaction feedback through static visual changes;
- do not make reduced motion a separate visual theme.

## 8. Visual states

Every major Task 8/9 surface must have deliberate visual treatment for these states when they are exposed by authoritative data:

- **Loading:** preserve the expected layout with restrained skeleton/static placeholders; do not flash fabricated metadata.
- **Empty:** concise explanation plus an action only when an authorized action exists. Empty Queue/Library/Search/Playlist are distinct states.
- **Missing artwork:** stable neutral artwork placeholder with the same layout footprint.
- **Missing/unavailable media:** retain recognizable song identity where the business model does, visibly mark availability, and avoid presenting it as normally playable.
- **No lyrics / lyrics read failure:** visually distinct when the underlying API distinguishes them; do not manufacture lyrics.
- **Long text:** Player may wrap important identity text; dense rows truncate with ellipsis while preserving access to the full value through normal accessible UI techniques.
- **Disconnected / stale / unknown:** use a persistent but non-obscuring status treatment and visibly distinguish stale/unknown data. Whether cached data is retained, controls are disabled, or reconnect occurs is governed by existing/future Task 8 contracts, not this visual document.
- **Operation error:** show local, actionable feedback near the affected control/surface when possible without replacing authoritative state with optimistic fiction.

## 9. Accessibility and interaction quality

- Maintain readable contrast over translucent/ambient backgrounds.
- Interactive controls require visible focus states and sufficiently large touch targets.
- Icon-only controls require accessible names; selected/disabled/error state must not rely on color alone.
- Glass/blur effects must have a contrast-safe fallback.
- Content must remain usable with text scaling and narrow mobile widths.

## 10. Task boundary summary

**Task 8** owns the typed Web state layer and the Player visual surface: shared visual foundations/styles, Player layout, artwork/lyrics stage, player metadata, progress presentation, playback controls, output/status presentation, responsive Player composition, and reduced-motion behavior.

**Task 9** owns the remaining application views and application navigation: Queue, Library, Playlist/Favorites, Search, Settings/About, shared list/grid patterns, FavoriteStar presentation, and responsive bottom navigation.

This split is visual ownership only. It does not move, invent, or freeze any server/client contract and does not change the dependency order in the Implementation Plan.

## 11. Reference-use rule

During Task 8/9 implementation, treat `docs/ui/web-pwa-mobile-reference.png` as the baseline for **mood, density, surface treatment, hierarchy, and mobile composition**. Do not trace it pixel-for-pixel, and do not use it to override authoritative semantics.

Any future intentional visual-direction change should update this specification and/or its reference explicitly rather than letting individual components drift into a second undocumented design system.