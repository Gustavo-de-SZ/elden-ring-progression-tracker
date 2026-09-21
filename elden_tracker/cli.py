"""Command-Line Interface for Elden Ring Save Progression Tracker."""

from __future__ import annotations

import sys
import argparse
import pathlib
from typing import Optional

from .save_parser import EldenSaveFile, find_save_file
from .progression import ProgressionAnalyzer
from .exporter import ProgressExporter
from .watcher import watch_save_file


def _get_save_and_slot(args: argparse.Namespace):
    save = EldenSaveFile(getattr(args, "save_path", None))
    profiles = save.get_characters()

    slot = getattr(args, "slot", None)
    if slot is None:
        # Default to first active slot
        active = [p for p in profiles if p.is_active]
        if not active:
            print("No active characters found in save file.")
            sys.exit(1)
        slot = active[0].slot_index

    if not (0 <= slot < len(profiles)):
        print(f"Error: Slot {slot} is out of range (0-{len(profiles)-1}).")
        sys.exit(1)

    return save, slot


def cmd_list(args: argparse.Namespace):
    """List all character slots in the save file."""
    save = EldenSaveFile(args.save_path)
    print(f"Save File: {save.path}\n")
    print(f"{'Slot':<6} {'Status':<10} {'Level':<8} {'Character Name'}")
    print("-" * 50)
    for p in save.get_characters():
        status = "Active" if p.is_active else "Empty"
        lvl_str = str(p.level) if p.is_active else "-"
        name_str = p.name if p.is_active else "-"
        prefix = "-> " if p.is_active else "   "
        print(f"{prefix}{p.slot_index:<4} {status:<10} {lvl_str:<8} {name_str}")


def cmd_stats(args: argparse.Namespace):
    """Display attributes and collectibles for a character."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)

    print(f"\n=== Character: {char.name} (Slot {slot}, Level {char.level}) ===")
    print(f"Runes: {char.runes:,}")
    print(f"HP: {char.hp[0]}/{char.hp[1]} | FP: {char.fp[0]}/{char.fp[1]} | Stamina: {char.stamina[0]}/{char.stamina[1]}")
    print("\n--- Attributes ---")
    for stat_name, val in char.stats.items():
        print(f"  {stat_name:<14}: {val}")

    if char.collectibles:
        print("\n--- Collectibles & Capacity ---")
        for name, count in char.collectibles.items():
            print(f"  {name:<22}: {count}")

    if char.upgrade_materials:
        print("\n--- Upgrade Materials Held ---")
        for mat_name, count in char.upgrade_materials.items():
            print(f"  {mat_name:<34}: {count}")
    print()


def cmd_materials(args: argparse.Namespace):
    """Display held upgrade materials (Smithing Stones, Somber Stones)."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)

    print(f"\n=== Upgrade Materials Held: {char.name} (Level {char.level}) ===")
    if not char.upgrade_materials:
        print("  (No upgrade materials currently held)")
    else:
        for mat_name, count in char.upgrade_materials.items():
            print(f"  {mat_name:<36}: {count}")
    print()


def cmd_summary(args: argparse.Namespace):
    """Display overall progression summary across regions."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)
    report = analyzer.analyze(char)

    print(f"\n=== Progression Summary: {char.name} (Level {char.level}) ===")
    print(
        f"Overall Catalog Progress: {report.completion_rate:.1f}% "
        f"({len(report.owned_items)} / {report.total_catalog_items} items collected)\n"
    )
    print(f"{'Region':<30} {'Found':<8} {'Total':<8} {'Progress'}")
    print("-" * 56)
    for region, data in report.region_stats.items():
        bar_len = int(data['percent'] / 5)
        bar = "#" * bar_len + "-" * (20 - bar_len)
        print(f"{region:<30} {data['found']:<8} {data['total']:<8} [{bar}] {data['percent']}%")
    print()


def cmd_missing(args: argparse.Namespace):
    """List missing items with location hints."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)
    report = analyzer.analyze(char)

    missing = report.missing_items

    if args.region:
        missing = [m for m in missing if m.region.lower() == args.region.lower()]
    if args.zone:
        missing = [m for m in missing if args.zone.lower() in m.zone.lower()]
    if args.type:
        missing = [m for m in missing if m.item_type.lower() == args.type.lower()]
    if getattr(args, "category", None):
        missing = [m for m in missing if m.category.lower() == args.category.lower()]

    print(f"\n=== Missing Items ({len(missing)} matching) ===")
    limit = args.limit or 30
    for item in missing[:limit]:
        print(f"\n• [{item.region} - {item.zone}] {item.name} ({item.item_type})")
        hint = item.clean_hint()
        if hint:
            print(f"  Hint: {hint}")

    if len(missing) > limit:
        print(f"\n... and {len(missing) - limit} more items. (Use --limit to display more)")
    print()


