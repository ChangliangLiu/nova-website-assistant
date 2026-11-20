"""Cloudflare AI Search retrieval for a single configured assistant."""
from __future__ import annotations
import os
import re
from urllib.parse import urlsplit
import httpx

class CloudflareSearch:
    def __init__(self, website, *, client=None):
        self.website = website
        self.client = client or httpx.AsyncClient(follow_redirects=False)
        self._owns_client = client is None
        self.account = os.getenv('CF_ACCOUNT_ID', '')
        self.token = os.getenv('CF_AI_SEARCH_TOKEN', '')
        self.namespace = os.getenv('CF_AI_SEARCH_NAMESPACE', 'default')
        self.instance = os.getenv('CF_AI_SEARCH_INSTANCE', '')
        self.enabled = bool(self.token and re.fullmatch(r'[0-9a-f]{32}', self.account) and
                            re.fullmatch(r'[a-z0-9][a-z0-9-]{0,27}', self.namespace) and
                            re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', self.instance))

    async def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 2048:
            raise ValueError('Invalid search query length')
        if not self.enabled:
            raise ValueError('Cloudflare AI Search is not configured')
        url = f'https://api.cloudflare.com/client/v4/accounts/{self.account}/ai-search/namespaces/{self.namespace}/instances/{self.instance}/search'
        async def request(client):
            r = await client.post(url, headers={'Authorization': f'Bearer {self.token}'},
                                  json={'query': query}, timeout=12.0)
            r.raise_for_status()
            body = r.json()
            if body.get('success') is not True or not isinstance(body.get('result', {}).get('chunks'), list):
                raise ValueError('Invalid Cloudflare search response')
            return body['result']['chunks']
        chunks = await request(self.client)
        passages, sources = [], []
        for chunk in chunks[:8]:
            if not isinstance(chunk, dict) or not isinstance(chunk.get('text'), str):
                continue
            item = chunk.get('item') if isinstance(chunk.get('item'), dict) else {}
            meta = item.get('metadata') if isinstance(item.get('metadata'), dict) else {}
            title = str(meta.get('title') or item.get('key') or 'Document')[:200]
            link = meta.get('url') or meta.get('source_url') or item.get('key', '')
            try:
                parsed = urlsplit(link) if isinstance(link, str) else None
            except ValueError:
                parsed = None
            link = link if parsed and parsed.scheme in ('https', 'http') and parsed.netloc and not parsed.username and not parsed.password else ''
            p = {'title': title, 'content': chunk['text'][:15000], 'url': link, 'citationId': len(passages)+1}
            passages.append(p)
            if link:
                sources.append({'id': str(p['citationId']), 'title': title, 'url': link,
                                'excerpt': p['content'][:240], 'citationId': p['citationId']})
        return {'provider': 'cloudflare', 'siteId': self.website.get('siteId'), 'passages': passages, 'sources': sources}

    async def warm_connection(self):
        # Establish DNS and TLS while the avatar connects, without submitting a query.
        try:
            await self.client.head('https://api.cloudflare.com/client/v4', timeout=3.0)
        except httpx.HTTPError:
            pass

    async def aclose(self):
        if self._owns_client:
            await self.client.aclose()
