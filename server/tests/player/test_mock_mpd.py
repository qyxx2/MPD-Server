import asyncio

from server.app.player.mock_mpd import MockMPD


def test_mock_mpd_controls_status_and_events():
    async def run():
        player = MockMPD(
            ["a.flac", "b.flac"],
            durations={"a.flac": 10, "b.flac": 20},
        )
        events = []
        player.subscribe(events.append)

        await player.play("a.flac")
        assert (await player.status()).state.value == "playing"
        await player.seek(3.5)
        assert (await player.status()).elapsed_seconds == 3.5

        await player.pause()
        assert (await player.status()).state.value == "paused"

        await player.play()
        await player.next()
        assert (await player.status()).song_uri == "b.flac"

        await player.previous()
        assert (await player.status()).song_uri == "a.flac"

        await player.set_repeat(True)
        await player.seek(9)
        await player.next()
        assert (await player.status()).song_uri == "b.flac"

        await player.set_random(True)
        await player.play("a.flac")
        await player.next()
        assert (await player.status()).song_uri in {"a.flac", "b.flac"}

        await player.set_volume(42)
        assert (await player.status()).volume == 42

        await player.update_database()
        await player.stop()

        assert [event.kind for event in events] == [
            "play", "seek", "pause", "play", "next", "previous",
            "set_repeat", "seek", "next", "set_random", "play", "next",
            "set_volume", "update_database", "stop",
        ]

    asyncio.run(run())


def test_mock_random_mode_is_deterministic_with_seed():
    async def run():
        first = MockMPD(["a", "b", "c"], random_seed=7)
        second = MockMPD(["a", "b", "c"], random_seed=7)

        await first.play("a")
        await second.play("a")
        await first.set_random(True)
        await second.set_random(True)
        await first.next()
        await second.next()

        assert (await first.status()).song_uri == (await second.status()).song_uri

    asyncio.run(run())
