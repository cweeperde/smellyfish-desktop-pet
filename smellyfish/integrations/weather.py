"""Current weather from Open-Meteo (free, no key). Only the place (or the coordinates) are sent.

The place can be typed, taken from the Windows location service or, when that is off and you allow it,
estimated from your IP address by an online lookup (ipwho.is)."""

import json
import subprocess
import sys
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


LOCATE_SCRIPT = (
    "Add-Type -AssemblyName System.Device; "
    "$w = New-Object System.Device.Location.GeoCoordinateWatcher; $w.Start(); $n = 0; "
    "while ($w.Status -ne 'Ready' -and $n -lt 40) { Start-Sleep -Milliseconds 250; $n++ }; "
    "$p = $w.Position.Location; if ($p.IsUnknown) { exit 1 }; "
    '$c = [cultureinfo]::InvariantCulture; "$($p.Latitude.ToString($c)),$($p.Longitude.ToString($c))"'
)


def device_location():
    """Latitude and longitude from the Windows (or macOS) location service, or None when it is off or unavailable."""
    if sys.platform == "darwin":
        return _mac_location()
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", LOCATE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=14,
            creationflags=0x08000000,
        )
        lat, lon = out.stdout.strip().split(",")
        lat, lon = float(lat), float(lon)
        if -90 <= lat <= 90 and -180 <= lon <= 180 and out.returncode == 0:
            return {"lat": lat, "lon": lon, "name": "Here"}
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _mac_location(timeout=14):
    """One fix from CoreLocation; macOS asks for Location access the first time."""
    try:
        import time

        import CoreLocation as CL
        from Foundation import NSDate, NSRunLoop

        mgr = CL.CLLocationManager.alloc().init()
        mgr.setDesiredAccuracy_(CL.kCLLocationAccuracyKilometer)
        if hasattr(mgr, "requestWhenInUseAuthorization"):
            mgr.requestWhenInUseAuthorization()
        mgr.startUpdatingLocation()
        end = time.time() + timeout
        loc = None
        while time.time() < end:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
            loc = mgr.location()
            if loc is not None and loc.horizontalAccuracy() >= 0:
                break
        mgr.stopUpdatingLocation()
        if loc is None:
            return None
        c = loc.coordinate()
        if -90 <= c.latitude <= 90 and -180 <= c.longitude <= 180:
            return {"lat": float(c.latitude), "lon": float(c.longitude), "name": "Here"}
    except Exception:
        pass
    return None


def ip_location():
    """Rough position from the public IP address (an online lookup, only when the user allowed it)."""
    try:
        data = _get("https://ipwho.is/?fields=success,latitude,longitude,city")
        if data.get("success"):
            return {"lat": float(data["latitude"]), "lon": float(data["longitude"]), "name": data.get("city") or "Here"}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


STORM = {95, 96, 99}
FOG = {45, 48}
WINDY_KMH = 40


def classify(code, temp, is_day, wind=None):
    if code in STORM:
        return "storm"
    if code in SNOW:
        return "snow"
    if code in RAIN:
        return "rain"
    if code in FOG:
        return "fog"
    if wind is not None and wind >= WINDY_KMH:
        return "wind"
    if temp is not None and temp < 5:
        return "cold"
    if code in (0, 1) and is_day and temp is not None and temp >= 20:
        return "sun"
    if code in (2, 3):
        return "cloud"
    return None


