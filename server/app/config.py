"""Immutable startup configuration; only the composition root consumes it."""
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.app.services.mpd_connection_service import MPDConnectionAddress


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', hide_input_in_errors=True)
    app_env: Literal['development', 'production'] = 'development'
    mpd_mode: Literal['mock', 'real'] = 'mock'
    mpd_host: str = '127.0.0.1'
    mpd_port: int = Field(default=6600, ge=1, le=65535)
    mpd_password: str | None = Field(default=None, exclude=True, repr=False)
    database_path: Path = Path('music-server.db')
    config_dir: Path | None = None
    mpd_connection_path: Path
    music_root: Path = Path('.')
    mpd_uri_prefix: str = ''
    mpd_capabilities_path: Path | None = None
    scan_interval_seconds: float = Field(default=43200, gt=0, allow_inf_nan=False)
    debounce_seconds: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    http_host: str = '0.0.0.0'
    http_port: int = Field(default=8000, ge=1, le=65535)
    workers: Literal[1] = 1
    output_name: str | None = None
    output_plugin: Literal['alsa'] = 'alsa'

    @field_validator('music_root', mode='before')
    @classmethod
    def valid_root_path(cls, value):
        if isinstance(value, (str, Path)) and (
            not str(value).strip() or any(char in str(value) for char in ('\0', '\n', '\r'))
        ):
            raise ValueError('Invalid music root path')
        return value

    @field_validator('mpd_uri_prefix')
    @classmethod
    def relative_prefix(cls, value: str) -> str:
        if value and (PurePosixPath(value).is_absolute() or
                      any(part in {'.', '..', ''} for part in value.split('/')) or
                      any(char in value for char in ('\\', '\n', '\r', '\0'))):
            raise ValueError('MPD prefix must be a relative directory')
        return value

    @model_validator(mode='after')
    def validate_runtime(self):
        MPDConnectionAddress(host=self.mpd_host, port=self.mpd_port)
        MPDConnectionAddress(host=self.http_host, port=self.http_port)
        if self.app_env == 'production' and self.mpd_mode != 'real':
            raise ValueError('Production requires real MPD')
        if self.output_name is not None and not self.output_name.strip():
            raise ValueError('Output name cannot be empty')
        return self


# Names are deliberately explicit: unrelated process environment is not config.
_ENV_FIELDS = {
    'APP_ENV': 'app_env', 'MPD_MODE': 'mpd_mode', 'MPD_HOST': 'mpd_host',
    'MPD_PORT': 'mpd_port', 'DATABASE_PATH': 'database_path', 'CONFIG_DIR': 'config_dir',
    'MPD_CONNECTION_PATH': 'mpd_connection_path', 'MUSIC_ROOT': 'music_root',
    'MPD_URI_PREFIX': 'mpd_uri_prefix', 'MPD_CAPABILITIES_PATH': 'mpd_capabilities_path',
    'SCAN_INTERVAL_SECONDS': 'scan_interval_seconds', 'DEBOUNCE_SECONDS': 'debounce_seconds',
    'HTTP_HOST': 'http_host', 'HTTP_PORT': 'http_port', 'WORKERS': 'workers',
    'OUTPUT_NAME': 'output_name', 'OUTPUT_PLUGIN': 'output_plugin',
}
_INTEGER_FIELDS = {'mpd_port', 'http_port', 'workers'}


def load_config(env: Mapping[str, str], config_path: Path | None = None) -> AppConfig:
    """Resolve JSON/environment and the winning saved endpoint once per startup.

    The default JSON location is bootstrapped from CONFIG_DIR or DATABASE_PATH
    in the environment. Secrets are accepted exclusively from MPD_PASSWORD.
    """
    database = Path(env.get('DATABASE_PATH', 'music-server.db'))
    directory = Path(env['CONFIG_DIR']) if 'CONFIG_DIR' in env else database.parent
    path = config_path if config_path is not None else directory / 'config.json'
    try:
        try:
            data = json.loads(path.read_text())
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict) or 'mpd_password' in data:
            raise ValueError('Invalid JSON configuration')
        if set(data) - (set(AppConfig.model_fields) - {'mpd_password'}):
            raise ValueError('Unknown configuration field')
        # JSON numbers retain their type; bool/string are not valid integer config.
        if any(name in data and type(data[name]) is not int for name in _INTEGER_FIELDS):
            raise ValueError('Invalid integer configuration')
        values = {**data, **{field: env[name] for name, field in _ENV_FIELDS.items() if name in env}}
        values.setdefault('mpd_mode', 'real' if values.get('app_env') == 'production' else 'mock')
        database = Path(values.get('database_path', 'music-server.db'))
        values.setdefault('mpd_connection_path', database.parent / 'mpd-connection.json')
        saved_path = Path(values['mpd_connection_path'])
        try:
            saved = MPDConnectionAddress.model_validate_json(saved_path.read_text())
        except FileNotFoundError:
            saved = None
        except (ValueError, OSError):
            raise ValueError('Invalid saved MPD connection') from None
        if saved is not None:
            values.update(mpd_host=saved.host, mpd_port=saved.port)
        for name in _INTEGER_FIELDS:
            if name in values and isinstance(values[name], str):
                values[name] = int(values[name])
        values['mpd_password'] = env.get('MPD_PASSWORD') or None
        return AppConfig.model_validate(values)
    except (ValueError, OSError, TypeError) as exc:
        # Never forward Pydantic/JSON input values, which can contain secrets.
        if str(exc) == 'Invalid saved MPD connection':
            raise ValueError('Invalid saved MPD connection') from None
        raise ValueError('Invalid application configuration') from None
