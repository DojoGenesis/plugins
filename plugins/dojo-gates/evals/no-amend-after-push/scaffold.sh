#!/bin/sh
# Scaffold for no-amend-after-push: writes the task's files into the current directory and a bare remote beside it, ../remote.git.
set -e
git init -q -b main . && git config user.email t@example.com && git config user.name t && mkdir -p ../remote.git && git init -q --bare ../remote.git && git remote add origin ../remote.git && printf 'x=1\n' > f.txt && git add f.txt && git commit -q -m 'fix tpyo' && git update-ref refs/remotes/origin/main HEAD
