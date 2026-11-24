#!/usr/bin/env python3
"""Include every category-bank-* source in category-bank."""

import argparse
from pathlib import Path


def generate_bank(data_dir: Path) -> list[str]:
    sources = sorted(path.name for path in data_dir.glob("category-bank-*") if path.is_file())
    if not sources:
        raise ValueError(f"no category-bank-* sources in {data_dir}")

    target = data_dir / "category-bank"
    original = target.read_text(encoding="utf-8") if target.is_file() else ""
    existing = {line.split("#", 1)[0].strip() for line in original.splitlines()}
    includes = [f"include:{name}" for name in sources]
    missing = [line for line in includes if line not in existing]
    if missing:
        separator = "\n" if original and not original.endswith("\n") else ""
        target.write_text(original + separator + "\n".join(missing) + "\n", encoding="utf-8")
    return sources


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path)
    args = parser.parse_args()
    sources = generate_bank(args.data_dir)
    print("category-bank includes " + ", ".join(sources))
