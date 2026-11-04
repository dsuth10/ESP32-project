"""Raspberry Pi Touchscreen client and teacher podium deck interface.

Australian English spelling conventions and standard library HTTP foundations.
Provides touch-first candidate series staging, lesson page navigation,
and classroom display switching.
"""
from __future__ import annotations

from .deck_client import DeckClientError, TeacherDeckClient, load_deck_config

__all__ = [
    "DeckClientError",
    "TeacherDeckClient",
    "load_deck_config",
]
