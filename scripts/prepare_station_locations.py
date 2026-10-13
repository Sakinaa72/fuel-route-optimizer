#!/usr/bin/env python
"""Convenience entry point; the management command owns all preprocessing."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
from django.core.management import execute_from_command_line  # noqa: E402

if __name__ == "__main__":
    execute_from_command_line([sys.argv[0], "prepare_locations", *sys.argv[1:]])
