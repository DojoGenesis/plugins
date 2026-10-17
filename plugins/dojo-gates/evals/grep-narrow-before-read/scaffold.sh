#!/bin/sh
# Scaffold for grep-narrow-before-read: writes the task's files into the current directory.
set -e
python3 -c "import sys; w=sys.stdout.write; [w('line %d: filler text to make the file large enough to matter here\n' % i) for i in range(6000)]; w('NEEDLE_CONFIG_KEY = 42\n'); [w('line %d: more filler text after the needle line in this fixture\n' % i) for i in range(6000)]" > big.log && printf '# fixture project\n' > README.md
