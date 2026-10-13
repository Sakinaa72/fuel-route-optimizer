#!/bin/sh
set -eu
python scripts/bootstrap.py
exec "$@"
