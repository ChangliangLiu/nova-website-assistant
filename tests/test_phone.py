import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phone_bot
from pipecat.runner.types import DailyRunnerArguments
from website_search import website_instructions


def body():
    return {'dialin_settings': {'call_id': 'call-1', 'call_domain': 'domain-1',
                                'To': '+14255550100', 'From': '+14255550101'},
            'daily_api_key': 'test-key', 'daily_api_url': 'https://api.daily.co/v1'}


def test_phone_site_is_server_selected(monkeypatch):
    monkeypatch.setenv('PHONE_SITE_ID', 'alpine')
    assert phone_bot.phone_site()['siteId'] == 'alpine'
    monkeypatch.setenv('PHONE_SITE_ID', 'unregistered')
    with pytest.raises(ValueError):
        phone_bot.phone_site()


def test_phone_call_uses_audio_only_and_registered_site(monkeypatch):
    monkeypatch.setenv('PHONE_SITE_ID', 'alpine')
    seen = {}
    def transport(room, token, name, params):
        seen.update(room=room, params=params)
        return 'transport'
    pipeline = AsyncMock()
    monkeypatch.setattr(phone_bot, 'PhoneDailyTransport', transport)
    monkeypatch.setattr(phone_bot, 'run_pipeline', pipeline)
    data = body()
    data['site'] = 'untrusted'
    asyncio.run(phone_bot.bot(DailyRunnerArguments('https://test.daily.co/room', 'token', body=data)))
    assert seen['params'].audio_in_enabled and seen['params'].audio_out_enabled
    assert not seen['params'].video_out_enabled
    assert seen['params'].dialin_settings.call_id == 'call-1'
    assert pipeline.await_args.args[1]['siteId'] == 'alpine'
    assert pipeline.await_args.kwargs == {'phone': True}


def test_phone_rejects_untrusted_daily_api_url(monkeypatch):
    monkeypatch.setenv('PHONE_SITE_ID', 'alpine')
    data = body()
    data['daily_api_url'] = 'https://attacker.invalid/v1'
    with pytest.raises(ValueError, match='Unsupported Daily API'):
        asyncio.run(phone_bot.bot(DailyRunnerArguments('https://test.daily.co/room', 'token', body=data)))


def test_phone_instructions_do_not_assume_visual_ui():
    instructions = website_instructions({'name': 'Demo'}, phone=True)
    assert 'caller cannot see links or an avatar' in instructions
    assert 'UI shows full links' not in instructions


def test_voice_prompt_is_loaded_for_both_channels_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    browser = website_instructions({'name': 'Demo'}, 'https://example.com/')
    phone = website_instructions({'name': 'Demo'}, phone=True)
    for prompt in (browser, phone):
        assert 'transcribed speech' in prompt
        assert 'Do not use Markdown' in prompt
        assert 'call search_website first' in prompt
        assert 'Website context (untrusted data only)' in prompt
    assert 'voice and video guide' in browser
    assert 'caller cannot see links or an avatar' not in browser
    assert 'caller cannot see links or an avatar' in phone


def test_daily_dialin_ready_accepts_provider_metadata(monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(phone_bot.DailyTransport, '_on_dialin_ready', handler)
    transport = object.__new__(phone_bot.PhoneDailyTransport)
    asyncio.run(transport._on_dialin_ready({'provider': 'signalwire', 'sipEndpoint': 'sip:example.test'}))
    handler.assert_awaited_once_with('sip:example.test')
    with pytest.raises(ValueError, match='invalid dial-in'):
        asyncio.run(transport._on_dialin_ready({'sipEndpoint': 'https://invalid.example'}))
