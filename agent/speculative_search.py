"""Start retrieval as soon as a final visitor transcript is available."""
import asyncio
from contextlib import suppress

from loguru import logger
from website_search import words


def _terms(query):
    return tuple(term for term in words(query) if term not in {'your', 'our', 'their'})


class SpeculativeSearch:
    def __init__(self, search):
        self.search = search
        self._terms = ()
        self._task = None
        self._last_terms = None
        self._last_result = None
        self._generation = 0
        warm_connection = getattr(search, 'warm_connection', None)
        self._warmup = asyncio.create_task(warm_connection()) if warm_connection else None

    def start(self, transcript):
        self._generation += 1
        self._last_terms = None
        self._last_result = None
        if not isinstance(transcript, str) or not 1 <= len(transcript.strip()) <= 2048:
            return
        terms = _terms(transcript)
        if not terms:
            return
        if self._task and not self._task.done():
            self._task.cancel()
        self._terms = terms
        self._task = asyncio.create_task(self.search.search(transcript))
        logger.info('Started early knowledge retrieval')
        # Retrieve exceptions even when the model decides not to call search.
        self._task.add_done_callback(self._consume_exception)

    @staticmethod
    def _consume_exception(task):
        if not task.cancelled():
            task.exception()

    async def resolve(self, query):
        generation = self._generation
        terms = _terms(query)
        if self._last_terms == terms and self._last_result is not None:
            return self._last_result
        # A rewritten or context-resolved query may mean something different.
        # Only share the result when the meaningful terms match exactly.
        if self._task and terms == self._terms:
            try:
                logger.info('Reusing early knowledge retrieval')
                result = await asyncio.shield(self._task)
                if generation == self._generation:
                    self._last_terms, self._last_result = terms, result
                return result
            except Exception:
                # A failed early attempt must not prevent the actual tool call.
                pass
        logger.info('Starting knowledge retrieval for tool query')
        result = await self.search.search(query)
        if generation == self._generation:
            self._last_terms, self._last_result = terms, result
        return result

    async def aclose(self):
        if self._warmup and not self._warmup.done():
            self._warmup.cancel()
            with suppress(asyncio.CancelledError):
                await self._warmup
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        await self.search.aclose()
