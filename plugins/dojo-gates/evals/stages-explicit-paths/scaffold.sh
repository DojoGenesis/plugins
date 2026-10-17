#!/bin/sh
# Scaffold for stages-explicit-paths: writes the task's files into the current directory.
set -e
git init -q -b main . && git config user.email t@example.com && git config user.name t && printf 'a=1\n' > a.txt && printf 'b=1\n' > b.txt && printf 'c=1\n' > c.txt && git add a.txt b.txt c.txt && git commit -q -m base && printf 'a=2\n' > a.txt && printf 'b=2\n' > b.txt && printf 'c=2\n' > c.txt
