# Security policy

## Scope

`lbf-extractor` parses untrusted binary `.lbf` input and writes recovered content to disk. Security reports are especially useful for:

- Directory traversal or writes outside the selected output directory.
- Malformed offsets, lengths, headers, or XML causing unsafe behavior.
- Unexpected file overwrites or other file-system side effects.
- Crashes that expose a security boundary or make crafted archives unsafe to inspect.

The extractor validates output paths, checks read boundaries, limits header size, and records failures. These controls reduce risk but do not guarantee that every malformed archive is safe.

## Report a vulnerability privately

**Do not publish security-sensitive details in a public issue.**

Use the repository's private vulnerability reporting feature, if available: open the repository's **Security** tab and choose **Report a vulnerability**. If that option is unavailable, contact the maintainer through the contact details on the GitHub profile.

Include a minimal synthetic reproducer, the exact command used, expected and observed behavior, and a redacted debug trace. Do not attach real backups or personal data.

## Limitations

- The LG format's fixed AES key is a property of the format, not by itself a vulnerability in this program.
- Path checks cannot guarantee safety against every pre-existing symlink or hostile output-directory setup.
- Large archives can consume substantial disk space. Streaming limits memory usage, not the amount of data that may be written.
- Results can be incomplete or corrupted; keep the original backup unchanged.