def cmd_query(args: argparse.Namespace):
    """Check if specific items are collected."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)
    owned_ids = set(char.item_ids)

    if args.death_mage:
        items = analyzer.get_death_mage_items()
        print(f"\n=== Death Mage Items Check: {char.name} ===")
        for item in items:
            status = "✅ ACQUIRED" if item.item_id in owned_ids else "❌ MISSING "
            print(f"[{status}] {item.name:<28} ({item.item_type}) | {item.zone}")
            if item.item_id not in owned_ids and item.clean_hint():
                print(f"        Hint: {item.clean_hint()}")
        print()
        return

    if not args.name:
        print("Please provide --name <item_name> or --death-mage.")
        return

    matches = analyzer.search_items(args.name, args.type)
    if not matches:
        print(f"No catalog items matching '{args.name}' found.")
        return

    print(f"\n=== Search Results for '{args.name}' ===")
    for item in matches:
        status = "✅ ACQUIRED" if item.item_id in owned_ids else "❌ MISSING "
        print(f"[{status}] {item.name} ({item.item_type}) — Region: {item.region} ({item.zone})")
        if item.item_id not in owned_ids and item.clean_hint():
            print(f"        Hint: {item.clean_hint()}")
    print()


def cmd_sync(args: argparse.Namespace):
    """Export character_tracker.md and save_summary.json."""
    save, slot = _get_save_and_slot(args)
    analyzer = ProgressionAnalyzer()
    char = save.parse_character(slot, analyzer.collectibles_definitions)
    report = analyzer.analyze(char)

    exporter = ProgressExporter(report)
    out_dir = args.out or "."
    md_path, json_path = exporter.export_all(out_dir)

    print(f"✅ Successfully exported tracker files for '{char.name}' (Level {char.level}):")
    print(f"   - Markdown: {md_path}")
    print(f"   - JSON:     {json_path}")


def cmd_watch(args: argparse.Namespace):
    """Watch save file and auto-sync on game changes."""
    watch_save_file(
        save_path=args.save_path,
        slot_index=args.slot,
        output_dir=args.out,
        poll_interval=args.interval or 3.0,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elden_tracker",
        description="Elden Ring Save File Progression Analyzer & AI Guide",
    )
    parser.add_argument(
        "--save-path",
        "-f",
        help="Explicit path to ER0000.sl2 / ER0000.co2 file (defaults to auto-detect).",
    )
    parser.add_argument(
        "--slot",
        "-s",
        type=int,
        help="Character slot index (0-9). Defaults to first active character.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    subparsers.add_parser("list", help="List all character slots in the save file.")

    # stats
    subparsers.add_parser("stats", help="Display stats, runes, and collectible capacities.")

    # materials
    subparsers.add_parser("materials", help="Display held upgrade materials (Smithing Stones, Somber Stones).")

    # summary
    subparsers.add_parser("summary", help="Display regional completion percentages.")

    # missing
    p_missing = subparsers.add_parser("missing", help="List missing items by region or zone.")
    p_missing.add_argument("--region", "-r", help="Filter by region (e.g. Limgrave, Caelid).")
    p_missing.add_argument("--zone", "-z", help="Filter by zone name substring.")
    p_missing.add_argument("--type", "-t", help="Filter by acquisition type (e.g. boss, chest, scarab, merchant, foe).")
    p_missing.add_argument("--category", "-c", help="Filter by gear category (weapon, armor, talisman, spell, ash_of_war, cookbook, key_item).")
    p_missing.add_argument("--limit", "-l", type=int, default=30, help="Max items to list.")

    # query
    p_query = subparsers.add_parser("query", help="Check status of specific items.")
    p_query.add_argument("--name", "-n", help="Item name to search for.")
    p_query.add_argument("--type", "-t", help="Acquisition type filter (boss, chest, etc.).")
    p_query.add_argument("--category", "-c", help="Gear category (weapon, armor, talisman, spell, etc.).")
    p_query.add_argument(
        "--death-mage",
        action="store_true",
        help="Check status of all key Death Mage sorceries, weapons, and staves.",
    )

    # sync
    p_sync = subparsers.add_parser("sync", help="Export character_tracker.md and save_summary.json.")
    p_sync.add_argument("--out", "-o", default=".", help="Target output directory.")

    # watch
    p_watch = subparsers.add_parser("watch", help="Continuously watch save file and re-sync on change.")
    p_watch.add_argument("--out", "-o", default=".", help="Target output directory.")
    p_watch.add_argument("--interval", "-i", type=float, default=3.0, help="Polling interval (seconds).")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        # Default behavior: run sync
        cmd_sync(args)
        return

    commands = {
        "list": cmd_list,
        "stats": cmd_stats,
        "materials": cmd_materials,
        "summary": cmd_summary,
        "missing": cmd_missing,
        "query": cmd_query,
        "sync": cmd_sync,
        "watch": cmd_watch,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
