"""Current weather from Open-Meteo (free, no key). Only the place you type is sent."""
import json
import threading
import time
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, QTimer, Signal

RAIN = set(range(51, 68)) | set(range(80, 83)) | set(range(95, 100))
SNOW = set(range(71, 78)) | {85, 86}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Smellyfish desktop pet"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def classify(code, temp, is_day):
    if code in SNOW:
        return "snow"
    if code in RAIN:
        return "rain"
    if temp is not None and temp < 5:
        return "cold"
    if code in (0, 1) and is_day and temp is not None and temp >= 20:
        return "sun"
    if code in (2, 3, 45, 48):
        return "cloud"
    return None


class Weather(QObject):
    changed = Signal(object)        # accessory name or None
    status = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.kind = None
        self.text = "Off"
        self.cur, self.loc_name, self.fetched_at, self.fetched_for = None, None, 0.0, None
        self.timer = QTimer(self, timeout=self.refresh)
        self.timer.start(30 * 60 * 1000)
        QTimer.singleShot(3000, self.refresh)

    def refresh(self, force=False):
        if not self.cfg.get("weather_place"):
            self._set(None, "Enter a place")
            return
        fresh = time.time() - self.fetched_at < 10 * 60 and self.fetched_for == self.cfg["weather_place"]
        if fresh and not force:
            return self.render()
        threading.Thread(target=self._fetch, daemon=True).start()

    def render(self):
        if not self.cur:
            return
        cur = self.cur
        kind = classify(cur.get("weather_code"), cur.get("temperature_2m"), cur.get("is_day"))
        label = {"rain": "rainy", "snow": "snowing", "cold": "cold", "sun": "sunny", "cloud": "cloudy"}
        temp = cur.get("temperature_2m")
        if temp is None:
            shown = "?"
        elif self.cfg.get("temp_unit") == "F":
            shown = f"{temp * 9 / 5 + 32:.0f} °F"
        else:
            shown = f"{temp:.1f} °C"
        self._set(kind, f"{self.loc_name}: {shown}, {cur.get('relative_humidity_2m')} % humidity, "
                        f"{label.get(kind, 'calm')}")

    def _fetch(self):
        try:
            place = self.cfg["weather_place"]
            loc = self.cfg.get("weather_loc")
            if not loc or loc.get("q") != place:
                res = _get("https://geocoding-api.open-meteo.com/v1/search?count=1&name="
                           + urllib.parse.quote(place)).get("results") or []
                if not res:
                    return self._set(None, f"Place '{place}' not found")
                loc = {"q": place, "lat": res[0]["latitude"], "lon": res[0]["longitude"],
                       "name": res[0].get("name", place)}
                self.cfg.set("weather_loc", loc)
            cur = _get(f"https://api.open-meteo.com/v1/forecast?latitude={loc['lat']}&longitude={loc['lon']}"
                       "&current=temperature_2m,relative_humidity_2m,weather_code,is_day")["current"]
            self.cur, self.loc_name = cur, loc["name"]
            self.fetched_at, self.fetched_for = time.time(), place
            self.render()
        except Exception as e:
            self._set(self.kind, f"Weather unavailable ({e.__class__.__name__})")

    def _set(self, kind, text):
        self.text = text
        self.status.emit(text)
        if kind != self.kind:
            self.kind = kind
            self.changed.emit(kind)
