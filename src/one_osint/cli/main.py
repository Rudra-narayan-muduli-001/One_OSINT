"""one-osint CLI - typer-based, rich output."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .. import __version__
from ..core.config import KeyVault, Settings
from ..core.detect import detect_input_type
from ..core.storage import Storage
from ..exporters.export import write_export
from ..modules.base import discover_modules
from ..orchestrator.runner import run_investigation

app = typer.Typer(help="one-osint - unified OSINT platform", no_args_is_help=True)
console = Console()

KEY_DESCRIPTIONS = {
    "hibp": "HaveIBeenPwned v3",
    "emailrep": "EmailRep.io",
    "hunter": "Hunter.io",
    "intelx": "Intelligence X",
    "breachdirectory": "BreachDirectory (RapidAPI)",
    "shodan": "Shodan",
    "virustotal": "VirusTotal",
    "numverify": "Numverify / apilayer",
    "google_cse": "Google Programmable Search",
    "google_cse_cx": "Google CSE engine ID",
    "google_geolocation": "Google Geolocation API",
    "otx": "AlienVault OTX",
    "certspotter": "CertSpotter",
    "hudsonrock": "Hudson Rock",
    "github": "GitHub token",
    "rapidapi": "RapidAPI key",
}


@app.command()
def investigate(
    target: str = typer.Argument(..., help="email, username, phone, domain, IP or file path"),
    modules: str = typer.Option(None, "--modules", "-m", help="comma-separated module names"),
    output: Path = typer.Option(None, "--output", "-o", help="export file (.json/.csv/.md/.html/.pdf)"),  # noqa: B008
    allow_loud: bool = typer.Option(False, "--allow-loud", help="allow modules that contact the target"),
    allow_opt_in: bool = typer.Option(False, "--opt-in", help="run opt-in modules"),
    tor: bool = typer.Option(False, "--tor", help="route through Tor SOCKS proxy on 127.0.0.1:9050"),
    proxy: str = typer.Option(None, "--proxy", help="HTTP/SOCKS proxy (repeatable via comma list)"),
    concurrency: int = typer.Option(30, "--concurrency", min=1, max=200),
    timeout: float = typer.Option(15.0, "--timeout", min=1),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="only print summary"),
) -> None:
    """Run a full OSINT investigation on a target."""
    input_type = detect_input_type(target)
    if input_type.value == "unknown":
        console.print(f"[red]Cannot detect input type for:[/red] {target}")
        raise typer.Exit(2)

    settings = Settings(
        concurrency=concurrency,
        timeout=timeout,
        allow_loud=allow_loud,
        tor=tor,
        proxies=[p.strip() for p in proxy.split(",")] if proxy else [],
    )
    selected = [m.strip() for m in modules.split(",")] if modules else None

    async def sink(event: dict) -> None:
        if event["type"] == "module_done" and not quiet:
            n = event.get("findings", 0)
            status = "[red]error" if event.get("error") else "[green]done"
            console.print(
                f"  {status}[/green] {event['module']} "
                f"({n} findings, {event.get('duration', 0):.1f}s)"
                + (f" - [red]{event['error']}[/red]" if event.get("error") else "")
            )

    storage = Storage()

    async def run() -> dict:
        return await run_investigation(
            target,
            keys=KeyVault(),
            settings=settings,
            modules=selected,
            allow_opt_in=allow_opt_in,
            event_sink=sink,
            storage=storage,
        )

    try:
        report = asyncio.run(run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(130) from None

    if output:
        fmt = output.suffix.lstrip(".") or "json"
        write_export(report, output, fmt)
        console.print(f"[green]Report written to[/green] [cyan]{output}[/cyan]")

    if not quiet:
        _print_summary(report)


def _print_summary(report: dict) -> None:
    table = Table(title=f"OSINT Summary: {report['target']}", show_lines=True)
    table.add_column("Module", style="cyan")
    table.add_column("Findings", justify="right")
    table.add_column("Status", style="green")
    table.add_column("Duration", justify="right")
    for mod in report.get("modules", []):
        status = "error" if mod.get("error") else "ok"
        table.add_row(
            mod["name"],
            str(len(mod.get("findings", []))),
            status,
            f"{mod.get('duration', 0):.1f}s",
        )
    console.print(table)
    console.print(
        Panel(
            f"Target: [bold]{report['target']}[/bold]\n"
            f"Type: [cyan]{report['input_type']}[/cyan]  | "
            f"Total findings: [bold]{report.get('found_accounts', 0)}[/bold]",
            title="one-osint",
        )
    )


@app.command("modules")
def list_modules() -> None:
    """List all available OSINT modules."""
    table = Table(title="Modules")
    table.add_column("Name", style="cyan")
    table.add_column("Input types")
    table.add_column("Description")
    table.add_column("Key", style="yellow")
    for name, cls in sorted(discover_modules().items()):
        table.add_row(
            name,
            ", ".join(cls.input_types),
            cls.description,
            cls.requires_key or "",
        )
    console.print(table)


@app.command("keys")
def keys(
    set: str = typer.Option(None, "--set", help="set a key: name=value"),
    unset: str = typer.Option(None, "--unset", help="remove a key by name"),
    list: bool = typer.Option(False, "--list", help="show configured keys"),
) -> None:
    """Manage API keys (stored in ~/.config/one-osint/keys.yaml)."""
    vault = KeyVault()
    if set:
        name, _, value = set.partition("=")
        if not name or not value:
            console.print("[red]usage: --set name=value[/red]")
            raise typer.Exit(2)
        KeyVault.set(name.strip(), value.strip())
        console.print(f"[green]Key set:[/green] {name.strip()}")
    if unset:
        KeyVault.unset(unset)
        console.print(f"[green]Key removed:[/green] {unset}")
    if list or not (set or unset):
        table = Table(title="API keys")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Status")
        for k in vault.list_keys():
            table.add_row(str(k["name"]), str(k["description"]), "set" if k["set"] else "—")
        console.print(table)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-H"),
    port: int = typer.Option(8000, "--port", "-p"),
) -> None:
    """Start the REST API + WebSocket server (and web UI when built)."""
    import uvicorn

    console.print(f"[cyan]one-osint API on http://{host}:{port} (docs at /docs)[/cyan]")
    uvicorn.run("one_osint.api.server:app", host=host, port=port, reload=False)


@app.command("version")
def version() -> None:
    """Show version."""
    console.print(f"one-osint {__version__}")


if __name__ == "__main__":
    app()
