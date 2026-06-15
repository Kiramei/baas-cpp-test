#!/usr/bin/env python3
"""Small resource assertions shared by BAAS_Cpp validation workflows."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


VENDORED_RESOURCE_PATHS = [
    "resource/bin",
    "resource/ocr_models",
    "apps/BAAS/resource/yolo_models",
]

MANIFEST_PATHS = [
    ("scrcpy server", "bin/scrcpy/scrcpy-server.jar"),
    ("Windows ADB", "bin/Windows/platform-tools/adb.exe"),
    ("macOS ADB", "bin/MacOS/platform-tools/adb"),
    ("Linux ADB", "bin/Linux/platform-tools/adb"),
    ("OCR config", "ocr_models/configs.txt"),
    ("YOLO config", "yolo_models/data.yaml"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BAAS_Cpp resource layout.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    no_vendored = subparsers.add_parser("no-vendored", help="Assert large resources are not tracked.")
    no_vendored.add_argument("--source-root", required=True, type=Path)

    outputs = subparsers.add_parser("outputs", help="Assert required output paths exist.")
    outputs.add_argument("--root", required=True, type=Path)
    outputs.add_argument("--path", action="append", default=[], required=True)

    manifest = subparsers.add_parser("manifest", help="Append a compact resource manifest.")
    manifest.add_argument("--root", required=True, type=Path)
    manifest.add_argument("--summary", type=Path)

    cache_snapshot = subparsers.add_parser("cache-snapshot", help="Write a deterministic cache manifest.")
    cache_snapshot.add_argument("--root", required=True, type=Path)
    cache_snapshot.add_argument("--out", required=True, type=Path)

    cache_list = subparsers.add_parser("cache-list", help="Print resource cache file sizes.")
    cache_list.add_argument("--root", required=True, type=Path)

    return parser.parse_args()


def check_no_vendored(source_root: Path) -> int:
    result = subprocess.run(
        ["git", "-C", str(source_root), "ls-files", *VENDORED_RESOURCE_PATHS],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if tracked:
        print("BAAS_Cpp still tracks vendored runtime resources:", file=sys.stderr)
        for path in tracked:
            print(f"  {path}", file=sys.stderr)
        return 1

    print("BAAS_Cpp checkout has no tracked vendored runtime resources.")
    return 0


def check_outputs(root: Path, paths: list[str]) -> int:
    missing = [path for path in paths if not (root / path).exists()]
    if missing:
        print(f"Missing required resource outputs under {root}:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    print(f"Required resource outputs exist under {root}:")
    for path in paths:
        print(f"  {path}")
    return 0


def dir_count(root: Path, relative: str) -> str:
    directory = root / relative
    if not directory.exists():
        return "missing"
    count = sum(1 for path in directory.rglob("*") if path.is_file())
    return str(count)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cache_entries(root: Path) -> list[dict[str, object]]:
    if not root.exists():
        return []

    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def write_cache_snapshot(root: Path, out: Path) -> int:
    entries = cache_entries(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(entries, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Wrote resource cache snapshot: {out} ({len(entries)} files)")
    return 0


def format_size(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{size} B"


def print_cache_list(root: Path) -> int:
    entries = cache_entries(root)
    total = sum(int(entry["size"]) for entry in entries)
    print(f"Resource cache root: {root}")
    print(f"Resource cache files: {len(entries)}")
    print(f"Resource cache size: {format_size(total)}")
    for entry in entries:
        print(f"{format_size(int(entry['size'])):>12}  {entry['path']}")
    return 0


def append_manifest(root: Path, summary: Path | None) -> int:
    lines = [
        "### BAAS resource manifest",
        "",
        "| Resource | Path | Size |",
        "|---|---|---:|",
    ]
    for label, relative in MANIFEST_PATHS:
        path = root / relative
        if path.exists():
            size = path.stat().st_size
            size_text = f"{size:,} bytes"
        else:
            size_text = "missing"
        lines.append(f"| {label} | `{relative}` | {size_text} |")

    lines.extend(
        [
            "",
            "| Directory | Files |",
            "|---|---:|",
            f"| `bin` | {dir_count(root, 'bin')} |",
            f"| `ocr_models` | {dir_count(root, 'ocr_models')} |",
            f"| `yolo_models` | {dir_count(root, 'yolo_models')} |",
            "",
        ]
    )

    text = "\n".join(lines)
    print(text)
    if summary:
        with summary.open("a", encoding="utf-8") as handle:
            handle.write(text)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "no-vendored":
        return check_no_vendored(args.source_root)
    if args.command == "outputs":
        return check_outputs(args.root, args.path)
    if args.command == "manifest":
        return append_manifest(args.root, args.summary)
    if args.command == "cache-snapshot":
        return write_cache_snapshot(args.root, args.out)
    if args.command == "cache-list":
        return print_cache_list(args.root)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
