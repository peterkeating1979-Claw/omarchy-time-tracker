import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker


class ObsidianTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'My Vault #1'
        self.vault.mkdir()
        self.db = tracker.connect(self.root/'tracker.db')
        self.run_cmd('timezone','America/Curacao')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def run_cmd(self, *args, now=1800000000):
        return tracker.execute(self.db, tracker.parser().parse_args(list(args)), now)

    def test_filtered_records_and_active_snapshot(self):
        self.run_cmd('vault', str(self.vault))
        self.assertEqual(self.run_cmd('status')['obsidian_vault'], str(self.vault))
        self.run_cmd('add-company', 'Acme | [[Link]] <img>')
        self.run_cmd('add-project','Website','--company','Acme | [[Link]] <img>')
        start = tracker.datetime.fromisoformat('2026-09-06T23:30:00-04:00').timestamp()
        self.run_cmd('start','--company','Acme | [[Link]] <img>','--project','Website','--note','Work <% script %> | note',now=start)
        result = self.run_cmd('report','daily','--date','2026-09-07','--company','Acme | [[Link]] <img>','--project','Website','--obsidian',now=start+7200)
        path = Path(result['obsidian_path'])
        content = path.read_text()
        self.assertEqual(path.parent, self.vault/'Time Tracker')
        self.assertIn('01:30:00', content)
        self.assertIn('Session records', content)
        self.assertIn('2026\\-09\\-06T23:30:00', content)
        self.assertIn('Work &lt;% script %&gt; \\| note', content)
        self.assertIn('provisional: true', content)
        self.assertNotIn('<img>', content.split('---',2)[2])
        self.assertEqual(unquote(result['obsidian_uri'].split('path=')[1]), str(path))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertIsNotNone(self.run_cmd('status')['running'])

    def test_reexports_preserve_notes_and_vault_config(self):
        self.run_cmd('vault', str(self.vault))
        existing = self.vault/'Personal.md'
        existing.write_text('My own note')
        config = self.vault/'.obsidian'
        config.mkdir()
        prefs = config/'app.json'
        prefs.write_text('{"setting":true}')
        a = self.run_cmd('report','monthly','--obsidian')['obsidian_path']
        b = self.run_cmd('report','monthly','--obsidian')['obsidian_path']
        self.assertNotEqual(a,b)
        self.assertTrue(Path(a).exists())
        self.assertEqual(existing.read_text(), 'My own note')
        self.assertEqual(prefs.read_text(), '{"setting":true}')
        self.run_cmd('vault','--clear')
        self.assertEqual(self.run_cmd('status')['obsidian_vault'], '')
        self.assertTrue(Path(b).exists())

    def test_missing_or_unsafe_vault_fails_without_notes(self):
        with self.assertRaises(ValueError):
            self.run_cmd('report','daily','--obsidian')
        missing = self.root/'missing'
        with self.assertRaises(ValueError):
            self.run_cmd('vault',str(missing))
        self.assertFalse(missing.exists())
        self.run_cmd('vault',str(self.vault))
        outside = self.root/'outside'
        outside.mkdir()
        (self.vault/'Time Tracker').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_cmd('report','daily','--obsidian')
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
