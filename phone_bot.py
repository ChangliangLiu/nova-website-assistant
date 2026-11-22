"""Audio-only Daily PSTN entry point for a separate Pipecat Cloud agent."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'agent'))
from pipecat.runner.types import DailyDialinRequest, DailyRunnerArguments
from pipecat.transports.daily.transport import DailyDialinSettings, DailyParams, DailyTransport
from server import run_pipeline

BASE = Path(__file__).resolve().parent


class PhoneDailyTransport(DailyTransport):
    async def _on_dialin_ready(self, endpoint):
        # The current Daily SDK supplies a metadata object; the pinned
        # Pipecat version expects just the SIP URI string.
        if isinstance(endpoint, dict):
            endpoint = endpoint.get('sipEndpoint')
        if not isinstance(endpoint, str) or not endpoint.startswith('sip:'):
            raise ValueError('Daily supplied an invalid dial-in SIP endpoint.')
        await super()._on_dialin_ready(endpoint)


def phone_site():
    """Select a trusted server-configured site, never from caller-supplied data."""
    site_id = os.environ.get('PHONE_SITE_ID', '')
    sites = json.loads((BASE / 'agent/knowledge/sites.json').read_text())
    site = sites.get(site_id)
    if not site or site.get('siteId') != site_id:
        raise ValueError('A registered PHONE_SITE_ID is required for phone calls.')
    return site


async def bot(args: DailyRunnerArguments):
    request = DailyDialinRequest.model_validate(args.body)
    if request.daily_api_url.rstrip('/') != 'https://api.daily.co/v1':
        raise ValueError('Unsupported Daily API endpoint.')
    if not request.dialin_settings.call_id or not request.dialin_settings.call_domain:
        raise ValueError('Missing Daily dial-in settings.')
    site = phone_site()
    transport = PhoneDailyTransport(args.room_url, args.token, 'Nova Phone', DailyParams(
        api_key=request.daily_api_key,
        api_url='https://api.daily.co/v1',
        dialin_settings=DailyDialinSettings(call_id=request.dialin_settings.call_id,
                                           call_domain=request.dialin_settings.call_domain),
        audio_in_enabled=True, audio_out_enabled=True, video_out_enabled=False))
    await run_pipeline(transport, site, '', phone=True)
