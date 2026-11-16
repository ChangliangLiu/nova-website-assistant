import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

spec = importlib.util.spec_from_file_location('sync_static_site', Path(__file__).parents[1] / 'scripts/sync-static-site.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def site(root):
    (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://shop.example/</loc></url><url><loc>https://shop.example/help/</loc></url></urlset>')
    (root / 'index.html').write_text('<title>Shop</title><nav>ignored navigation</nav><main><h1>Welcome</h1><script>ignored script</script><p>Demo shop</p></main>')
    (root / 'help').mkdir()
    (root / 'help/index.html').write_text('<title>Help</title><main><h1>Returns</h1><p>Within 30 days.</p></main>')


def test_uploads_public_pages_with_source_metadata(tmp_path, monkeypatch):
    site(tmp_path)
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={'success': True})
    original_client = httpx.Client
    monkeypatch.setattr(sync.httpx, 'Client', lambda **kw: original_client(transport=httpx.MockTransport(respond), **kw))
    for key, value in {'CF_ACCOUNT_ID': 'a' * 32, 'CF_AI_SEARCH_NAMESPACE': 'default', 'CF_AI_SEARCH_INSTANCE': 'shop', 'CF_AI_SEARCH_TOKEN': 'test-secret'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, 'argv', ['sync-static-site.py', '--root', str(tmp_path)])
    sync.main()
    assert len(calls) == 2
    assert all(call.method == 'POST' and call.url.path.endswith('/instances/shop/items') for call in calls)
    bodies = [call.content.decode() for call in calls]
    assert 'https://shop.example/help/' in bodies[1]
    assert 'Within 30 days.' in bodies[1]
    assert 'ignored navigation' not in bodies[0]
    assert 'ignored script' not in bodies[0]


def test_rejects_cross_origin_sitemap_before_upload(tmp_path):
    site(tmp_path)
    p = tmp_path / 'sitemap.xml'
    p.write_text(p.read_text().replace('https://shop.example/help/', 'https://other.example/help/'))
    with pytest.raises(ValueError, match='same origin'):
        sync.collect_pages(tmp_path)
