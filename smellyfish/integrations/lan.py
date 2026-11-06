"""LAN lobby: visit friends' jellyfish and send little letters over the local network.

Nothing leaves your network and nothing runs until you create or join a lobby.
Security: every lobby has a password. Both sides run an X25519 key exchange and mix the password (stretched
with scrypt) into the session keys, so a wrong password never gets a readable answer. All traffic after the
handshake is ChaCha20-Poly1305 encrypted with strictly counted nonces (no replay, no reordering).
The host also limits message size, rate and the number of people, and blocks addresses that guess passwords.
"""
import hashlib
import json
import re
import secrets
import struct
import time
import unicodedata

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface, QTcpServer, QTcpSocket, QUdpSocket

from smellyfish import __version__

PROTOCOL = 2
MIN_PASSWORD = 4
KICK_BAN = 60
DISCOVERY_PORT = 47812
DEFAULT_PORT = 47813
MAX_MEMBERS = 8
MAX_FRAME = 4096
HANDSHAKE_SECONDS = 5
BAN_SECONDS = 60
MAX_FAILS = 3
COOLDOWN = {"chat": 2.0, "letter": 30.0, "visit": 45.0}
TEXT_LIMIT = {"chat": 200, "letter": 280}
NAME_LIMIT = 16
STRIKES_TO_KICK = 6
FLOOD_FRAMES, FLOOD_SECONDS = 25, 10
INFO = b"smellyfish-lan-1"
AAD = b"sf1"
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
OUTFITS = {"santa", "witch", "party", "valentine"}
WEATHERS = {"sun", "rain", "cold", "snow"}
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def clean(text, limit):
    text = "".join(" " if ch.isspace() else ch for ch in str(text or "") if unicodedata.category(ch)[0] != "C"
                   or ch.isspace())
    return " ".join(text.split())[:limit]


def clean_color(value):
    return value if isinstance(value, str) and COLOR_RE.match(value) else "#c492ec"


def clean_look(look):
    """What a visitor wears: season outfit, weather clothes, headset, focus band (whitelisted values only)."""
    look = look if isinstance(look, dict) else {}
    return {"o": look.get("o") if look.get("o") in OUTFITS else None,
            "w": look.get("w") if look.get("w") in WEATHERS else None,
            "h": "mic" if look.get("h") == "mic" else None, "b": look.get("b") is True}


def make_password():
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def stretch(password, salt):
    return hashlib.scrypt(password.strip().upper().replace("-", "").encode(), salt=salt, n=2 ** 14, r=8, p=1,
                          dklen=32)


def derive(shared, psk, cpub, spub, cr, sr):
    key = HKDF(hashes.SHA256(), 64, psk, INFO + cpub + spub + cr + sr).derive(shared)
    return key[:32], key[32:]


def raw_pub(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def compatible(version):
    """Lobbies work together when the first two numbers of the app version match (and the protocol, checked apart)."""
    try:
        a = [int(x) for x in str(version).split(".")[:2]]
        b = [int(x) for x in __version__.split(".")[:2]]
    except ValueError:
        return False
    return a == b


def local_addresses():
    """This PC's private IPv4 addresses, the likeliest first (what a friend could type to join)."""
    out = []
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.IsUp and flags & QNetworkInterface.IsRunning) \
                or flags & QNetworkInterface.IsLoopBack:
            continue
        for e in iface.addressEntries():
            ip = e.ip()
            if ip.protocol() == QAbstractSocket.IPv4Protocol and ip.isInSubnet(QHostAddress("10.0.0.0"), 8) \
                    or ip.isInSubnet(QHostAddress("192.168.0.0"), 16) or ip.isInSubnet(QHostAddress("172.16.0.0"), 12):
                out.append(ip.toString())
    return sorted(set(out), key=lambda s: (not s.startswith("192.168."), s))


def strip_v4(addr):
    return addr.rsplit(":", 1)[-1] if addr.startswith("::ffff:") else addr


