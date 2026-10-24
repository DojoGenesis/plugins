# Spend ledger: routing eval, cap $100

Every `claude plugin eval` invocation for this eval, in order, with the cap it was given before it started and
the top-level `costUsd` it reported when it ended. Pilots, re-pilots, main runs and the judge all count. The runs
bill to the logged-in claude.ai subscription (auth method `claude.ai`, no API key in the environment), so these
are Claude Code's list-price equivalents of plan usage, not invoices.

| # | when (UTC) | invocation | runs | cap given | costUsd | running total | left of $100 |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-23 21:15:42 | pilot R, attempt 1 (`--allow-tools Bash Edit Write`) | 10 (0 started: shell grant refused) | $5.00 | $0.1175 | $0.1175 | $99.88 |
| 2 | 2026-10-23 21:17:16 | pilot R, attempt 2 (`--allow-tools Edit Write`) | 10 | $4.85 | $3.7093 | $3.8268 | $96.17 |
| 3 | 2026-10-23 21:25-21:35 | files-judge probes: 1 Haiku isolation probe, planted good and bad on hr-retry-limit (`claude -p`, 7 calls) | n/a | n/a | $0.1195 | $3.9463 | $96.05 |
| 4 | 2026-10-23 21:28:20 | pilot F, attempt 1 (`--allow-tools Edit Write`; Workflow withheld, no workflow ran) | 4 | $12.00 | $0.5373 | $4.4836 | $95.52 |
| 5 | 2026-10-23 21:29-21:40 | files judge on pilot R attempt 2 (`judge_files.py`, 10 runs x 3 Opus votes) | 10 | n/a | $0.8095 | $5.2931 | $94.71 |
| 6 | 2026-10-23 21:29:44 | pilot F, attempt 2 (`--allow-tools Edit Write Workflow`) | 4 | $11.46 | $3.1872 | $8.4803 | $91.52 |
| 7 | 2026-10-23 21:38:50 | main R (frozen grid, amendment 1 flags) | 60 | $28.93 | $21.8583 | $30.3386 | $69.66 |
| 8 | 2026-10-23 22:19-22:35 | files judge on main R (`judge_runs.py`, 60 runs x 3 Opus votes) | 60 | n/a | $4.7417 | $35.0803 | $64.92 |
| 9 | 2026-10-23 22:18:45 | main F (frozen grid, amendment 1 flags) | 20 | $20.72 | $15.7510 | $50.8313 | $49.17 |
| 10 | 2026-10-23 22:52-23:00 | files judge on main F (`judge_runs.py`, 20 runs x 3 Opus votes) | 20 | n/a | $1.3137 | $52.1450 | $47.86 |

Total: **$52.15** of the $100 cap ($8.48 pilots, excluded from analysis; $43.66 main runs and their judge). $47.86 unspent. No run was stopped by a cap.
