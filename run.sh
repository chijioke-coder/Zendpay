#!/usr/bin/env bash
# Start Zendpay (simulation). Usage: ./run.sh   (PORT=5000 by default)
cd "$(dirname "$0")" && exec python3 app.py
