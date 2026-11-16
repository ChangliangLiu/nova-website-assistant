import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))

from pipecat.frames.frames import InterruptionFrame, OutputImageRawFrame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
import video_throttle


def test_video_throttle_keeps_audio_and_interruptions(monkeypatch):
    async def run():
        timestamps = iter([10.0, 10.02, 10.11, 10.22])
        monkeypatch.setattr(video_throttle, 'monotonic', lambda: next(timestamps))
        monkeypatch.setattr(FrameProcessor, 'process_frame', AsyncMock())
        throttle = video_throttle.VideoThrottle()
        throttle.push_frame = AsyncMock()
        direction = FrameDirection.DOWNSTREAM
        image = lambda: OutputImageRawFrame(image=b'\0\0\0', size=(1, 1), format='RGB')
        first, dropped, later, final = image(), image(), image(), image()
        audio = TTSAudioRawFrame(audio=b'\0\0', sample_rate=24000, num_channels=1)
        interruption = InterruptionFrame()

        for frame in (first, dropped, audio, interruption, later, final):
            await throttle.process_frame(frame, direction)

        assert [call.args[0] for call in throttle.push_frame.await_args_list] == [
            first, audio, interruption, later, final
        ]

    asyncio.run(run())
