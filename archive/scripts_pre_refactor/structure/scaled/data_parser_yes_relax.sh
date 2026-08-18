#!/usr/bin/env bash
# data_parser_yes_relax.sh
# Thin wrapper – delegates to data_parser.sh with -r -x flags.
# Kept for backwards compatibility; use data_parser.sh directly.
exec bash "$(dirname "${BASH_SOURCE[0]}")/data_parser.sh" --relax --xml "$@"
