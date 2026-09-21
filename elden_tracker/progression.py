"""Progression Analyzer.

Loads the Elden Ring item database and cross-references it with character save data
to compute zone progression, missing items, location hints, and build-specific item queries.
"""

from __future__ import annotations

import json
import pathlib
from typing import Dict, List, Any, Optional, Set

DATA_DIR = pathlib.Path(__file__).parent / "data"


class ItemInfo:
    def __init__(
        self,
        item_id: str,
        name: str,
        region: str,
        zone: str,
        item_type: str,
        hint: str,
        multiple: bool = False,
    ):
        self.item_id = item_id
        self.name = name
        self.region = region
        self.zone = zone
        self.item_type = item_type
        self.hint = hint
        self.multiple = multiple

    @property
    def category(self) -> str:
        """Categorize item based on FromSoftware ID prefix and name."""
        prefix = self.item_id[:2]
        if prefix in ("00", "01", "02", "03", "04"):
            return "weapon"
        elif prefix == "10":
            return "armor"
        elif prefix == "20":
            return "talisman"
        elif prefix == "80":
            return "ash_of_war"
        elif prefix == "40":
            lower = self.name.lower()
            if "cookbook" in lower or "recipe" in lower or "note:" in lower:
                return "cookbook"
            elif any(k in lower for k in ("stone", "tear", "seed", "key", "bell bearing", "whetblade", "medallion", "scroll", "prayerbook", "great rune", "remanence", "potion", "whistle")):
                return "key_item"
            else:
                return "spell"
        return "other"

    def clean_hint(self) -> str:
        """Strip HTML tags from hint for clean CLI and Markdown display."""
        text = self.hint.replace("<ul>", "").replace("</ul>", "").replace("<li>", "").replace("</li>", "")
        text = text.replace("&nbsp;", " ").replace("<p>", "").replace("</p>", "").strip()
        while "  " in text:
            text = text.replace("  ", " ")
        return text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.item_id,
            "name": self.name,
            "region": self.region,
            "zone": self.zone,
            "type": self.item_type,
            "hint": self.clean_hint(),
        }


class ProgressionReport:
    """Detailed completion and progression analysis for a character."""

    def __init__(
        self,
        character_name: str,
        character_level: int,
        stats: Dict[str, int],
        runes: int,
        collectibles: Dict[str, int],
        collectibles_definitions: List[Dict[str, Any]],
        owned_items: List[ItemInfo],
        missing_items: List[ItemInfo],
        region_stats: Dict[str, Dict[str, Any]],
        upgrade_materials: Optional[Dict[str, int]] = None,
    ):
        self.character_name = character_name
        self.character_level = character_level
        self.stats = stats
        self.runes = runes
        self.collectibles = collectibles
        self.collectibles_definitions = collectibles_definitions
        self.owned_items = owned_items
        self.missing_items = missing_items
        self.region_stats = region_stats
        self.upgrade_materials = upgrade_materials or {}

        total_catalog = len(owned_items) + len(missing_items)
        self.total_catalog_items = total_catalog
        self.completion_rate = (len(owned_items) / total_catalog * 100.0) if total_catalog > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": {
                "name": self.character_name,
                "level": self.character_level,
                "stats": self.stats,
                "runes": self.runes,
            },
            "completion": {
                "overall_percent": round(self.completion_rate, 1),
                "items_found": len(self.owned_items),
                "total_items": self.total_catalog_items,
            },
            "collectibles": self.collectibles,
            "upgrade_materials": self.upgrade_materials,
            "regions": self.region_stats,
        }


