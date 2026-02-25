#!/usr/bin/env python3
"""Terminal UI agent using Gradient SDK (OpenAI-compatible)."""

import sys, os, json, time, traceback, textwrap, re

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Auto-load .env
_env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                _v = _v.strip().strip("'").strip('"')
                os.environ.setdefault(_k.strip(), _v)

import requests as http_requests
from actions import TOOLS, refresh, _connect

API_KEY = os.environ.get('GRADIENT_API_KEY', '')
API_URL = os.environ.get('GRADIENT_API_URL', 'https://inference.do-ai.run/v1/chat/completions')
MODEL = os.environ.get('GRADIENT_MODEL', 'llama3.3-70b-instruct')
FALLBACK_MODELS = ['llama3.3-70b-instruct', 'deepseek-r1-distill-llama-70b', 'mistral-nemo-instruct-2407']

SYSTEM_PROMPT = """Kamu adalah AI Commander untuk game Supremacy: World War 3 (Conflict of Nations).
Kamu mengendalikan Nigeria (Player 88) di game 10687600, speed 4x.

ATURAN PENTING:
1. Kamu BUKAN coding agent. Kamu TIDAK menulis kode. Kamu LANGSUNG menjalankan aksi game.
2. Ketika user minta sesuatu, LANGSUNG panggil tool/function yang tersedia.
3. Bicara Bahasa Indonesia casual (kayak ngobrol sama teman).
4. SEBELUM melakukan aksi di kota tertentu, SELALU panggil get_cities_detail dulu untuk mendapatkan city_id yang valid.
5. SEBELUM move army, panggil get_armies_detail dulu untuk mendapatkan army_id yang valid.
6. Setelah aksi, laporkan hasilnya dengan jelas dan ringkas.
7. Jika user minta search/cari info, gunakan tool search_web.
8. Untuk SEMUA tool yang menerima player — kamu bisa pakai NAMA NEGARA (misal "Ghana", "Mali") atau angka ID.
9. Jika user bilang "semua kota" atau "all cities", gunakan build_in_all_cities atau auto_produce, JANGAN loop manual.
10. Jika aksi gagal, jelaskan kenapa dan sarankan alternatif.

KONTEKS:
- Main sebagai Nigeria (P88) di Afrika
- Teman: Morocco (P87, "edSheeran.") — JANGAN SERANG!
- Intel allies: China (P5), Philippines (P48), Kyrgyzstan (P42)
- Target: semua AI bot lemah (Ghana P29, Niger P121, South Sudan P124, Sudan P146, Mali P32, dll)

UNIT: infantry, motorized_infantry (mot), attack_helicopter (heli), mbt (tank), sam, recon, artillery, mlrs, strike_fighter, bomber
UNIT CATEGORIES: infantry(land), armored(land), support(land), helicopter(air), fighter(air), heavy(air), naval(sea), submarine(sea), missile(strategic)
BUILDING: army_base, recruiting_office, local_industry, arms_industry, airbase, barracks, propaganda, research_lab
CITY TYPES: hometown (full production, high morale), occupied (25% resources, no mobilization), annexed (50% resources, can mobilize)

SHORTCUT TOOLS:
- auto_conquer = kirim semua idle army ke musuh terdekat otomatis
- auto_produce = produce unit di semua kota idle otomatis
- auto_build_infrastructure = bangun building penting di kota yang butuh
- full_conquest_cycle = declare war + conquer + produce + build SEKALIGUS
- build_in_all_cities("recruiting_office") = bangun recruiting office di SEMUA kota
- declare_war_on_all_bots = declare war ke SEMUA bot lemah sekaligus
- move_all_idle_to_target("Ghana") = kirim SEMUA army idle ke Ghana
- scan_threats = deteksi musuh mendekat ke wilayah kita
- smart_expansion = analisis target ekspansi paling gampang
- search_web("query") = cari info strategi dari internet

Kamu commander agresif, efisien, dan selalu cari keuntungan maksimal.

CARA PANGGIL TOOL: Respond HANYA dengan JSON ini (TANPA markdown/explanation):
{"name": "function_name", "parameters": {"key": "value"}}
Contoh: {"name": "get_status", "parameters": {}}
Contoh: {"name": "produce_unit", "parameters": {"city_id": 612, "unit_type": 3294}}
JANGAN tulis ```json atau penjelasan. LANGSUNG JSON saja."""


