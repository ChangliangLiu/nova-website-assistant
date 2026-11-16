import asyncio

from pipecat.audio.resamplers.sinc_stream_resampler import SincStreamAudioResampler


def test_voice_audio_resamples_with_installed_native_dependency():
    resampler = SincStreamAudioResampler()
    output = asyncio.run(resampler.resample(bytes(960), 24000, 16000))
    assert len(output) == 640
