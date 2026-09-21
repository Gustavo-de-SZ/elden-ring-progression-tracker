"""Elden Ring Save File Parser.

Parses ER0000.sl2 (standard) and ER0000.co2 (Seamless Co-op) save files.
Pure Python standard library implementation - zero external dependencies.
"""

from __future__ import annotations

import os
import sys
import struct
import pathlib
from typing import List, Dict, Any, Optional, Tuple


# BND4 Constants & Offsets
BND4_MAGIC = b"BND4"
SLOT_START = 0x00000310
SLOT_LEN = 0x280000          # 2,621,440 bytes
SLOT_INTERVAL = 0x280010     # 2,621,456 bytes (0x10 checksum + 0x280000 data)
NUM_SLOTS = 10

HEADER_NAMES_START = 0x1901D0E
HEADER_NAMES_INTERVAL = 588
HEADER_LEVEL_OFFSET = 34

INVENTORY_PATTERN_1 = b"\xb0\xad\x01\x00\x01\xff\xff\xff"
INVENTORY_PATTERN_2 = b"\xb0\xad\x01\x00\x01"


def get_default_save_dirs() -> List[pathlib.Path]:
    """Return potential Elden Ring save directory paths based on current OS."""
    candidates = []

    # Windows %APPDATA%\EldenRing
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(pathlib.Path(appdata) / "EldenRing")

    # User home dir fallbacks
    home = pathlib.Path.home()
    candidates.append(home / "AppData" / "Roaming" / "EldenRing")

    # Linux / Steam Deck Proton paths
    steam_roots = [
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
    ]
    for steam_root in steam_roots:
        proton_er = (
            steam_root
            / "steamapps"
            / "compatdata"
            / "1245620"
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
            / "AppData"
            / "Roaming"
            / "EldenRing"
        )
        candidates.append(proton_er)

    # Current working directory
    candidates.append(pathlib.Path.cwd())

    return [c for c in candidates if c.exists()]


def find_save_file(explicit_path: Optional[str | pathlib.Path] = None) -> Optional[pathlib.Path]:
    """Find Elden Ring save file (.sl2 or .co2)."""
    if explicit_path:
        p = pathlib.Path(explicit_path).expanduser().resolve()
        if p.is_file():
            return p
        if p.is_dir():
            for name in ("ER0000.sl2", "ER0000.co2"):
                target = p / name
                if target.is_file():
                    return target
            for sub in p.glob("*/*.sl2"):
                return sub
            for sub in p.glob("*/*.co2"):
                return sub
        return None

    # Search candidate directories
    for save_dir in get_default_save_dirs():
        if save_dir.is_file() and save_dir.name.endswith((".sl2", ".co2")):
            return save_dir

        # Look in steam ID subfolders (17 digits)
        for entry in save_dir.iterdir():
            if entry.is_dir():
                for name in ("ER0000.sl2", "ER0000.co2"):
                    f = entry / name
                    if f.is_file():
                        return f
            elif entry.is_file() and entry.name in ("ER0000.sl2", "ER0000.co2"):
                return entry

    return None


class CharacterProfile:
    """High-level summary of a character slot."""
    def __init__(self, slot_index: int, name: str, level: int, is_active: bool):
        self.slot_index = slot_index
        self.name = name
        self.level = level
        self.is_active = is_active

    def __repr__(self) -> str:
        status = "Active" if self.is_active else "Empty"
        return f"<CharacterSlot {self.slot_index}: '{self.name}' (Level {self.level}) [{status}]>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_index": self.slot_index,
            "name": self.name,
            "level": self.level,
            "is_active": self.is_active,
        }


class CharacterData:
    """Full parsed character details including stats, inventory, and collectibles."""
    def __init__(
        self,
        slot_index: int,
        name: str,
        level: int,
        stats: Dict[str, int],
        runes: int,
        hp: Tuple[int, int],
        fp: Tuple[int, int],
        stamina: Tuple[int, int],
        item_ids: List[str],
        collectibles: Dict[str, int],
        is_dlc_format: bool,
    ):
        self.slot_index = slot_index
        self.name = name
        self.level = level
        self.stats = stats
        self.runes = runes
        self.hp = hp
        self.fp = fp
        self.stamina = stamina
        self.item_ids = item_ids
        self.collectibles = collectibles
        self.is_dlc_format = is_dlc_format

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_index": self.slot_index,
            "name": self.name,
            "level": self.level,
            "stats": self.stats,
            "runes": self.runes,
            "hp": {"current": self.hp[0], "max": self.hp[1]},
            "fp": {"current": self.fp[0], "max": self.fp[1]},
            "stamina": {"current": self.stamina[0], "max": self.stamina[1]},
            "total_items_held": len(self.item_ids),
            "item_ids": self.item_ids,
            "collectibles": self.collectibles,
            "is_dlc_format": self.is_dlc_format,
        }


