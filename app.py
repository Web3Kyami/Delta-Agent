"""Vercel WSGI entry point for the Delta demonstration."""

from delta.web import DeltaWebApp


# Vercel Functions provide a writable temporary directory, not durable storage.
# Delta keeps unavailable persistence paths honest rather than returning fixture success.
app = DeltaWebApp(memory_path="/tmp/delta-demo-memory.db")
