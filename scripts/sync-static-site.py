#!/usr/bin/env python3
"""Upload a built static site's sitemap pages to Cloudflare AI Search.

The site must have local HTML files and a sitemap with absolute, same-origin
URLs. Existing uploaded documents are left in place. Run again after deployment
to update the same per-page items; removed pages are not deleted automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx
from dotenv import load_dotenv


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.main_depth = 0
        self.hidden_depth = 0
        self.in_title = False
        self.title = []
        self.content = []

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True
        if tag == 'main':
            self.main_depth += 1
        if tag in ('script', 'style', 'svg', 'noscript'):
            self.hidden_depth += 1
        if self.main_depth and tag in ('p', 'section', 'article', 'h1', 'h2', 'h3', 'li', 'br', 'div'):
            self.content.append('\n')

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'main':
            self.main_depth = max(0, self.main_depth - 1)
        if tag in ('script', 'style', 'svg', 'noscript'):
            self.hidden_depth = max(0, self.hidden_depth - 1)
        if self.main_depth and tag in ('p', 'section', 'article', 'h1', 'h2', 'h3', 'li', 'div'):
            self.content.append('\n')

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.main_depth and not self.hidden_depth:
            self.content.append(data + ' ')

    def text(self):
        lines = (re.sub(r'\s+', ' ', line).strip() for line in ''.join(self.content).splitlines())
        return '\n'.join(line for line in lines if line)


def collect_pages(root: Path):
    root = root.resolve()
    sitemap = ET.parse(root / 'sitemap.xml').getroot()
    urls = [element.text.strip() for element in sitemap.findall('{*}url/{*}loc') if element.text and element.text.strip()]
    if not urls:
        raise ValueError('The sitemap has no page URLs.')
    origin = None
    pages = []
    seen = set()
    for url in urls:
        u = urlsplit(url)
        if u.scheme != 'https' or not u.netloc or u.username or u.password or u.query or u.fragment:
            raise ValueError('Sitemap URLs must be HTTPS page URLs without credentials, query, or fragment.')
        current = (u.scheme, u.netloc.lower())
        if origin is None:
            origin = current
        if current != origin:
            raise ValueError('Every sitemap URL must use the same origin.')
        if url in seen:
            continue
        seen.add(url)
        relative = unquote(u.path).lstrip('/')
        filename = (root / relative / 'index.html' if not relative or relative.endswith('/') else root / relative).resolve()
        if not filename.is_relative_to(root):
            raise ValueError('A sitemap path escapes the build directory.')
        if not filename.is_file() or filename.stat().st_size > 2_000_000:
            raise ValueError('Missing or oversized HTML page: ' + u.path)
        parser = PageText()
        parser.feed(filename.read_text(encoding='utf-8'))
        content = parser.text()
        if not content:
            raise ValueError('No main content found: ' + u.path)
        title = re.sub(r'\s+', ' ', ''.join(parser.title)).strip() or u.path
        key = 'site-sync-' + hashlib.sha256(url.encode()).hexdigest()[:24] + '.txt'
        pages.append((url, key, title, content))
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Directory containing sitemap.xml and built HTML pages')
    parser.add_argument('--dry-run', action='store_true', help='List pages without contacting Cloudflare')
    args = parser.parse_args()
    pages = collect_pages(args.root)
    if args.dry_run:
        for url, _, _, _ in pages:
            print(url)
        print(f'{len(pages)} pages ready to index.')
        return
    load_dotenv()
    account = os.getenv('CF_ACCOUNT_ID', '')
    namespace = os.getenv('CF_AI_SEARCH_NAMESPACE', 'default')
    instance = os.getenv('CF_AI_SEARCH_INSTANCE', '')
    token = os.getenv('CF_AI_SEARCH_TOKEN', '')
    if not re.fullmatch(r'[a-f0-9]{32}', account) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,27}', namespace) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', instance) or not token:
        raise ValueError('Set CF_ACCOUNT_ID, CF_AI_SEARCH_NAMESPACE, CF_AI_SEARCH_INSTANCE and CF_AI_SEARCH_TOKEN in the environment or .env.')
    endpoint = f'https://api.cloudflare.com/client/v4/accounts/{account}/ai-search/namespaces/{namespace}/instances/{instance}/items'
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for url, key, title, content in pages:
            response = client.post(endpoint, headers={'Authorization': 'Bearer ' + token},
                                   files={'file': (key, (title + '\n\n' + content).encode('utf-8'), 'text/plain')},
                                   data={'metadata': json.dumps({'source_url': url, 'title': title})})
            if not response.is_success or response.json().get('success') is not True:
                raise RuntimeError(f'Cloudflare upload failed for {url} (HTTP {response.status_code}).')
            print('Uploaded', url, flush=True)
    print(f'Uploaded {len(pages)} pages. Cloudflare indexes them asynchronously.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, ET.ParseError, RuntimeError, httpx.HTTPError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
