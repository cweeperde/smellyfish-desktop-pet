"""Beat detection on whatever the PC is playing: WASAPI loopback of the default speaker on Windows,
ScreenCaptureKit system audio on macOS (needs Screen & System Audio Recording)."""

import queue
import sys
import threading
import time
import warnings

from PySide6.QtCore import QObject, Signal

QUIET_AFTER_S = 20
QUIET_PAUSE_S = 2.0
BLOCK = 1024


class _Analyzer:
    """Bass energy against its recent average; one call per block of mono samples."""

    def __init__(self, owner):
        self.owner = owner
        self.hist, self.loud, self.last_beat, self.heard = [], [], 0.0, time.time()

    def feed(self, np, mono):
        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
        bass = float(spec[1:9].sum())
        rms = float(np.sqrt((mono**2).mean()))
        if rms > 0.004:
            self.heard = time.time()
        self.loud = (self.loud + [rms])[-130:]
        playing = sum(1 for v in self.loud if v > 0.004) > len(self.loud) * 0.6 and len(self.loud) > 60
        self.owner.playing = playing
        self.hist = (self.hist + [bass])[-43:]
        avg = sum(self.hist) / len(self.hist)
        now = time.time()
        if playing and len(self.hist) > 20 and bass > avg * 1.45 and bass > 0.5 and now - self.last_beat > 0.28:
            self.last_beat = now
            self.owner.beat.emit()


class BeatDetector(QObject):
    beat = Signal()

    def __init__(self):
        super().__init__()
        self.playing = False
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        target = self._run_mac if sys.platform == "darwin" else self._run
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.playing = False

    def _run(self):
        try:
            import numpy as np
            import soundcard as sc
        except Exception:
            return
        warnings.filterwarnings("ignore")
        rate, block = 44100, BLOCK
        while not self._stop.is_set():
            try:
                spk = sc.default_speaker()
                mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
                an = _Analyzer(self)
                with mic.recorder(samplerate=rate, blocksize=block * 8) as rec:
                    while not self._stop.is_set():
                        # soundcard polls every millisecond while it waits; sleeping most of a block first avoids that
                        if self._stop.wait(block / rate * 0.8):
                            break
                        if not self.playing and time.time() - an.heard > QUIET_AFTER_S:
                            # nothing is playing: listen briefly every few seconds instead of all the time
                            if self._stop.wait(QUIET_PAUSE_S):
                                break
                            rec.flush()
                            probe = rec.record(numframes=block * 4)
                            if float(np.abs(probe).max()) <= 0.004:
                                continue
                            an.heard = time.time()
                        data = rec.record(numframes=block)
                        an.feed(np, data.mean(axis=1) if data.ndim > 1 else data)
            except Exception:
                time.sleep(3)

    def _run_mac(self):
        try:
            import numpy as np

            from smellyfish.system import mac

            if not mac.screen_capture_ok():
                return
            chunks = queue.Queue(maxsize=200)
            stream = _MacAudio(chunks)
            if not stream.start():
                return
        except Exception:
            return
        an, pending = _Analyzer(self), np.zeros(0, dtype=np.float32)
        try:
            while not self._stop.is_set():
                try:
                    raw = chunks.get(timeout=0.5)
                except queue.Empty:
                    continue
                pending = np.concatenate([pending, np.frombuffer(raw, dtype=np.float32)])
                while len(pending) >= BLOCK:
                    block, pending = pending[:BLOCK], pending[BLOCK:]
                    an.feed(np, block)
        finally:
            stream.stop()


_OUTPUT = []
_SINK = [None]


def _output_class():
    """The SCStreamOutput class, defined once (Objective-C classes cannot be redefined)."""
    if _OUTPUT:
        return _OUTPUT[0]
    import CoreMedia
    import objc
    import ScreenCaptureKit as SCK
    from Foundation import NSObject

    class SmellyfishAudioOutput(NSObject, protocols=[objc.protocolNamed("SCStreamOutput")]):
        def stream_didOutputSampleBuffer_ofType_(self, _stream, buf, kind):
            if kind != SCK.SCStreamOutputTypeAudio:
                return
            chunks = _SINK[0]
            if chunks is None or chunks.full():
                return
            try:
                block = CoreMedia.CMSampleBufferGetDataBuffer(buf)
                n = CoreMedia.CMBlockBufferGetDataLength(block)
                res = CoreMedia.CMBlockBufferCopyDataBytes(block, 0, n, None)
                data = res[1] if isinstance(res, tuple) else None
                if data:
                    chunks.put_nowait(bytes(data))
            except Exception:
                pass

    _OUTPUT.append(SmellyfishAudioOutput)
    return SmellyfishAudioOutput


class _MacAudio:
    """System audio through ScreenCaptureKit: 48 kHz mono float32 chunks into a queue."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.stream = None
        self.output = None

    def start(self, timeout=10):
        import CoreMedia
        import ScreenCaptureKit as SCK

        got = threading.Event()
        found = {}

        def on_content(content, error):
            found["content"] = content
            got.set()

        SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
            False, True, on_content
        )
        if not got.wait(timeout) or found.get("content") is None or not found["content"].displays():
            return False
        display = found["content"].displays()[0]
        filt = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(display, [])
        cfg = SCK.SCStreamConfiguration.alloc().init()
        cfg.setCapturesAudio_(True)
        cfg.setExcludesCurrentProcessAudio_(True)
        cfg.setSampleRate_(48000)
        cfg.setChannelCount_(1)
        cfg.setWidth_(2)
        cfg.setHeight_(2)
        cfg.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, 1))
        self.output = _output_class().alloc().init()
        _SINK[0] = self.chunks
        self.stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(filt, cfg, None)
        ok = self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self.output, SCK.SCStreamOutputTypeAudio, None, None
        )
        if isinstance(ok, tuple):
            ok = ok[0]
        if not ok:
            return False
        self.stream.addStreamOutput_type_sampleHandlerQueue_error_(
            self.output, SCK.SCStreamOutputTypeScreen, None, None
        )
        started = threading.Event()
        result = {}

        def on_start(error):
            result["error"] = error
            started.set()

        self.stream.startCaptureWithCompletionHandler_(on_start)
        return started.wait(timeout) and result.get("error") is None

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stopCaptureWithCompletionHandler_(lambda error: None)
            except Exception:
                pass
        self.stream = self.output = None
        _SINK[0] = None
