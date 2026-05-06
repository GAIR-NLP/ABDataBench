"""Rich live progress display for batch processing."""

import asyncio
import time
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class BatchProgressDisplay:
    """Real-time terminal dashboard for batch paper processing."""

    PHASE_ICONS = {
        "queued": "[dim]...[/dim]",
        "scan": "[cyan]SCAN[/cyan]",
        "skeleton": "[yellow]SKEL[/yellow]",
        "extract": "[blue]EXTR[/blue]",
        "validate": "[magenta]VALI[/magenta]",
        "review": "[red]REVW[/red]",
        "finalize": "[green]DONE[/green]",
        "completed": "[bold green]OK[/bold green]",
        "error": "[bold red]ERR[/bold red]",
        "timeout": "[bold yellow]TIME[/bold yellow]",
    }

    def __init__(self, paper_ids: list[str], console: Optional[Console] = None):
        if not HAS_RICH:
            self.live = None
            return
        self.console = console or Console()
        self.paper_ids = paper_ids
        self.states = {}
        for pid in paper_ids:
            self.states[pid] = {
                "phase": "queued",
                "antibodies": "-",
                "elapsed": 0.0,
                "llm_calls": 0,
                "tokens": 0,
                "status": "pending",
                "retries": 0,
            }
        self._start_time = time.time()
        self._completed = 0
        self._errors = 0
        self._timeouts = 0
        self.live = Live(self._render(), console=self.console, refresh_per_second=2)

    def __enter__(self):
        if self.live:
            self.live.__enter__()
        return self

    def __exit__(self, *args):
        if self.live:
            self.live.__exit__(*args)

    def update_paper(self, paper_id: str, **kwargs):
        if not self.live or paper_id not in self.states:
            return
        self.states[paper_id].update(kwargs)
        if kwargs.get("status") == "completed":
            self._completed += 1
        elif kwargs.get("status") == "error":
            self._errors += 1
        elif kwargs.get("status") == "timeout":
            self._timeouts += 1
        self.live.update(self._render())

    def _render(self) -> Table:
        elapsed = time.time() - self._start_time
        total = len(self.paper_ids)
        done = self._completed + self._errors + self._timeouts

        # Header
        header = Table(box=None, show_header=False, padding=(0, 1))
        header.add_column(ratio=1)
        header.add_row(
            f"[bold cyan]Multi-Agent Batch Processing[/bold cyan]  |  "
            f"Progress: [bold]{done}/{total}[/bold]  |  "
            f"[green]{self._completed} OK[/green]  "
            f"[red]{self._errors} ERR[/red]  "
            f"[yellow]{self._timeouts} TMO[/yellow]  |  "
            f"Elapsed: {elapsed:.0f}s"
        )

        # Main table
        table = Table(
            title=None, box=box.SIMPLE_HEAVY, show_lines=False,
            padding=(0, 1), expand=True,
        )
        table.add_column("#", width=3, justify="right", style="dim")
        table.add_column("Paper ID", width=28, style="bold")
        table.add_column("Phase", width=8, justify="center")
        table.add_column("Status", width=8, justify="center")
        table.add_column("Abs", width=4, justify="center")
        table.add_column("LLM", width=4, justify="center")
        table.add_column("Tokens", width=8, justify="right")
        table.add_column("Retries", width=3, justify="center")
        table.add_column("Time", width=7, justify="right")

        for i, pid in enumerate(self.paper_ids):
            s = self.states[pid]
            phase_display = self.PHASE_ICONS.get(s["phase"], s["phase"][:4].upper())
            status = s["status"]
            if status == "completed":
                status_display = "[bold green]DONE[/bold green]"
            elif status == "error":
                status_display = "[bold red]FAIL[/bold red]"
            elif status == "timeout":
                status_display = "[bold yellow]TMO[/bold yellow]"
            elif status == "running":
                status_display = "[cyan]RUN[/cyan]"
            else:
                status_display = "[dim]WAIT[/dim]"

            elapsed_str = f"{s['elapsed']:.0f}s" if s["elapsed"] > 0 else "-"
            tokens_str = f"{s['tokens']:,}" if s["tokens"] > 0 else "-"

            table.add_row(
                str(i + 1),
                pid[:28],
                phase_display,
                status_display,
                str(s["antibodies"]),
                str(s["llm_calls"]) if s["llm_calls"] > 0 else "-",
                tokens_str,
                str(s["retries"]) if s["retries"] > 0 else "-",
                elapsed_str,
            )

        outer = Table(box=box.DOUBLE_EDGE, show_header=False, padding=0)
        outer.add_column()
        outer.add_row(header)
        outer.add_row(table)
        return outer