class Channel(QObject):
    """One TCP connection: framing plus the handshake and the encrypted messages."""
    message = Signal(object)
    plain = Signal(object)
    closed = Signal()

    def __init__(self, sock, parent=None):
        super().__init__(parent)
        self.sock = sock
        self.buf = b""
        self.send_key = self.recv_key = None
        self.sent = self.received = 0
        self.alive = True
        sock.readyRead.connect(self.on_ready)
        sock.disconnected.connect(self.on_closed)

    def peer(self):
        return strip_v4(self.sock.peerAddress().toString())

    def set_keys(self, send_key, recv_key):
        self.send_key, self.recv_key = ChaCha20Poly1305(send_key), ChaCha20Poly1305(recv_key)

    def write(self, data):
        if self.alive and len(data) <= MAX_FRAME + 64:
            self.sock.write(struct.pack(">I", len(data)) + data)

    def send_plain(self, obj):
        self.write(json.dumps(obj).encode())

    def send(self, obj):
        data = json.dumps(obj, separators=(",", ":")).encode()
        if len(data) > MAX_FRAME or self.send_key is None:
            return False
        nonce = b"\0\0\0\0" + struct.pack(">Q", self.sent)
        self.sent += 1
        self.write(self.send_key.encrypt(nonce, data, AAD))
        return True

    def on_ready(self):
        self.buf += bytes(self.sock.readAll())
        while self.alive and len(self.buf) >= 4:
            (n,) = struct.unpack(">I", self.buf[:4])
            if n > MAX_FRAME + 64:
                return self.close()
            if len(self.buf) < 4 + n:
                break
            frame, self.buf = self.buf[4:4 + n], self.buf[4 + n:]
            if self.recv_key is None:
                try:
                    obj = json.loads(frame)
                except ValueError:
                    return self.close()
                if not isinstance(obj, dict):
                    return self.close()
                self.plain.emit(obj)
                continue
            nonce = b"\0\0\0\0" + struct.pack(">Q", self.received)
            try:
                obj = json.loads(self.recv_key.decrypt(nonce, frame, AAD))
            except (InvalidTag, ValueError):
                return self.close(failed=True)
            self.received += 1
            if isinstance(obj, dict):
                self.message.emit(obj)

    def close_soon(self):
        """Lets the last message out before the connection is dropped."""
        self.sock.flush()
        QTimer.singleShot(400, self.close)

    def close(self, failed=False):
        self.failed = failed
        if self.alive:
            self.alive = False
            self.sock.abort()
            self.closed.emit()

    def on_closed(self):
        if self.alive:
            self.alive = False
            self.closed.emit()


class Member:
    def __init__(self, mid, name, color, channel=None):
        self.id, self.name, self.color, self.channel = mid, name, color, channel
        self.last = {}
        self.strikes = 0
        self.frames = []

    def info(self):
        return {"id": self.id, "name": self.name, "color": self.color, "owner": self.id == 0}


