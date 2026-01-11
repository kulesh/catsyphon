"""
CatSyphon CLI - Main command-line interface for CatSyphon.

Minimal CLI providing essential commands for automation and server management.
For interactive features, use the web UI.
"""

import typer
from rich.console import Console

from catsyphon.logging_config import setup_logging

app = typer.Typer(
    name="catsyphon",
    help="CatSyphon - Coding agent conversation analysis tool",
    no_args_is_help=True,
)

console = Console()


@app.command()
def ingest(
    path: str = typer.Argument(..., help="Path to conversation log file or directory"),
    project: str = typer.Option(None, help="Project name"),
    developer: str = typer.Option(None, help="Developer username"),
    batch: bool = typer.Option(False, help="Process directory in batch mode"),
    dry_run: bool = typer.Option(False, help="Parse without storing to database"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force re-ingest (skip file deduplication and replace existing conversations)",
    ),
    skip_duplicates: bool = typer.Option(
        True,
        help="[DEPRECATED] Use --force instead. Skip files that have already been processed",
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

    # Initialize logging (fallback to console if file logging not permitted)
    try:
        setup_logging(context="cli")
    except PermissionError:
        # Basic logging to stdout
        import logging

        logging.basicConfig(level=logging.INFO)

    # Handle --force flag and deprecation warning
    if force:
        skip_duplicates = False
        update_mode = "replace"
    else:
        update_mode = "skip"

    # Show deprecation warning if --no-skip-duplicates used
    if not skip_duplicates and not force:
        console.print(
            "[yellow]⚠ Warning: --no-skip-duplicates is deprecated. "
            "Use --force instead.[/yellow]\n"
        )
        # Make deprecated flag work by setting update_mode
        update_mode = "replace"

    console.print(f"[bold blue]Ingesting logs from:[/bold blue] {path}")
    console.print(f"  Project: {project or 'N/A'}")
    console.print(f"  Developer: {developer or 'N/A'}")
    console.print(f"  Batch mode: {batch}")
    console.print(f"  Dry run: {dry_run}")
    console.print(f"  Force: {force}")
    console.print(f"  Update mode: {update_mode}")
    console.print(f"  Skip duplicates: {skip_duplicates}")
    console.print(f"  LLM tagging: {enable_tagging}")
    console.print()

    # Validate tagging configuration if enabled
    if enable_tagging:
        if not settings.openai_api_key:
            console.print(
                "[bold red]Error:[/bold red] OPENAI_API_KEY not set in environment"
            )
            raise typer.Exit(1)
        console.print("[green]✓ LLM tagging will be queued after ingestion[/green]\n")

    # Get parser registry
    registry = get_default_registry()

    # Convert path to Path object
    log_path = Path(path)

    if not log_path.exists():
        console.print(f"[bold red]Error:[/bold red] Path not found: {path}")
        raise typer.Exit(1)

    # Collect files to process

    all_files = []
    if log_path.is_file():
        all_files = [log_path]
    elif log_path.is_dir():
        all_files = list(log_path.rglob("*.jsonl"))
        if not all_files:
            console.print("[yellow]No .jsonl files found in directory[/yellow]")
            raise typer.Exit(0)
    else:
        console.print(f"[bold red]Error:[/bold red] Invalid path: {path}")
        raise typer.Exit(1)

    # Process all files (including metadata-only files)
    files_to_process = all_files

    if not files_to_process:
        console.print("[yellow]No log files found to process[/yellow]")
        raise typer.Exit(0)

    console.print(f"Found {len(files_to_process)} conversational log(s) to process\n")

    # Process files
    successful = 0
    failed = 0
    skipped = 0

    for log_file in files_to_process:
        try:
            console.print(f"[blue]Ingesting:[/blue] {log_file.name}... ", end="")

            # Store to database (unless dry-run)
            if not dry_run:
                from catsyphon.db.connection import db_session
                from catsyphon.pipeline.ingestion import _get_or_create_default_workspace
                from catsyphon.services import IngestionService

                try:
                    with db_session() as session:
                        # Get default workspace
                        workspace_id = _get_or_create_default_workspace(session)

                        # Use unified ingestion service
                        service = IngestionService(session)
                        outcome = service.ingest_from_file(
                            file_path=log_file,
                            workspace_id=workspace_id,
                            project_name=project,
                            developer_username=developer,
                            source_type="cli",
                            enable_tagging=enable_tagging,
                        )
                        session.commit()

                        status_label = outcome.status
                        if status_label == "error":
                            color = "red"
                            console.print(f"  [red]✗ Error:[/red] {outcome.error_message}")
                            failed += 1
                            continue
                        elif status_label in {"duplicate", "skipped"}:
                            color = "yellow"
                        else:
                            color = "green"

                        verb = "Stored" if status_label == "success" else status_label
                        conv_id = outcome.conversation_id
                        tagging_note = " (tagging queued)" if enable_tagging and status_label == "success" else ""
                        if conv_id:
                            console.print(
                                f"  [{color}]✓ {verb}[/{color}] "
                                f"conversation={conv_id}{tagging_note}"
                            )
                        else:
                            console.print(f"  [{color}]✓ {verb}[/{color}]{tagging_note}")

                    if outcome.status in {"duplicate", "skipped"}:
                        skipped += 1
                    else:
                        successful += 1
                except Exception as db_error:
                    console.print(f"  [red]✗ DB Error:[/red] {str(db_error)}")
                    failed += 1
            else:
                # Dry-run parse to validate content and surface skips
                try:
                    registry.parse_with_metadata(log_file)
                    console.print("  [green]✓ Parsed[/green] (dry-run)")
                    successful += 1
                except Exception as parse_error:
                    console.print(f"  [yellow]Skipped:[/yellow] {parse_error}")
                    skipped += 1

        except Exception as e:
            console.print(f"[red]✗[/red] {str(e)}")
            failed += 1
            continue

    # Post-ingestion linking for batch mode (Phase 2: Epic 7u2)
    # Link orphaned agents to parents after all files are processed
    # This handles cases where agents were ingested before their parent conversations
    if not dry_run and log_path.is_dir() and successful > 0:
        console.print()
        console.print("[cyan]Linking orphaned agents to parents...[/cyan]")
        try:
            from catsyphon.db.connection import db_session
            from catsyphon.pipeline.ingestion import (
                _get_or_create_default_workspace,
                link_orphaned_agents,
            )

            with db_session() as session:
                workspace_id = _get_or_create_default_workspace(session)
                linked_count = link_orphaned_agents(session, workspace_id)
                session.commit()
                if linked_count > 0:
                    console.print(
                        f"[green]✓ Linked {linked_count} orphaned agents[/green]"
                    )
                else:
                    console.print("[green]✓ No orphaned agents to link[/green]")
        except Exception as link_error:
            console.print(f"[yellow]⚠ Linking failed:[/yellow] {link_error}")
            # Don't fail the command if linking fails

    # Summary
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Successful: {successful}")
    console.print(f"  Skipped: {skipped}")
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


if __name__ == "__main__":
    app()
