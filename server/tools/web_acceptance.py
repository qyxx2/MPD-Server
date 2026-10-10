"""Local phone acceptance: real FastAPI/Services with explicit MockMPD injection.

No public fixture API. The agent changes scene.txt locally; each server launch
uses a fresh owned SQLite file. No real MPD/NAS or music directory is accessed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import time
import wave
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI

from server.app.models.library import Song
from server.app.player.capabilities import MPDCapabilities
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo, PlayerState
from server.app.repositories.library_repository import LibraryRepository

SCENES = ('normal', 'long', 'unknown', 'unbound', 'stale')


class AcceptancePlayer(MockMPD):
    unknown_duration = False

    def __init__(self, songs=(), *, monotonic=None, outputs=None):
        super().__init__(songs, outputs=outputs)
        self._acceptance_clock = monotonic
        self._acceptance_last = monotonic() if monotonic else 0

    def _advance_acceptance(self):
        if self._acceptance_clock is None:
            return
        now = self._acceptance_clock()
        delta = max(0, now - self._acceptance_last)
        self._acceptance_last = now
        if self._connected and self._state == PlayerState.PLAYING and self._current_index is not None:
            duration = self._durations[self._songs[self._current_index]]
            # Display fixture only: reaching duration never fabricates natural finish.
            self._elapsed = min(duration, self._elapsed + delta)

    def _status(self):
        self._advance_acceptance()
        return super()._status()

    async def play(self, song_uri=None):
        self._advance_acceptance()
        await super().play(song_uri)

    async def pause(self):
        self._advance_acceptance()
        await super().pause()

    async def seek(self, seconds):
        self._advance_acceptance()
        await super().seek(seconds)

    async def stop(self):
        self._advance_acceptance()
        await super().stop()

    async def queue_play(self, mpd_song_id):
        self._advance_acceptance()
        await super().queue_play(mpd_song_id)

    async def status(self):
        value = await super().status()
        return value.model_copy(update={'duration_seconds': None}) if self.unknown_duration else value

    async def read_execution_sample(self):
        sample = await super().read_execution_sample()
        if self.unknown_duration:
            return sample.model_copy(update={
                'status': sample.status.model_copy(update={'duration_seconds': None}),
            })
        return sample


def configure_acceptance(app: FastAPI, runtime: Path, *, advance_clock: bool = False, w5: bool = False) -> None:
    runtime.mkdir(parents=True, exist_ok=True)
    media = runtime / 'media'
    media.mkdir(exist_ok=True)
    media_names = ('normal', 'long', 'unknown', 'external') + (('lyrics-error',) if w5 else ())
    for name in media_names:
        path = media / f'{name}.wav'
        if not path.exists():
            with wave.open(str(path), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(44100)
                output.writeframes(b'\x00\x00' * 44100)
    scenes = SCENES + ('lyrics-error',) if w5 else SCENES
    outputs = [OutputInfo(id=7, name='Mock NAS DAC · simulated ALSA', plugin='alsa', enabled=True)] if w5 else None
    player = AcceptancePlayer([str((media / f'{name}.wav').resolve()) for name in media_names], monotonic=time.monotonic if advance_clock else None, outputs=outputs)
    app.state.player = player  # main.lifespan consumes this, not an unused MPD_MODE flag.
    original = app.router.lifespan_context
    scene_file = runtime / 'scene.txt'

    @asynccontextmanager
    async def fixture_capabilities(application):
        previous = getattr(application.state, 'mpd_capabilities', None)
        if w5:
            # Verified only for our deterministic Mock. No live capability probe.
            application.state.mpd_capabilities = replace(
                MPDCapabilities.from_commands({'outputs', 'enableoutput', 'disableoutput', 'status', 'currentsong', 'playlistinfo'}),
                verified_operations=frozenset({'set_output_enabled', 'queue_entries'}),
            )
        try:
            yield
        finally:
            if w5:
                if previous is None:
                    del application.state.mpd_capabilities
                else:
                    application.state.mpd_capabilities = previous

    @asynccontextmanager
    async def lifespan(application):
        async with fixture_capabilities(application), original(application):
            library = LibraryRepository(application.state.queue_manager.queue_repository.path)
            for name, title, artists in (
                ('normal', '夜航 · 本地验收曲', ('测试艺术家',)),
                ('long', '这是用于手机阅读的很长中文标题 · A Very Long English Song Title / Long Journey Across the Night Sky', ('很长的艺术家名称 / Example Artist With a Long Name',)),
                ('unknown', '未知元数据 · 本地验收曲', ()),
                *((('lyrics-error', '歌词读取失败 · 本地验收曲', ('测试艺术家',)),) if w5 else ()),
            ):
                lyrics = '[00:01]本地夹具歌词' if name == 'normal' else None
                lyrics_format = 'lrc' if name == 'normal' else None
                lyrics_status = 'available' if name == 'normal' else 'missing'
                if w5 and name == 'normal':
                    lyrics = '[offset:500]\n' + '\n'.join(
                        f'[{i // 60:02}:{i % 60:02}]第 {i // 5 + 1} 行 · 夜航中的中文歌词 / A line across the night sky'
                        for i in range(0, 301, 5)
                    ) + '\n[00:35]同一时间 · 第二句'
                elif w5 and name == 'long':
                    lyrics = '\n'.join(f'普通歌词第 {i} 行 · 可自由滚动和选择文字' for i in range(1, 21))
                    lyrics_format, lyrics_status = 'text', 'available'
                elif name == 'lyrics-error':
                    lyrics = '读取失败后保留的普通歌词文本\n这段 fallback 不代表读取成功'
                    lyrics_format, lyrics_status = 'text', 'read_error'
                await library.upsert_song(Song(
                    song_id=f'acceptance-{name}', title=title, artists=artists,
                    file_uri=str((media / f'{name}.wav').resolve()),
                    codec=None if name == 'unknown' else 'PCM',
                    bit_depth=None if name == 'unknown' else 16,
                    sample_rate_hz=None if name == 'unknown' else 44100,
                    channel_count=None if name == 'unknown' else 1,
                    lyrics=lyrics, lyrics_format=lyrics_format,
                    lyrics_source='embedded' if w5 and lyrics else None,
                    lyrics_status=lyrics_status,
                ))

            async def scene(name):
                if name not in scenes:
                    raise ValueError(f'Unknown scene: {name}')
                player.reconnect()
                player.unknown_duration = name == 'unknown'
                playback = application.state.playback_service
                await playback.start_track(f"acceptance-{name if name in ('long', 'unknown', 'lyrics-error') else 'normal'}")
                if w5 and name == 'normal':
                    for song in ('long', 'lyrics-error', 'unknown'):
                        await playback.add_to_queue(f'acceptance-{song}')
                    await playback.pause()
                    await playback.seek(37)
                elif advance_clock and name in ('normal', 'long'):
                    await playback.add_to_queue('acceptance-long' if name == 'normal' else 'acceptance-normal')
                if name == 'unbound':
                    await player.queue_clear()
                    entry = await player.queue_add(str((media / 'external.wav').resolve()))
                    await player.queue_play(entry)
                    player.reconnect()
                    await playback.observe()  # First sample retires the previous binding; next read is UNBOUND.
                elif name == 'stale':
                    await playback.observe()
                    player.disconnect()
                await playback.observe()
                if w5:
                    await application.state.output_manager.get_state()
                print(f'fixture scene={name}; simulated clock={advance_clock}; Mock only, no real MPD/DAC', flush=True)

            application.state.acceptance_scene = scene
            initial = scene_file.read_text().strip() if scene_file.exists() else 'normal'
            await scene(initial)

            async def watch_scene():
                current = initial
                while True:
                    await asyncio.sleep(.5)
                    desired = scene_file.read_text().strip() if scene_file.exists() else current
                    if desired != current:
                        if desired not in scenes:
                            print(f'Ignored invalid fixture scene: {desired}', flush=True)
                        else:
                            await scene(desired)
                        current = desired

            task = asyncio.create_task(watch_scene(), name='local-acceptance-scene')
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    app.router.lifespan_context = lifespan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--advance-clock', action='store_true', help='W4 simulated elapsed; no natural finish')
    parser.add_argument('--w5', action='store_true', help='W5 lyrics and simulated NAS DAC output')
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ['DATABASE_PATH'] = str(runtime / f'phone-{uuid4().hex}.db')
    import uvicorn

    from server.app.main import app

    configure_acceptance(app, runtime, advance_clock=args.advance_clock, w5=args.w5)
    print(f'Owned fixture DB: {os.environ["DATABASE_PATH"]}', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