def _build_tools_prompt():
    """Build a tool list description for models that don't support function calling."""
    lines = ["AVAILABLE TOOLS (call by responding with JSON):"]
    for tool in TOOLS:
        params = ', '.join(f'{k}: {v.get("type","string")}' for k, v in tool.get('parameters', {}).items())
        lines.append(f'  {tool["name"]}({params}) - {tool["description"]}')
    lines.append('  search_web(query: string) - Search the web for game strategies')
    lines.append('')
    lines.append('To call a tool, respond with ONLY this JSON format (no markdown, no explanation):')
    lines.append('{"name": "function_name", "parameters": {"key": "value"}}')
    lines.append('')
    lines.append('After getting the result, explain it to the user in Bahasa Indonesia.')
    return '\n'.join(lines)


_TOOL_NAMES = {t['name'] for t in TOOLS} | {'search_web'}


def _parse_text_tool_call(text):
    """Extract tool call from text response when model doesn't use function calling.
    
    Returns list of (name, args) tuples, or empty list if no tool call found.
    """
    calls = []
    seen = set()
    patterns = [
        re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL),
        re.compile(r'(\{"name"\s*:\s*"[^"]+"\s*,\s*"parameters"\s*:\s*\{.*?\}\s*\})', re.DOTALL),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            try:
                obj = json.loads(match.group(1))
                name = obj.get('name', '')
                params = obj.get('parameters', obj.get('params', obj.get('arguments', {})))
                if name in _TOOL_NAMES:
                    key = (name, json.dumps(params, sort_keys=True))
                    if key not in seen:
                        seen.add(key)
                        calls.append((name, params if isinstance(params, dict) else {}))
            except (json.JSONDecodeError, TypeError):
                continue
    return calls


def _build_openai_tools():
    """Convert TOOLS list to OpenAI function calling format."""
    result = []
    for tool in TOOLS:
        params = {"type": "object", "properties": {}, "required": []}
        for pname, pinfo in tool.get('parameters', {}).items():
            ptype = pinfo.get('type', 'string')
            json_type = {'integer': 'integer', 'int': 'integer', 'number': 'number',
                         'float': 'number', 'boolean': 'boolean', 'bool': 'boolean'
                         }.get(ptype, 'string')
            params['properties'][pname] = {
                'type': json_type,
                'description': pinfo.get('description', ''),
            }
            params['required'].append(pname)
        result.append({
            'type': 'function',
            'function': {
                'name': tool['name'],
                'description': tool['description'],
                'parameters': params,
            }
        })
    # Add web search tool
    result.append({
        'type': 'function',
        'function': {
            'name': 'search_web',
            'description': 'Search the web for game strategies, tips, guides, or any information',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string', 'description': 'Search query'},
                },
                'required': ['query'],
            }
        }
    })
    return result


def search_web(query: str) -> dict:
    """Search the web using DuckDuckGo HTML."""
    try:
        r = http_requests.get(
            'https://html.duckduckgo.com/html/',
            params={'q': query},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=10,
        )
        results = []
        for match in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', r.text):
            url, title = match.groups()
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title:
                results.append({'title': title, 'url': url})
        # Extract snippets
        for i, match in enumerate(re.finditer(r'<a class="result__snippet"[^>]*>(.*?)</a>', r.text)):
            snippet = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if i < len(results):
                results[i]['snippet'] = snippet
        return {'results': results[:5], 'query': query}
    except Exception as e:
        return {'error': str(e), 'query': query}


def _execute_function(name: str, args: dict) -> str:
    """Execute a tool function by name."""
    if name == 'search_web':
        result = search_web(args.get('query', ''))
        return json.dumps(result, default=str, ensure_ascii=False)

    tool_map = {t['name']: t['fn'] for t in TOOLS}
    fn = tool_map.get(name)
    if not fn:
        return json.dumps({'error': f'Unknown function: {name}'})
    try:
        params = {}
        tool_def = next((t for t in TOOLS if t['name'] == name), {})
        for pname, pinfo in tool_def.get('parameters', {}).items():
            if pname in args:
                ptype = pinfo.get('type', 'string')
                val = args[pname]
                if ptype in ('integer', 'int'):
                    val = int(val)
                elif ptype in ('number', 'float'):
                    val = float(val)
                params[pname] = val
        result = fn(**params)
        return json.dumps(result, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e), 'trace': traceback.format_exc()})


