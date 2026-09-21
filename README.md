# Elden Ring Save Analyzer & Progression Tracker

A lightweight, zero-dependency Python tool that reads your Elden Ring save file (`ER0000.sl2` or Seamless Co-op `ER0000.co2`), tracks your collection and regional progression, finds missing items/spells with hints, and automatically syncs with AI coding assistants (like Antigravity) for real-time build guidance.

---

## ✨ Features

- **Zero Dependencies**: Uses pure Python 3 standard library (`struct`, `json`, `pathlib`, `hashlib`, `argparse`). Works out-of-the-box on Windows, Linux, and Steam Deck.
- **Automatic Save File Detection**: Automatically discovers your save file in `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2` (or `.co2`).
- **Comprehensive Item Database**: Pre-bundled with complete item data (Base Game + *Shadow of the Erdtree* DLC) sourced from the [Elden Ring Progression Tracker](https://elden-ring-progression-tracker.github.io/).
- **Live Sync & Watcher**: Continuously monitors your save file and updates your progression report in real time whenever the game autosaves.
- **AI Companion Ready**: Generates both `character_tracker.md` and `save_summary.json` so your AI assistant can inspect your live game state and provide targeted guidance.

---

## 🚀 Quick Start (Windows / Linux)

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/elden-ring-progression.git
cd elden
```

### 2. Run with Python 3
No `pip install` required! Just run with standard Python:

```bash
# Export character_tracker.md and save_summary.json (defaults to first active character)
python -m elden_tracker sync

# View character stats and attributes
python -m elden_tracker stats

# View overall world & regional progression percentages
python -m elden_tracker summary

# Check key items for your build (e.g. Death Mage)
python -m elden_tracker query --death-mage

# Watch for game saves in real-time (auto-updates tracker when you rest or loot)
python -m elden_tracker watch
```

---

## 🛠️ CLI Command Reference

### List Characters in Save
```bash
python -m elden_tracker list
```
Displays all 10 character slots with name, level, and active status.

### View Character Stats & Attributes
```bash
python -m elden_tracker stats
python -m elden_tracker stats --slot 1
```
Displays Vigor, Mind, Endurance, Strength, Dexterity, Intelligence, Faith, Arcane, Runes, HP/FP/Stamina, collectible capacities (Memory Stones, Pots, etc.), and held upgrade materials.

### View Upgrade Materials
```bash
python -m elden_tracker materials
```
Displays all held Smithing Stones (1–8 + Ancient Dragon), Somber Stones (1–9 + Ancient Dragon), and Gloveworts.

### Regional Completion Summary
```bash
python -m elden_tracker summary
```
Displays a breakdown of collected vs total items for every region:
- Limgrave, Weeping Peninsula, Liurnia of the Lakes, Caelid, Altus Plateau, Mt Gelmir, Mountaintops of the Giants, Underground, and DLC zones.

### Check Missing Items with Location Hints
```bash
# Find missing items in a specific region
python -m elden_tracker missing --region "Limgrave"

# Find missing spells
python -m elden_tracker missing --type "spell"

# Find missing items in a specific dungeon or zone
python -m elden_tracker missing --zone "Stormveil"
```

### Query Specific Items
```bash
# Check if a specific item is in your inventory
python -m elden_tracker query --name "Meteorite Staff"
python -m elden_tracker query --name "Rancorcall"

# Check all Death Mage items (Sorceries, Staves, Talismans, Weapons)
python -m elden_tracker query --death-mage
```

### Real-Time Auto Watcher
```bash
python -m elden_tracker watch
```
Monitors the save file timestamp. Whenever you sit at a Site of Grace, loot an item, or fast travel, the tracker updates `character_tracker.md` automatically!

---

## 📁 How the AI Assistant Uses This Tool

When chatting with an AI assistant (like Antigravity), the assistant can:
1. Run `python -m elden_tracker sync` to snapshot your current inventory and stats.
2. Read `character_tracker.md` or `save_summary.json` directly from the workspace.
3. Query `python -m elden_tracker missing --region <Region>` to advise on which bosses, items, or quests you should tackle next based on your exact inventory!

---

## 🔒 Safe & Read-Only
This tool strictly reads the save file. It never alters bytes or modifies the save file, ensuring zero risk of corruption or anti-cheat flags.