class Weather(QObject):
    changed = Signal(object)  # accessory name or None
    status = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.kind = None
        self.text = "Off"
        self.cur, self.loc_name, self.fetched_at, self.fetched_for = None, None, 0.0, None
        self.here, self.here_at = None, 0.0
        self.timer = QTimer(self, timeout=self.refresh)
        self.timer.start(30 * 60 * 1000)
        QTimer.singleShot(3000, self.refresh)

    def refresh(self, force=False):
        if not self.cfg.get("weather_place") and not self.cfg.get("weather_auto"):
            self._set(None, "Enter a place")
            return
        fresh = time.time() - self.fetched_at < 10 * 60 and self.fetched_for == self.source()
        if fresh and not force:
            return self.render()
        threading.Thread(target=self._fetch, daemon=True).start()

    def source(self):
        return "here" if self.cfg.get("weather_auto") else self.cfg.get("weather_place")

    def locate(self):
        """Where the user is right now (cached for 30 minutes). None when nothing worked."""
        if self.here and time.time() - self.here_at < 30 * 60:
            return self.here
        found = device_location()
        if found is None and self.cfg.get("weather_ip"):
            found = ip_location()
        if found:
            self.here, self.here_at = found, time.time()
        return found

    def render(self):
        if not self.cur:
            return
        cur = self.cur
        kind = classify(
            cur.get("weather_code"), cur.get("temperature_2m"), cur.get("is_day"), cur.get("wind_speed_10m")
        )
        label = {
            "rain": "rainy",
            "snow": "snowing",
            "cold": "cold",
            "sun": "sunny",
            "cloud": "cloudy",
            "storm": "thunderstorm",
            "fog": "foggy",
            "wind": "windy",
        }
        fahrenheit = self.cfg.get("temp_unit") == "F"

        def deg(value, digits=0):
            if value is None:
                return None
            return f"{value * 9 / 5 + 32:.0f} °F" if fahrenheit else f"{value:.{digits}f} °C"

        temp = cur.get("temperature_2m")
        lines = [f"{self.loc_name}: {deg(temp, 1) or '?'}, {label.get(kind, 'calm')}"]
        feels = cur.get("apparent_temperature")
        if feels is not None and temp is not None and abs(feels - temp) >= 2:
            lines.append(f"Feels like {deg(feels)}")
        if cur.get("high") is not None and cur.get("low") is not None:
            lines.append(f"Today {deg(cur['low'])} to {deg(cur['high'])}")
        extra = [f"{cur.get('relative_humidity_2m')} % humidity"]
        if cur.get("wind_speed_10m") is not None:
            extra.append(f"wind {cur['wind_speed_10m']:.0f} km/h")
        lines.append(", ".join(extra))
        self._set(kind, "\n".join(lines))

    def _fetch(self):
        try:
            place = self.cfg.get("weather_place")
            loc = None
            if self.cfg.get("weather_auto"):
                loc = self.locate()
                if loc is None and not place:
                    return self._set(None, "Location is off. Turn it on in the system settings or allow the IP lookup.")
            if loc is None:
                loc = self.cfg.get("weather_loc")
            if loc is None or ("q" in loc and loc.get("q") != place):
                res = (
                    _get(
                        "https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(place)
                    ).get("results")
                    or []
                )
                if not res:
                    return self._set(None, f"Place '{place}' not found")
                loc = {
                    "q": place,
                    "lat": res[0]["latitude"],
                    "lon": res[0]["longitude"],
                    "name": res[0].get("name", place),
                }
                self.cfg.set("weather_loc", loc)
            data = _get(
                f"https://api.open-meteo.com/v1/forecast?latitude={loc['lat']}&longitude={loc['lon']}"
                "&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m"
                "&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=auto"
            )
            cur = dict(data["current"])
            daily = data.get("daily") or {}
            for key, name in (("temperature_2m_max", "high"), ("temperature_2m_min", "low")):
                values = daily.get(key) or [None]
                cur[name] = values[0]
            self.cur, self.loc_name = cur, loc["name"]
            self.fetched_at, self.fetched_for = time.time(), self.source()
            self.render()
        except Exception as e:
            self._set(self.kind, f"Weather unavailable ({e.__class__.__name__})")

    def _set(self, kind, text):
        self.text = text
        self.status.emit(text)
        if kind != self.kind:
            self.kind = kind
            self.changed.emit(kind)
