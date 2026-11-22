"""Retrieve only from the administrator-configured Onyx document set."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


def _base_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1'))):
        raise ValueError('Onyx URL must use HTTPS or localhost HTTP')
    if not parsed.netloc or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Onyx URL must be an origin')
    return value.rstrip('/')


class OnyxSearch:
    def __init__(self, website, *, client=None):
        self.website = website
        self.base_url = _base_url(os.getenv('ONYX_URL', 'https://cloud.onyx.app'))
        self.token = os.getenv('ONYX_API_KEY', '')
        self.document_set = os.getenv('ONYX_DOCUMENT_SET', '').strip()
        self.client = client or httpx.AsyncClient(follow_redirects=False)
        self._owns_client = client is None

    async def warm_connection(self):
        try:
            await self.client.head(self.base_url + '/', timeout=3.0)
        except httpx.HTTPError:
            pass

    async def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 2048:
            raise ValueError('Invalid search query length')
        if not self.token or not self.document_set:
            raise ValueError('Onyx search is not configured')
        response = await self.client.post(
            self.base_url + '/api/search/send-search-message',
            headers={'Authorization': f'Bearer {self.token}'},
            json={'search_query': query, 'filters': {'document_set': [self.document_set]},
                  'run_query_expansion': False, 'num_hits': 8, 'include_content': True, 'stream': False},
            timeout=12.0,
        )
        response.raise_for_status()
        body = response.json()
        if body.get('error') or not isinstance(body.get('search_docs'), list):
            raise ValueError('Invalid Onyx search response')
        passages, sources = [], []
        for item in body['search_docs'][:8]:
            if not isinstance(item, dict):
                continue
            content = item.get('content') or item.get('blurb')
            if not isinstance(content, str) or not content.strip():
                continue
            title = str(item.get('semantic_identifier') or item.get('title') or 'Document')[:200]
            link = item.get('link', '')
            try:
                parsed = urlsplit(link) if isinstance(link, str) else None
            except ValueError:
                parsed = None
            link = link if parsed and parsed.scheme in ('https', 'http') and parsed.netloc and not parsed.username and not parsed.password else ''
            passage = {'title': title, 'content': content[:15000], 'url': link, 'citationId': len(passages) + 1}
            passages.append(passage)
            if link:
                sources.append({'id': str(passage['citationId']), 'title': title, 'url': link,
                                'excerpt': passage['content'][:240], 'citationId': passage['citationId']})
        return {'provider': 'onyx', 'siteId': self.website.get('siteId'), 'passages': passages, 'sources': sources}

    async def aclose(self):
        if self._owns_client:
            await self.client.aclose()
