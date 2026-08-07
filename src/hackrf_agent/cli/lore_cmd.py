"""``hackrf-agent lore`` — search the on-disk RF/SIGINT corpus.

The human-facing companion to the MCP knowledge_* verbs. Same
read-only backend (``hackrf_agent.domain.knowledge``); no MCP host
required. Useful for grepping the corpus, previewing a topic, or
looking up a band without leaving the terminal.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from hackrf_agent.domain.knowledge import (
    KnowledgeError,
    default_paths,
    list_topics,
    lookup_band,
    lookup_decoder,
    lookup_keyfob,
    lookup_modulation,
    lookup_protocol,
    read_file,
    search,
)

lore_app = typer.Typer(no_args_is_help=True, help="Search the RF/SIGINT knowledge corpus.")
_console = Console()


@lore_app.command("list")
def lore_list() -> None:
    """List every topic dir and its markdown files."""
    try:
        paths = default_paths()
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e

    topics = list_topics(paths)
    if not topics:
        _console.print("[dim]No topics found.[/]")
        return
    table = Table(title=f"knowledge/ — {len(topics)} topics")
    table.add_column("topic", style="bold")
    table.add_column("files", style="dim")
    for entry in topics:
        table.add_row(entry["topic"], ", ".join(entry["files"]))
    _console.print(table)


@lore_app.command("read")
def lore_read(
    topic: str = typer.Argument(..., help="Topic dir (e.g. 'dsp', 'ism-433')."),
    name: str = typer.Argument(
        "README.md", help="Filename inside the topic dir. Default: README.md."
    ),
) -> None:
    """Print one markdown file's contents to stdout."""
    try:
        paths = default_paths()
        result = read_file(paths, topic, name)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    _console.print(result["content"])


@lore_app.command("search")
def lore_search(
    query: str = typer.Argument(..., help="Substring to search for."),
    max_results: int = typer.Option(
        20, "--max-results", "-n", help="Maximum number of hits."
    ),
) -> None:
    """Case-insensitive substring search across every corpus markdown."""
    try:
        paths = default_paths()
        hits = search(paths, query, max_results=max_results)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    if not hits:
        _console.print(f"[dim]No matches for {query!r}.[/]")
        return
    table = Table(title=f"{len(hits)} hits for {query!r}")
    table.add_column("topic")
    table.add_column("file")
    table.add_column("line", justify="right")
    table.add_column("text")
    for h in hits:
        table.add_row(h["topic"], h["name"], str(h["line"]), h["text"])
    _console.print(table)


@lore_app.command("lookup-band")
def lore_lookup_band(
    freq_hz: int = typer.Argument(..., help="Frequency of interest in Hz."),
) -> None:
    """Return records covering ``freq_hz`` from ``bands.json``."""
    try:
        paths = default_paths()
        records = lookup_band(paths, freq_hz)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    _dump_records(records, f"bands covering {freq_hz} Hz")


@lore_app.command("lookup-modulation")
def lore_lookup_modulation(
    name: str = typer.Argument(
        ..., help="Modulation family name or alias (e.g. 'OOK', 'GFSK')."
    ),
) -> None:
    """Return the ``modulations.json`` record for a named family."""
    try:
        paths = default_paths()
        record = lookup_modulation(paths, name)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    if record is None:
        _console.print(f"[dim]No modulation record matches {name!r}.[/]")
        raise typer.Exit(code=1)
    _console.print_json(json.dumps(record, indent=2))


@lore_app.command("lookup-protocol")
def lore_lookup_protocol(
    name: str = typer.Argument(..., help="Protocol name (e.g. 'POCSAG', 'AX.25')."),
) -> None:
    """Return the ``protocols.json`` record for a named protocol."""
    try:
        paths = default_paths()
        record = lookup_protocol(paths, name)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    if record is None:
        _console.print(f"[dim]No protocol record matches {name!r}.[/]")
        raise typer.Exit(code=1)
    _console.print_json(json.dumps(record, indent=2))


@lore_app.command("lookup-decoder")
def lore_lookup_decoder(
    name: str = typer.Argument(
        ..., help="Decoder family (e.g. 'Manchester', 'PWM', 'NRZ')."
    ),
) -> None:
    """Return the ``decoders.json`` record for a named decoder family."""
    try:
        paths = default_paths()
        record = lookup_decoder(paths, name)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    if record is None:
        _console.print(f"[dim]No decoder record matches {name!r}.[/]")
        raise typer.Exit(code=1)
    _console.print_json(json.dumps(record, indent=2))


@lore_app.command("lookup-keyfob")
def lore_lookup_keyfob(
    vendor: str | None = typer.Option(None, "--vendor", help="Vendor substring."),
    model: str | None = typer.Option(None, "--model", help="Model substring."),
) -> None:
    """Return keyfob-system records matching vendor and/or model."""
    if not vendor and not model:
        _console.print("[red]must supply --vendor and/or --model[/]")
        raise typer.Exit(code=2)
    try:
        paths = default_paths()
        records = lookup_keyfob(paths, vendor, model)
    except KnowledgeError as e:
        _console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2) from e
    _dump_records(records, f"keyfobs matching vendor={vendor!r} model={model!r}")


def _dump_records(records: list[dict], header: str) -> None:
    if not records:
        _console.print(f"[dim]No records for {header}.[/]")
        raise typer.Exit(code=1)
    _console.print(f"[bold]{header}[/] — {len(records)} record(s)")
    for r in records:
        _console.print_json(json.dumps(r, indent=2))
