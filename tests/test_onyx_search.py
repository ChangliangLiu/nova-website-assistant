import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from onyx_search import OnyxSearch


def test_fast_search_is_scoped_to_document_set(monkeypatch):
    monkeypatch.setenv('ONYX_API_KEY', 'test-secret')
    monkeypatch.setenv('ONYX_DOCUMENT_SET', 'Alpine Public')
    async def run():
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={'search_docs': [
                {'semantic_identifier': 'Returns', 'content': 'Return within 30 days.', 'link': 'https://shop.example/returns'},
                {'semantic_identifier': 'Bad link', 'content': 'Other content', 'link': 'javascript:alert(1)'},
            ], 'error': None})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            search = OnyxSearch({'siteId': 'alpine'}, client=client)
            result = await search.search('return policy')
            await search.aclose()
            assert not client.is_closed
        payload = json.loads(requests[0].content)
        assert requests[0].url.path == '/api/search/send-search-message'
        assert payload['filters'] == {'document_set': ['Alpine Public']}
        assert payload['include_content'] is True and payload['run_query_expansion'] is False
        assert result['passages'][0]['content'] == 'Return within 30 days.'
        assert result['sources'][0]['url'] == 'https://shop.example/returns'
        assert result['passages'][1]['url'] == ''
        assert 'test-secret' not in str(result)
    asyncio.run(run())


def test_missing_scope_fails_closed(monkeypatch):
    monkeypatch.setenv('ONYX_API_KEY', 'test-secret')
    monkeypatch.delenv('ONYX_DOCUMENT_SET', raising=False)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: pytest.fail('Unexpected request'))) as client:
            search = OnyxSearch({'siteId': 'alpine'}, client=client)
            with pytest.raises(ValueError, match='not configured'):
                await search.search('return policy')
    asyncio.run(run())


def test_invalid_endpoint_rejects_credentials_and_insecure_remote(monkeypatch):
    for url in ('http://external.example', 'https://user:pass@example.com', 'https://example.com/path'):
        monkeypatch.setenv('ONYX_URL', url)
        with pytest.raises(ValueError):
            OnyxSearch({'siteId': 'alpine'})
