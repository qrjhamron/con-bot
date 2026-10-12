"""Game chat over the chat WebSocket (wss://chatServer:8925).

Protocol mirrored from the game client: JSON envelopes
{command, arguments, requestID, version, client, modID?, ...userData},
opcodes /join /talk /whisper. Scope: public rooms of our own game only
(ingame_<gameID>); whispers are send-only for explicit diplomacy, never
intercepted. Network may be unavailable from some hosts (port filtered).
"""
import json
import time

CHAT_VERSION = '374'
CHAT_CLIENT = 'con-client'
JOIN = '/join'
TALK = '/talk'
WHISPER = '/whisper'

PUBLIC_ROOM_PREFIXES = ('ingame_', 'global', 'help', 'confrontline', 'security council')


def build_message(command, arguments, userdata, mod_id=None, request_id=1):
    """Envelope persis klien; userdata = param play.php + siteUserID."""
    message = {'command': command, 'arguments': list(arguments),
               'requestID': request_id, 'version': CHAT_VERSION, 'client': CHAT_CLIENT}
    if mod_id is not None:
        message['modID'] = mod_id
    if isinstance(userdata, dict):
        message.update(userdata)
    return message


def is_public_room(room):
    """Hanya room publik; whisper/private tidak dibuka untuk baca."""
    if not isinstance(room, str) or not room:
        return False
    lowered = room.lower()
    return lowered.startswith(PUBLIC_ROOM_PREFIXES)


def parse_message(raw):
    """Pesan masuk jadi dict rapi; rusak jadi {}."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode('utf-8', 'replace')
        except Exception:
            return {}
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    text = data.get('text', data.get('message', data.get('body', '')))
    return {'room': str(data.get('room', data.get('roomName', '?'))),
            'author': str(data.get('author', data.get('userName', data.get('username', '?')))),
            'site_user_id': data.get('siteUserID', data.get('siteUserId', data.get('userID', 0))),
            'text': str(text or '')[:1000],
            'received_at': data.get('receivedTime', data.get('timestamp', 0)),
            'kind': str(data.get('type', data.get('@c', '?')))}


class ChatClient:
    """Koneksi chat sekali pakai: join room publik, baca, kirim, tutup."""

    def __init__(self, chat_server, userdata, mod_id=None, timeout=15):
        self.url = f'wss://{chat_server}:8925/'
        self.userdata = userdata if isinstance(userdata, dict) else {}
        self.mod_id = mod_id
        self.timeout = timeout
        self._ws = None
        self._request_id = 0

    def connect(self):
        import websocket
        self._ws = websocket.create_connection(self.url, timeout=self.timeout)
        return True

    def send_command(self, command, arguments):
        if self._ws is None:
            raise RuntimeError('Belum connect ke server chat.')
        self._request_id += 1
        self._ws.send(json.dumps(build_message(command, arguments, self.userdata,
                                               self.mod_id, self._request_id)))
        return self._request_id

    def join(self, room):
        if not is_public_room(room):
            raise ValueError(f'Room privat tidak dibuka: {room}')
        return self.send_command(JOIN, [room])

    def talk(self, room, text):
        if not is_public_room(room):
            raise ValueError(f'Room privat tidak dibuka: {room}')
        text = str(text or '').strip()
        if not text:
            raise ValueError('Pesan kosong.')
        return self.send_command(TALK, [room, text[:500]])

    def whisper(self, site_user_id, text):
        try:
            target = int(site_user_id)
        except (TypeError, ValueError):
            raise ValueError('site_user_id harus angka.')
        text = str(text or '').strip()
        if not text:
            raise ValueError('Pesan kosong.')
        return self.send_command(WHISPER, [target, text[:500]])

    def read(self, duration=10):
        """Kumpulkan pesan masuk selama durasi detik."""
        if self._ws is None:
            raise RuntimeError('Belum connect ke server chat.')
        import websocket as _wsmod
        deadline = time.time() + max(1, duration)
        messages = []
        while time.time() < deadline:
            self._ws.settimeout(max(0.5, deadline - time.time()))
            try:
                parsed = parse_message(self._ws.recv())
            except _wsmod.WebSocketTimeoutException:
                break
            except Exception:
                break
            if parsed:
                messages.append(parsed)
        return messages

    def close(self):
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
