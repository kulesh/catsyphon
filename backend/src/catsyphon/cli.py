"""
CatSyphon CLI - Main command-line interface for CatSyphon.

Provides commands for ingesting conversation logs, running the API server,
and managing the database.
"""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="catsyphon",
    help="CatSyphon - Coding agent conversation analysis tool",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version() -> None:
    """Show CatSyphon version."""
    console.print("[bold green]CatSyphon v0.1.0[/bold green]")


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to conversation log file or directory"),
    project: str = typer.Option(None, help="Project name"),
    developer: str = typer.Option(None, help="Developer username"),
    batch: bool = typer.Option(False, help="Process directory in batch mode"),
    dry_run: bool = typer.Option(False, help="Parse without storing to database"),
    skip_duplicates: bool = typer.Option(
        True, help="Skip files that have already been processed"
    ),
    enable_tagging: bool = typer.Option(
        False, "--enable-tagging", help="Enable LLM-based tagging (uses OpenAI API)"
    ),
) -> None:
    """
    Ingest conversation logs into the database.

    Parse and tag conversation logs, then store them in the database
    for analysis.
    """
    from pathlib import Path

    from catsyphon.config import settings
    from catsyphon.parsers import get_default_registry

    console.print(f"[bold blue]Ingesting logs from:[/bold blue] {path}")
    console.print(f"  Project: {project or 'N/A'}")
    console.print(f"  Developer: {developer or 'N/A'}")
    console.print(f"  Batch mode: {batch}")
    console.print(f"  Dry run: {dry_run}")
    console.print(f"  Skip duplicates: {skip_duplicates}")
    console.print(f"  LLM tagging: {enable_tagging}")
    console.print()

    # Initialize tagging pipeline if enabled
    tagging_pipeline = None
    if enable_tagging:
        if not settings.openai_api_key:
            console.print(
                "[bold red]Error:[/bold red] OPENAI_API_KEY not set in environment"
            )
            raise typer.Exit(1)

        from catsyphon.tagging import TaggingPipeline

        tagging_pipeline = TaggingPipeline(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            cache_dir=Path(settings.tagging_cache_dir),
            cache_ttl_days=settings.tagging_cache_ttl_days,
            enable_cache=settings.tagging_enable_cache,
        )
        console.print("[green]✓ LLM tagging pipeline initialized[/green]\n")

    # Get parser registry
    registry = get_default_registry()

    # Convert path to Path object
    log_path = Path(path)

    if not log_path.exists():
        console.print(f"[bold red]Error:[/bold red] Path not found: {path}")
        raise typer.Exit(1)

    # Collect files to process
    files_to_process = []
    if log_path.is_file():
        files_to_process = [log_path]
    elif log_path.is_dir():
        files_to_process = list(log_path.rglob("*.jsonl"))
        if not files_to_process:
            console.print("[yellow]No .jsonl files found in directory[/yellow]")
            raise typer.Exit(0)
    else:
        console.print(f"[bold red]Error:[/bold red] Invalid path: {path}")
        raise typer.Exit(1)

    console.print(f"Found {len(files_to_process)} file(s) to process\n")

    # Process files
    successful = 0
    failed = 0

    for log_file in files_to_process:
        try:
            console.print(f"[blue]Parsing:[/blue] {log_file.name}... ", end="")

            # Parse the file
            conversation = registry.parse(log_file)

            console.print(
                f"[green]✓[/green] "
                f"{len(conversation.messages)} messages, "
                f"{sum(len(m.tool_calls) for m in conversation.messages)} tool calls"
            )

            # Run tagging if enabled
            tags = None
            if tagging_pipeline:
                console.print("  [cyan]Tagging...[/cyan] ", end="")
                try:
                    tags = tagging_pipeline.tag_conversation(conversation)
                    console.print(
                        f"[green]✓[/green] intent={tags.get('intent')}, "
                        f"outcome={tags.get('outcome')}, "
                        f"sentiment={tags.get('sentiment')}"
                    )
                except Exception as tag_error:
                    console.print(f"[yellow]⚠ Tagging failed:[/yellow] {tag_error}")
                    tags = None  # Continue without tags

            # Store to database (unless dry-run)
            if not dry_run:
                from catsyphon.db.connection import db_session
                from catsyphon.exceptions import DuplicateFileError
                from catsyphon.pipeline.ingestion import ingest_conversation

                try:
                    with db_session() as session:
                        db_conversation = ingest_conversation(
                            session=session,
                            parsed=conversation,
                            project_name=project,
                            developer_username=developer,
                            file_path=log_file,
                            tags=tags,
                            skip_duplicates=skip_duplicates,
                        )
                        session.commit()
                        console.print(
                            f"  [green]✓ Stored[/green] "
                            f"conversation={db_conversation.id}"
                        )
                except DuplicateFileError as dup_error:
                    console.print(f"  [yellow]⊘ Duplicate:[/yellow] {dup_error}")
                    raise  # Re-raise to count as failed
                except Exception as db_error:
                    console.print(f"  [red]✗ DB Error:[/red] {str(db_error)}")
                    raise  # Re-raise to count as failed

            successful += 1

        except Exception as e:
            console.print(f"[red]✗[/red] {str(e)}")
            failed += 1
            continue

    # Summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {failed}")

    if failed > 0:
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """
    Start the FastAPI server.

    Runs the CatSyphon API server for querying conversation data.
    """
    import uvicorn

    console.print("[bold green]Starting CatSyphon API server...[/bold green]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Reload: {reload}")
    console.print(f"\n  API docs: http://{host}:{port}/docs")

    uvicorn.run(
        "catsyphon.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def db_init() -> None:
    """Initialize the database (run migrations)."""
    console.print("[bold blue]Initializing database...[/bold blue]")

    # TODO: Run Alembic migrations
    console.print("[yellow]⚠ Database initialization not yet implemented[/yellow]")
    console.print("  Hint: Use 'alembic upgrade head' to run migrations")


@app.command()
def db_status() -> None:
    """Show database status and statistics."""
    console.print("[bold blue]Database Status[/bold blue]\n")

    # TODO: Query database for stats
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    table.add_row("Conversations", "0")
    table.add_row("Messages", "0")
    table.add_row("Developers", "0")
    table.add_row("Projects", "0")

    console.print(table)
    console.print("\n[yellow]⚠ Database queries not yet implemented[/yellow]")


if __name__ == "__main__":
    app()
