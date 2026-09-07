# Security

## Report a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/peterkeating1979-Claw/omarchy-time-tracker/security/advisories/new). Include the affected version, a minimal reproduction using fictional records, and the expected impact. Do not post credentials, personal work records, or sensitive proof-of-concept details in public issues.

Security fixes target the latest release. Upgrade older versions before reporting an already-fixed issue.

## Boundaries

This is a single-user, local desktop plugin. Omarchy executes QML with the logged-in user's permissions; Time Tracker is not a sandbox or a multi-user server.

Version 1.0.1 includes these protections:

- Database files and existing SQLite sidecars are opened without following symlinks, checked for ownership, regular-file type and a single hard link, then restricted to `0600` before SQLite access.
- Database storage and PDF export directories must be user-owned and not writable by other users. Ancestors must be owned by the user or root; sticky shared ancestors such as `/tmp` are permitted only above a private child directory. Custom storage in a shared writable directory is rejected.
- New storage directories use `0700`; the default database and report directories are restricted to that mode. PDF temporary files remain `0600`. Completed exports are linked atomically without replacing an existing destination, including dangling symlinks.
- SQLite queries bind values as parameters and use foreign keys. `trusted_schema` is disabled. The plugin never loads database extensions.
- The bridge accepts a bounded JSON object and known commands, rejects malformed arguments before opening storage, and returns JSON errors. SQL punctuation remains ordinary text in names.
- New names and notes have length limits and reject control and bidirectional override characters. QML name controls use plain text; PDF paragraphs escape markup.
- The widget invokes Python through an argument array, ignores Python environment injection and user-site packages (`-E -s`), and disables bytecode writes (`-B`). A 60-second watchdog stops a stuck bridge without automatically retrying an action. After a timeout, check timer status because an operation may already have committed.
- There are no runtime network requests, automatic dependency installations, or privilege requests. `xdg-open` runs only after the user chooses Open PDF. Documented dependency setup commands are executed manually by the user.
- GitHub Actions use pinned action revisions and read-only repository permissions. Dependabot checks development requirements and action updates.

## Limits

Automatic Obsidian logging (1.2.0) requires an explicit opt-in and a saved vault. A completed session and its delivery job are committed before any vault write. Jobs retain a snapshot and original vault path in the private database. Generated filenames contain a random persistent job key; retries accept an existing note only if it is a regular, user-owned, single-link file with exactly matching content, opened without following symlinks. Edited or redirected notes are never overwritten. The automatic action only creates notes; it does not launch Obsidian or run vault plugins.

Obsidian export (1.1.0) is an explicit local write to a user-selected, existing vault. Notes are new owner-only Markdown files published atomically without replacing existing files. The fixed export subfolder cannot be a symlink. Text fields are escaped for Markdown/HTML and properties use JSON-encoded YAML scalars. Existing vault notes and configuration are not read or changed. Opening a note launches an encoded `obsidian://open?path=...` URI only after a click. Any synchronization is controlled by the vault's existing software, not this plugin.

These protections do not defend against root, a compromised logged-in account, malicious same-user software, or a compromised plugin source/Python/Qt/PDF dependency. Such software can read the user's records and change files within the user's directories. Records are not encrypted at rest. Users who need at-rest protection should use appropriate operating-system storage encryption.

Imported or manually edited SQLite databases are not supported as an untrusted interchange format. Existing long names are preserved; the new input limits apply to new additions. Backups and older exported PDFs retain their existing permissions. A dependency advisory scan is a point-in-time check and cannot prove the absence of vulnerabilities.

Marketplace validation and listing approval are not security audits or certifications.
