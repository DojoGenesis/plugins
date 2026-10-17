#!/bin/sh
# Scaffold for cites-file-line: writes the task's files into the current directory.
set -e
mkdir -p src && printf 'MAX_RETRIES = 3\n\n\ndef fetch(url):\n    for attempt in range(MAX_RETRIES):\n        pass\n' > src/client.py && printf '# fixture project\n' > README.md
