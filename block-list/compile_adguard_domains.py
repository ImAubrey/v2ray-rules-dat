#!/usr/bin/env python3
"""Convert the hostname rules that GeoSite can represent into category files."""

import argparse
from collections import Counter
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit


CATEGORIES = (
    "important-allow",
    "important-block",
    "allow",
    "block",
)
TAG = re.compile(r"[a-z0-9][a-z0-9_-]*", re.ASCII)
DOMAIN = re.compile(r"[a-z0-9_-]{1,63}(?:\.[a-z0-9_-]{1,63})+", re.ASCII)
INLINE_COMMENT = re.compile(r"\s+#")


def hostname(value: str) -> str | None:
    normalized = value.removesuffix(".").lower()
    if (
        len(normalized) > 253
        or not DOMAIN.fullmatch(normalized)
        or normalized.replace(".", "").isdigit()
    ):
        return None
    return normalized


def rules(source: Path):
    with source.open(encoding="utf-8-sig") as stream:
        for raw in stream:
            line = INLINE_COMMENT.split(raw.strip(), maxsplit=1)[0].strip()
            if line and not line.startswith(("!", "#", "[Adblock", "[AdGuard")):
                yield line


def disabled_rules(source: Path) -> set[str]:
    disabled = set()
    for line in rules(source):
        pattern, separator, settings = line.partition("$")
        if not separator:
            continue
        modifiers = settings.split(",")
        if "badfilter" in modifiers:
            remaining = ",".join(value for value in modifiers if value != "badfilter")
            disabled.add(pattern + ("$" + remaining if remaining else ""))
    return disabled


def convert(line: str) -> tuple[str, list[str]] | tuple[None, str]:
    exception = line.startswith("@@")
    text = line[2:] if exception else line
    if text.startswith("/"):
        return None, "exception_regex" if exception else "regex"

    pattern, separator, modifiers = text.partition("$")
    if separator and modifiers != "important":
        reason = "exception_modifiers" if exception else "modifiers"
        return None, reason
    category = ("important-" if separator else "") + ("allow" if exception else "block")

    if pattern.startswith("||") and pattern.endswith("^"):
        domain = hostname(pattern[2:-1])
        if domain:
            return category, [f"domain:{domain}"]
    elif pattern.startswith("||"):
        domain = hostname(pattern[2:])
        if domain:
            return category, [r"regexp:(^|\.)" + domain.replace(".", r"\.")]
    elif not separator and not exception:
        domain = hostname(pattern)
        if domain:
            return category, [f"full:{domain}"]
        values = pattern.split()
        if len(values) > 1:
            address, *aliases = values
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                return None, "unsupported_pattern"
            if not (ip.is_unspecified or ip.is_loopback):
                return None, "hosts_rewrite"
            matched = [f"full:{domain}" for alias in aliases if (domain := hostname(alias))]
            if matched:
                return category, matched

    return None, "exception_pattern" if exception else "unsupported_pattern"


def category_name(name: str, kind: str) -> str:
    return name if kind == "block" else f"{name}-{kind}"


def compile_categories(source: Path, output: Path, name: str) -> dict:
    disabled = disabled_rules(source)
    categories = {category: set() for category in CATEGORIES}
    skipped = Counter()
    for rule in rules(source):
        if rule in disabled or "badfilter" in rule.partition("$")[2].split(","):
            skipped["badfilter"] += 1
            continue
        category, converted = convert(rule)
        if category is None:
            skipped[converted] += 1
        else:
            categories[category].update(converted)

    if not any(categories.values()):
        raise ValueError(f"{name} contains no supported domain rules")
    output.mkdir(parents=True, exist_ok=True)
    tags = {}
    records = {}
    for category, entries in categories.items():
        # The source's primary label includes its important blocks. Its separate
        # important label is also available for an earlier DNS policy rule.
        include = ""
        if category == "block" and categories["important-block"]:
            include = f"include:{category_name(name, 'important-block')}\n"
        if not entries and not include:
            continue
        tag = category_name(name, category)
        path = output / tag
        if path.exists():
            raise ValueError(f"duplicate generated GeoSite tag: {tag}")
        path.write_text(include + "".join(f"{entry}\n" for entry in sorted(entries)), encoding="utf-8")
        tags[category] = f"ext:block-list.dat:{tag}"
        records[tag] = len(entries)
    with source.open("rb") as stream:
        input_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "input_sha256": input_sha256,
        "category_records": records,
        "skipped_rules": dict(sorted(skipped.items())),
        "tags": tags,
    }


def compile_sources(sources: dict[str, Path], output: Path) -> dict:
    return {"sources": {name: compile_categories(path, output, name) for name, path in sources.items()}}


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    data = {}
    for name, value in pairs:
        if name in data:
            raise ValueError(f"duplicate JSON member: {name}")
        data[name] = value
    return data


def load_sources(manifest: Path) -> dict[str, str]:
    data = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(data, dict):
        raise ValueError("the AdGuard source manifest must be a JSON object of names and URLs")
    selected = {}
    for key, url in data.items():
        name = key.lower()
        if not TAG.fullmatch(name) or name == "all":
            raise ValueError(f"invalid GeoSite tag: {key!r}")
        if name in selected:
            raise ValueError(f"duplicate GeoSite tag: {name}")
        if not isinstance(url, str):
            raise ValueError(f"{name} requires an HTTPS URL")
        address = urlsplit(url)
        if address.scheme != "https" or not address.hostname or address.username is not None:
            raise ValueError(f"{name} requires a public HTTPS URL")
        selected[name] = url
    return selected


def download_and_compile(manifest: Path, output: Path) -> dict:
    selected = load_sources(manifest)
    with TemporaryDirectory(prefix="adguard-lists-") as scratch:
        sources = {}
        for name, url in selected.items():
            path = Path(scratch) / name
            subprocess.run(
                ["curl", "--fail", "--silent", "--show-error", "--location", "--retry", "3",
                 "--max-time", "120", "--proto", "=https", "--proto-redir", "=https",
                 "--output", str(path), url],
                check=True,
            )
            sources[name] = path
        return compile_sources(sources, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.dumps(download_and_compile(args.manifest, args.output), indent=2)
    args.report.write_text(report + "\n", encoding="utf-8")
    print(report)
