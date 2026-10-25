# Usage examples

## 1. Recover a single-file backup

```bash
lbf-extractor phone_backup.lbf -o ./recovered
```

Expected output:

```
LG Backup Extractor (lbf-extractor) v1.2.1 by Mustafa Koca
Archive: phone_backup.lbf (1,234.56 MiB across 1 part(s))
Platform: Linux 6.x | Python: 3.11.7

[14:22:01] [INF] Security check: archive is unencrypted/unlocked.
[14:22:01] [INF] Evaluating header architecture format: [NEW]
...
┌──────────────────────────────────────────────────────────┐
│                  EXTRACTION AUDIT REPORT                 │
├──────────────────────────────────────┬───────────────────┤
│  Catalog Items Located               │ 1432              │
│  Files Extracted Successfully        │ 1289              │
│  Unmapped Forensic Blocks            │ 0                 │
│  Skipped (Sparse / Null Content)     │ 141               │
│  Failed Catalog Operations           │ 0                 │
│  Failed Unmapped Blocks              │ 0                 │
│  Execution Duration                  │ 12.45s            │
└──────────────────────────────────────┴───────────────────┘
```

---

2. Split archive

LG Mobile Switch may split a large backup into .lbf0, .lbf1, …, .lbf.
Point the tool at the .lbf file — it discovers the slices automatically.

```bash
lbf-extractor phone_backup.lbf -o ./recovered --debug
```

--debug prints the assembly order:

```
[14:22:01] [INF] Multipart slice assembly order:
[14:22:01] [INF]   [0] phone_backup.lbf0 (2,097,152,000 bytes)
[14:22:01] [INF]   [1] phone_backup.lbf1 (2,097,152,000 bytes)
[14:22:01] [INF]   [2] phone_backup.lbf  (1,234,567,890 bytes)
```

If your backup has .lbf at the beginning:

```bash
lbf-extractor phone_backup.lbf --split-lbf-first
```

---

3. Forensics / raw recovery

```bash
lbf-extractor phone_backup.lbf -o ./forensics \
    --debug --log run.log
```

Orphaned byte ranges land in forensics/unmapped/, named by byte offsets:

```
unmapped/block_0x000002A0_0x00001FFF.bin
unmapped/block_0x01234567_0x01234FFF.bin
```

Carve them with binwalk, foremost, or photorec as usual.

---

4. Library use

```python
from lbf_extractor import LBFExtractor

with LBFExtractor(
    "phone_backup.lbf",
    output_dir="./recovered",
    try_path_reconstruct=True,
    overwrite=False,
    extract_unmapped=True,
    debug=False,
    log_file="run.log",
) as ex:
    ex.execute()

print("extracted:", ex.stats.extracted)
print("failed:   ", ex.stats.failed)
for rec in ex.audit_failed:
    print(rec)
```

---

5. Reproducible runs for bug reports

```bash
NO_COLOR=1 lbf-extractor phone_backup.lbf -o /tmp/lbf-out \
    --debug --log /tmp/lbf-run.log
```

NO_COLOR=1 disables ANSI escapes so the log file is plain text — helpful when
pasting into an issue. Redact any personal paths before submitting.

```
