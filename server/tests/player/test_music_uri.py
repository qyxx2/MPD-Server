"""MIN-URI: exact paths, no filename guessing or escape from the music tree."""
import importlib

import pytest


def mapper_type():
    return importlib.import_module('server.app.player.music_uri').MusicUriMapper


def test_relative_uri_round_trip_and_escape_rejection(tmp_path):
    root = tmp_path / 'music'
    root.mkdir()
    mapper = mapper_type()(root, 'archive/music')
    for relative in ('A/中文 空格.flac', 'B/中文 空格.flac', 'A/Case.FLAC'):
        local = str(root / relative)
        assert mapper.to_mpd(local) == 'archive/music/' + relative
        assert mapper.to_local('archive/music/' + relative) == local
    plain = mapper_type()(root)
    assert plain.to_mpd(str(root / 'A/song.flac')) == 'A/song.flac'
    assert plain.to_local('A/song.flac') == str(root / 'A/song.flac')
    for uri in (str(tmp_path / 'outside.flac'), str(root / '../outside.flac'),
                'relative.flac', str(root), str(root / 'A/../song.flac')):
        with pytest.raises(ValueError):
            mapper.to_mpd(uri)
    for uri in ('/A/song.flac', '../song.flac', 'archive/music/../song.flac',
                'archive/music', 'other/song.flac', 'archive/music//song.flac',
                'archive/music/./song.flac', 'archive/music/a\n.flac',
                'archive/music/a\0.flac', 'archive/music/a\\b.flac'):
        with pytest.raises(ValueError):
            mapper.to_local(uri)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'escape').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        mapper.to_mpd(str(root / 'escape/song.flac'))
    with pytest.raises(ValueError):
        mapper.to_local('archive/music/escape/song.flac')
    # In-tree symlinks preserve the indexed spelling, not the resolved target.
    (root / 'A').mkdir()
    (root / 'alias').symlink_to(root / 'A', target_is_directory=True)
    assert mapper.to_local('archive/music/alias/song.flac') == str(root / 'alias/song.flac')
    assert mapper.to_mpd(str(root / 'alias/song.flac')) == 'archive/music/alias/song.flac'


@pytest.mark.parametrize('prefix', ['/music', '../music', 'a//b', 'a/./b', 'a\\b', 'a\n'])
def test_invalid_prefix_rejected(tmp_path, prefix):
    with pytest.raises(ValueError):
        mapper_type()(tmp_path, prefix)
