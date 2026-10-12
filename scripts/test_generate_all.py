import tempfile
import unittest
from pathlib import Path

from generate_all import generate_all


class GenerateAllTests(unittest.TestCase):
    def test_unfiltered_includes_cover_children(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "leaf").write_text("domain:example.com\n", encoding="utf-8")
            (data / "middle").write_text("include:leaf\n", encoding="utf-8")
            (data / "root").write_text("include:middle\n", encoding="utf-8")
            (data / "filtered").write_text("include:leaf @cn\n", encoding="utf-8")

            self.assertEqual(generate_all(data), ["filtered", "root"])
            self.assertEqual((data / "all").read_text(encoding="utf-8"), "include:filtered\ninclude:root\n")

    def test_filtered_include_does_not_cover_child(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "leaf").write_text("domain:example.com\n", encoding="utf-8")
            (data / "filtered").write_text("include:leaf @cn\n", encoding="utf-8")

            self.assertEqual(generate_all(data), ["filtered", "leaf"])

    def test_existing_all_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "loop").write_text("include:all\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "reserved ALL"):
                generate_all(data)


if __name__ == "__main__":
    unittest.main()
