from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from generate_bank import generate_bank, prepare_bank_inputs


class BankCategoryTests(unittest.TestCase):
    def test_preserves_custom_rules_and_includes_all_bank_sources_once(self):
        with TemporaryDirectory() as temporary:
            data = Path(temporary)
            target = data / "category-bank"
            target.write_text("domain:bank.example\ninclude:category-bank-cn # existing")
            for name in ("category-bank-cn", "category-bank-jp", "category-bank-legacy", "category-ads-all"):
                (data / name).touch()
            (data / "category-bank-directory").mkdir()
            self.assertEqual(generate_bank(data), ["category-bank-cn", "category-bank-jp", "category-bank-legacy"])
            self.assertEqual(
                target.read_text(),
                "domain:bank.example\ninclude:category-bank-cn # existing\n"
                "include:category-bank-jp\ninclude:category-bank-legacy\n",
            )
            first = target.read_bytes()
            generate_bank(data)
            self.assertEqual(target.read_bytes(), first)

    def test_external_build_copies_only_bank_dependencies_and_legacy_rules(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "community"
            source.mkdir()
            data = root / "output"
            legacy = root / "legacy"
            legacy.write_text("domain:archived.example\n")
            (source / "category-bank-cn").write_text("include:some-bank @cn\n")
            (source / "some-bank").write_text("include:bank-provider\n")
            (source / "bank-provider").write_text("domain:provider.example\n")
            (source / "unrelated").write_text("domain:unrelated.example\n")

            self.assertEqual(prepare_bank_inputs(source, data, legacy), ["category-bank-cn", "category-bank-legacy"])
            self.assertEqual(
                sorted(path.name for path in data.iterdir()),
                ["bank-provider", "category-bank", "category-bank-cn", "category-bank-legacy", "some-bank"],
            )
            self.assertEqual((data / "category-bank-cn").read_text(), "include:some-bank @cn\n")
