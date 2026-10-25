# Contributing

Thanks for helping improve `lbf-extractor`. Please prefer focused, testable changes that preserve the existing CLI and Python API unless a change is intentional and documented.

## Before you start

- Work only with backups you own or are authorized to inspect.
- Never attach a real `.lbf` backup or extracted personal data to an issue or pull request. Use synthetic data.
- Keep runtime dependencies small. PyCryptodome is the only runtime dependency.
- For new flags or behavior, update both language versions of the README and the usage examples.

## Set up a development environment

```bash
git clone https://github.com/MustafaKoca9/lbf-extractor.git
cd lbf-extractor
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Checks before a pull request

```bash
pytest -q
python -m py_compile lbf_extractor.py
lbf-extractor --version
```

If a change affects CLI behavior, add or update parser tests. If it affects binary parsing, add tests based on synthetic fixtures rather than real personal backups.

## Project conventions

- Support Python 3.9 and newer.
- Add type annotations to new public functions and methods.
- Prefer the standard library; avoid unnecessary runtime dependencies.
- Keep streaming behavior: do not read an entire large backup into memory.
- Validate offsets and lengths before reading or writing archive data.
- Keep extracted paths confined to the requested output directory.
- Keep README, CLI help, usage examples, and the changelog in sync.
- Update `__version__` in `lbf_extractor.py` and `version` in `pyproject.toml` together when preparing a release.

## Commit messages

Use Conventional Commits, for example:

- `fix: validate multipart segment boundaries`
- `docs: clarify recovery output layout`
- `test: cover malformed header lengths`
- `chore: update development dependencies`

## Reporting bugs

Include the application version, operating system, Python version, command used, and a redacted debug trace. Do not upload real backups, recovered files, personal paths, or metadata that can identify a device owner.

For security vulnerabilities, follow [SECURITY.md](SECURITY.md) and use the private reporting channel rather than a public issue.
