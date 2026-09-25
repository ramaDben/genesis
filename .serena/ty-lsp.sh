#!/bin/bash
cd "$(dirname "$0")/.." && exec uv run ty server
