"""Human-readable terminal summary and extraction audit output."""
from __future__ import annotations

from .common import Terminal


class ReportingMixin:
    @staticmethod
    def _format_row(label: str, raw_value: str, *styles: str) -> str:
        """Format a two-cell report row with fixed visible widths."""
        if len(label) > 35:
            label = label[:33] + ".."
        left = f"  {label:<35} "

        if len(raw_value) > 15:
            raw_value = raw_value[:13] + ".."
        styled = Terminal.style(raw_value, *styles) if styles else raw_value
        right = f" {styled}{' ' * max(0, 17 - len(raw_value))} "

        border = Terminal.style("│", Terminal.CYAN)
        return f"{border}{left}{border}{right}{border}"

    def print_summary_box(self) -> None:
        elapsed = (
            (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time
            else 0.0
        )

        print("\n" + Terminal.style("┌" + "─" * 58 + "┐", Terminal.CYAN))
        heading = "EXTRACTION AUDIT REPORT"
        left_padding = (58 - len(heading)) // 2
        right_padding = 58 - len(heading) - left_padding
        centered_heading = (
            f"{' ' * left_padding}{heading}{' ' * right_padding}"
        )
        print(
            Terminal.style("│", Terminal.CYAN)
            + Terminal.style(centered_heading, Terminal.BOLD)
            + Terminal.style("│", Terminal.CYAN)
        )
        print(Terminal.style("├" + "─" * 38 + "┬" + "─" * 19 + "┤", Terminal.CYAN))

        rows = [
            ("Catalog Items Located", str(self.stats.total_items), ()),
            ("Files Extracted Successfully", str(self.stats.extracted), (Terminal.GREEN, Terminal.BOLD)),
            ("Unmapped Forensic Blocks", str(self.stats.missed_blocks), ()),
            ("Skipped (Sparse / Null Content)", str(self.stats.skipped_null), ()),
            (
                "Failed Catalog Operations",
                str(self.stats.failed),
                (Terminal.RED,) if self.stats.failed else (Terminal.DIM,),
            ),
            (
                "Failed Unmapped Blocks",
                str(self.stats.missed_failed),
                (Terminal.YELLOW,) if self.stats.missed_failed else (Terminal.DIM,),
            ),
            ("Execution Duration", f"{elapsed:.2f}s", ()),
        ]
        for label, value, styles in rows:
            print(self._format_row(label, value, *styles))

        print(Terminal.style("└" + "─" * 38 + "┴" + "─" * 19 + "┘", Terminal.CYAN))

        if self.audit_failed:
            print(Terminal.style("\nFailure Audit Records:", Terminal.RED, Terminal.BOLD))
            for record in self.audit_failed:
                tag = "[UNMAPPED]" if record.is_unmapped else "[CATALOG] "
                print(
                    f"  • {tag} {record.path} "
                    f"[offset: {record.offset:,}, len: {record.length:,}]: {record.reason}"
                )
