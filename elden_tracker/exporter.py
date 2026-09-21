"""Progress Exporter.

Generates human-readable Markdown reports (character_tracker.md) and
machine-readable JSON snapshots (save_summary.json) from parsed progression data.
"""

from __future__ import annotations

import json
import pathlib
from typing import Optional, List
from .progression import ProgressionReport, ItemInfo


class ProgressExporter:
    """Exports progression reports into Markdown and JSON formats."""

    def __init__(self, report: ProgressionReport):
        self.report = report

    def to_json(self) -> str:
        """Export progression report as a formatted JSON string."""
        return json.dumps(self.report.to_dict(), indent=2, ensure_ascii=False)

    def to_markdown(self, highlight_build: str = "Death Mage") -> str:
        """Generate a rich Markdown progression tracker."""
        lines: List[str] = []

        lines.append(f"# Elden Ring Character Tracker: {self.report.character_name}")
        lines.append("")
        lines.append("## 📊 Character Stats & Overview")
        lines.append(f"- **Character Name:** {self.report.character_name}")
        lines.append(f"- **Rune Level:** {self.report.character_level}")
        lines.append(f"- **Runes Held:** {self.report.runes:,}")
        lines.append("")

        # Stat table
        lines.append("| Attribute | Level | Attribute | Level |")
        lines.append("| :--- | :--- | :--- | :--- |")
        s = self.report.stats
        lines.append(f"| **Vigor** | {s.get('Vigor', 0)} | **Strength** | {s.get('Strength', 0)} |")
        lines.append(f"| **Mind** | {s.get('Mind', 0)} | **Dexterity** | {s.get('Dexterity', 0)} |")
        lines.append(f"| **Endurance** | {s.get('Endurance', 0)} | **Intelligence** | {s.get('Intelligence', 0)} |")
        lines.append(f"| **Arcane** | {s.get('Arcane', 0)} | **Faith** | {s.get('Faith', 0)} |")
        lines.append("")

        # Collectibles
        if self.report.collectibles:
            lines.append("## 🎒 Collectibles & Capacity")
            for col_def in self.report.collectibles_definitions:
                name = col_def.get("name", "")
                qty = self.report.collectibles.get(name, 0)
                total_places = len(col_def.get("places", []))
                lines.append(f"- **{name}:** {qty} / {total_places}")
            lines.append("")

        # Upgrade Materials Held
        if self.report.upgrade_materials:
            lines.append("## 💎 Upgrade Materials Held")
            lines.append("| Material | Quantity |")
            lines.append("| :--- | :--- |")
            for mat_name, count in self.report.upgrade_materials.items():
                lines.append(f"| **{mat_name}** | {count} |")
            lines.append("")

        # Owned Items Summary
        if self.report.owned_items:
            lines.append("## 🎒 Collected Equipment & Key Items")
            for item in self.report.owned_items[:40]:
                lines.append(f"- **{item.name}** ({item.item_type}) — *{item.zone}*")
            if len(self.report.owned_items) > 40:
                lines.append(f"- *...and {len(self.report.owned_items) - 40} more items collected.*")
            lines.append("")

        # Completion summary
        lines.append("## 🗺️ Overall World Progression")
        lines.append(
            f"- **Catalog Completion:** {self.report.completion_rate:.1f}% "
            f"({len(self.report.owned_items)} / {self.report.total_catalog_items} items collected)"
        )
        lines.append("")

        lines.append("| Region | Items Found | Total | Completion |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for region, data in self.report.region_stats.items():
            lines.append(
                f"| **{region}** | {data['found']} | {data['total']} | {data['percent']}% |"
            )
        lines.append("")

        # Build-specific highlights (Death Mage)
        if highlight_build.lower() == "death mage":
            lines.append("## 💀 Death Mage Build Item Tracker")
            lines.append(
                "> Key items, staves, weapons, and Death Sorceries for your build:\n"
            )

            death_mage_targets = [
                ("Rancorcall", "Sorcery", "Stormveil Castle (Crypt scarab - requires 16 INT / 14 FTH)"),
                ("Ancient Death Rancor", "Sorcery", "Liurnia (Death Rite Bird at Gate Town North - Night)"),
                ("Tibia's Summons", "Sorcery", "Altus Plateau (Wyndham Ruins Tibia Mariner)"),
                ("Explosive Ghostflame", "Sorcery", "Consecrated Snowfield (Death Rite Bird)"),
                ("Fia's Mist", "Sorcery", "Deeproot Depths (Fia's Champions)"),
                ("Meteorite Staff", "Staff", "Caelid (Street of Sages Ruins - S INT scaling, early MVP)"),
                ("Prince of Death's Staff", "Staff", "Deeproot Depths (Endgame staff for INT/FTH)"),
                ("Death's Poker", "Greatsword", "Southern Caelid (Death Rite Bird - Ghostflame Ignition)"),
                ("Death Ritual Spear", "Spear", "Mountaintops (Death Rite Bird)"),
                ("Sacrificial Axe", "Axe", "Weeping Peninsula (Deathbird at Night - restores 4 FP per kill)"),
                ("Graven-School Talisman", "Talisman", "Raya Lucaria Academy (Raises sorcery damage by 4%)"),
                ("Graven-Mass Talisman", "Talisman", "Consecrated Snowfield (Raises sorcery damage by 8%)"),
            ]

            owned_names = {item.name.lower(): item for item in self.report.owned_items}
            lines.append("| Item Name | Category | Status | Acquisition Hint |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for target_name, cat, hint in death_mage_targets:
                if target_name.lower() in owned_names:
                    status = "✅ **Acquired**"
                else:
                    status = "❌ *Missing*"
                lines.append(f"| **{target_name}** | {cat} | {status} | {hint} |")
            lines.append("")

        # Missing items in early regions (Limgrave / Weeping Peninsula)
        lines.append("## 🔍 Early Region Missing Items & Hints")
        for region in ("Limgrave", "Weeping Peninsula"):
            reg_data = self.report.region_stats.get(region)
            if not reg_data:
                continue
            lines.append(f"### {region} ({reg_data['percent']}% complete)")
            missing_in_reg = [
                item for item in self.report.missing_items if item.region == region
            ]
            if not missing_in_reg:
                lines.append("- *All tracked items in this region collected!*")
            else:
                for item in missing_in_reg[:15]:
                    lines.append(
                        f"- [ ] **{item.name}** ({item.item_type}) — *{item.zone}*: {item.clean_hint()}"
                    )
                if len(missing_in_reg) > 15:
                    lines.append(
                        f"- *...and {len(missing_in_reg) - 15} more items in {region}. Run `python -m elden_tracker missing --region '{region}'` for the full list.*"
                    )
            lines.append("")

        return "\n".join(lines)

    def export_all(
        self,
        output_dir: Optional[pathlib.Path | str] = None,
        md_filename: str = "character_tracker.md",
        json_filename: str = "save_summary.json",
    ) -> Tuple[pathlib.Path, pathlib.Path]:
        """Save both markdown tracker and JSON summary to the target directory."""
        target_dir = pathlib.Path(output_dir or ".").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        md_path = target_dir / md_filename
        json_path = target_dir / json_filename

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

        return md_path, json_path
