"""Pipecat Cloud entry point. Tenant data is loaded from the server's allowlist."""
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parent / 'agent'))
from pipecat.runner.types import DailyRunnerArguments
from pipecat.transports.daily.transport import DailyTransport, DailyParams
from server import get_site, run_pipeline
from video_throttle import VIDEO_FPS, VIDEO_SIZE

async def bot(args: DailyRunnerArguments):
    data = args.body if isinstance(args.body, dict) else {}
    site = get_site(data.get('site', ''), data.get('parentOrigin', ''))
    page = data.get('pageUrl', '')
    if not isinstance(page, str) or urlsplit(page).scheme + '://' + urlsplit(page).netloc != site['origin']:
        page = ''
    transport = DailyTransport(args.room_url, args.token, 'Nova', DailyParams(
        audio_in_enabled=True, audio_out_enabled=True, video_out_enabled=True,
        video_out_is_live=True, video_out_width=VIDEO_SIZE, video_out_height=VIDEO_SIZE,
        video_out_framerate=VIDEO_FPS))
    await run_pipeline(transport, site, page)
