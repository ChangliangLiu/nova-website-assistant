import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from fastapi.testclient import TestClient
import server

client = TestClient(server.app)
SITE = {'site':'alpine', 'parentOrigin':'http://localhost:8000'}

def test_site_config_and_origin_isolation():
    response = client.get('/api/widget/config', params=SITE)
    assert response.status_code == 200
    assert response.json()['documentCount'] == 29
    assert client.get('/api/widget/config', params={**SITE, 'parentOrigin':'https://evil.example'}).status_code == 403
    response = client.get('/embed', params=SITE)
    assert response.status_code == 200
    assert "frame-ancestors 'self'" in response.headers['content-security-policy']

def test_offline_search_and_foreign_origin():
    data = {**SITE, 'query':'return policy'}
    response = client.post('/api/widget/search', headers={'origin':'http://testserver'}, json=data)
    assert response.status_code == 200
    assert any('/guides/returns/' in s['url'] for s in response.json()['sources'])
    assert client.post('/api/widget/search', headers={'origin':'https://evil.example'}, json=data).status_code == 403

def test_search_provider_selection(monkeypatch):
    website = server.get_site('alpine', 'http://localhost:8000')
    monkeypatch.delenv('NOVA_SEARCH_PROVIDER', raising=False)
    assert isinstance(server.make_search(website), server.WebsiteSearch)
    monkeypatch.setenv('NOVA_SEARCH_PROVIDER', 'cloudflare')
    assert isinstance(server.make_search(website), server.CloudflareSearch)

def test_missing_keys_fail_before_offer(monkeypatch):
    for name in ('ZOOM_AI_API_KEY', 'SIMLI_API_KEY', 'SIMLI_FACE_ID'):
        monkeypatch.delenv(name, raising=False)
    response = client.post('/api/offer', headers={'origin':'http://testserver'}, json={'sdp':'x','type':'offer','requestData':SITE})
    assert response.status_code == 503
