# Contributing to lbf-extractor

Thanks for helping! This is a small, focused tool — please keep changes surgical.

## Ground rules

- **Only test on backups you own.** Never attach a real `.lbf` (or parts of it)
  to an issue or PR. Attach a **synthetic** sample or the *structure* only.
- Do not add heavy dependencies (`numpy`, `pandas`, etc.). `pycryptodome` is the
  only runtime dependency.
- Keep the CLI surface stable. If you add a flag, document it in `README.md` and
  add it to the argparse help.

## Local setup

```bash
git clone https://github.com/mustafakoca/lbf-extractor.git
cd lbf-extractor
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

Before opening a PR

```bash
pytest -v
ruff check .
ruff format .          # optional, keeps diffs clean
python -m py_compile lbf_extractor.py
```

· Update CHANGELOG.md under ## [Unreleased].
· If you change the CLI, update both README.md (CLI reference table) and
  examples/usage.md.
· If you bump the version, update it in both places:
  · lbf_extractor.py → __version__
  · pyproject.toml → version

Commit messages

Use Conventional Commits:

```
feat: add --follow-symlinks flag
fix: prevent header re-parse when --force-new is set
docs: clarify --split-lbf-first behaviour
chore: bump pycryptodome to 3.20
```

Code style

· Python 3.9+, from __future__ import annotations at the top.
· Type hints on public methods and on every new function.
· Prefer pathlib.Path for new code; the streaming layer still uses raw file
  handles by design.
· No global mutable state beyond the module-level _INSTANCE_COUNTER used for
  per-instance logger naming.

Reporting bugs

Please include:

1. Output of lbf-extractor --version.
2. OS and Python version (platform.platform()).
3. The first 64 bytes of the archive, hex-encoded only if you are sure it
   contains no personal data — for .lbf, that's usually the format marker and
   an offset, safe to share. When in doubt, skip it.
4. Full --debug trace (redact any personal paths).

Security

See SECURITY.md for disclosure guidance. Do not file public
issues for security bugs.

```
