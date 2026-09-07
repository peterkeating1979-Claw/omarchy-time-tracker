# Time Tracker for Omarchy

Track work by company and project from the Omarchy bar. Start a timer, get back to work, and export a polished PDF when you need to report your hours.

![Example monthly PDF report with fictional data](preview.png)

## Features

- Add companies and projects, and save your current selection.
- Start and stop a persistent timer. See elapsed time and the active company directly in the bar.
- Review daily, weekly, monthly, and yearly reports for all companies, one company, or one project.
- Export PDFs with total time, company totals, project breakdowns, daily detail, and page numbers.
- Open the latest PDF directly from the popup.
- Store everything locally in SQLite. No account, cloud service, or Codex installation required.

[View an example PDF](docs/sample-report.pdf) (fictional companies and hours).

## Requirements

- Omarchy Quattro with its Quickshell-based shell and `omarchy plugin` commands. This is not a Waybar module.
- Python 3.10+ with SQLite and timezone data (included in a normal Omarchy installation).
- `python-reportlab` for PDF export. Core tracking works without it.
- `xdg-utils` and an associated PDF viewer for **Open PDF**.
- Optional `noto-fonts` for the PDF's Noto Sans typography and accented Latin names. Otherwise, PDFs use Helvetica.

Install PDF support from the Arch repositories:

```bash
sudo pacman -S --needed python-reportlab noto-fonts
```

The plugin does not download dependencies, run installation hooks, or invoke a package manager. Dependency setup is an explicit user action.

## Install

```bash
omarchy plugin add https://github.com/peterkeating1979-Claw/omarchy-time-tracker --enable
```

Time Tracker appears on the right side of the bar. Click it to open the popup. To move it:

```bash
omarchy bar move peter.time-tracker --section right --index 0
```

## Use

1. Enter a company name and click **Add**.
2. Optionally add a project under that company.
3. Click **Start timer**, then **Stop timer** when finished.
4. Under **Reports**, choose a period and scope. Leave the date blank for the current period, or enter any date within the desired period as `YYYY-MM-DD`.
5. Click **Show report** or **Export PDF**. Exports are saved to `~/Documents/Time Tracker Reports/`; **Open PDF** opens the latest successful export.

**Save selection** remembers the company and project between popup visits. Changing the selection does not move a running timer to another company. Stop it before starting work for someone else.

Only one timer can run at once. It continues while applications are closed or the computer is asleep, until you stop it. No per-second background writes are needed; elapsed time comes from the saved start timestamp.

Weeks start Monday. Monthly and yearly reports use calendar periods. Overnight sessions are split into local days. Active timers are included through the report snapshot time and marked provisional in the PDF. Exports never overwrite an existing file.

## Timezone and command line

On first use, the plugin detects an IANA timezone from `TZ` or `/etc/localtime`, falling back to UTC. A previously saved timezone is preserved.

```bash
cd ~/.config/omarchy/plugins/peter.time-tracker
python3 tracker.py timezone America/Curacao
python3 tracker.py status
python3 tracker.py report weekly --company 'Acme' --date 2026-09-07
python3 tracker.py report monthly --company 'Acme' --pdf
python3 tracker.py report yearly --date 2026-01-01 --pdf --output /tmp/work-2026.pdf
```

Run `python3 tracker.py --help` to list commands. Output is JSON.

## Data and privacy

The SQLite database is stored at `$XDG_DATA_HOME/codex-time-tracker/tracker.sqlite3`, normally `~/.local/share/codex-time-tracker/tracker.sqlite3`. The historical folder name preserves compatibility with the original Codex companion; Codex is not required. `TIME_TRACKER_DB` overrides the database path, and the CLI also accepts `--db PATH` before the command.

The widget polls the local database every five seconds and updates the visible clock every second. It runs the included Python bridge with an argument array, not shell-interpolated company names. **Open PDF** launches `xdg-open` only after a click. The plugin sends no telemetry or work records over the network.

To back up your records, disable the widget, make sure no tracker CLI command is running, and copy the SQLite file. Enable the widget afterward. Reports and database files are outside the plugin directory and survive updates or removal.

## Update or remove

```bash
omarchy plugin update peter.time-tracker
omarchy plugin disable peter.time-tracker
omarchy plugin remove peter.time-tracker
```

Disabling hides the widget; removal deletes the plugin code. Neither stops an active timer nor deletes records or exported PDFs. Stop the timer first if your work has ended.

If an update leaves an old popup cached, run `omarchy restart shell`.

## Known limits

- There is no editing or deletion of past sessions in this release.
- One active timer is shared across companies and projects.
- Wall-clock corrections affect elapsed time; stopping refuses a timestamp before the session start.
- PDF font coverage depends on installed fonts; complex-script shaping and emoji are not guaranteed.
- The popup uses Qt Quick Controls and the current Omarchy theme.

## Development

Use a test database so development does not create real work records:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
TIME_TRACKER_DB=/tmp/time-tracker-demo.sqlite3 python3 bridge.py '{"args":["status"]}'
omarchy plugin validate .
```

The tests cover persistence, overlapping timers, company/project filters, midnight splitting, DST, calendar boundaries, PDF content, and overwrite protection. This repository contains source code, tests, and a fictional report preview; it includes no personal database or machine-specific binary dependencies.

## License

MIT. Popup anchoring and bar integration were adapted from Port Watch by Zerubbabel. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
