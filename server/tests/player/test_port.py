import inspect

from server.app.player.ports import PlayerPort


def test_player_port_exposes_required_async_interface():
    required = (
        "status", "play", "pause", "stop", "next", "previous",
        "seek", "set_repeat", "set_random", "set_volume",
        "update_database", "outputs",
    )
    for name in required:
        assert inspect.iscoroutinefunction(getattr(PlayerPort, name))
