import json, tempfile, unittest
from pathlib import Path

from ad_runner_gui import (
    add_or_update_exoclick_ad, ensure_site_sheet, list_sites, load_workbook,
    parse_dimensions, save_workbook
)

class WorkbookHelpersTest(unittest.TestCase):
    def new_wb(self): return {"SheetNames": ["_README"], "Sheets": {"_README": {"aoa": [["keep"]]}}}

    def test_create_new_website(self):
        wb = self.new_wb(); rows = ensure_site_sheet(wb, "animeplex.lol", "maximum-revenue")
        self.assertIn("animeplex.lol", list_sites(wb))
        self.assertTrue(any(r["block_type"] == "SITE" and r["field"] == "site_id" for r in rows))

    def test_add_exoclick_ad(self):
        wb = self.new_wb(); info = add_or_update_exoclick_ad(wb, "animeplex.lol", "Top Banner", "728x90", "top", "<script>exo()</script>")
        rows = wb["Sheets"]["animeplex.lol"]["rows"]
        self.assertEqual(info["unit_id"], "top-banner-exoclick")
        self.assertTrue(any(r["block_type"] == "NETWORK" and r["value"] == "exoclick" for r in rows))
        self.assertTrue(any(r["block_type"] == "PLACEMENT" and r["field"] == "candidates" and r["value"] == "top-banner-exoclick" for r in rows))

    def test_update_same_ad_without_duplication(self):
        wb = self.new_wb()
        add_or_update_exoclick_ad(wb, "animeplex.lol", "Top Banner", "728x90", "top", "one")
        add_or_update_exoclick_ad(wb, "animeplex.lol", "Top Banner", "970x90", "leaderboard", "two")
        rows = wb["Sheets"]["animeplex.lol"]["rows"]
        keys = [(r["block_type"], r["block_id"], r["field"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn(("UNIT", "top-banner-exoclick", "markup"), keys)
        self.assertEqual([r for r in rows if r["block_id"] == "top-banner-exoclick" and r["field"] == "markup"][0]["value"], "two")

    def test_preserve_unrelated_rows(self):
        wb = self.new_wb(); rows = ensure_site_sheet(wb, "animeplex.lol")
        rows.append({"block_type":"UNIT","block_id":"house","field":"html","value":"<b>House</b>"})
        add_or_update_exoclick_ad(wb, "animeplex.lol", "Rectangle", "300x250", "in-content", "exo")
        self.assertTrue(any(r.get("block_id") == "house" and r.get("value") == "<b>House</b>" for r in rows))

    def test_reject_invalid_sizes(self):
        for bad in ["728", "0x90", "10x10001", "widextall"]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): parse_dimensions(bad)

    def test_preserve_multiline_exoclick_code(self):
        wb = self.new_wb(); markup = "<script>\nvar a = 1;\n</script>\n<div>ad</div>"
        add_or_update_exoclick_ad(wb, "animeplex.lol", "Top Banner", "728x90", "top", markup)
        rows = wb["Sheets"]["animeplex.lol"]["rows"]
        self.assertEqual([r for r in rows if r["field"] == "markup"][0]["value"], markup)

    def test_atomic_workbook_saving(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ad-runner.xlsx"
            wb = self.new_wb(); save_workbook(path, wb)
            wb2 = load_workbook(path); add_or_update_exoclick_ad(wb2, "animeplex.lol", "Top Banner", "728x90", "top", "exo")
            backup = save_workbook(path, wb2)
            self.assertTrue(path.exists()); self.assertTrue(backup.exists())
            self.assertEqual(json.loads(path.read_text())["SheetNames"], ["_README", "animeplex.lol"])
            self.assertFalse(list(Path(td).glob("*.tmp")))

if __name__ == "__main__":
    unittest.main()
