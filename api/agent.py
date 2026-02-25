#!/usr/bin/env python3
"""
SWW3 AI Agent — Gemini-powered game commander.

Not a coding agent. This agent UNDERSTANDS natural language commands
(Indonesian or English) and EXECUTES real game actions.

Usage:
    python agent.py                    # Interactive mode
    python agent.py "bangun army base" # Single command mode
    python agent.py --auto             # Auto-play mode (full cycle every N minutes)
"""

import sys, os, json, time, traceback, warnings

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import google.generativeai as genai
from actions import TOOLS, refresh, _connect

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDNPeqNhDlv7tP3u-NHuHQ2cRizv68IATw')
MODEL_NAME = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
FALLBACK_MODELS = ['gemini-2.5-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-flash']
API_KEYS = [
    'AIzaSyDNPeqNhDlv7tP3u-NHuHQ2cRizv68IATw',
    'AIzaSyDFpPci4kCLVC43VvPNb1dNF-FH_iYylvY',
]

SYSTEM_PROMPT = """Kamu adalah AI Commander untuk game Supremacy: World War 3 (Conflict of Nations).
Kamu mengendalikan Nigeria (Player 88) di game 10687600, speed 4x.

ATURAN PENTING:
1. Kamu BUKAN coding agent. Kamu TIDAK menulis kode. Kamu LANGSUNG menjalankan aksi game.
2. Ketika user minta sesuatu, kamu LANGSUNG panggil tool/function yang tersedia untuk menjalankannya.
3. Selalu bicara dalam Bahasa Indonesia yang casual (kayak ngobrol sama teman).
4. Sebelum mengambil aksi besar, panggil get_status atau get_cities_detail dulu untuk lihat kondisi terkini.
5. Setelah menjalankan aksi, laporkan hasilnya dengan jelas.

KONTEKS GAME:
- Kamu main sebagai Nigeria (P88) di Afrika
- Teman dekat: Morocco (P87, player "edSheeran.") — jangan serang!
- Intel allies: China (P5), Philippines (P48), Kyrgyzstan (P42)
- Target utama: semua AI bot lemah di sekitar (Ghana, Niger, South Sudan, Sudan, dll)
- Resource penting: Money, Manpower, Metal, Oil, Electronics
- Unit favorit: Motorized Infantry, Attack Helicopter, MBT

BUILDING TYPES:
army_base, army_base_lv2, recruiting_office, local_industry, arms_industry,
airbase, naval_base, barracks, propaganda, research_lab, radar, bunker, hospital

UNIT TYPES:
infantry, motorized_infantry (mot), attack_helicopter (heli), mbt (tank),
sam, recon, artillery, mlrs, strike_fighter, bomber

STRATEGI:
- Build army_base di semua kota = lebih banyak slot produksi
- Build recruiting_office = bisa produce unit
- Prioritas produksi: infantry (murah), motorized_infantry (kuat), attack_helicopter (OP)
- Auto conquer = kirim semua idle army ke provinsi musuh terdekat
- Full conquest cycle = declare war + conquer + produce + build infrastructure sekaligus
- Scan threats = deteksi musuh yang mendekat ke teritori kita
- Smart expansion = analisis target ekspansi paling optimal
- Market = beli resource yang kurang, jual yang surplus
- Spy = intel gathering dan sabotase ekonomi musuh

Kamu adalah commander yang agresif, efisien, dan selalu mencari keuntungan maksimal."""


def _build_gemini_tools():
    """Convert our TOOLS list to Gemini function declarations."""
    declarations = []
    for tool in TOOLS:
        props = {}
        required = []
        for pname, pinfo in tool.get('parameters', {}).items():
            ptype = pinfo.get('type', 'string')
            schema_type = {
                'integer': 'INTEGER', 'int': 'INTEGER',
                'string': 'STRING', 'str': 'STRING',
                'number': 'NUMBER', 'float': 'NUMBER',
                'boolean': 'BOOLEAN', 'bool': 'BOOLEAN',
            }.get(ptype, 'STRING')
            props[pname] = genai.protos.Schema(
                type=schema_type,
                description=pinfo.get('description', ''),
            )
            required.append(pname)

        params = None
        if props:
            params = genai.protos.Schema(
                type='OBJECT',
                properties=props,
                required=required,
            )

        decl = genai.protos.FunctionDeclaration(
            name=tool['name'],
            description=tool['description'],
            parameters=params,
        )
        declarations.append(decl)

    return genai.protos.Tool(function_declarations=declarations)


def _execute_function(name: str, args: dict) -> str:
    """Execute a tool function by name with given args."""
    tool_map = {t['name']: t['fn'] for t in TOOLS}
    fn = tool_map.get(name)
    if not fn:
        return json.dumps({'error': f'Unknown function: {name}'})

    try:
        # Convert args types
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
        return json.dumps({'error': str(e), 'traceback': traceback.format_exc()})


