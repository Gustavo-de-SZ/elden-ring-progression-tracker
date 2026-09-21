"""Unit tests for Elden Ring Save Analyzer & Progression Tracker."""

import unittest
import struct
import tempfile
import pathlib

from elden_tracker.save_parser import (
    EldenSaveFile,
    BND4_MAGIC,
    HEADER_NAMES_START,
    HEADER_NAMES_INTERVAL,
    HEADER_LEVEL_OFFSET,
    SLOT_START,
    SLOT_LEN,
    SLOT_INTERVAL,
    INVENTORY_PATTERN_1,
)
from elden_tracker.progression import ProgressionAnalyzer
from elden_tracker.exporter import ProgressExporter


class TestProgressionAnalyzer(unittest.TestCase):
    """Test item database loading and queries."""

    def setUp(self):
        self.analyzer = ProgressionAnalyzer()

    def test_database_loaded(self):
        self.assertGreater(len(self.analyzer.items_by_id), 1000)
        self.assertGreater(len(self.analyzer.collectibles_definitions), 0)

    def test_search_known_items(self):
        meteorite = self.analyzer.search_items("Meteorite Staff")
        self.assertTrue(len(meteorite) > 0)
        self.assertEqual(meteorite[0].name, "Meteorite Staff")

        rancor = self.analyzer.search_items("Rancorcall")
        self.assertTrue(len(rancor) > 0)

    def test_death_mage_items(self):
        items = self.analyzer.get_death_mage_items()
        names = {i.name for i in items}
        self.assertIn("Rancorcall", names)
        self.assertIn("Ancient Death Rancor", names)
        self.assertIn("Meteorite Staff", names)


class TestSaveParserWithSyntheticSave(unittest.TestCase):
    """Test save parser logic using a synthetic BND4 structure."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_path = pathlib.Path(self.temp_dir.name) / "ER0000.sl2"

        # Build a minimal valid synthetic BND4 file with 1 active slot
        total_size = HEADER_NAMES_START + (10 * HEADER_NAMES_INTERVAL) + 1000
        buffer = bytearray(total_size)

        # 1. BND4 Magic
        buffer[0:4] = BND4_MAGIC

        # 2. Slot 0 Header Name and Level
        name = "TarnishedMage"
        name_bytes = name.encode("utf-16le")
        buffer[HEADER_NAMES_START : HEADER_NAMES_START + len(name_bytes)] = name_bytes
        lvl_offset = HEADER_NAMES_START + HEADER_LEVEL_OFFSET
        buffer[lvl_offset : lvl_offset + 2] = struct.pack("<H", 30)

        # 3. Slot 0 Data
        slot_data = bytearray(SLOT_LEN)

        # Stat block: Level 30 -> target_sum = 30 + 79 = 109
        # Vig=20, Mnd=15, End=10, Str=10, Dex=12, Int=25, Fth=9, Arc=8 -> sum = 109
        stats = [20, 15, 10, 10, 12, 25, 9, 8]
        self.assertEqual(sum(stats), 109)

        stat_start = 50000
        # HP: current 700, max 700 at stat_start - 44
        slot_data[stat_start - 44 : stat_start - 40] = struct.pack("<I", 700)
        slot_data[stat_start - 40 : stat_start - 36] = struct.pack("<I", 700)

        # FP: current 90, max 90 at stat_start - 32
        slot_data[stat_start - 32 : stat_start - 28] = struct.pack("<I", 90)
        slot_data[stat_start - 28 : stat_start - 24] = struct.pack("<I", 90)

        # Stamina: current 95, max 95 at stat_start - 16
        slot_data[stat_start - 16 : stat_start - 12] = struct.pack("<I", 95)
        slot_data[stat_start - 12 : stat_start - 8] = struct.pack("<I", 95)

        # Stats
        for i, val in enumerate(stats):
            slot_data[stat_start + (i * 4)] = val

        # Level at stat_start + 44
        slot_data[stat_start + 44 : stat_start + 46] = struct.pack("<H", 30)
        # Runes at stat_start + 48
        slot_data[stat_start + 48 : stat_start + 52] = struct.pack("<I", 12500)

        # 4. Inventory in Slot 0
        inv_start = 80000
        slot_data[inv_start : inv_start + len(INVENTORY_PATTERN_1)] = INVENTORY_PATTERN_1

        # Add two items:
        # Item 1: Spectral Steed Whistle ("40000082" -> little endian bytes: [0x82, 0x00, 0x00, 0x40])
        # Item 2: Meteorite Staff ("00B71B00" -> little endian bytes: [0x00, 0x1B, 0xB7, 0x00])
        item1_bytes = bytes.fromhex("40000082")[::-1]
        item2_bytes = bytes.fromhex("00B71B00")[::-1]

        items_offset = inv_start + len(INVENTORY_PATTERN_1) + 8
        slot_data[items_offset : items_offset + 4] = item1_bytes
        slot_data[items_offset + 16 : items_offset + 20] = item2_bytes

        # 5. Collectible: Memory Stone [46, 39, 0] -> quantity 1
        col_pattern = bytes([46, 39, 0, 0xB0])
        col_offset = 120000
        slot_data[col_offset : col_offset + 4] = col_pattern
        slot_data[col_offset + 4] = 1

        # 6. Upgrade material: Smithing Stone [1] (0x74, 0x27) -> quantity 5
        mat_pattern = bytes([0x74, 0x27, 0x00, 0xB0])
        mat_offset = 125000
        slot_data[mat_offset : mat_offset + 4] = mat_pattern
        slot_data[mat_offset + 4 : mat_offset + 6] = struct.pack("<H", 5)

        # Copy slot_data into buffer
        buffer[SLOT_START : SLOT_START + SLOT_LEN] = slot_data

        with open(self.save_path, "wb") as f:
            f.write(buffer)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_profiles(self):
        save = EldenSaveFile(self.save_path)
        profiles = save.get_characters()
        self.assertEqual(len(profiles), 10)
        self.assertTrue(profiles[0].is_active)
        self.assertEqual(profiles[0].name, "TarnishedMage")
        self.assertEqual(profiles[0].level, 30)
        self.assertFalse(profiles[1].is_active)

    def test_parse_character_data(self):
        save = EldenSaveFile(self.save_path)
        analyzer = ProgressionAnalyzer()
        char = save.parse_character(0, analyzer.collectibles_definitions)

        self.assertEqual(char.name, "TarnishedMage")
        self.assertEqual(char.level, 30)
        self.assertEqual(char.runes, 12500)
        self.assertEqual(char.stats["Vigor"], 20)
        self.assertEqual(char.stats["Intelligence"], 25)
        self.assertEqual(char.collectibles.get("Memory Stone"), 1)
        self.assertEqual(char.upgrade_materials.get("Smithing Stone [1]"), 5)

        # Check items parsed
        self.assertIn("40000082", char.item_ids)
        self.assertIn("00B71B00", char.item_ids)

    def test_exporter(self):
        save = EldenSaveFile(self.save_path)
        analyzer = ProgressionAnalyzer()
        char = save.parse_character(0, analyzer.collectibles_definitions)
        report = analyzer.analyze(char)

        exporter = ProgressExporter(report)
        md = exporter.to_markdown()
        json_str = exporter.to_json()

        self.assertIn("TarnishedMage", md)
        self.assertIn("Rune Level:** 30", md)
        self.assertIn("Spectral Steed Whistle", md)
        self.assertIn("Smithing Stone [1]", md)
        self.assertIn('"Smithing Stone [1]": 5', json_str)
        self.assertIn('"overall_percent":', json_str)


if __name__ == "__main__":
    unittest.main()
