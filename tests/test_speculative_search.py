import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
from speculative_search import SpeculativeSearch


def test_matching_query_reuses_inflight_search():
    async def run():
        release = asyncio.Event()
        async def search(query):
            await release.wait()
            return {'query': query}
        provider = type('Provider', (), {})()
        provider.search = AsyncMock(side_effect=search)
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        s.start('What is your returns policy?')
        pending = asyncio.create_task(s.resolve('return policy'))
        await asyncio.sleep(0)
        release.set()
        assert await pending == {'query': 'What is your returns policy?'}
        assert provider.search.await_count == 1
        await s.aclose()
        provider.aclose.assert_awaited_once()
    asyncio.run(run())


def test_context_resolved_query_uses_its_own_search():
    async def run():
        provider = type('Provider', (), {})()
        provider.search = AsyncMock(side_effect=lambda query: {'query': query})
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        s.start('What about those?')
        result = await s.resolve('return policy for ski boots')
        assert result['query'] == 'return policy for ski boots'
        await s.aclose()
    asyncio.run(run())


def test_close_cancels_unneeded_prefetch():
    async def run():
        provider = type('Provider', (), {})()
        async def slow_search(query):
            await asyncio.sleep(60)
        provider.search = AsyncMock(side_effect=slow_search)
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        s.start('ski return policy')
        await asyncio.sleep(0)
        await s.aclose()
        provider.aclose.assert_awaited_once()
    asyncio.run(run())


def test_failed_prefetch_retries_the_real_search():
    async def run():
        provider = type('Provider', (), {})()
        provider.search = AsyncMock(side_effect=[RuntimeError('temporary failure'), {'passages': []}])
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        s.start('return policy')
        assert await s.resolve('return policy') == {'passages': []}
        assert provider.search.await_count == 2
        await s.aclose()
    asyncio.run(run())


def test_expansion_reuses_result_and_new_turn_clears_cache():
    async def run():
        provider = type('Provider', (), {})()
        provider.search = AsyncMock(side_effect=lambda query: {'query': query})
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        assert await s.resolve('return policy') == await s.resolve('return policy')
        assert provider.search.await_count == 1
        s.start('ski boots')
        await s.resolve('return policy')
        assert provider.search.await_count >= 2
        await s.aclose()
    asyncio.run(run())


def test_old_inflight_result_cannot_fill_new_turn_cache():
    async def run():
        release = asyncio.Event()
        started = asyncio.Event()
        async def search(query):
            if query == 'return policy':
                started.set()
                await release.wait()
            return {'query': query}
        provider = type('Provider', (), {})()
        provider.search = AsyncMock(side_effect=search)
        provider.aclose = AsyncMock()
        s = SpeculativeSearch(provider)
        pending = asyncio.create_task(s.resolve('return policy'))
        await started.wait()
        s.start('ski boots')
        release.set()
        await pending
        await s.resolve('return policy')
        assert sum(call.args[0] == 'return policy' for call in provider.search.await_args_list) == 2
        await s.aclose()
    asyncio.run(run())
