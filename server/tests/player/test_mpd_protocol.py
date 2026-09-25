import pytest

from server.app.player.mpd_protocol import MPDAckError, MPDProtocolError, parse_response, quote_argument


def test_parse_response_decodes_escaped_values_and_keeps_repeated_keys():
    response = parse_response([
        r"Artist: AC\\DC",
        r"Comment: line1\nline2",
        "Tag: one",
        "Tag: two",
        "OK",
    ])
    assert response.as_dict()["Artist"] == r"AC\DC"
    assert response.as_dict()["Comment"] == "line1
line2"
    assert response.as_dict()["Tag"] == ["one", "two"]


def test_parse_response_rejects_malformed_lines():
    with pytest.raises(MPDProtocolError):
        parse_response(["not-a-pair", "OK"])


def test_parse_response_raises_typed_ack_error():
    with pytest.raises(MPDAckError) as exc:
        parse_response(["ACK [50@0] {play} No such song"])
    assert exc.value.error_code == 50
    assert exc.value.command_list_index == 0
    assert exc.value.command == "play"
    assert "No such song" in str(exc.value)


def test_parse_response_requires_completion_marker():
    with pytest.raises(MPDProtocolError):
        parse_response(["Volume: 80"])


def test_quote_argument_escapes_protocol_special_characters():
    assert quote_argument("simple") == "simple"
    assert quote_argument("two words") == '"two words"'
    assert quote_argument('a"b') == '"a\\\"b"'
