import asyncio

from server.app.services.library_change_detector import LibraryChangeDetector


def test_new_stable_file_is_detected_without_rescanning_unchanged_media(tmp_path):
    async def run():
        now = [0.0]
        batches = []

        async def accept(paths, trigger):
            batches.append((paths, trigger))
            return "activity"

        detector = LibraryChangeDetector(tmp_path, accept, clock=lambda: now[0])
        file = tmp_path / "中文.flac"
        file.write_bytes(b"half")
        await detector.check_once()
        assert batches == []
        now[0] = 2
        file.write_bytes(b"complete")
        await detector.check_once()
        assert batches == []
        now[0] = 4
        await detector.check_once()
        assert batches == [((file,), "automatic")]
        now[0] = 6
        await detector.check_once()
        assert len(batches) == 1
        file.unlink()
        now[0] = 8
        await detector.check_once()
        now[0] = 10
        await detector.check_once()
        assert batches[-1] == (None, "automatic")  # deletion needs reconciliation
        # Root replacement/unmount cannot be interpreted as mass deletion.
        tmp_path.rename(tmp_path.with_name(tmp_path.name + "-unmounted"))
        tmp_path.mkdir()
        now[0] = 12
        await detector.check_once()
        assert len(batches) == 2
        await detector.close()

    asyncio.run(run())
