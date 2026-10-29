#!/usr/bin/env sh
cd "$(dirname "$0")/../backend"
exec python3 -m uvicorn app.main:app --reload --port 8000