class EldenSaveFile:
    """Parser and reader for Elden Ring save files."""

    def __init__(self, path: Optional[str | pathlib.Path] = None):
        save_path = find_save_file(path)
        if not save_path:
            raise FileNotFoundError(
                f"Could not locate an Elden Ring save file (ER0000.sl2/co2). "
                f"Specified path: '{path}'. Please provide a valid save file path."
            )
        self.path = save_path
        with open(self.path, "rb") as f:
            self.data = f.read()

        if len(self.data) < 4 or self.data[:4] != BND4_MAGIC:
            raise ValueError(f"File at '{self.path}' is not a valid Elden Ring BND4 save file.")

    def get_characters(self) -> List[CharacterProfile]:
        """Read character names and levels from the save header."""
        profiles = []
        for i in range(NUM_SLOTS):
            offset = HEADER_NAMES_START + (i * HEADER_NAMES_INTERVAL)
            if offset + 32 > len(self.data):
                break

            raw_name = self.data[offset : offset + 32]
            try:
                name_str = raw_name.decode("utf-16le", errors="ignore").split("\x00")[0].strip()
            except Exception:
                name_str = ""

            lvl_offset = offset + HEADER_LEVEL_OFFSET
            if lvl_offset + 2 <= len(self.data):
                level = struct.unpack("<H", self.data[lvl_offset : lvl_offset + 2])[0]
            else:
                level = 0

            is_active = bool(name_str) and level > 0
            profiles.append(CharacterProfile(slot_index=i, name=name_str, level=level, is_active=is_active))

        return profiles

    def get_slot_bytes(self, slot_index: int) -> bytes:
        """Extract the raw binary data of a given character slot (0-9)."""
        if not (0 <= slot_index < NUM_SLOTS):
            raise IndexError(f"Slot index {slot_index} out of range (0-{NUM_SLOTS-1}).")

        start = SLOT_START + (slot_index * SLOT_INTERVAL)
        end = start + SLOT_LEN
        if end > len(self.data):
            raise ValueError(f"Save file is truncated; slot {slot_index} exceeds file length.")
        return self.data[start:end]

    def parse_character(
        self,
        slot_index: int,
        collectibles_definitions: Optional[List[Dict[str, Any]]] = None,
    ) -> CharacterData:
        """Parse all stats, runes, items, and collectibles for the given slot."""
        profiles = self.get_characters()
        profile = profiles[slot_index]
        slot = self.get_slot_bytes(slot_index)

        # 1. Parse Attributes & Stats
        stats_dict, runes, hp, fp, stamina = self._parse_stats(slot, profile.level)

        # 2. Parse Inventory Item IDs
        item_ids, is_dlc = self._parse_inventory(slot)

        # 3. Parse Collectibles
        collectibles = self._parse_collectibles(slot, collectibles_definitions or [])

        return CharacterData(
            slot_index=slot_index,
            name=profile.name,
            level=profile.level,
            stats=stats_dict,
            runes=runes,
            hp=hp,
            fp=fp,
            stamina=stamina,
            item_ids=item_ids,
            collectibles=collectibles,
            is_dlc_format=is_dlc,
        )

    def _parse_stats(
        self, slot: bytes, level: int
    ) -> Tuple[Dict[str, int], int, Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """Locate the stat block in slot data and extract attributes."""
        stat_names = [
            "Vigor", "Mind", "Endurance", "Strength",
            "Dexterity", "Intelligence", "Faith", "Arcane"
        ]
        default_stats = {name: 10 for name in stat_names}
        runes = 0
        hp = (0, 0)
        fp = (0, 0)
        stamina = (0, 0)

        # Search for stat block where sum(stats) == level + 79
        target_sum = level + 79
        limit = min(len(slot) - 60, 150000)

        found_index = -1
        for idx in range(0, limit, 4):
            # Check little-endian 32-bit stats spaced by 4 bytes or 1 byte
            # In ER save format, stats can be stored as uint32 or uint8 with 3 bytes pad
            s = [
                slot[idx],
                slot[idx + 4],
                slot[idx + 8],
                slot[idx + 12],
                slot[idx + 16],
                slot[idx + 20],
                slot[idx + 24],
                slot[idx + 28],
            ]
            if sum(s) == target_sum:
                # Level check at offset + 44
                stored_level = struct.unpack("<H", slot[idx + 44 : idx + 46])[0]
                if stored_level == level:
                    found_index = idx
                    default_stats = {name: val for name, val in zip(stat_names, s)}
                    break

        if found_index != -1:
            # HP is at found_index - 44 (current hp, max hp)
            hp_cur = struct.unpack("<I", slot[found_index - 44 : found_index - 40])[0]
            hp_max = struct.unpack("<I", slot[found_index - 40 : found_index - 36])[0]
            hp = (hp_cur, hp_max)

            # FP is at found_index - 32 (current fp, max fp)
            fp_cur = struct.unpack("<I", slot[found_index - 32 : found_index - 28])[0]
            fp_max = struct.unpack("<I", slot[found_index - 28 : found_index - 24])[0]
            fp = (fp_cur, fp_max)

            # Stamina is at found_index - 16 (current sp, max sp)
            sp_cur = struct.unpack("<I", slot[found_index - 16 : found_index - 12])[0]
            sp_max = struct.unpack("<I", slot[found_index - 12 : found_index - 8])[0]
            stamina = (sp_cur, sp_max)

            # Runes are at found_index + 48 (uint32)
            runes = struct.unpack("<I", slot[found_index + 48 : found_index + 52])[0]

        return default_stats, runes, hp, fp, stamina

    def _parse_inventory(self, slot: bytes) -> Tuple[List[str], bool]:
        """Extract inventory items using pattern scanning from elden-ring-progression-tracker."""
        is_dlc = False
        start_idx = slot.find(INVENTORY_PATTERN_1)

        if start_idx != -1:
            start_idx += len(INVENTORY_PATTERN_1) + 8
        else:
            # Try DLC pattern
            idx = 0
            while True:
                found = slot.find(INVENTORY_PATTERN_2, idx)
                if found == -1:
                    break
                candidate = found + len(INVENTORY_PATTERN_2) + 3
                if candidate >= 3 and slot[candidate - 3] == 0:
                    start_idx = candidate
                    is_dlc = True
                    break
                idx = found + 1

        if start_idx is None or start_idx == -1:
            return [], False

        # Inventory ends when encountering 50 consecutive zero bytes
        zero_pattern = b"\x00" * 50
        end_idx = slot.find(zero_pattern, start_idx)
        if end_idx == -1:
            end_idx = len(slot)
        else:
            end_idx += 6

        inventory_bytes = slot[start_idx:end_idx]
        chunk_size = 8 if is_dlc else 16

        item_ids = []
        for i in range(0, len(inventory_bytes) - 4, chunk_size):
            chunk = inventory_bytes[i : i + 4]
            if len(chunk) < 4:
                continue
            # Reverse little endian bytes to get the item ID in big-endian hex
            reversed_bytes = bytes(reversed(chunk))
            hex_id = reversed_bytes.hex().upper()
            if hex_id != "00000000" and hex_id != "FFFFFFFF":
                item_ids.append(hex_id)

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for iid in item_ids:
            if iid not in seen:
                seen.add(iid)
                unique_ids.append(iid)

        return unique_ids, is_dlc

    def _parse_collectibles(
        self, slot: bytes, definitions: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Scan slot bytes for quantifiable collectibles (Pots, Memory Stones, etc.)."""
        results = {}
        for item in definitions:
            name = item.get("name", "")
            raw_id = item.get("id", [])
            if len(raw_id) < 3:
                continue

            id_pattern = bytes([raw_id[0], raw_id[1], raw_id[2], 0xB0])
            pos = slot.find(id_pattern)
            if pos != -1 and pos + 4 < len(slot):
                results[name] = slot[pos + 4]
            else:
                results[name] = 0

        return results
