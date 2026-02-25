# con-bot

AI-powered automation bot for **Conflict of Nations: World War 3** (Bytro Labs).

Control your nation with an AI agent in the terminal — declare wars, move armies, build infrastructure, trade resources, and run full conquest cycles using natural language.

## Features

- **AI Agent (TUI)** — Terminal UI with LLM-powered command execution (llama3.3-70b via Gradient SDK)
- **31 Game Actions** — War, army movement, production, building, diplomacy, market, intel
- **Auto-play** — Full conquest cycle: declare war → deploy armies → produce → build
- **Exploit System** — Resource manipulation, speedup, spy recruitment, ghost intel
- **24 CLI Scripts** — Individual scripts for every game action
- **Web Search** — Search strategy tips from the web inside the TUI
- **Game Selector** — Manage and switch between multiple games

## Quick Start

```bash
# Install
pip install requests

# Set API key for AI agent
cp .env.example .env
# Edit .env → add your Gradient API key

# Configure game credentials in sww3bot/auth.py

# Launch
source .env
python api/tui_agent.py
```

## Usage

### AI Agent (TUI)
```bash
python api/tui_agent.py              # Interactive TUI
python api/tui_agent.py "cek status" # Single command
python api/tui_agent.py --auto       # Auto-play loop
python api/tui_agent.py --simple     # No-curses fallback
```

**Shortcuts:** `/status` `/conquer` `/threats` `/armies` `/cities` `/resources` `/ranking` `/produce` `/build` `/search <query>` `/help` `/quit`

### CLI Scripts
```bash
python api/status.py          # Game status
python api/list_armies.py     # List armies
python api/war.py <player>    # Declare war
python api/move_army.py       # Move armies
python api/produce.py         # Produce units
python api/build.py           # Build in cities
python api/bypass.py          # Full auto cycle
python api/games.py           # Game selector
```

### Auto-play
```bash
python api/bypass.py              # Run once
python api/bypass.py --loop       # Loop every 30 min
python api/bypass.py --status     # Dry run
```

## Project Structure

```
api/                 # CLI scripts & AI agent
  tui_agent.py       # Main AI agent with TUI
  actions.py         # 31 game action functions + tool registry
  _conn.py           # Shared connection module
  bypass.py          # Auto-play system
  games.py           # Game selector
  agent.py           # Legacy Gemini agent
  cli.py             # CLI router
  test_agent.py      # Direct function tests (40 tests)
  test_prompts.py    # LLM prompt tests (44 tests)

sww3bot/             # Core game engine
  controller.py      # Move, produce, build, war
  auth.py            # Authentication
  exploits.py        # Exploit modules
  api.py             # HTTP API layer
  autoplay.py        # Auto-play logic
  intel.py           # Intelligence system
  ...
```

## Agent Tools (31)

| Category | Tools |
|----------|-------|
| **Info** | `get_status` `get_armies_detail` `get_cities_detail` `get_resources_detail` `get_players_info` `get_research_info` `get_spy_info` `get_ranking` `get_battle_log` `get_enemy_provinces` |
| **Analysis** | `scan_threats` `smart_expansion` `search_web` |
| **War** | `declare_war` `declare_war_on_all_bots` `offer_peace` |
| **Army** | `move_army` `move_all_idle_to_target` `auto_conquer` |
| **Build** | `build_building` `build_in_all_cities` `auto_build_infrastructure` |
| **Produce** | `produce_unit` `auto_produce` |
| **Diplomacy** | `offer_shared_intel` `offer_right_of_way` `send_message` |
| **Market** | `buy_market_resource` `sell_market_resource` |
| **Composite** | `full_conquest_cycle` |

## Environment Variables

```bash
GRADIENT_API_KEY=xxx                    # Required for AI agent
GRADIENT_MODEL=llama3.3-70b-instruct   # Optional
```

## Tests

```bash
python api/test_agent.py      # 40 direct function tests
python api/test_prompts.py    # 44 LLM prompt accuracy tests
python -m pytest tests/ -v    # Unit tests
```

## Disclaimer

Educational project. Use at your own risk.
