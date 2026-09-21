"""Generates a sample ER0000.sl2 save file with the user's Level 30 Astrologer."""

import sys
import struct
import pathlib

# Ensure repo root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from elden_tracker.save_parser import (
    BND4_MAGIC,
    HEADER_NAMES_START,
    HEADER_NAMES_INTERVAL,
    HEADER_LEVEL_OFFSET,
    SLOT_START,
    SLOT_LEN,
    INVENTORY_PATTERN_1,
)

def create_sample_save(output_path: str = "sample/ER0000.sl2"):
    p = pathlib.Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    total_size = HEADER_NAMES_START + (10 * HEADER_NAMES_INTERVAL) + 1000
    buffer = bytearray(total_size)
    buffer[0:4] = BND4_MAGIC

    # Slot 0: Astrologer
    char_name = "Astrologer"
    name_bytes = char_name.encode("utf-16le")
    buffer[HEADER_NAMES_START : HEADER_NAMES_START + len(name_bytes)] = name_bytes
    lvl_offset = HEADER_NAMES_START + HEADER_LEVEL_OFFSET
    buffer[lvl_offset : lvl_offset + 2] = struct.pack("<H", 30)

    slot_data = bytearray(SLOT_LEN)

    # Stats: Vigor: 20, Mind: 16, Endurance: 10, Strength: 10, Dexterity: 12, Intelligence: 27, Faith: 7, Arcane: 7
    # sum = 20+16+10+10+12+27+7+7 = 109 = 30 + 79
    stats = [20, 16, 10, 10, 12, 27, 7, 7]
    stat_start = 50000

    # HP: 652/652
    slot_data[stat_start - 44 : stat_start - 40] = struct.pack("<I", 652)
    slot_data[stat_start - 40 : stat_start - 36] = struct.pack("<I", 652)

    # FP: 100/100
    slot_data[stat_start - 32 : stat_start - 28] = struct.pack("<I", 100)
    slot_data[stat_start - 28 : stat_start - 24] = struct.pack("<I", 100)

    # Stamina: 92/92
    slot_data[stat_start - 16 : stat_start - 12] = struct.pack("<I", 92)
    slot_data[stat_start - 12 : stat_start - 8] = struct.pack("<I", 92)

    for i, val in enumerate(stats):
        slot_data[stat_start + (i * 4)] = val

    slot_data[stat_start + 44 : stat_start + 46] = struct.pack("<H", 30)
    slot_data[stat_start + 48 : stat_start + 52] = struct.pack("<I", 4500)

    # Inventory
    inv_start = 80000
    slot_data[inv_start : inv_start + len(INVENTORY_PATTERN_1)] = INVENTORY_PATTERN_1

    sample_items = [
        "01FB5AD0",  # Meteorite Staff
        "007A8730",  # Bloodhound's Fang
        "003E8FA0",  # Grafted Blade Greatsword
        "40001266",  # Rock Sling
        "40001158",  # Carian Slicer
        "10107AC0",  # Imp Head (Cat)
        "2000088E",  # Roar Medallion
        "20000FAA",  # Spelldrake Talisman
        "20000848",  # Twinblade Talisman
        "2000047E",  # Green Turtle Talisman
        "40000082",  # Spectral Steed Whistle
    ]

    items_offset = inv_start + len(INVENTORY_PATTERN_1) + 8
    for i, hex_id in enumerate(sample_items):
        rev_bytes = bytes.fromhex(hex_id)[::-1]
        offset = items_offset + (i * 16)
        slot_data[offset : offset + 4] = rev_bytes

    # Collectibles: Memory Stone = 1
    col_pattern = bytes([46, 39, 0, 0xB0])
    col_offset = 120000
    slot_data[col_offset : col_offset + 4] = col_pattern
    slot_data[col_offset + 4] = 1

    # Upgrade Materials
    sample_materials = [
        ((0x74, 0x27), 6),  # Smithing Stone [1]
        ((0x75, 0x27), 3),  # Smithing Stone [2]
        ((0xB0, 0x27), 1),  # Somber Smithing Stone [1]
    ]
    mat_offset = 125000
    for i, ((low, high), qty) in enumerate(sample_materials):
        cur = mat_offset + (i * 16)
        slot_data[cur : cur + 4] = bytes([low, high, 0x00, 0xB0])
        slot_data[cur + 4 : cur + 6] = struct.pack("<H", qty)

    buffer[SLOT_START : SLOT_START + SLOT_LEN] = slot_data

    with open(p, "wb") as f:
        f.write(buffer)
    print(f"Generated sample save file at: {p}")

if __name__ == "__main__":
    create_sample_save()