class SWW3Agent:
    """AI Agent that plays Supremacy WW3 using Gemini as the brain."""

    def __init__(self):
        self.tools = _build_gemini_tools()
        self.verbose = True
        self._init_model()
        # Initialize game connection
        print("Connecting to game server...")
        _connect()
        print("Connected! Agent ready.\n")

    def _init_model(self, model_name=None, api_key=None):
        """Initialize or switch Gemini model with fallback."""
        key = api_key or os.environ.get('GEMINI_API_KEY', API_KEYS[0])
        genai.configure(api_key=key)
        name = model_name or MODEL_NAME
        self.current_model = name
        self.current_key = key
        self.model = genai.GenerativeModel(
            model_name=name,
            system_instruction=SYSTEM_PROMPT,
            tools=[self.tools],
        )
        self.chat = self.model.start_chat(history=[])

    def execute(self, user_message: str) -> str:
        """Process a user message, execute actions, return response."""
        # Retry with exponential backoff on rate limits, with model/key fallback
        response = None
        for attempt in range(6):
            try:
                response = self.chat.send_message(user_message)
                break
            except Exception as e:
                if '429' in str(e):
                    # Try switching model or key
                    switched = False
                    for key in API_KEYS:
                        for model in FALLBACK_MODELS:
                            if model == self.current_model and key == self.current_key:
                                continue
                            try:
                                print(f"  Switching to {model}...")
                                self._init_model(model, key)
                                response = self.chat.send_message(user_message)
                                switched = True
                                break
                            except Exception:
                                continue
                        if switched:
                            break
                    if switched:
                        break
                    wait = min((attempt + 1) * 15, 60)
                    print(f"  Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                return f"Gemini error: {e}"

        if response is None:
            return "All models rate limited. Try again later."

        # Process function calls in a loop until Gemini gives a text response
        max_rounds = 10
        for _ in range(max_rounds):
            # Check if there are function calls
            func_calls = []
            for part in response.parts:
                if part.function_call:
                    func_calls.append(part.function_call)

            if not func_calls:
                # No more function calls — extract text response
                texts = []
                for part in response.parts:
                    if part.text:
                        texts.append(part.text)
                return '\n'.join(texts) if texts else '(no response)'

            # Execute all function calls
            func_responses = []
            for fc in func_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                if self.verbose:
                    args_str = ', '.join(f'{k}={v}' for k, v in args.items())
                    print(f"  {name}({args_str})")

                result_str = _execute_function(name, args)

                if self.verbose:
                    # Show abbreviated result
                    preview = result_str[:200] + '...' if len(result_str) > 200 else result_str
                    print(f"  → {preview}")

                func_responses.append(
                    genai.protos.Part(function_response=genai.protos.FunctionResponse(
                        name=name,
                        response={'result': result_str},
                    ))
                )

            # Send function results back to Gemini
            for retry in range(3):
                try:
                    response = self.chat.send_message(
                        genai.protos.Content(parts=func_responses)
                    )
                    break
                except Exception as e:
                    if '429' in str(e) and retry < 2:
                        wait = (retry + 1) * 15
                        print(f"  Rate limited, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    return f"Gemini error on function response: {e}"

        return "Max rounds reached — agent stopped to prevent infinite loop."

    def auto_play(self, interval_minutes: int = 30):
        """Auto-play mode: run conquest cycle every N minutes."""
        print(f"Auto-play mode: conquest cycle every {interval_minutes} min")
        print("   Press Ctrl+C to stop\n")

        while True:
            print(f"\n{'='*50}")
            print(f"{time.strftime('%H:%M:%S')} — Running conquest cycle...")
            print(f"{'='*50}")

            try:
                result = self.execute("Jalankan full conquest cycle: declare war semua bot lemah, kirim semua army idle ke musuh, produce unit di semua kota idle. Laporkan hasilnya.")
                print(f"\n{result}")
            except Exception as e:
                print(f"Error: {e}")

            print(f"\nSleeping {interval_minutes} minutes...")
            try:
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print("\nAuto-play stopped.")
                break


def main():
    import argparse
    parser = argparse.ArgumentParser(description='SWW3 AI Agent')
    parser.add_argument('command', nargs='*', help='Single command to execute')
    parser.add_argument('--auto', action='store_true', help='Auto-play mode')
    parser.add_argument('--interval', type=int, default=30, help='Auto-play interval (minutes)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Hide function call details')
    args = parser.parse_args()

    agent = SWW3Agent()
    if args.quiet:
        agent.verbose = False

    if args.auto:
        agent.auto_play(args.interval)
        return

    if args.command:
        # Single command mode
        cmd = ' '.join(args.command)
        print(f"Command: {cmd}\n")
        result = agent.execute(cmd)
        print(f"\n{result}")
        return

    # Interactive mode
    print("SWW3 AI AGENT")
    print("Type commands or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ('quit', 'exit', 'q'):
            print("Bye!")
            break

        print()
        result = agent.execute(user_input)
        print(f"\nAgent > {result}\n")


if __name__ == '__main__':
    main()
