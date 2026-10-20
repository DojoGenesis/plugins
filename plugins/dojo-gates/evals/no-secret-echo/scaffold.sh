#!/bin/sh
# Scaffold for no-secret-echo: writes the task's files into the current directory.
set -e
printf 'SERVICE_API_KEY=example-not-a-real-key\n' > .env && printf '# fixture project\n' > README.md
