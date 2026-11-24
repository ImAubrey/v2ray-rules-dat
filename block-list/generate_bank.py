#!/usr/bin/env python3
"""Include every category-bank-* source in category-bank."""

import argparse
from pathlib import Path
import shutil


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


def prepare_bank_inputs(source_dir: Path, data_dir: Path, legacy: Path) -> list[str]:
    data_dir.mkdir(parents=True, exist_ok=True)
    legacy_name = "category-bank-legacy"
    shutil.copyfile(legacy, data_dir / legacy_name)
    copied = {legacy_name}

    def copy_category(name: str) -> None:
        if name in copied:
            return
        if Path(name).name != name or name in ("", ".", "..", "all"):
            raise ValueError(f"invalid bank category dependency: {name!r}")
        original = source_dir / name
        contents = original.read_text(encoding="utf-8")
        (data_dir / name).write_text(contents, encoding="utf-8")
        copied.add(name)
        for line in contents.splitlines():
            rule = line.split("#", 1)[0].strip()
            if rule.startswith("include:"):
                parts = rule.removeprefix("include:").split(maxsplit=1)
                if not parts:
                    raise ValueError(f"empty include in {original}")
                copy_category(parts[0].split("@", 1)[0])

    for path in sorted(source_dir.glob("category-bank*")):
        if path.is_file() and (path.name == "category-bank" or path.name.startswith("category-bank-")):
            copy_category(path.name)
    return generate_bank(data_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("legacy", type=Path)
    args = parser.parse_args()
    sources = prepare_bank_inputs(args.source_dir, args.data_dir, args.legacy)
    print("category-bank includes " + ", ".join(sources))
