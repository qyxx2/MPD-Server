import inspect

from server.app.player.models import DatabaseUpdateStatus, MPDStats, PlayerQueueEntry
from server.app.player.ports import PlayerPort


def test_new_player_transport_models_preserve_explicit_fields_and_unknowns():
    entry = PlayerQueueEntry(mpd_song_id=12, position=3, song_uri="music/three.flac")
    stats = MPDStats(songs=403, albums=344, artists=264, db_playtime=103730)
    update = DatabaseUpdateStatus(updating=True, job_id=9)

    assert entry.model_dump() == {
        "mpd_song_id": 12,
        "position": 3,
        "song_uri": "music/three.flac",
    }
    assert stats.songs == 403
    assert stats.albums == 344
    assert stats.artists == 264
    assert stats.db_playtime == 103730
    assert stats.db_update is None
    assert stats.playtime is None
    assert stats.uptime is None
    assert update.updating is True
    assert update.job_id == 9


def test_player_port_exposes_task1r_transport_methods():
    required = (
        "queue_entries",
        "queue_clear",
        "queue_add",
        "queue_delete",
        "queue_move",
        "queue_play",
        "set_output_enabled",
        "stats",
        "database_update_status",
    )
    for name in required:
        assert inspect.iscoroutinefunction(getattr(PlayerPort, name))
