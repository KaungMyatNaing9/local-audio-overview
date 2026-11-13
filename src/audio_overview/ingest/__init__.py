"""Load a PDF, URL, text file, or local repository into one document."""

from audio_overview.ingest.chunk import chunk_text
from audio_overview.ingest.load import load_source

__all__ = ["chunk_text", "load_source"]
