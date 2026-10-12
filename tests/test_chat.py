from sww3bot import chat as chat_mod


def test_envelope_matches_client_spec():
    userdata = {'siteUserID': 7, 'gameID': 10928316, 'auth': 'A'}
    message = chat_mod.build_message('/join', ['ingame_10928316'], userdata, mod_id=60,
                                     request_id=3)
    assert message['command'] == '/join'
    assert message['arguments'] == ['ingame_10928316']
    assert message['requestID'] == 3
    assert message['version'] == '374'
    assert message['client'] == 'con-client'
    assert message['modID'] == 60
    assert message['siteUserID'] == 7 and message['auth'] == 'A'
    bare = chat_mod.build_message('/talk', ['r', 'hi'], None)
    assert 'modID' not in bare and bare['arguments'] == ['r', 'hi']


def test_public_room_policy():
    assert chat_mod.is_public_room('ingame_10928316')
    assert chat_mod.is_public_room('Global_en')
    assert not chat_mod.is_public_room('whisper_7_9')
    assert not chat_mod.is_public_room('')
    assert not chat_mod.is_public_room(None)


def test_parse_message_shapes():
    assert chat_mod.parse_message('') == {}
    assert chat_mod.parse_message('bukan json') == {}
    assert chat_mod.parse_message('[1,2]') == {}
    parsed = chat_mod.parse_message(
        '{"room": "ingame_1", "author": "Bos", "siteUserID": 9, '
        '"text": "damai?", "receivedTime": 123}')
    assert parsed['room'] == 'ingame_1' and parsed['author'] == 'Bos'
    assert parsed['site_user_id'] == 9 and parsed['text'] == 'damai?'


class FakeWs:
    def __init__(self, incoming=None):
        self.sent = []
        self.incoming = list(incoming or [])
        self.closed = False

    def send(self, payload):
        self.sent.append(payload)

    def settimeout(self, value):
        pass

    def recv(self):
        if not self.incoming:
            import websocket
            raise websocket.WebSocketTimeoutException('habis')
        return self.incoming.pop(0)

    def close(self):
        self.closed = True


def test_client_guards_and_envelopes():
    client = chat_mod.ChatClient('x.test', {'siteUserID': 7})
    client._ws = FakeWs()
    assert client.join('ingame_1') == 1
    assert client.talk('ingame_1', 'halo semua') == 2
    try:
        client.join('whisper_7_9')
        raise AssertionError('room privat harus ditolak')
    except ValueError:
        pass
    try:
        client.talk('ingame_1', '   ')
        raise AssertionError('pesan kosong harus ditolak')
    except ValueError:
        pass
    assert client.whisper(9, 'damai?') == 3
    import json
    first = json.loads(client._ws.sent[0])
    assert first['command'] == '/join' and first['siteUserID'] == 7
    third = json.loads(client._ws.sent[2])
    assert third['command'] == '/whisper' and third['arguments'][0] == 9


def test_client_read_collects_and_closes():
    client = chat_mod.ChatClient('x.test', {})
    client._ws = FakeWs(['{"room": "ingame_1", "author": "A", "text": "hi"}', 'rusak'])
    messages = client.read(duration=5)
    assert len(messages) == 1 and messages[0]['author'] == 'A'
    client.close()
    assert client._ws is None
