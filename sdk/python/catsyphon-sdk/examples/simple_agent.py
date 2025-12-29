#!/usr/bin/env python3
"""
Example: Simple AI Agent with CatSyphon SDK

This example shows how to integrate the CatSyphon SDK into an AI agent
to log conversation events to a CatSyphon server.

Usage:
    # First, register your collector (one-time setup):
    python -c "
from catsyphon_sdk import CollectorClient
client = CollectorClient.register(
    server_url='http://localhost:8000',
    workspace_id='YOUR_WORKSPACE_ID',
)
print(f'Registered! Collector ID: {client.config.collector_id}')
"

    # Then run this example:
    python examples/simple_agent.py
"""

import os
import uuid
from datetime import datetime

from catsyphon_sdk import CollectorClient


def simulate_agent_conversation():
    """Simulate an AI agent conversation with CatSyphon logging."""

    # Configuration - in production, get these from environment or config
    SERVER_URL = os.environ.get("CATSYPHON_URL", "http://localhost:8000")
    WORKSPACE_ID = os.environ.get("CATSYPHON_WORKSPACE_ID", "")
    COLLECTOR_ID = os.environ.get("CATSYPHON_COLLECTOR_ID", "")
    API_KEY = os.environ.get("CATSYPHON_API_KEY", "")

    # Try to load from stored credentials first
    client = CollectorClient.from_stored(SERVER_URL, WORKSPACE_ID)

    if client is None:
        if not COLLECTOR_ID or not API_KEY:
            print("No stored credentials found and env vars not set.")
            print("Please register first or set CATSYPHON_* environment variables.")
            return

        client = CollectorClient(
            server_url=SERVER_URL,
            collector_id=COLLECTOR_ID,
            api_key=API_KEY,
        )

    # Generate a unique session ID (in practice, this might come from your agent)
    session_id = f"example-{uuid.uuid4().hex[:8]}"

    print(f"Starting session: {session_id}")

    # Use the session context manager for automatic lifecycle management
    with client.session(session_id) as session:
        # Start the session with agent metadata
        session.start(
            agent_type="example-agent",
            agent_version="1.0.0",
            working_directory="/home/user/project",
            git_branch="main",
        )

        # Simulate a conversation
        print("User: What files are in this directory?")
        session.message(role="user", content="What files are in this directory?")

        print("Assistant: Let me check...")
        session.message(
            role="assistant",
            content="I'll list the files in the current directory.",
            model="example-model-v1",
        )

        # Simulate a tool call
        print("  [Tool: ListFiles]")
        tool_id = session.tool_call(
            name="ListFiles",
            parameters={"path": "."},
        )

        # Simulate tool result
        files = ["README.md", "setup.py", "src/", "tests/"]
        session.tool_result(
            tool_use_id=tool_id,
            success=True,
            result="\n".join(files),
        )

        print(f"  [Result: {', '.join(files)}]")

        # Continue conversation
        session.message(
            role="assistant",
            content=f"I found {len(files)} items: {', '.join(files)}",
        )

        print("User: Thanks!")
        session.message(role="user", content="Thanks!")

        session.message(
            role="assistant",
            content="You're welcome! Let me know if you need anything else.",
        )

        # Complete the session
        session.complete(
            outcome="success",
            summary="Listed directory contents successfully",
            files_touched=[],
        )

    print(f"Session completed! ID: {session_id}")
    print(f"View it at: {SERVER_URL}/conversations")


def simulate_async_agent():
    """Example of async agent conversation."""
    import asyncio

    from catsyphon_sdk import AsyncCollectorClient

    async def run():
        # In production, load from environment or stored credentials
        SERVER_URL = os.environ.get("CATSYPHON_URL", "http://localhost:8000")
        WORKSPACE_ID = os.environ.get("CATSYPHON_WORKSPACE_ID", "")

        client = AsyncCollectorClient.from_stored(SERVER_URL, WORKSPACE_ID)
        if client is None:
            print("No stored credentials. Register first.")
            return

        session_id = f"async-{uuid.uuid4().hex[:8]}"

        async with client.session(session_id) as session:
            await session.start(agent_type="async-example")
            await session.message(role="user", content="Hello async!")
            await session.message(role="assistant", content="Hi from async agent!")
            await session.complete(outcome="success")

        print(f"Async session completed: {session_id}")

    asyncio.run(run())


if __name__ == "__main__":
    print("=== CatSyphon SDK Example ===\n")

    # Run sync example
    print("--- Synchronous Example ---")
    simulate_agent_conversation()

    # Uncomment to run async example:
    # print("\n--- Asynchronous Example ---")
    # simulate_async_agent()
