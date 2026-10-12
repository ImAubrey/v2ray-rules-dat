#!/usr/bin/env python3
"""Build an ALL GeoSite list from the final community/data directory."""

import argparse
from pathlib import Path


def generate_all(data_dir: Path) -> list[str]:
    files = {
        path.name.casefold(): path
        for path in data_dir.iterdir()
        if path.is_file() and path.name.casefold() != "all"
    }
    if not files:
        raise ValueError(f"no GeoSite category files in {data_dir}")

    # An unfiltered include carries every rule from the child category. A
    # filtered include does not, so that child must remain a top-level input.
    included = set()
    children = {name: set() for name in files}
    for name, path in files.items():
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line.startswith("include:"):
                continue
            target, attribute_marker, _ = line[len("include:") :].partition("@")
            target = target.strip().casefold()
            if target == "all":
                raise ValueError(f"{path} includes reserved ALL category")
            if not attribute_marker and target in files:
                included.add(target)
                children[name].add(target)

    roots = sorted(files.keys() - included)
    reached = set(roots)
    pending = list(roots)
    while pending:
        for child in children[pending.pop()]:
            if child not in reached:
                reached.add(child)
                pending.append(child)
    if reached != files.keys():
        raise ValueError(f"categories are not covered by ALL: {sorted(files.keys() - reached)}")

    (data_dir / "all").write_text(
        "".join(f"include:{files[name].name}\n" for name in roots), encoding="utf-8"
    )
    return roots


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path)
    args = parser.parse_args()
    roots = generate_all(args.data_dir)
    print(f"ALL covers {len(list(args.data_dir.iterdir())) - 1} categories using {len(roots)} includes")
