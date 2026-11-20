import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from cloudflare_search import CloudflareSearch


def test_reuses_session_client_and_preserves_passages(monkeypatch):
    monkeypatch.setenv('CF_ACCOUNT_ID', 'a' * 32)
    monkeypatch.setenv('CF_AI_SEARCH_TOKEN', 'test-token')
    monkeypatch.setenv('CF_AI_SEARCH_INSTANCE', 'shop')
    async def run():
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={'success': True, 'result': {'chunks': [
                {'text': 'Returns are accepted within 30 days.',
                 'item': {'key': 'https://shop.example/returns', 'metadata': {'title': 'Returns'}}}
            ]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            search = CloudflareSearch({'siteId': 'shop'}, client=client)
            await search.warm_connection()
            first = await search.search('return policy')
            second = await search.search('returns')
            await search.aclose()
            assert not client.is_closed
        assert len(requests) == 3
        assert requests[0].method == 'HEAD'
        assert 'authorization' not in requests[0].headers
        assert first['passages'][0]['content'] == second['passages'][0]['content']
        assert first['sources'][0]['url'] == 'https://shop.example/returns'
    asyncio.run(run())
