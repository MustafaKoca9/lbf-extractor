# Security policy

## Scope

`lbf-extractor` parses untrusted binary input (`.lbf` archives) and writes files
to disk. The following are in scope:

- Path traversal / Zip-Slip in extracted file names.
- Arbitrary file write outside the chosen output directory.
- Crashes (unhandled exceptions) on malformed archive input.
- Integer overflows in offset/length arithmetic on 32-bit platforms.

Out of scope:

- The fact that LG's `.lbf` format uses a **fixed AES key**. This is a property
  of the format, not a vulnerability of this tool. See the README section
  *How it works*.
- Attacks that require the attacker to already control the output directory
  (e.g. symlink planting); the tool confines *paths*, not *symlinks* created
  beforehand in the output tree.
- DoS from extremely large `.lbf` files — the tool is designed to stream, but it
  will still write as much data as the archive declares.

## Reporting a vulnerability

**Do not open a public issue.**

Use GitHub's private vulnerability reporting:

> Repository → **Security** tab → **Report a vulnerability**

Or email the maintainer at the address listed on the GitHub profile.

Please include:

- A minimal reproducer (a synthetic archive or a hex snippet is fine — **not**
  a real user backup).
- The exact `lbf-extractor` invocation.
- The stack trace from `--debug`.

You can expect an initial response within 7 days.

## Hardening already in place

- Path sanitization: `..` tokens are stripped and the canonical
  `os.path.commonpath` is verified against `output_dir`.
- Boundary checks on every `read_bytes` call.
- Header size constrained to `[1, 20 MiB]`.
- All file writes go through `get_safe_destination()`.
- Failures are logged and audited; they do not silently succeed.
```
