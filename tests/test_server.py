import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from fastapi.testclient import TestClient
import server

client = TestClient(server.app)
SITE = {'site':'alpine', 'parentOrigin':'http://localhost:8000'}

def test_site_config_and_origin_isolation():
    response = client.get('/api/widget/config', params=SITE)
    assert response.status_code == 200
    assert response.json()['name'] == 'Alpine Outfitters'
    assert client.get('/api/widget/config', params={**SITE, 'parentOrigin':'https://evil.example'}).status_code == 403
    response = client.get('/embed', params=SITE)
    assert response.status_code == 200
    assert "frame-ancestors 'self'" in response.headers['content-security-policy']

def test_search_uses_onyx_and_rejects_foreign_origin(monkeypatch):
    monkeypatch.setenv('ONYX_API_KEY', 'test-key')
    monkeypatch.setenv('ONYX_DOCUMENT_SET', 'public')
    search = type('Search', (), {})()
    search.search = AsyncMock(return_value={'provider': 'onyx', 'sources': [{'url': 'https://example.com/returns'}]})
    search.aclose = AsyncMock()
    monkeypatch.setattr(server, 'make_search', lambda site: search)
    data = {**SITE, 'query': 'return policy'}
    response = client.post('/api/widget/search', headers={'origin': 'http://testserver'}, json=data)
    assert response.status_code == 200
    assert response.json()['provider'] == 'onyx'
    assert client.post('/api/widget/search', headers={'origin': 'https://evil.example'}, json=data).status_code == 403


def test_search_always_uses_onyx(monkeypatch):
    monkeypatch.delenv('NOVA_SEARCH_PROVIDER', raising=False)
    search = server.make_search(server.get_site('alpine', 'http://localhost:8000'))
    assert isinstance(search, server.OnyxSearch)
    asyncio.run(search.aclose())


def test_missing_onyx_configuration_does_not_use_website_content(monkeypatch):
    monkeypatch.delenv('ONYX_API_KEY', raising=False)
    response = client.post('/api/widget/search', headers={'origin': 'http://testserver'}, json={**SITE, 'query': 'return policy'})
    assert response.status_code == 503
    assert 'passages' not in response.json()

def test_missing_keys_fail_before_offer(monkeypatch):
    for name in ('ZOOM_AI_API_KEY', 'SIMLI_API_KEY', 'SIMLI_FACE_ID'):
        monkeypatch.delenv(name, raising=False)
    response = client.post('/api/offer', headers={'origin':'http://testserver'}, json={'sdp':'x','type':'offer','requestData':SITE})
    assert response.status_code == 503


def test_unclaimed_session_stops_without_stopping_a_connected_visitor():
    async def run():
        class Runner:
            cancel = AsyncMock()
        runner = Runner()
        await server.stop_unclaimed_session(runner, asyncio.Event(), timeout=0.001)
        runner.cancel.assert_awaited_once()
        runner.cancel.reset_mock()
        connected = asyncio.Event()
        connected.set()
        await server.stop_unclaimed_session(runner, connected, timeout=0.001)
        runner.cancel.assert_not_awaited()
    asyncio.run(run())
