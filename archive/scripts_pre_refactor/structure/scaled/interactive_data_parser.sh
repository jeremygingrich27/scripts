#!/usr/bin/env bash
# interactive_data_parser.sh
# Thin wrapper – delegates to data_parser.sh (interactive mode, no flags).
# Kept for backwards compatibility; use data_parser.sh directly.
exec bash "$(dirname "${BASH_SOURCE[0]}")/data_parser.sh" "$@"
