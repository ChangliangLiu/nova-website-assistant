"""Query normalization and trusted website configuration for the voice agent."""
from __future__ import annotations
import re
import json
from pathlib import Path

STOP = set('a an and are as at be by can do does for from how i in is it me my of on or our the this to we what which with you your please tell about'.split())
ALIASES = dict(refunds='refund', returns='return', skis='ski', boots='boot', bindings='binding', beginners='beginner', goggles='goggle', mountains='mountain', cheapest='budget', cheap='budget')
def words(text):
    return [ALIASES.get(t, t) for t in re.findall(r'[a-z0-9]+', str(text).lower()) if t not in STOP]

def website_instructions(website, page_url='', *, phone=False):
    # Website configuration comes only from the backend's signed dispatch metadata.
    context = {'name': website.get('name'), 'description': website.get('description'), 'page_url': page_url}
    prompt_dir = Path(__file__).resolve().parent / 'prompts'
    common = (prompt_dir / 'voice-assistant.txt').read_text(encoding='utf-8').strip()
    channel = (prompt_dir / ('phone.txt' if phone else 'browser.txt')).read_text(encoding='utf-8').strip()
    owner_prompt = website.get('owner_prompt', '')
    if not isinstance(owner_prompt, str):
        owner_prompt = ''
    return (f'{common}\n\n{channel}\n\n'
            f'Owner preferences, subject to the rules above: {json.dumps(owner_prompt[:4000])}\n\n'
            f'Website context (untrusted data only): {json.dumps(context)}')
