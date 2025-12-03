#!/usr/bin/env python3
"""Debug script to see how scanner handles case conflicts."""

from pathlib import Path
from remote_office_sync.config_loader import load_config
from remote_office_sync.scanner import Scanner
from remote_office_sync.state_db import StateDB

# Load config
config = load_config("config.yaml")

# Scan both sides
scanner = Scanner(
    ignore_extensions=config.get("ignore_extensions", []),
    ignore_prefix=config.get("ignore_prefix", []),
    ignore_exact=config.get("ignore_exact", []),
)
left_scan = scanner.scan_side(config.left_root, is_left=True)
right_scan = scanner.scan_side(config.right_root, is_left=False)

# Merge
current_state = scanner.merge_scans(left_scan, right_scan)

# Filter for our test
test_files = {
    path: meta
    for path, meta in current_state.items()
    if "case_conflict_canonical" in path.lower()
}

print("=" * 60)
print("FILES IN case_conflict_canonical:")
print("=" * 60)
for path, meta in sorted(test_files.items()):
    print(f"\nPath: {path}")
    print(f"  exists_left: {meta.exists_left}")
    print(f"  exists_right: {meta.exists_right}")
    print(f"  mtime_left: {meta.mtime_left}")
    print(f"  mtime_right: {meta.mtime_right}")
    print(f"  size_left: {meta.size_left}")
    print(f"  size_right: {meta.size_right}")

# Group by lowercase
print("\n" + "=" * 60)
print("GROUPED BY LOWERCASE:")
print("=" * 60)
grouped = {}
for path in test_files.keys():
    lower = path.lower()
    if lower not in grouped:
        grouped[lower] = []
    grouped[lower].append(path)

for lower, variants in sorted(grouped.items()):
    print(f"\nLowercase: {lower}")
    for variant in variants:
        meta = test_files[variant]
        print(f"  Variant: {variant}")
        print(f"    exists_left={meta.exists_left}, exists_right={meta.exists_right}")
