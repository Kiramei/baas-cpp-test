#!/usr/bin/env python3
"""Small resource assertions shared by BAAS_Cpp validation workflows."""

from __future__ import annotations

import argparse
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
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
