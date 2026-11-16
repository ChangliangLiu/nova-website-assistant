"""Nova website assistant: Pipecat + Zoom Voice + Simli, with peer-to-peer WebRTC."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pipecat.frames.frames import LLMRunFrame, LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.simli.video import SimliVideoService
from pipecat.services.zoom_ai.realtime.events import Speak
from pipecat.services.zoom_ai.realtime.llm import ZoomAIRealtimeLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import IceServer
from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest, SmallWebRTCRequestHandler
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner
from website_search import WebsiteSearch, website_instructions
from cloudflare_search import CloudflareSearch
from video_throttle import VIDEO_FPS, VIDEO_SIZE, VideoThrottle

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / '.env')
app = FastAPI(docs_url=None, redoc_url=None)
app.mount('/assets', StaticFiles(directory=BASE / 'web'), name='assets')
handler = SmallWebRTCRequestHandler(ice_servers=[IceServer(urls='stun:stun.l.google.com:19302')])
tasks: set[asyncio.Task] = set()

@app.get('/')
async def home():
    return HTMLResponse('''<!doctype html><html><head><title>Nova Pipecat Assistant</title></head><body><main><h1>Nova Pipecat Assistant</h1><p>Open the assistant to try the Alpine Outfitters knowledge base.</p></main><script src="/widget.js" data-site="alpine" defer></script></body></html>''')


def get_site(site_id: str, parent: str) -> dict:
    sites = json.loads(Path(os.getenv('NOVA_SITES_FILE', str(BASE / 'agent/knowledge/sites.json'))).read_text())
    site = sites.get(site_id)
    if not site or parent not in site.get('allowedOrigins', []):
        raise HTTPException(403, 'This website is not registered for the assistant.')
    return site


def same_origin(request: Request):
    origin = request.headers.get('origin')
    base = str(request.base_url).rstrip('/')
    if not origin or origin != base:
        raise HTTPException(403, 'Invalid request origin')


@app.get('/widget.js')
async def widget():
    return FileResponse(BASE / 'web/widget.js', media_type='application/javascript')


@app.get('/embed')
async def embed(site: str, parentOrigin: str):
    website = get_site(site, parentOrigin)
    response = HTMLResponse((BASE / 'web/embed.html').read_text())
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' " + ' '.join(website['allowedOrigins'])
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/widget/config')
async def config(site: str, parentOrigin: str):
    website = get_site(site, parentOrigin)
    return {'name': website['name'], 'documentCount': len(website['documents']),
            'ready': bool(os.getenv('ZOOM_AI_API_KEY') and os.getenv('SIMLI_API_KEY') and os.getenv('SIMLI_FACE_ID')),
            'prompts': website.get('suggestions', [])}


@app.post('/api/widget/search')
async def search_endpoint(request: Request):
    same_origin(request)
    data = await request.json()
    site = get_site(data.get('site', ''), data.get('parentOrigin', ''))
    try:
        return await make_search(site).search(data.get('query', ''))
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(503, 'Knowledge search is temporarily unavailable.') from error


def make_search(website):
    if os.getenv('NOVA_SEARCH_PROVIDER') == 'cloudflare':
        return CloudflareSearch(website)
    return WebsiteSearch(website)


async def run_pipeline(transport, website, page_url, *, phone=False):
    search = make_search(website)
    worker = None

    async def search_website(params: FunctionCallParams, query: str):
        """Search the registered website for relevant passages and source links.

        Args:
            query: The visitor's question or search terms.
        """
        try:
            result = await search.search(query)
            if not phone:
                await worker.rtvi.send_server_message({'type': 'sources', 'sources': result['sources']})
            await params.result_callback(result)
        except Exception:
            await params.result_callback({'error': 'Website search is unavailable.'})

    llm = ZoomAIRealtimeLLMService(api_key=os.environ['ZOOM_AI_API_KEY'],
        settings=ZoomAIRealtimeLLMService.Settings(
            system_instruction=website_instructions(website, page_url, phone=phone),
            speak=Speak(voice=os.getenv('ZOOM_VOICE', 'jenna'))))
    avatar = None if phone else SimliVideoService(api_key=os.environ['SIMLI_API_KEY'],
        face_id=os.environ['SIMLI_FACE_ID'], max_session_length=600, max_idle_time=120)
    context = LLMContext([{'role': 'developer', 'content': 'Greet the visitor briefly as Nova and ask how you can help.'}], [search_website])
    user, assistant = LLMContextAggregatorPair(context)
    class TypedInputBridge(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, LLMMessagesAppendFrame) and direction == FrameDirection.DOWNSTREAM:
                for entry in frame.messages:
                    if entry.get('role') == 'user' and isinstance(entry.get('content'), str):
                        await llm._send_message_item(entry['content'], role='user')
                        context.add_message(entry)
                if frame.run_llm:
                    await llm._create_response()
                return
            await self.push_frame(frame, direction)
    processors = [transport.input(), TypedInputBridge(), user, llm]
    if avatar:
        processors.extend([avatar, VideoThrottle()])
    processors += [transport.output(), assistant]
    worker = PipelineWorker(Pipeline(processors), idle_timeout_secs=120, enable_rtvi=not phone)
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    @transport.event_handler('on_client_connected')
    async def connected(transport, client):
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler('on_client_disconnected')
    async def disconnected(transport, client):
        await runner.cancel()

    try:
        async with asyncio.timeout(600):
            await runner.run()
    except TimeoutError:
        await runner.cancel()


@app.post('/api/offer')
async def offer(request: Request):
    same_origin(request)
    data = await request.json()
    custom = data.get('requestData') or data.get('request_data') or {}
    website = get_site(custom.get('site', ''), custom.get('parentOrigin', ''))
    if not all(os.getenv(k) for k in ('ZOOM_AI_API_KEY', 'SIMLI_API_KEY', 'SIMLI_FACE_ID')):
        raise HTTPException(503, 'Zoom Voice and Simli credentials must be configured on the server.')
    page = custom.get('pageUrl', '')
    if not isinstance(page, str) or urlsplit(page).scheme + '://' + urlsplit(page).netloc != website['origin']:
        page = ''
    async def connected(connection):
        transport = SmallWebRTCTransport(webrtc_connection=connection, params=TransportParams(
            audio_in_enabled=True, audio_out_enabled=True, video_out_enabled=True,
            video_out_is_live=True, video_out_width=VIDEO_SIZE, video_out_height=VIDEO_SIZE,
            video_out_framerate=VIDEO_FPS))
        task = asyncio.create_task(run_pipeline(transport, website, page))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    try:
        req = SmallWebRTCRequest.from_dict(data)
        return await handler.handle_web_request(req, connected)
    except (ValueError, TypeError, KeyError) as error:
        raise HTTPException(400, 'Invalid WebRTC offer') from error
