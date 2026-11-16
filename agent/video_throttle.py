"""Limit avatar video work while letting audio and control frames pass through."""
from time import monotonic

from pipecat.frames.frames import OutputImageRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

VIDEO_FPS = 10
VIDEO_SIZE = 256


class VideoThrottle(FrameProcessor):
    def __init__(self, fps: int = VIDEO_FPS):
        super().__init__()
        self._interval = 1.0 / fps
        self._next_frame = 0.0

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, OutputImageRawFrame) and direction == FrameDirection.DOWNSTREAM:
            now = monotonic()
            if now < self._next_frame:
                return
            self._next_frame = max(now, self._next_frame) + self._interval
        await self.push_frame(frame, direction)
