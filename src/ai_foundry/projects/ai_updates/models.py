"""Typed research records."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Paper:
    """Metadata retrieved from the arXiv API."""

    identifier: str
    title: str
    abstract: str
    published: datetime
    url: str


@dataclass(frozen=True)
class PaperSummary:
    """A paper paired with its abstract-based summary."""

    paper: Paper
    summary: str
