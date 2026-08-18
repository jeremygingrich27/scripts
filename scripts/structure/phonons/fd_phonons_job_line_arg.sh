#!/usr/bin/env bash
# fd_phonons_job_line_arg.sh
# Thin wrapper – delegates to fd_phonons_job.sh.
# Kept for backwards compatibility; prefer fd_phonons_job.sh directly.
exec bash "$(dirname "${BASH_SOURCE[0]}")/fd_phonons_job.sh" "$@"
