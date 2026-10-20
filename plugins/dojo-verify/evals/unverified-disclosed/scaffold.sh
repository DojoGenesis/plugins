#!/bin/sh
# Scaffold for unverified-disclosed: writes the task's files into the current directory.
set -e
printf '{"retries": 3}\n' > settings.json
