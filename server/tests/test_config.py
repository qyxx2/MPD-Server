"""MIN-CONFIG-001: startup-only configuration, with no deployment secrets in DTOs."""
import importlib
import json

import pytest


def test_defaults_precedence_and_secret_redaction(tmp_path):
    module = importlib.import_module('server.app.config')
    load = module.load_config
    path = tmp_path / 'config.json'
    env = {'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path)}
    config = load(env)
    assert config.scan_interval_seconds == 12 * 60 * 60
    assert config.debounce_seconds == 0.5
    assert config.app_env == 'development' and config.mpd_mode == 'mock'
    path.write_text(json.dumps({'mpd_host': 'json.example', 'mpd_port': 6601,
                                'scan_interval_seconds': 100, 'debounce_seconds': 0.2}))
    config = load({**env, 'MPD_HOST': '2001:db8::1', 'MPD_PORT': '16600',
                   'MPD_PASSWORD': 'private-secret', 'APP_ENV': 'production'})
    assert config.mpd_host == '2001:db8::1' and config.mpd_port == 16600
    assert config.mpd_mode == 'real'
    assert config.scan_interval_seconds == 100 and config.debounce_seconds == 0.2
    assert config.mpd_password == 'private-secret'
    for value in (repr(config), str(config.model_dump()), config.model_dump_json()):
        assert 'private-secret' not in value and 'mpd_password' not in value
    with pytest.raises(ValueError):
        config.mpd_mode = 'mock'
    explicit = tmp_path / 'explicit.json'
    explicit.write_text('{"mpd_host":"explicit.example"}')
    assert load(env, explicit).mpd_host == 'explicit.example'
    config_dir = tmp_path / 'config-dir'
    config_dir.mkdir()
    (config_dir / 'config.json').write_text('{"mpd_port":6602}')
    assert load({**env, 'CONFIG_DIR': str(config_dir)}).mpd_port == 6602


@pytest.mark.parametrize('data', [
    'broken', '[]', '{"unknown":1}', '{"mpd_password":"secret"}',
    '{"scan_interval_seconds":0}', '{"debounce_seconds":-1}',
    '{"mpd_port":true}', '{"mpd_port":0}', '{"mpd_host":"http://bad"}',
    '{"app_env":"staging"}', '{"mpd_mode":"fallback"}',
    '{"app_env":"production","mpd_mode":"mock"}', '{"workers":2}',
    '{"http_port":65536}', '{"mpd_uri_prefix":"../escape"}',
    '{"scan_interval_seconds":"nan"}',
])
def test_invalid_config_fails_without_exposing_input(tmp_path, data):
    load = importlib.import_module('server.app.config').load_config
    path = tmp_path / 'config.json'
    path.write_text(data)
    with pytest.raises(ValueError) as error:
        load({'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path)})
    assert 'secret' not in str(error.value)


def test_missing_music_root_is_deferred_and_invalid_environment_fails(tmp_path):
    load = importlib.import_module('server.app.config').load_config
    env = {'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path / 'missing')}
    assert load(env).music_root == tmp_path / 'missing'
    for extra in ({'MPD_PORT': 'invalid'},
                  {'SCAN_INTERVAL_SECONDS': 'NaN'}, {'HTTP_PORT': 'invalid'}):
        with pytest.raises(ValueError):
            load({'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path), **extra})


def test_hardware_volume_flag_defaults_disabled_and_environment_overrides_json(tmp_path):
    load = importlib.import_module('server.app.config').load_config
    config_path = tmp_path / 'config.json'
    base_env = {'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path)}

    assert load(base_env).mpd_hardware_volume_enabled is False

    config_path.write_text(json.dumps({'mpd_hardware_volume_enabled': True}))
    assert load(base_env, config_path).mpd_hardware_volume_enabled is True
    assert load({**base_env, 'MPD_HARDWARE_VOLUME_ENABLED': 'false'}, config_path).mpd_hardware_volume_enabled is False
    assert load({**base_env, 'MPD_HARDWARE_VOLUME_ENABLED': 'TRUE'}, config_path).mpd_hardware_volume_enabled is True


@pytest.mark.parametrize('value', ['enabled', '2', '', 'yes'])
def test_hardware_volume_environment_flag_rejects_non_boolean_values(tmp_path, value):
    load = importlib.import_module('server.app.config').load_config
    env = {
        'DATABASE_PATH': str(tmp_path / 'music.db'),
        'MUSIC_ROOT': str(tmp_path),
        'MPD_HARDWARE_VOLUME_ENABLED': value,
    }
    with pytest.raises(ValueError, match='Invalid application configuration'):
        load(env)


@pytest.mark.parametrize('value', [1, 'true', None])
def test_hardware_volume_json_flag_requires_a_json_boolean(tmp_path, value):
    load = importlib.import_module('server.app.config').load_config
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'mpd_hardware_volume_enabled': value}))
    env = {'DATABASE_PATH': str(tmp_path / 'music.db'), 'MUSIC_ROOT': str(tmp_path)}
    with pytest.raises(ValueError, match='Invalid application configuration'):
        load(env, path)