class GradientAgent:
    """AI Agent using Gradient SDK (OpenAI-compatible API)."""

    def __init__(self, api_key=None):
        self.api_key = api_key or API_KEY
        if not self.api_key:
            raise ValueError("API key required! Set GRADIENT_API_KEY env var.")
        self.model = MODEL
        self.tools = _build_openai_tools()
        self.messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        self.log = []  # TUI log buffer
        self.verbose = True

    def _log(self, msg):
        self.log.append(msg)
        if self.verbose:
            print(msg)

    def _api_call(self, messages, tools=None):
        """Make API call with model fallback."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        models_to_try = [self.model] + [m for m in FALLBACK_MODELS if m != self.model]

        for model in models_to_try:
            data = {
                'model': model,
                'messages': messages,
                'max_tokens': 2000,
            }
            if tools:
                data['tools'] = tools
                data['tool_choice'] = 'auto'
            try:
                r = http_requests.post(API_URL, headers=headers, json=data, timeout=60)
                if r.status_code == 200:
                    self.model = model
                    return r.json()
                elif r.status_code == 429:
                    self._log(f"  [WAIT] Rate limited on {model}, trying next...")
                    continue
                elif r.status_code == 401:
                    self._log(f"  [WARN] {model} not available, trying next...")
                    continue
                else:
                    self._log(f"  [ERR] {model}: HTTP {r.status_code}")
                    continue
            except Exception as e:
                self._log(f"  [ERR] {model}: {e}")
                continue

        return None

    def _trim_history(self, max_messages=40):
        """Keep conversation history bounded to prevent token overflow."""
        if len(self.messages) <= max_messages:
            return
        # Keep system prompt + last N messages
        self.messages = [self.messages[0]] + self.messages[-(max_messages - 1):]

    def execute(self, user_message: str) -> str:
        """Process user message, execute tools, return response."""
        self.messages.append({'role': 'user', 'content': user_message})
        self._trim_history()

        max_rounds = 10
        for round_num in range(max_rounds):
            resp = self._api_call(self.messages, self.tools)
            if not resp:
                return "[ERR] All models failed. Check API key and connection."

            choice = resp.get('choices', [{}])[0]
            msg = choice.get('message', {})

            # Check for native tool calls (OpenAI-compatible)
            tool_calls = msg.get('tool_calls', [])
            if tool_calls:
                self.messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get('function', {})
                    name = fn.get('name', '')
                    try:
                        args = json.loads(fn.get('arguments', '{}'))
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    tc_id = tc.get('id', f'call_{round_num}')
                    args_str = ', '.join(f'{k}={v}' for k, v in args.items())
                    self._log(f"  [CALL] {name}({args_str})")
                    result_str = _execute_function(name, args)
                    preview = result_str[:200] + '...' if len(result_str) > 200 else result_str
                    self._log(f"  [RESULT] {preview}")
                    self.messages.append({
                        'role': 'tool', 'tool_call_id': tc_id, 'content': result_str,
                    })
                continue

            # Text response — check if it contains a tool call in text
            content = msg.get('content', '')
            if content:
                text_calls = _parse_text_tool_call(content)
                if text_calls:
                    self.messages.append({'role': 'assistant', 'content': content})
                    all_results = []
                    for name, args in text_calls:
                        args_str = ', '.join(f'{k}={v}' for k, v in args.items())
                        self._log(f"  [CALL] {name}({args_str})")
                        result_str = _execute_function(name, args)
                        preview = result_str[:200] + '...' if len(result_str) > 200 else result_str
                        self._log(f"  [RESULT] {preview}")
                        all_results.append(f"Result of {name}: {result_str}")
                    # Feed results back so model can summarize
                    self.messages.append({
                        'role': 'user',
                        'content': f"[TOOL RESULTS]\n" + "\n".join(all_results) + "\n\nJelaskan hasilnya ke user dalam Bahasa Indonesia. JANGAN panggil tool lagi.",
                    })
                    continue

                self.messages.append({'role': 'assistant', 'content': content})
                return content
            return '(no response)'

        return "[WARN] Max rounds reached."

    def connect_game(self):
        """Connect to the game server."""
        self._log("[CONN] Connecting to game server...")
        try:
            _connect()
            self._log("[OK] Connected!")
        except Exception as e:
            self._log(f"[ERR] Connection failed: {e}")
            self._log("[WARN] Agent will work but game actions will fail until reconnected.")


def run_tui(agent):
    """Run the TUI interface."""
    try:
        import curses
        curses.wrapper(lambda stdscr: _tui_main(stdscr, agent))
    except ImportError:
        print("[WARN] curses not available, falling back to simple mode")
        run_simple(agent)
    except Exception as e:
        print(f"[WARN] TUI error: {e}, falling back to simple mode")
        run_simple(agent)


def _tui_main(stdscr, agent):
    """Main TUI loop using curses."""
    import curses
    curses.curs_set(1)
    stdscr.nodelay(False)
    stdscr.timeout(-1)

    # Colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)    # header/success
    curses.init_pair(2, curses.COLOR_CYAN, -1)      # tool calls
    curses.init_pair(3, curses.COLOR_YELLOW, -1)    # user input/status
    curses.init_pair(4, curses.COLOR_RED, -1)       # errors
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_CYAN)   # header bar
    curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_GREEN)  # status bar
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLUE)   # input line
    curses.init_pair(8, curses.COLOR_MAGENTA, -1)   # agent response

    output_lines = []
    input_buf = ""
    input_cursor = 0
    scroll_offset = 0
    processing = False
    cmd_history = []
    history_idx = -1
    game_info = {'day': '?', 'vp': '?', 'provs': '?'}
    tool_count = 0

    def add_output(text, color_pair=0):
        for line in text.split('\n'):
            max_w = curses.COLS - 2 if curses.COLS > 10 else 78
            wrapped = textwrap.wrap(line, width=max_w) if line.strip() else ['']
            for w in wrapped:
                output_lines.append((w, color_pair))

    def draw():
        nonlocal scroll_offset
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if h < 6 or w < 20:
            return

        header = f" SWW3 AI COMMANDER  |  Nigeria (P88)  |  {agent.model}  |  {len(TOOLS)+1} tools "
        try:
            stdscr.addnstr(0, 0, header.center(w), w, curses.color_pair(5) | curses.A_BOLD)
        except curses.error:
            pass

        output_h = h - 4  # header(1) + separator(1) + input(1) + status(1)
        if scroll_offset > max(0, len(output_lines) - output_h):
            scroll_offset = max(0, len(output_lines) - output_h)

        if scroll_offset > 0:
            start = max(0, len(output_lines) - output_h - scroll_offset)
            visible = output_lines[start:start + output_h]
        else:
            visible = output_lines[-output_h:] if len(output_lines) > output_h else output_lines

        for i, item in enumerate(visible):
            row = i + 1  # offset by header
            if row >= h - 3:
                break
            if isinstance(item, tuple):
                text, cp = item
            else:
                text, cp = str(item), 0
            try:
                stdscr.addnstr(row, 0, text, w - 1, curses.color_pair(cp))
            except curses.error:
                pass

        sep_y = h - 3
        scroll_ind = f" [scroll:{scroll_offset}]" if scroll_offset > 0 else ""
        help_text = f" /help /status /search /conquer /quit{scroll_ind} "
        sep = "─" * max(0, w - len(help_text)) + help_text
        try:
            stdscr.addnstr(sep_y, 0, sep[:w], w, curses.color_pair(3))
        except curses.error:
            pass

        input_y = h - 2
        prompt = "> "
        try:
            stdscr.addstr(input_y, 0, prompt, curses.color_pair(7) | curses.A_BOLD)
            display_buf = input_buf
            max_input = w - len(prompt) - 1
            if max_input > 0:
                if len(display_buf) > max_input:
                    display_buf = display_buf[-(max_input):]
                stdscr.addnstr(input_y, len(prompt), display_buf, max_input)
        except curses.error:
            pass

        status_y = h - 1
        if processing:
            elapsed = time.time() - processing if isinstance(processing, float) else 0
            status = f" PROCESSING... ({elapsed:.0f}s)  |  tools called: {tool_count}"
            cp = 4
        else:
            status = f" Day {game_info['day']} | VP {game_info['vp']} | {game_info['provs']} provs | {len(output_lines)} lines | {len(cmd_history)} cmds"
            cp = 6
        try:
            stdscr.addnstr(status_y, 0, status.ljust(w), w, curses.color_pair(cp) | curses.A_BOLD)
        except curses.error:
            pass

        # Cursor
        cx = len(prompt) + min(input_cursor, max(0, (w - len(prompt) - 1)))
        try:
            stdscr.move(input_y, min(cx, w - 1))
        except curses.error:
            pass

        stdscr.refresh()

    # Override agent log
    agent.verbose = False
    def tui_log(msg):
        nonlocal tool_count
        if '[CALL]' in msg:
            tool_count += 1
            add_output(msg, 2)
        elif '[RESULT]' in msg:
            add_output(msg, 2)
        elif '[ERR]' in msg:
            add_output(msg, 4)
        elif '[OK]' in msg or '[CONN]' in msg:
            add_output(msg, 1)
        elif '[WAIT]' in msg or '[RETRY]' in msg:
            add_output(msg, 3)
        else:
            add_output(msg, 3)
        draw()
    agent._log = tui_log

    add_output("SWW3 AI COMMANDER", 1)
    add_output("", 0)
    add_output("  /status   game dashboard        /conquer  full conquest cycle", 1)
    add_output("  /threats  scan enemy movement    /expand   expansion targets", 1)
    add_output("  /armies   list armies            /cities   list cities", 1)
    add_output("  /search Q web search             /help     all shortcuts", 1)
    add_output("  /quit     exit", 1)
    add_output("")

    # Connect
    try:
        agent.connect_game()
        add_output("[OK] Game server connected!", 1)
    except Exception as e:
        add_output(f"[ERR] Connection failed: {e}", 4)

    draw()

    # Slash command shortcuts
    SLASH_CMDS = {
        '/status': 'Cek status game sekarang: day, VP, provinces, resources, armies, production, wars',
        '/conquer': 'Jalankan full conquest cycle: declare war semua bot, kirim army, produce, build',
        '/threats': 'Scan ancaman: ada musuh yang mendekat ke wilayah kita?',
        '/expand': 'Analisis target ekspansi paling gampang dan optimal',
        '/armies': 'Tampilkan semua army kita dengan detail unit, HP, lokasi',
        '/cities': 'Tampilkan semua kota kita dengan buildings dan produksi',
        '/resources': 'Tampilkan semua resource detail: amount, production, consumption',
        '/ranking': 'Tampilkan leaderboard ranking VP top 20',
        '/produce': 'Auto produce unit di semua kota yang idle',
        '/build': 'Auto build infrastructure di kota yang butuh',
        '/battles': 'Cek active battles dan combat log',
        '/spies': 'Cek spy kita: status, lokasi, misi',
    }

    while True:
        try:
            ch = stdscr.getch()
        except (KeyboardInterrupt, Exception):
            break

        if ch == curses.KEY_RESIZE:
            draw()
            continue

        if ch == 10 or ch == 13:  # Enter
            cmd = input_buf.strip()
            input_buf = ""
            input_cursor = 0
            history_idx = -1

            if not cmd:
                draw()
                continue

            # Save to history
            if not cmd_history or cmd_history[-1] != cmd:
                cmd_history.append(cmd)

            if cmd.lower() in ('/quit', '/exit', '/q'):
                break

            if cmd.lower() == '/help':
                add_output("\n[HELP] Shortcuts:", 3)
                for sc, desc in SLASH_CMDS.items():
                    add_output(f"  {sc:12s} — {desc}", 2)
                add_output("")
                draw()
                continue

            if cmd.lower() == '/clear':
                output_lines.clear()
                scroll_offset = 0
                draw()
                continue

            # Resolve slash commands
            slash_key = cmd.lower().split()[0] if cmd.startswith('/') else None
            if slash_key in SLASH_CMDS:
                cmd = SLASH_CMDS[slash_key]
            elif cmd.lower().startswith('/search '):
                cmd = f"Search web: {cmd[8:]}"

            add_output(f"\n{'─'*40}", 3)
            add_output(f"[>] You > {cmd}", 3)
            scroll_offset = 0
            draw()

            processing = time.time()
            tool_count = 0
            draw()

            try:
                result = agent.execute(cmd)
                add_output(f"\n[BOT] Agent >\n{result}", 8)
                if 'day' in str(agent.messages[-2:]).lower():
                    try:
                        for m in reversed(agent.messages):
                            if m.get('role') == 'tool':
                                data = json.loads(m.get('content', '{}'))
                                if 'day' in data:
                                    game_info['day'] = data.get('day', '?')
                                    game_info['vp'] = data.get('vp', '?')
                                    game_info['provs'] = data.get('provinces', '?')
                                    break
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
            except Exception as e:
                add_output(f"\n[ERR] Error: {e}", 4)

            processing = False
            add_output("")
            draw()

        elif ch == curses.KEY_BACKSPACE or ch == 127 or ch == 8:
            if input_cursor > 0:
                input_buf = input_buf[:input_cursor-1] + input_buf[input_cursor:]
                input_cursor -= 1
            draw()

        elif ch == curses.KEY_LEFT:
            input_cursor = max(0, input_cursor - 1)
            draw()

        elif ch == curses.KEY_RIGHT:
            input_cursor = min(len(input_buf), input_cursor + 1)
            draw()

        elif ch == curses.KEY_UP:
            if cmd_history:
                if history_idx == -1:
                    history_idx = len(cmd_history) - 1
                elif history_idx > 0:
                    history_idx -= 1
                input_buf = cmd_history[history_idx]
                input_cursor = len(input_buf)
            draw()

        elif ch == curses.KEY_DOWN:
            if history_idx >= 0:
                history_idx += 1
                if history_idx >= len(cmd_history):
                    history_idx = -1
                    input_buf = ""
                else:
                    input_buf = cmd_history[history_idx]
                input_cursor = len(input_buf)
            draw()

        elif ch == curses.KEY_PPAGE:  # Page Up
            scroll_offset = min(scroll_offset + 15, max(0, len(output_lines) - 5))
            draw()

        elif ch == curses.KEY_NPAGE:  # Page Down
            scroll_offset = max(0, scroll_offset - 15)
            draw()

        elif 32 <= ch <= 126:  # Printable
            input_buf = input_buf[:input_cursor] + chr(ch) + input_buf[input_cursor:]
            input_cursor += 1
            history_idx = -1
            draw()

        elif ch == 21:  # Ctrl+U: clear line
            input_buf = ""
            input_cursor = 0
            draw()

        elif ch == 12:  # Ctrl+L: clear screen
            output_lines.clear()
            scroll_offset = 0
            draw()


def run_simple(agent):
    print(f"SWW3 AI COMMANDER (simple mode) | {agent.model}")
    print("Type commands or /quit to exit.\n")

    agent.connect_game()
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ('/quit', '/exit', '/q', 'quit', 'exit'):
            break

        if user_input.lower() == '/status':
            user_input = "cek status game sekarang"
        if user_input.lower().startswith('/search '):
            user_input = f"search web: {user_input[8:]}"

        print()
        result = agent.execute(user_input)
        print(f"\n[BOT] Agent > {result}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='SWW3 AI Commander TUI')
    parser.add_argument('command', nargs='*', help='Single command to execute')
    parser.add_argument('--auto', action='store_true', help='Auto-play mode')
    parser.add_argument('--interval', type=int, default=30, help='Auto-play interval (min)')
    parser.add_argument('--simple', action='store_true', help='Simple mode (no TUI)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Hide tool details')
    parser.add_argument('--model', type=str, help='Override model name')
    args = parser.parse_args()

    if not API_KEY:
        print("Error: GRADIENT_API_KEY not set")
        sys.exit(1)

    agent = GradientAgent()
    if args.quiet:
        agent.verbose = False
    if args.model:
        agent.model = args.model

    if args.auto:
        agent.connect_game()
        print(f"Auto-play: conquest cycle every {args.interval} min")
        while True:
            print(f"\n{'='*50}")
            print(f"{time.strftime('%H:%M:%S')} running cycle...")
            try:
                result = agent.execute("Jalankan full conquest cycle dan laporkan hasilnya.")
                print(f"\n{result}")
            except Exception as e:
                print(f"Error: {e}")
            print(f"Next in {args.interval} min...")
            try:
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                break
        return

    if args.command:
        agent.connect_game()
        cmd = ' '.join(args.command)
        result = agent.execute(cmd)
        print(f"\n{result}")
        return

    if args.simple:
        run_simple(agent)
    else:
        run_tui(agent)


if __name__ == '__main__':
    main()