class ProgressionAnalyzer:
    """Manages the Elden Ring items database and provides progress tracking."""

    def __init__(self, data_dir: Optional[pathlib.Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self.items_by_id: Dict[str, ItemInfo] = {}
        self.items_by_region_zone: Dict[str, Dict[str, List[ItemInfo]]] = {}
        self.collectibles_definitions: List[Dict[str, Any]] = []
        self._load_databases()

    def _load_databases(self):
        # 1. Collectibles
        col_path = self.data_dir / "collectibles.json"
        if col_path.exists():
            with open(col_path, "r", encoding="utf-8") as f:
                self.collectibles_definitions = json.load(f)

        # 2. Base Game + DLC Data
        combined_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for fname in ("data.json", "dlc_data.json"):
            p = self.data_dir / fname
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    for region, zones in content.items():
                        if region not in combined_data:
                            combined_data[region] = {}
                        for zone, items in zones.items():
                            if zone not in combined_data[region]:
                                combined_data[region][zone] = {}
                            combined_data[region][zone].update(items)

        # Index all items
        for region, zones in combined_data.items():
            if region not in self.items_by_region_zone:
                self.items_by_region_zone[region] = {}
            for zone, items in zones.items():
                if zone not in self.items_by_region_zone[region]:
                    self.items_by_region_zone[region][zone] = []
                for item_id, details in items.items():
                    info = ItemInfo(
                        item_id=item_id.upper(),
                        name=details.get("name", "Unknown Item"),
                        region=region,
                        zone=zone,
                        item_type=details.get("type", "unknown"),
                        hint=details.get("hint", ""),
                        multiple=details.get("multiple", False),
                    )
                    self.items_by_id[info.item_id] = info
                    self.items_by_region_zone[region][zone].append(info)

    def analyze(self, char_data: Any) -> ProgressionReport:
        """Analyze character save data against item database."""
        owned_set: Set[str] = set(char_data.item_ids)
        owned_items: List[ItemInfo] = []
        missing_items: List[ItemInfo] = []
        region_stats: Dict[str, Dict[str, Any]] = {}

        for region, zones in self.items_by_region_zone.items():
            region_found = 0
            region_total = 0
            zone_dict: Dict[str, Any] = {}

            for zone, items in zones.items():
                z_found = 0
                z_total = len(items)
                z_missing: List[Dict[str, Any]] = []

                for item in items:
                    if item.item_id in owned_set:
                        z_found += 1
                        owned_items.append(item)
                    else:
                        missing_items.append(item)
                        z_missing.append(item.to_dict())

                pct = round((z_found / z_total * 100.0), 1) if z_total > 0 else 100.0
                zone_dict[zone] = {
                    "found": z_found,
                    "total": z_total,
                    "percent": pct,
                    "missing_count": z_total - z_found,
                }
                region_found += z_found
                region_total += z_total

            reg_pct = round((region_found / region_total * 100.0), 1) if region_total > 0 else 100.0
            region_stats[region] = {
                "found": region_found,
                "total": region_total,
                "percent": reg_pct,
                "zones": zone_dict,
            }

        return ProgressionReport(
            character_name=char_data.name,
            character_level=char_data.level,
            stats=char_data.stats,
            runes=char_data.runes,
            collectibles=char_data.collectibles,
            collectibles_definitions=self.collectibles_definitions,
            owned_items=owned_items,
            missing_items=missing_items,
            region_stats=region_stats,
            upgrade_materials=getattr(char_data, "upgrade_materials", {}),
        )

    def search_items(
        self, query: str, item_type: Optional[str] = None
    ) -> List[ItemInfo]:
        """Search items by name or type substring."""
        q = query.lower()
        results = []
        for item in self.items_by_id.values():
            if item_type and item.item_type.lower() != item_type.lower():
                continue
            if q in item.name.lower() or q in item.zone.lower():
                results.append(item)
        return results

    def get_death_mage_items(self) -> List[ItemInfo]:
        """Key Death Sorcery and ghostflame items."""
        keywords = [
            "rancorcall", "ancient death rancor", "explosive ghostflame",
            "tibia's summons", "fia's mist", "ghostflame", "prince of death",
            "death's poker", "death ritual spear", "helphen's steeple",
            "sacrificial axe", "graven-school", "graven-mass", "godfrey icon",
            "meteorite staff"
        ]
        matches = []
        for kw in keywords:
            for item in self.search_items(kw):
                if item not in matches:
                    matches.append(item)
        return matches
