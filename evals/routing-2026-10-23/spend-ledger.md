# Spend ledger: routing eval, cap $100

Every `claude plugin eval` invocation for this eval, in order, with the cap it was given before it started and
the top-level `costUsd` it reported when it ended. Pilots, re-pilots, main runs and the judge all count. The runs
bill to the logged-in claude.ai subscription (auth method `claude.ai`, no API key in the environment), so these
are Claude Code's list-price equivalents of plan usage, not invoices.

| # | when (UTC) | invocation | runs | cap given | costUsd | running total | left of $100 |
|---|---|---|---|---|---|---|---|
