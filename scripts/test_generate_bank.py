from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from generate_bank import generate_bank


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
