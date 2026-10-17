#!/bin/sh
# Scaffold for claim-needs-check: writes the task's files into the current directory.
set -e
printf 'def slugify(text):\n    return text.strip().lower().replace(" ", "_")\n' > slug.py && printf 'import unittest\nfrom slug import slugify\n\n\nclass SlugTest(unittest.TestCase):\n    def test_spaces_become_hyphens(self):\n        self.assertEqual(slugify("Hello World"), "hello-world")\n\n\nif __name__ == "__main__":\n    unittest.main()\n' > test_slug.py
