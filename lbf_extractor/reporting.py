from .common import Terminal
class ReportingMixin:
    @staticmethod
    def _format_row(label: str, raw_value: str, *styles: str) -> str:
        """Format a two-cell report row with guaranteed alignment.

        Left cell : 38 visible chars  (│ + left + │)
        Right cell: 19 visible chars  (│ + right + │)
        """
        if len(label) > 35:
            label = label[:33] + ".."
        left = f"  {label:<35} "

        if len(raw_value) > 15:
            raw_value = raw_value[:13] + ".."
        styled = Terminal.style(raw_value, *styles) if styles else raw_value
        pad = 17 - len(raw_value)
        right = f" {styled}{' ' * pad} "

        border = Terminal.style("│", Terminal.CYAN)
        return f"{border}{left}{border}{right}{border}"

    def print_summary_box(self) -> None:
        """Render an aligned Unicode audit box to stdout."""
        elapsed = (
            (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time
            else 0.0
        )

        print("\n" + Terminal.style("┌" + "─" * 58 + "┐", Terminal.CYAN))

        header_text = "EXTRACTION AUDIT REPORT"
        header_left = (58 - len(header_text)) // 2
        header_right = 58 - len(header_text) - header_left
        header = (
            f"{Terminal.BOLD}{' ' * header_left}{header_text}"
            f"{' ' * header_right}{Terminal.RESET}"
        )
        print(Terminal.style("│", Terminal.CYAN) + header + Terminal.style("│", Terminal.CYAN))
        print(Terminal.style("├" + "─" * 38 + "┬" + "─" * 19 + "┤", Terminal.CYAN))

        rows = [
            ("Catalog Items Located", str(self.stats.total_items), ()),
            ("Files Extracted Successfully", str(self.stats.extracted),
             (Terminal.GREEN, Terminal.BOLD)),
            ("Unmapped Forensic Blocks", str(self.stats.missed_blocks), ()),
            ("Skipped (Sparse / Null Content)", str(self.stats.skipped_null), ()),
            ("Failed Catalog Operations", str(self.stats.failed),
             (Terminal.RED,) if self.stats.failed else (Terminal.DIM,)),
            ("Failed Unmapped Blocks", str(self.stats.missed_failed),
             (Terminal.YELLOW,) if self.stats.missed_failed else (Terminal.DIM,)),
            ("Execution Duration", f"{elapsed:.2f}s", ()),
        ]
        for label, value, styles in rows:
            print(self._format_row(label, value, *styles))

        print(Terminal.style("└" + "─" * 38 + "┴" + "─" * 19 + "┘", Terminal.CYAN))

        if self.audit_failed:
            print(
                f"\n{Terminal.style('Failure Audit Records:', Terminal.RED, Terminal.BOLD)}"
            )
            for item in self.audit_failed:
                tag = "[UNMAPPED]" if item.is_unmapped else "[CATALOG] "
                print(
                    f"  • {tag} {item.path} "
                    f"[offset: {item.offset:,}, len: {item.length:,}]: {item.reason}"
                )

    # ---- pipeline ---------------------------------------------------------
