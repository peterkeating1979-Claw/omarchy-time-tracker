import importlib.util
from pathlib import Path
import tempfile
import unittest
from datetime import datetime

spec = importlib.util.spec_from_file_location('tracker', Path(__file__).resolve().parents[1] / 'tracker.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'tracker.db'
        self.db = t.connect(self.path)
        self.run_cmd('timezone', 'America/Curacao')
        self.run_cmd('add-company', 'Acme')
        self.run_cmd('add-company', 'Other')
        self.run_cmd('add-project', 'Website', '--company', 'Acme')
        self.run_cmd('select', '--company', 'Acme', '--project', 'Website')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def run_cmd(self, *args, now=1800000000):
        return t.execute(self.db, t.parser().parse_args(list(args)), now)

    def test_persistence_selection_and_no_overlap(self):
        self.run_cmd('start', now=100)
        self.db.close()
        self.db = t.connect(self.path)
        self.assertEqual(self.run_cmd('status', now=160)['running']['seconds'], 60)
        with self.assertRaises(ValueError):
            self.run_cmd('start', now=160)
        self.run_cmd('select', '--company', 'Other')
        stopped = self.run_cmd('stop', now=3700)
        self.assertEqual((stopped['company'], stopped['project'], stopped['seconds']), ('Acme', 'Website', 3600))
        self.assertEqual(self.run_cmd('start', now=3800)['company'], 'Other')

    def test_midnight_and_company_project_filters(self):
        start = datetime.fromisoformat('2026-09-06T23:30:00-04:00').timestamp()
        self.run_cmd('start', now=start)
        self.run_cmd('stop', now=start + 7200)
        result = self.run_cmd('report', 'monthly', '--date', '2026-09-07')
        self.assertEqual([r['seconds'] for r in result['daily']], [1800, 5400])
        self.assertEqual(result['total_hours'], 2)
        week = self.run_cmd('report', 'weekly', '--date', '2026-09-07', '--company', 'Acme', '--project', 'Website')
        self.assertEqual(week['total_hours'], 1.5)
        self.assertEqual(self.run_cmd('report', 'yearly', '--date', '2026-09-07', '--company', 'Other')['total_hours'], 0)

    def test_running_report_clipped_at_year_boundary(self):
        start = datetime.fromisoformat('2025-12-31T23:00:00-04:00').timestamp()
        self.run_cmd('start', now=start)
        result = self.run_cmd('report', 'yearly', '--date', '2026-01-01', now=start+7200)
        self.assertEqual(result['total_hours'], 1)
        self.assertTrue(result['includes_running_timer'])

    def test_dst_actual_elapsed_time(self):
        self.run_cmd('timezone', 'America/New_York')
        for beginning, finish, expected in [
            ('2026-03-08T00:00:00-05:00', '2026-03-09T00:00:00-04:00', 23),
            ('2026-11-01T00:00:00-04:00', '2026-11-02T00:00:00-05:00', 25),
        ]:
            start = datetime.fromisoformat(beginning).timestamp()
            end = datetime.fromisoformat(finish).timestamp()
            self.run_cmd('start', now=start)
            self.run_cmd('stop', now=end)
            result = self.run_cmd('report', 'daily', '--date', beginning[:10], now=end)
            self.assertEqual(result['total_hours'], expected)

    def test_general_time_and_invalid_project(self):
        self.assertIsNone(self.run_cmd('start', '--no-project', now=100)['project'])
        self.run_cmd('stop', now=200)
        with self.assertRaises(ValueError):
            self.run_cmd('start', '--company', 'Other', '--project', 'Website')
        self.assertIsNone(self.run_cmd('status')['running'])

    def test_calendar_bounds(self):
        a, b = t.period_bounds('monthly', t.date(2024, 2, 29))
        self.assertEqual((b-a).days, 29)
        self.assertEqual(t.period_bounds('monthly', t.date(2026, 12, 7))[1], t.date(2027, 1, 1))


if __name__ == '__main__':
    unittest.main()
