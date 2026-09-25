import pytest
from pydantic import ValidationError

from server.app.player.models import OutputInfo, PlayerState, PlayerStatus


def test_player_state_values_are_stable():
    assert PlayerState.PLAYING.value == "playing"
    assert PlayerState.PAUSED.value == "paused"
    assert PlayerState.STOPPED.value == "stopped"


def test_player_status_keeps_unknown_optional_values_unknown():
    status = PlayerStatus(state=PlayerState.PLAYING)
    assert status.song_uri is None
    assert status.elapsed_seconds is None
    assert status.duration_seconds is None
    assert status.volume is None


def test_player_status_validates_volume_range():
    with pytest.raises(ValidationError):
        PlayerStatus(state=PlayerState.STOPPED, volume=101)


def test_output_info_contains_runtime_output_fields():
    output = OutputInfo(
        id=3,
        name="USB DAC",
        plugin="alsa",
        enabled=True,
        attributes={"device": "hw:1,0"},
    )
    assert output.id == 3
    assert output.name == "USB DAC"
    assert output.plugin == "alsa"
    assert output.enabled is True
    assert output.attributes["device"] == "hw:1,0"
