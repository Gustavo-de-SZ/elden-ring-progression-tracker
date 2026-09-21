"""Save File Watcher.

Monitors the Elden Ring save file for changes and automatically re-syncs
the progression tracker whenever the game auto-saves (e.g. resting, looting, warping).
"""

from __future__ import annotations

import time
import pathlib
from typing import Optional
from .save_parser import EldenSaveFile
from .progression import ProgressionAnalyzer
from .exporter import ProgressExporter


def watch_save_file(
    save_path: Optional[str | pathlib.Path] = None,
    slot_index: Optional[int] = None,
    output_dir: Optional[str | pathlib.Path] = None,
    poll_interval: float = 3.0,
):
    """Continuously poll save file mtime and trigger export on change."""
    save = EldenSaveFile(save_path)
    analyzer = ProgressionAnalyzer()
    target_dir = pathlib.Path(output_dir or ".").resolve()

    # Determine slot
    profiles = save.get_characters()
    active = [p for p in profiles if p.is_active]
    if not active:
        print("[Watcher] No active characters found in save file.")
        return

    if slot_index is None:
        selected_slot = active[0].slot_index
    else:
        selected_slot = slot_index

    char_name = profiles[selected_slot].name
    print(f"[Watcher] Monitoring: {save.path}")
    print(f"[Watcher] Character: {char_name} (Slot {selected_slot})")
    print(f"[Watcher] Export directory: {target_dir}")
    print(f"[Watcher] Polling interval: {poll_interval}s. Press Ctrl+C to stop.\n")

    def run_sync():
        try:
            # Reload save file
            reloaded = EldenSaveFile(save.path)
            data = reloaded.parse_character(selected_slot, analyzer.collectibles_definitions)
            report = analyzer.analyze(data)
            exporter = ProgressExporter(report)
            md_path, json_path = exporter.export_all(target_dir)
            timestamp = time.strftime("%H:%M:%S")
            print(
                f"[{timestamp}] Synced: Level {data.level} | "
                f"{len(data.item_ids)} items | "
                f"{report.completion_rate:.1f}% catalog completion -> {md_path.name}"
            )
        except Exception as e:
            print(f"[Watcher Error] Failed to parse updated save: {e}")

    # Initial sync
    run_sync()

    last_mtime = save.path.stat().st_mtime
    try:
        while True:
            time.sleep(poll_interval)
            try:
                current_mtime = save.path.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    run_sync()
            except FileNotFoundError:
                pass
    except KeyboardInterrupt:
        print("\n[Watcher] Stopped.")
