from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from compile_adguard_domains import compile_categories, compile_sources, load_sources


class AdGuardGeoSiteTests(unittest.TestCase):
    def test_preserves_hostname_scope_priority_exceptions_and_badfilter(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rules.txt"
            source.write_text(
                "\n".join(
                    [
                        "! comment",
                        "[Adblock Plus]",
                        "||Ads.Example.org^",
                        "tracking.example.org",
                        "0.0.0.0 exact.example.org # comment",
                        "192.0.2.1 rewrite.example.org",
                        "@@||safe.ads.example.org^",
                        "||priority.example.org^$important",
                        "@@||exception.example.org^$important",
                        "||disabled.example.org^",
                        "||disabled.example.org^$badfilter",
                        "||priority-disabled.example.org^$important",
                        "||priority-disabled.example.org^$important,badfilter",
                        "||private.example.org^$client=192.0.2.5",
                        "@@||special.example.org^$dnstype=AAAA",
                        r"/^foo\.example\.org$/",
                        "example.org##.cosmetic",
                        "||ads.example.org^",
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "data"
            report = compile_categories(source, output, "fixture")
            self.assertEqual(
                (output / "fixture").read_text().splitlines(),
                [
                    "include:fixture-important-block",
                    "domain:ads.example.org",
                    "full:exact.example.org",
                    "full:tracking.example.org",
                ],
            )
            self.assertEqual(
                (output / "fixture-allow").read_text(),
                "domain:safe.ads.example.org\n",
            )
            self.assertEqual(
                (output / "fixture-important-block").read_text(),
                "domain:priority.example.org\n",
            )
            self.assertEqual(
                (output / "fixture-important-allow").read_text(),
                "domain:exception.example.org\n",
            )
            self.assertEqual(
                report["skipped_rules"],
                {
                    "badfilter": 4,
                    "exception_modifiers": 1,
                    "hosts_rewrite": 1,
                    "modifiers": 1,
                    "regex": 1,
                    "unsupported_pattern": 1,
                },
            )

    def test_empty_source_is_rejected_before_creating_artifacts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rules.txt"
            source.write_text("! empty\n/^10\\./\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no supported domain rules"):
                compile_categories(source, root / "data", "fixture")
            self.assertFalse((root / "data").exists())

    def test_selected_source_names_become_independent_geosite_tags(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = {
                "aubrey-custom": "||prefix.example.org\n||priority.example.org^$important\n",
                "rebind": "@@||allow.example.org^\n/^10\\./\n",
            }
            sources = {}
            for name, rules in inputs.items():
                sources[name] = root / f"{name}.txt"
                sources[name].write_text(rules, encoding="utf-8")
            output = root / "data"
            result = compile_sources(sources, output)
            self.assertEqual(
                result["sources"]["aubrey-custom"]["tags"],
                {
                    "block": "ext:block-list.dat:aubrey-custom",
                    "important-block": "ext:block-list.dat:aubrey-custom-important-block",
                },
            )
            self.assertEqual(result["sources"]["rebind"]["tags"], {"allow": "ext:block-list.dat:rebind-allow"})
            self.assertEqual(result["sources"]["rebind"]["skipped_rules"], {"regex": 1})
            self.assertEqual(
                (output / "aubrey-custom").read_text(),
                "include:aubrey-custom-important-block\n"
                "regexp:(^|\\.)prefix\\.example\\.org\n",
            )
            self.assertFalse((output / "rebind").exists())

    def test_manifest_rejects_ambiguous_names_and_accepts_an_empty_selection(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "sources.json"
            manifest.write_text('{"Aubrey": "https://example.org/rules.txt"}', encoding="utf-8")
            self.assertEqual(load_sources(manifest), {"aubrey": "https://example.org/rules.txt"})
            manifest.write_text(
                '{"Aubrey": "https://example.org/a", "aubrey": "https://example.org/b"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate GeoSite tag"):
                load_sources(manifest)
            manifest.write_text('{"../other": "https://example.org/rules.txt"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid GeoSite tag"):
                load_sources(manifest)
            manifest.write_text("{}", encoding="utf-8")
            output = root / "data"
            self.assertEqual(compile_sources(load_sources(manifest), output), {"sources": {}})
            self.assertFalse(output.exists())
