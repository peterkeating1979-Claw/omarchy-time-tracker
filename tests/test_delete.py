import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker
import bridge


class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = tracker.connect(self.root/'tracker.db')
        self.run_cmd('add-company', 'Acme')
        self.run_cmd('add-project', 'Website', '--company', 'Acme')
        self.run_cmd('select', '--company', 'Acme', '--project', 'Website')
        self.vault = self.root/'Vault'
        self.vault.mkdir()
        self.run_cmd('vault', str(self.vault))
        self.run_cmd('auto-obsidian', 'on')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def run_cmd(self, *args, now=100):
        return tracker.execute(self.db, tracker.parser().parse_args(args), now)

    def session(self, start=100):
        self.run_cmd('start', now=start)
        return self.run_cmd('stop', now=start+60)

    def test_confirmation_is_required_including_bridge(self):
        session = self.session()
        for args in (['clear-records'], ['delete-record', str(session['id'])]):
            with self.assertRaisesRegex(ValueError, '--confirm'):
                tracker.execute(self.db, bridge.parse_request(json.dumps({'args': args})))
        self.assertEqual(len(self.run_cmd('records')), 1)

    def test_delete_one_preserves_exports_and_other_sessions(self):
        first = self.session()
        second = self.session(200)
        note = Path(first['obsidian_path'])
        content = note.read_bytes()
        self.assertEqual(self.run_cmd('delete-record', str(first['id']), '--confirm')['deleted_records'], 1)
        self.assertEqual([r['id'] for r in self.run_cmd('records')], [second['id']])
        self.assertIsNone(self.db.execute('SELECT * FROM obsidian_jobs WHERE session_id=?', (first['id'],)).fetchone())
        self.assertEqual(note.read_bytes(), content)
        with self.assertRaisesRegex(ValueError, 'not found'):
            self.run_cmd('delete-record', str(first['id']), '--confirm')

    def test_clear_all_cancels_pending_jobs_and_keeps_setup(self):
        self.vault.rmdir()
        self.session()
        self.assertEqual(self.run_cmd('status')['obsidian_pending'], 1)
        result = self.run_cmd('clear-records', '--confirm')
        self.assertEqual(result['deleted_records'], 1)
        self.assertEqual(self.run_cmd('records'), [])
        status = self.run_cmd('status')
        self.assertEqual(status['obsidian_pending'], 0)
        self.assertEqual(status['selected_company'], 'Acme')
        self.assertEqual(status['selected_project'], 'Website')
        self.assertEqual(status['obsidian_vault'], str(self.vault))
        self.assertTrue(status['obsidian_autolog'])
        self.assertEqual(len(self.run_cmd('companies')), 1)
        self.assertEqual(len(self.run_cmd('projects')), 1)
        self.assertEqual(self.run_cmd('retry-obsidian')['attempted'], 0)
        self.assertEqual(self.run_cmd('clear-records', '--confirm')['deleted_records'], 0)
        self.vault.mkdir()
        self.assertIn('obsidian_path', self.session(300))

    def test_running_timer_is_protected(self):
        stopped = self.session()
        running = self.run_cmd('start', now=200)
        for args in (('clear-records', '--confirm'), ('delete-record', str(running['id']), '--confirm')):
            with self.assertRaisesRegex(ValueError, 'Stop the running timer'):
                self.run_cmd(*args)
        self.assertEqual(len(self.run_cmd('records')), 2)
        self.run_cmd('delete-record', str(stopped['id']), '--confirm')
        self.assertEqual(self.run_cmd('status')['running']['id'], running['id'])

    def test_failed_delete_rolls_back_jobs(self):
        self.session()
        self.db.execute("CREATE TRIGGER block_delete BEFORE DELETE ON sessions BEGIN SELECT RAISE(ABORT, 'blocked'); END")
        with self.assertRaises(tracker.sqlite3.IntegrityError):
            self.run_cmd('clear-records', '--confirm')
        self.assertEqual(self.db.execute('SELECT count(*) FROM obsidian_jobs').fetchone()[0], 1)
        self.assertEqual(len(self.run_cmd('records')), 1)


if __name__ == '__main__':
    unittest.main()
