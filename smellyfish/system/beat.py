"""Beat detection on whatever the PC is playing (WASAPI loopback of the default speaker)."""
import threading
import time
import warnings

from PySide6.QtCore import QObject, Signal


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
        self._thread = threading.Thread(target=self._run, daemon=True)
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
        rate, block = 44100, 1024
        while not self._stop.is_set():
            try:
                spk = sc.default_speaker()
                mic = sc.get_microphone(id=str(spk.name), include_loopback=True)
                hist, loud, last_beat = [], [], 0.0
                with mic.recorder(samplerate=rate, blocksize=block) as rec:
                    while not self._stop.is_set():
                        data = rec.record(numframes=block)
                        mono = data.mean(axis=1) if data.ndim > 1 else data
                        spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
                        bass = float(spec[1:9].sum())
                        rms = float(np.sqrt((mono ** 2).mean()))
                        loud = (loud + [rms])[-130:]
                        self.playing = sum(1 for v in loud if v > 0.004) > len(loud) * 0.6 and len(loud) > 60
                        hist = (hist + [bass])[-43:]
                        avg = sum(hist) / len(hist)
                        now = time.time()
                        if (self.playing and len(hist) > 20 and bass > avg * 1.45 and bass > 0.5
                                and now - last_beat > 0.28):
                            last_beat = now
                            self.beat.emit()
            except Exception:
                time.sleep(3)
