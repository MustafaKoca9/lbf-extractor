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
