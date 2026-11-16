"""Exercise an already-running local assistant with a synthetic WebRTC client.

This incurs provider usage. It sends silent audio and a typed question, so it does
not verify a physical microphone. Pass an expected phrase from your own corpus.
"""
import argparse
import asyncio
import json
import uuid

import httpx
from aiortc import AudioStreamTrack, RTCPeerConnection, RTCSessionDescription


async def verify(question, expected, assistant_origin, website_origin, site):
    pc = RTCPeerConnection()
    pc.addTrack(AudioStreamTrack())
    pc.addTransceiver('video', direction='recvonly')
    dc = pc.createDataChannel('chat')
    frames = {'audio': 0, 'video': 0}
    output = []
    recording = False
    ready = asyncio.Event()

    @pc.on('track')
    def on_track(track):
        async def consume():
            try:
                while True:
                    await track.recv()
                    frames[track.kind] += 1
            except Exception:
                pass
        asyncio.create_task(consume())

    @dc.on('open')
    def on_open():
        dc.send(json.dumps({'label': 'rtvi-ai', 'type': 'client-ready', 'id': uuid.uuid4().hex,
                            'data': {'version': '2.2.0', 'about': {'library': 'nova-smoke-test'}}}))

    @dc.on('message')
    def on_message(message):
        try:
            item = json.loads(message)
            if item.get('type') == 'bot-ready': ready.set()
            if recording and item.get('type') == 'bot-llm-text': output.append(item.get('data', {}).get('text', ''))
        except (ValueError, AttributeError):
            pass

    try:
        await pc.setLocalDescription(await pc.createOffer())
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(assistant_origin + '/api/offer',
                headers={'Origin': assistant_origin},
                json={'sdp': pc.localDescription.sdp, 'type': 'offer',
                      'requestData': {'site': site, 'parentOrigin': website_origin, 'pageUrl': ''}})
            response.raise_for_status()
            answer = response.json()
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer['sdp'], type=answer['type']))
        await asyncio.wait_for(ready.wait(), timeout=45)
        await asyncio.sleep(10)  # Allow the greeting to complete before the question.
        recording = True
        dc.send(json.dumps({'label': 'rtvi-ai', 'type': 'send-text', 'id': uuid.uuid4().hex,
                            'data': {'content': question, 'options': {'run_immediately': True, 'audio_response': True}}}))
        for _ in range(45):
            await asyncio.sleep(1)
            if expected.casefold() in ''.join(output).casefold() and frames['audio'] and frames['video']:
                print('PASS: received an answer containing the expected text, audio, and avatar video.')
                return
        raise RuntimeError(f'Preview test failed: expected response not observed; audio frames={frames["audio"]}, video frames={frames["video"]}.')
    finally:
        await pc.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', required=True)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--assistant-origin', default='http://127.0.0.1:8000')
    parser.add_argument('--website-origin', default='http://127.0.0.1:4173')
    parser.add_argument('--site', default='alpine')
    args = parser.parse_args()
    asyncio.run(verify(args.question, args.expected, args.assistant_origin.rstrip('/'), args.website_origin.rstrip('/'), args.site))