class LanService(QObject):
    state = Signal(str)                    # "off", "hosting", "connecting", "joined"
    members = Signal(list)
    chat = Signal(str, str)                # name, text
    letter = Signal(str, str, str, object)  # name, color, text, look
    visit = Signal(str, str, object)       # name, color, look
    notice = Signal(str)
    lobbies = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.role = None
        self.lobby_name = ""
        self.password = ""
        self.me = None
        self.roster = []
        self.server = None
        self.pending = {}                  # channel -> handshake data (host side)
        self.clients = {}                  # member id -> Member
        self.next_id = 1
        self.bans, self.fails = {}, {}
        self.salt = self.lobby_id = b""
        self.channel = None                # client side
        self.hs = None
        self.local_last = {}
        self.look_provider = None
        self.announcer = QTimer(self, timeout=self.announce)
        self.udp_out = QUdpSocket(self)
        self.udp_in = None
        self.browsing = False
        self.fail_reason = ""
        self.found = {}
        self.prune = QTimer(self, timeout=self.prune_found)

    # ------------------------------------------------------------ discovery
    def sync_listener(self):
        want = self.browsing or self.role == "host"
        if want and self.udp_in is None:
            sock = QUdpSocket(self)
            if sock.bind(QHostAddress.AnyIPv4, DISCOVERY_PORT,
                         QAbstractSocket.ShareAddress | QAbstractSocket.ReuseAddressHint):
                sock.readyRead.connect(self.read_announce)
                self.udp_in = sock
        elif not want and self.udp_in is not None:
            self.udp_in.close()
            self.udp_in = None
        if self.browsing and not self.prune.isActive():
            self.prune.start(2000)
        if not self.browsing:
            self.prune.stop()
            self.found = {}

    def browse(self, on):
        self.browsing = bool(on)
        self.sync_listener()
        if on:
            self.probe()

    def broadcast(self, data):
        """Sends to the broadcast address of every network card. A plain 255.255.255.255 only leaves through one
        card, which is often a virtual one (WSL, Hyper-V, VPN) and never reaches the real network."""
        sent = False
        for iface in QNetworkInterface.allInterfaces():
            flags = iface.flags()
            if not (flags & QNetworkInterface.IsUp and flags & QNetworkInterface.IsRunning) \
                    or flags & QNetworkInterface.IsLoopBack:
                continue
            for e in iface.addressEntries():
                if e.ip().protocol() == QAbstractSocket.IPv4Protocol and not e.broadcast().isNull():
                    self.udp_out.writeDatagram(data, e.broadcast(), DISCOVERY_PORT)
                    sent = True
        if not sent:
            self.udp_out.writeDatagram(data, QHostAddress.Broadcast, DISCOVERY_PORT)

    def probe(self):
        """Asks every host on the network to announce itself right now."""
        self.broadcast(json.dumps({"app": "smellyfish", "v": PROTOCOL, "q": 1}).encode())

    def announce(self):
        if self.role != "host" or self.server is None:
            return
        data = json.dumps({"app": "smellyfish", "v": PROTOCOL, "ver": __version__, "id": self.lobby_id.hex(),
                           "name": self.lobby_name, "port": self.server.serverPort(), "n": len(self.clients) + 1,
                           "max": MAX_MEMBERS}).encode()
        self.broadcast(data)

    def read_announce(self):
        while self.udp_in is not None and self.udp_in.hasPendingDatagrams():
            d = self.udp_in.receiveDatagram()
            data = bytes(d.data())
            if len(data) > 512:
                continue
            try:
                obj = json.loads(data)
                if obj.get("app") != "smellyfish":
                    continue
                if obj.get("q") == 1:
                    if self.role == "host":
                        self.announce()
                    continue
                lid, port = str(obj["id"])[:32], int(obj["port"])
                if not 1024 <= port <= 65535:
                    continue
                item = {"id": lid, "name": clean(obj.get("name"), 24) or "Lobby", "port": port,
                        "ip": strip_v4(d.senderAddress().toString()), "n": int(obj.get("n", 1)),
                        "max": int(obj.get("max", MAX_MEMBERS)), "seen": time.time(),
                        "ver": clean(obj.get("ver"), 12) or "?"}
                item["ok"] = obj.get("v") == PROTOCOL and compatible(item["ver"])
            except (ValueError, KeyError, TypeError):
                continue
            if lid == self.lobby_id.hex() and self.role == "host":
                continue
            if lid in self.found or len(self.found) < 20:
                self.found[lid] = item
        self.lobbies.emit(self.lobby_list())

    def lobby_list(self):
        return sorted(self.found.values(), key=lambda i: i["name"].lower())

    def prune_found(self):
        now = time.time()
        old = len(self.found)
        self.found = {k: v for k, v in self.found.items() if now - v["seen"] < 20}
        if len(self.found) != old:
            self.lobbies.emit(self.lobby_list())

    # ------------------------------------------------------------ host
    def host(self, name, color, lobby_name, password=None):
        """Opens a lobby; returns the password people need to join (or None when the port is unavailable)."""
        self.leave()
        wanted = (password or "").strip()
        if wanted and len(wanted) < MIN_PASSWORD:
            self.notice.emit(f"The password needs at least {MIN_PASSWORD} characters")
            return None
        self.password = wanted or make_password()
        self.salt, self.lobby_id = secrets.token_bytes(16), secrets.token_bytes(8)
        self.psk = stretch(self.password, self.salt)
        self.server = QTcpServer(self)
        if not (self.server.listen(QHostAddress.Any, DEFAULT_PORT) or self.server.listen(QHostAddress.Any, 0)):
            self.server = None
            self.notice.emit("Could not open a port for the lobby")
            return None
        self.server.newConnection.connect(self.on_connection)
        self.role = "host"
        self.lobby_name = clean(lobby_name, 24) or "Smellyfish lobby"
        self.me = Member(0, clean(name, NAME_LIMIT) or "Jelly", clean_color(color))
        self.clients, self.next_id = {}, 1
        self.announcer.start(5000)
        self.sync_listener()
        self.announce()
        self.state.emit("hosting")
        self.broadcast_members()
        return self.password

    def on_connection(self):
        while self.server is not None and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            ch = Channel(sock, self)
            ip = ch.peer()
            if self.bans.get(ip, 0) > time.time() or len(self.pending) >= MAX_MEMBERS + 2:
                ch.close()
                ch.deleteLater()
                continue
            timer = QTimer(self, singleShot=True, timeout=lambda c=ch: c.close())
            timer.start(HANDSHAKE_SECONDS * 1000)
            self.pending[ch] = {"timer": timer, "member": None, "ip": ip}
            ch.plain.connect(lambda obj, c=ch: self.host_hello(c, obj))
            ch.message.connect(lambda obj, c=ch: self.host_message(c, obj))
            ch.closed.connect(lambda c=ch: self.host_closed(c))

    def host_hello(self, ch, obj):
        info = self.pending.get(ch)
        if info is None or info["member"] is not None or ch.recv_key is not None:
            return ch.close()
        try:
            if obj.get("p") != PROTOCOL or not compatible(obj.get("ver", "0.0")):
                ch.send_plain({"err": "version", "p": PROTOCOL, "ver": __version__})
                return ch.close_soon()
            cpub, cr = bytes.fromhex(obj["k"]), bytes.fromhex(obj["r"])
            if len(cpub) != 32 or len(cr) != 16:
                raise ValueError
            eph = X25519PrivateKey.generate()
            spub, sr = raw_pub(eph), secrets.token_bytes(16)
            shared = eph.exchange(X25519PublicKey.from_public_bytes(cpub))
        except (KeyError, ValueError, TypeError):
            return ch.close()
        c2s, s2c = derive(shared, self.psk, cpub, spub, cr, sr)
        ch.send_plain({"k": spub.hex(), "r": sr.hex(), "s": self.salt.hex()})
        ch.set_keys(s2c, c2s)

    def host_message(self, ch, obj):
        info = self.pending.get(ch)
        if info is None:
            return ch.close()
        member = info["member"]
        if member is None:
            if obj.get("t") != "join" or len(self.clients) >= MAX_MEMBERS - 1:
                return ch.close()
            info["timer"].stop()
            name = clean(obj.get("name"), NAME_LIMIT) or "Guest"
            taken = {m.name.lower() for m in self.clients.values()} | {self.me.name.lower()}
            while name.lower() in taken:
                name = clean(name, NAME_LIMIT - 2) + str(secrets.randbelow(90) + 10)
            member = Member(self.next_id, name, clean_color(obj.get("color")), ch)
            self.next_id += 1
            info["member"] = member
            self.clients[member.id] = member
            self.fails.pop(info["ip"], None)
            ch.send({"t": "welcome", "id": member.id, "lobby": self.lobby_name, "members": self.roster_list()})
            self.broadcast_members()
            self.notice.emit(f"{member.name} joined")
            return
        now = time.time()
        member.frames = [t for t in member.frames if now - t < FLOOD_SECONDS] + [now]
        if len(member.frames) > FLOOD_FRAMES:
            return ch.close()
        self.dispatch(member, obj)

    def host_closed(self, ch):
        info = self.pending.pop(ch, None)
        if info is None:
            return
        info["timer"].stop()
        member = info["member"]
        if member is not None:
            self.clients.pop(member.id, None)
            self.broadcast_members()
            if not getattr(member, "kicked", False):
                self.notice.emit(f"{member.name} left")
        elif getattr(ch, "failed", False):
            ip = info["ip"]
            now = time.time()
            recent = [t for t in self.fails.get(ip, []) if now - t < BAN_SECONDS] + [now]
            self.fails[ip] = recent
            if len(recent) >= MAX_FAILS:
                self.bans[ip] = now + BAN_SECONDS
        ch.deleteLater()

    def kick(self, mid):
        """Owner only: removes someone from the lobby and keeps them out for a minute."""
        member = self.clients.get(mid) if self.role == "host" else None
        if member is None:
            return False
        member.kicked = True
        self.bans[member.channel.peer()] = time.time() + KICK_BAN
        member.channel.send({"t": "kicked"})
        member.channel.close_soon()
        self.notice.emit(f"{member.name} was removed")
        return True

    def roster_list(self):
        return [self.me.info()] + [m.info() for m in self.clients.values()]

    def broadcast_members(self):
        roster = self.roster_list()
        self.roster = roster
        self.members.emit(roster)
        for m in self.clients.values():
            m.channel.send({"t": "members", "members": roster})

    def allowed(self, member, kind):
        now = time.time()
        if now - member.last.get(kind, 0) < COOLDOWN[kind]:
            member.strikes += 1
            return False
        member.last[kind] = now
        return True

    def dispatch(self, member, obj):
        """Handles a message from a member (a remote one or the host itself)."""
        kind = obj.get("t")
        if kind not in COOLDOWN:
            return
        remote = member.channel is not None
        if not self.allowed(member, kind):
            if remote:
                member.channel.send({"t": "notice", "text": "Slow down a little"})
                if member.strikes >= STRIKES_TO_KICK:
                    member.channel.close()
            return
        if kind == "chat":
            text = clean(obj.get("text"), TEXT_LIMIT["chat"])
            if text:
                self.deliver(None, {"t": "chat", "name": member.name, "text": text})
        elif kind in ("letter", "visit"):
            target = obj.get("to")
            if not isinstance(target, int) or target == member.id:
                return
            msg = {"t": kind, "name": member.name, "color": member.color, "look": clean_look(obj.get("look"))}
            if kind == "letter":
                text = clean(obj.get("text"), TEXT_LIMIT["letter"])
                if not text:
                    return
                msg["text"] = text
            self.deliver(target, msg)

    def deliver(self, target, msg):
        """target None = everybody."""
        if target in (None, 0):
            self.receive(msg)
        for mid, m in self.clients.items():
            if target is None or target == mid:
                m.channel.send(msg)

    # ------------------------------------------------------------ client
    def join(self, ip, port, password, name, color):
        self.leave()
        self.role = "client"
        self.password = password
        self.hs = {"name": clean(name, NAME_LIMIT) or "Guest", "color": clean_color(color),
                   "eph": X25519PrivateKey.generate(), "r": secrets.token_bytes(16)}
        sock = QTcpSocket(self)
        self.channel = Channel(sock, self)
        self.channel.plain.connect(self.client_hello)
        self.channel.message.connect(self.client_message)
        self.channel.closed.connect(self.client_closed)
        sock.connected.connect(self.client_connected)
        sock.errorOccurred.connect(lambda _e: self.channel.close() if self.channel else None)
        self.timeout = QTimer(self, singleShot=True, timeout=self.connect_timeout)
        self.timeout.start(HANDSHAKE_SECONDS * 2000)
        self.state.emit("connecting")
        sock.connectToHost(ip, int(port))

    def connect_timeout(self):
        if self.channel is not None and self.me is None:
            self.channel.close()

    def client_connected(self):
        self.channel.send_plain({"p": PROTOCOL, "ver": __version__, "k": raw_pub(self.hs["eph"]).hex(),
                                 "r": self.hs["r"].hex()})

    def client_hello(self, obj):
        hs = self.hs
        if hs is None or self.channel.recv_key is not None:
            return self.channel.close()
        if obj.get("err") == "version":
            self.fail_reason = (f"That lobby runs Smellyfish {clean(obj.get('ver'), 12)} and you have "
                                f"{__version__}. Update so both match.")
            return self.channel.close()
        try:
            spub, sr, salt = bytes.fromhex(obj["k"]), bytes.fromhex(obj["r"]), bytes.fromhex(obj["s"])
            if len(spub) != 32 or len(sr) != 16 or len(salt) != 16:
                raise ValueError
            shared = hs["eph"].exchange(X25519PublicKey.from_public_bytes(spub))
        except (KeyError, ValueError, TypeError):
            return self.channel.close()
        cpub = raw_pub(hs["eph"])
        c2s, s2c = derive(shared, stretch(self.password, salt), cpub, spub, hs["r"], sr)
        self.channel.set_keys(c2s, s2c)
        self.channel.send({"t": "join", "name": hs["name"], "color": hs["color"]})

    def client_message(self, obj):
        kind = obj.get("t")
        if kind == "welcome" and self.me is None:
            self.timeout.stop()
            self.lobby_name = clean(obj.get("lobby"), 24)
            self.me = Member(int(obj.get("id", -1)), self.hs["name"], self.hs["color"])
            self.hs = None
            self.state.emit("joined")
            self.set_roster(obj.get("members"))
        elif self.me is None:
            self.channel.close()
        elif kind == "members":
            self.set_roster(obj.get("members"))
        elif kind == "kicked":
            self.fail_reason = "The lobby owner removed you."
            self.channel.close()
        elif kind in ("chat", "letter", "visit", "notice"):
            self.receive(obj)

    def set_roster(self, items):
        roster = []
        for it in (items if isinstance(items, list) else [])[:MAX_MEMBERS]:
            if isinstance(it, dict) and isinstance(it.get("id"), int):
                roster.append({"id": it["id"], "name": clean(it.get("name"), NAME_LIMIT),
                               "color": clean_color(it.get("color")), "owner": it.get("owner") is True})
        self.roster = roster
        self.members.emit(roster)

    def client_closed(self):
        joined = self.me is not None
        if self.role == "client":
            self.notice.emit(self.fail_reason or ("Left the lobby" if joined else
                                                  "Could not join: wrong password or no lobby there"))
            self.fail_reason = ""
            self.leave()

    # ------------------------------------------------------------ both
    def receive(self, msg):
        kind = msg.get("t")
        name = clean(msg.get("name"), NAME_LIMIT)
        if kind == "chat":
            self.chat.emit(name, clean(msg.get("text"), TEXT_LIMIT["chat"]))
        elif kind == "letter":
            self.letter.emit(name, clean_color(msg.get("color")), clean(msg.get("text"), TEXT_LIMIT["letter"]),
                             clean_look(msg.get("look")))
        elif kind == "visit":
            self.visit.emit(name, clean_color(msg.get("color")), clean_look(msg.get("look")))
        elif kind == "notice":
            self.notice.emit(clean(msg.get("text"), 80))

    def id_for(self, name):
        """Member id of the person with this name, or None when they are gone."""
        return next((m["id"] for m in self.roster if m["name"] == name), None)

    def cooldown_left(self, kind):
        return max(0.0, COOLDOWN[kind] - (time.time() - self.local_last.get(kind, 0)))

    def send(self, kind, **fields):
        """Returns "" when sent, otherwise a short reason."""
        if self.me is None or self.role is None:
            return "Not in a lobby"
        left = self.cooldown_left(kind)
        if left > 0:
            return f"Wait {int(left) + 1} s"
        if kind in TEXT_LIMIT and not clean(fields.get("text"), TEXT_LIMIT[kind]):
            return "Nothing to send"
        self.local_last[kind] = time.time()
        msg = dict(fields, t=kind)
        if kind in ("letter", "visit") and self.look_provider:
            msg["look"] = self.look_provider()
        if self.role == "host":
            self.dispatch(self.me, msg)
        else:
            self.channel.send(msg)
        return ""

    def leave(self):
        was = self.role is not None or self.me is not None
        self.announcer.stop()
        self.fail_reason = ""
        if self.channel is not None:
            ch, self.channel = self.channel, None
            self.role = None
            ch.close()
            ch.deleteLater()
        for ch in list(self.pending):
            ch.close()
        self.pending, self.clients = {}, {}
        if self.server is not None:
            self.server.close()
            self.server.deleteLater()
            self.server = None
        self.role, self.me, self.hs, self.roster = None, None, None, []
        self.local_last = {}
        if was:
            self.members.emit([])
        self.sync_listener()
        self.state.emit("off")
