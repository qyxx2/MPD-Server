"""Static deployment contracts; these tests never execute Docker/Compose."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _section(text, name, indent):
    """Read one block in our checked-in, block-style Compose documents."""
    match = re.search(rf'^{" " * indent}{re.escape(name)}:\s*\n', text, re.MULTILINE)
    assert match, f'Missing Compose section: {name}'
    tail = text[match.end():]
    end = re.search(rf'^\S|^ {{1,{indent}}}\S', tail, re.MULTILINE)
    return tail[:end.start()] if end else tail


def test_prod_and_dev_persistence_modes_and_single_worker():
    prod = (ROOT / 'deploy/docker-compose.yml').read_text()
    dev = (ROOT / 'deploy/docker-compose.dev.yml').read_text()
    env = _section(_section(prod, 'server', 2), 'environment', 4)
    for entry in (
        'APP_ENV: production', 'MPD_MODE: real', 'MUSIC_ROOT: /music',
        'DATABASE_PATH: /data/music-server.db', 'CONFIG_DIR: /config',
        'MPD_CONNECTION_PATH: /data/mpd-connection.json', 'WORKERS: "1"',
        'MPD_URI_PREFIX: ${MPD_URI_PREFIX:-}',
        'MPD_CAPABILITIES_PATH:',
        'SCAN_INTERVAL_SECONDS: ${SCAN_INTERVAL_SECONDS:-43200}',
        'DEBOUNCE_SECONDS: ${DEBOUNCE_SECONDS:-0.5}',
        'OUTPUT_NAME:', 'OUTPUT_PLUGIN: ${OUTPUT_PLUGIN:-alsa}',
    ):
        assert entry in env, entry
    for optional in ('MPD_CAPABILITIES_PATH', 'OUTPUT_NAME'):
        assert re.search(rf'^      {optional}: *$', env, re.MULTILINE)
    for target in ('/data', '/config', '/backups'):
        assert re.search(rf'^\s+- \$\{{MPD_SERVER_\w+_DIR[^\n]*\}}:{target}$', prod, re.MULTILINE)
    assert '${MUSIC_DIR:-/volume1/music}:/music:ro' in prod
    assert 'http://127.0.0.1:8000/api/health' in prod
    assert 'driver: json-file' in prod and 'max-size: "10m"' in prod and 'max-file: "3"' in prod
    dev_server = _section(dev, 'server', 2)
    for entry in ('APP_ENV: development', 'MPD_MODE: mock',
                  'CONFIG_DIR: /config', 'MUSIC_ROOT: /music',
                  'MPD_CONNECTION_PATH: /config/mpd-connection.json',
                  'mpd_server_dev_config:/config', 'mpd_server_dev_music:/music:ro',
                  'mpd_server_dev_backups:/backups', 'mpd_server_dev_data:/data'):
        assert entry in dev_server, entry
    assert 'MPD_SERVER_CONFIG_DIR' not in dev and 'MUSIC_DIR' not in dev
    dockerfile = (ROOT / 'deploy/Dockerfile').read_text()
    assert 'COPY web/package.json web/package-lock.json ./' in dockerfile
    assert 'RUN npm ci' in dockerfile
    assert 'COPY web/ ./' not in dockerfile, 'Host node_modules must not overwrite image dependencies'
    assert 'COPY web/src/ ./src/' in dockerfile
    assert 'COPY --from=web-build /web/dist ./web/dist/' in dockerfile
    assert 'CMD ["python", "-m", "server.app.main"]' in dockerfile
    assert '--reload' not in dockerfile


def test_production_artifact_directory_matches_docker_copy():
    from server.app.main import WEB_DIST

    assert WEB_DIST == ROOT / 'web/dist'


def test_http_process_consumes_startup_config_with_one_worker(tmp_path, monkeypatch):
    import uvicorn

    from server.app import main

    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('MPD_MODE', 'mock')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'db.sqlite'))
    monkeypatch.setenv('CONFIG_DIR', str(tmp_path))
    monkeypatch.setenv('MUSIC_ROOT', str(tmp_path))
    monkeypatch.setenv('MPD_CONNECTION_PATH', str(tmp_path / 'saved.json'))
    (tmp_path / 'config.json').write_text('{"http_host":"::","http_port":8123}')
    monkeypatch.delenv('HTTP_HOST', raising=False)
    monkeypatch.delenv('HTTP_PORT', raising=False)
    calls = []
    monkeypatch.setattr(uvicorn, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    main.run_server()
    assert calls == [(('server.app.main:app',), {'host': '::', 'port': 8123, 'workers': 1})]


def test_ci_image_publication_requires_validation_and_uses_commit_identity():
    """Check workflow structure only; a real Actions run is separate evidence."""
    workflow = (ROOT / '.github/workflows/container.yml').read_text()
    assert 'pull_request:' in workflow and 'workflow_dispatch:' in workflow
    assert 'needs: validate' in workflow
    assert "github.event_name != 'pull_request'" in workflow
    assert 'packages: write' in workflow
    assert 'file: deploy/Dockerfile' in workflow
    assert 'platforms: linux/amd64,linux/arm64' in workflow
    assert '${{ github.sha }}' in workflow
    assert ':latest' not in workflow
    for action in re.findall(r'uses: ([^\s]+)', workflow):
        assert re.fullmatch(r'[\w-]+/[\w-]+@[a-f0-9]{40}', action), action
