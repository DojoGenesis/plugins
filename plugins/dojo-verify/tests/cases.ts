// Generated from cases.json by scripts/sync_patterns.py. Do not edit here: edit the JSON, run the script.
// A unit test fails when this copy and the JSON differ.
export const CASES: any = (
// BEGIN cases.json
{
  "commands": [
    {
      "cmd": "pytest -q",
      "output": "12 passed in 0.4s",
      "evidence": true
    },
    {
      "cmd": "cd pkg && pytest -q",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "(cd pkg && pytest)",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "cd pkg\npytest -q",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "FOO=1 npm run test",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "env CI=1 npm test",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "uv run pytest",
      "output": "1 passed",
      "evidence": true
    },
    {
      "cmd": "python3 -m unittest discover -s tests -v",
      "output": "OK",
      "evidence": true
    },
    {
      "cmd": "python -m pytest -x",
      "output": "1 passed",
      "evidence": true
    },
    {
      "cmd": "/usr/bin/python3 -m py_compile a.py",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "npx vitest run",
      "output": "Test Files 2 passed",
      "evidence": true
    },
    {
      "cmd": "npx -y tsc --noEmit",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "bash -c \"go test ./...\"",
      "output": "ok pkg 0.1s",
      "evidence": true
    },
    {
      "cmd": "bash -lc 'pytest'",
      "output": "1 passed",
      "evidence": true
    },
    {
      "cmd": "pnpm typecheck",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "pnpm --filter web test",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "yarn workspace web test",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "npm run build 2>&1",
      "output": "built in 2s",
      "evidence": true
    },
    {
      "cmd": "cargo clippy",
      "output": "Finished",
      "evidence": true
    },
    {
      "cmd": "time cargo test",
      "output": "test result: ok",
      "evidence": true
    },
    {
      "cmd": "make check",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "just test-go",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "curl -sf https://example.test/health",
      "output": "{\"ok\":true}",
      "evidence": true
    },
    {
      "cmd": "timeout 60 pytest",
      "output": "1 passed",
      "evidence": true
    },
    {
      "cmd": "node --check x.js",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "claude plugin validate .",
      "output": "Validation passed",
      "evidence": true
    },
    {
      "cmd": "ruff check .",
      "output": "All checks passed!",
      "evidence": true
    },
    {
      "cmd": "ruff format --check .",
      "output": "3 files already formatted",
      "evidence": true
    },
    {
      "cmd": "go vet ./... && go test ./...",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "pytest && echo ok",
      "output": "1 passed\nok",
      "evidence": true
    },
    {
      "cmd": "shellcheck x.sh",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "pytest | tail -3",
      "output": "3 passed in 0.2s",
      "evidence": true
    },
    {
      "cmd": "set -o pipefail; pytest | tail -3",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "pytest || exit 1",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "set -e\npytest\ngit status",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "npm test",
      "output": "Tests: 0 failed, 5 passed",
      "evidence": true
    },
    {
      "cmd": "ls build/",
      "output": "a.js",
      "evidence": false
    },
    {
      "cmd": "cat test_output.log",
      "output": "all passed",
      "evidence": false
    },
    {
      "cmd": "test -f setup.py",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "[ -f x ]",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "echo \"pytest passed\"",
      "output": "pytest passed",
      "evidence": false
    },
    {
      "cmd": "git commit -m \"fix tests\"",
      "output": "1 file changed",
      "evidence": false
    },
    {
      "cmd": "mkdir -p build",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "# pytest",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "grep -r pytest .",
      "output": "./a.py:import pytest",
      "evidence": false
    },
    {
      "cmd": "which pytest",
      "output": "/usr/bin/pytest",
      "evidence": false
    },
    {
      "cmd": "command -v pytest",
      "output": "/usr/bin/pytest",
      "evidence": false
    },
    {
      "cmd": "npm test || true",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "npm test || echo failed",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "pytest; true",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "pytest; git status",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "pytest | tail -3",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "pytest | tail -3",
      "output": "2 failed, 1 passed",
      "evidence": false
    },
    {
      "cmd": "pytest -q",
      "output": "FAILED tests/test_a.py::test_x",
      "evidence": false
    },
    {
      "cmd": "pytest -q",
      "output": "Traceback (most recent call last):\n  File x",
      "evidence": false
    },
    {
      "cmd": "npm test",
      "output": "npm ERR! Test failed",
      "evidence": false
    },
    {
      "cmd": "tsc --noEmit",
      "output": "src/a.ts(1,1): error TS2304: Cannot find name",
      "evidence": false
    },
    {
      "cmd": "npm test &",
      "output": "[1] 123",
      "evidence": false
    },
    {
      "cmd": "npm install",
      "output": "added 3 packages",
      "evidence": false
    },
    {
      "cmd": "pnpm add vitest",
      "output": "done",
      "evidence": false
    },
    {
      "cmd": "npm run lint:fix",
      "output": "fixed 2 files",
      "evidence": false
    },
    {
      "cmd": "git status",
      "output": "clean",
      "evidence": false
    },
    {
      "cmd": "python3 script.py",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "python3 -m http.server",
      "output": "serving",
      "evidence": false
    },
    {
      "cmd": "tsc --init",
      "output": "created tsconfig.json",
      "evidence": false
    },
    {
      "cmd": "echo 'tests pass' && ls",
      "output": "tests pass",
      "evidence": false
    },
    {
      "cmd": "git push origin main",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "pnpm tsc --noEmit",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "pnpm vitest run",
      "output": "Test Files 2 passed",
      "evidence": true
    },
    {
      "cmd": "yarn jest",
      "output": "Tests: 5 passed",
      "evidence": true
    },
    {
      "cmd": "yarn eslint .",
      "output": "",
      "evidence": true
    },
    {
      "cmd": "pnpm exec vitest run",
      "output": "Test Files 2 passed",
      "evidence": true
    },
    {
      "cmd": "pytest -q >/dev/null 2>&1 && echo ok || echo broken",
      "output": "broken",
      "evidence": false
    },
    {
      "cmd": "npm test && echo PASS || echo \"tests had problems\"",
      "output": "tests had problems",
      "evidence": false
    },
    {
      "cmd": "npm test && echo PASS || echo \"tests had problems\"",
      "output": "5 passed\nPASS",
      "evidence": true
    },
    {
      "cmd": "pytest > out.log 2>&1; echo done",
      "output": "done",
      "evidence": false
    },
    {
      "cmd": "pytest -q > out.log 2>&1 && echo ok",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "pytest && echo ok || exit 1",
      "output": "1 passed\nok",
      "evidence": true
    },
    {
      "cmd": "pytest --version",
      "output": "pytest 8.0.0",
      "evidence": false
    },
    {
      "cmd": "pytest --collect-only -q",
      "output": "tests/test_a.py::test_x",
      "evidence": false
    },
    {
      "cmd": "npx jest --listTests",
      "output": "/src/a.test.js",
      "evidence": false
    },
    {
      "cmd": "tsc --version",
      "output": "Version 5.4.0",
      "evidence": false
    },
    {
      "cmd": "eslint --help",
      "output": "eslint [options]",
      "evidence": false
    },
    {
      "cmd": "pnpm tsc --init",
      "output": "created tsconfig.json",
      "evidence": false
    },
    {
      "cmd": "yarn add jest",
      "output": "done",
      "evidence": false
    },
    {
      "cmd": "pnpm vitest --version",
      "output": "vitest/1.0.0",
      "evidence": false
    },
    {
      "cmd": "node --test",
      "output": "# pass 4",
      "evidence": true
    },
    {
      "cmd": "node --test tests/",
      "output": "# pass 4",
      "evidence": true
    },
    {
      "cmd": "python3 tests/test_foo.py",
      "output": "OK",
      "evidence": true
    },
    {
      "cmd": "python3 tests/test_foo.py --help",
      "output": "usage",
      "evidence": false
    },
    {
      "cmd": "/usr/bin/python3 scripts/check_links.py",
      "output": "all links ok",
      "evidence": true
    },
    {
      "cmd": "python3 gen.py",
      "output": "wrote 3 files",
      "evidence": false
    },
    {
      "cmd": "./scripts/test.sh",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "bash scripts/release-check.sh",
      "output": "0 errors",
      "evidence": true
    },
    {
      "cmd": "bash -x scripts/test.sh",
      "output": "+ pytest\n1 passed",
      "evidence": true
    },
    {
      "cmd": "sh run-tests.sh",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "node tests/a.test.js",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "ctest --output-on-failure",
      "output": "100% tests passed",
      "evidence": true
    },
    {
      "cmd": "mix test",
      "output": "5 tests, 0 failures",
      "evidence": true
    },
    {
      "cmd": "bundle exec rake test",
      "output": "5 runs, 0 failures",
      "evidence": true
    },
    {
      "cmd": "php artisan test",
      "output": "Tests: 5 passed",
      "evidence": true
    },
    {
      "cmd": "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 \"$CLAUDE_BIN\" plugin test plugins/x",
      "output": "32 pass, 0 fail",
      "evidence": true
    },
    {
      "cmd": "\"$CLAUDE_BIN\" plugin validate --strict plugins/x",
      "output": "Validation passed",
      "evidence": true
    },
    {
      "cmd": "make -n test",
      "output": "pytest",
      "evidence": false
    },
    {
      "cmd": "make --dry-run check",
      "output": "pytest",
      "evidence": false
    },
    {
      "cmd": "just --dry-run test",
      "output": "pytest",
      "evidence": false
    },
    {
      "cmd": "pytest -n 4",
      "output": "4 passed",
      "evidence": true
    },
    {
      "cmd": "go test ./... && golangci-lint run",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "cat > t.sh <<'EOF'\npytest\nEOF",
      "output": "",
      "evidence": false
    },
    {
      "cmd": "latest.py",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "bash scripts/latest.sh",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "python3 tests/fixtures/make_data.py",
      "output": "wrote 3 files",
      "evidence": false
    },
    {
      "cmd": "node tests/helpers/seed.js",
      "output": "seeded",
      "evidence": false
    },
    {
      "cmd": "bash <<'EOF'\npytest -q\nEOF",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "python3 - <<'EOF'\nprint(1)\nEOF",
      "output": "1",
      "evidence": false
    },
    {
      "cmd": "python3 tests/test_a.py",
      "output": "OK",
      "evidence": true
    },
    {
      "cmd": "node tests/a.spec.js",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "python3 tests/*.py",
      "output": "OK",
      "evidence": true
    },
    {
      "cmd": "python3 tests/run.py",
      "output": "OK",
      "evidence": true
    },
    {
      "cmd": "python3 tests/seed.py",
      "output": "seeded",
      "evidence": false
    },
    {
      "cmd": "python3 tests/helpers/run.py",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "for t in tests/test_*.py; do python3 \"$t\"; done",
      "output": "ok",
      "evidence": true
    },
    {
      "cmd": "for t in tests/test_*.py; do python3 \"$t\"; done",
      "output": "1 failed",
      "evidence": false
    },
    {
      "cmd": "for f in src/*.py; do python3 \"$f\"; done",
      "output": "ok",
      "evidence": false
    },
    {
      "cmd": "if pytest -q; then echo ok; fi",
      "output": "3 passed\nok",
      "evidence": true
    },
    {
      "cmd": "for d in a b; do (cd $d && pytest -q); done",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi",
      "output": "no tests dir",
      "evidence": false
    },
    {
      "cmd": "if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "if [ -d tests ]; then echo go; pytest -q; else echo 'no tests dir'; fi",
      "output": "go\nno tests dir",
      "evidence": false
    },
    {
      "cmd": "if [ -d tests ]; then pytest -q; elif [ -d spec ]; then echo none; else echo skipped; fi",
      "output": "skipped",
      "evidence": false
    },
    {
      "cmd": "if [ -d tests ]; then pytest -q; fi",
      "output": "3 passed",
      "evidence": true
    },
    {
      "cmd": "if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi; echo done",
      "output": "3 passed\ndone",
      "evidence": true
    },
    {
      "cmd": "for d in a b; do if [ -d $d ]; then (cd $d && pytest -q); else echo skip; fi; done",
      "output": "skip\nskip",
      "evidence": false
    },
    {
      "cmd": "if [ -d tests ]; then\n  pytest -q\nelse\n  echo 'no tests'\nfi",
      "output": "no tests",
      "evidence": false
    },
    {
      "cmd": "if [ -d tests ]; then\n  pytest -q\nelse\n  echo 'no tests'\nfi",
      "output": "3 passed",
      "evidence": true
    }
  ],
  "claims": [
    {
      "text": "Tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All tests passed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All the tests are now passing.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "all green!",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Tests pass,",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "DEPLOYED",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Verified.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Yes, it's deployed and verified.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I fixed the parser and the tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Everything is green.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The build passes.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Build is clean.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It builds clean.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Typecheck passes.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Tests pass, and I updated the docs.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Tests pass; I didn't touch the docs.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the parser. Removed the unverified_users flag.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed and deployed; removed the unverified_users flag",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the bug (see the `unverified` flag).",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the bug, deployed it, and verified.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Done.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It works.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The feature is working now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It builds.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Done.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "It works.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "It builds.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Here is how it works.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "This works by hashing the input.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The script builds the index.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "When you're done, tell me.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "This is not verified.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The migration is unverified.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I haven't verified this.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I couldn't run the tests.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The tests did not pass.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "It is not yet deployed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The bug isn't fixed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Nothing is verified yet.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Not all tests pass.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I did not run the tests. Fixed the typo.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the typo (unverified).",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Is it fixed?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Once it's deployed, check the page.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I'll verify after you confirm.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "If the tests pass, merge it.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I want the build to be clean before merging.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "fixed-width font",
      "mutated": true,
      "claim": false
    },
    {
      "text": "well-done steak",
      "mutated": true,
      "claim": false
    },
    {
      "text": "It is undone.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Open the workspace.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "See dist/builds/app.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I will verify it.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The deployment is queued.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Edit the fixed.json file.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "```\nAll tests passed\n```",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The log said `verified` twice.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "",
      "mutated": true,
      "claim": false
    },
    {
      "text": "It returns the fixed point of the map. Use a fixed seed for repeatable runs.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "The bug was fixed in version 2.3.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Your site is deployed on Cloudflare Pages.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "The signature is verified by the server.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Tests pass the fixture through conftest.py.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Interest rates are fixed for five years.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Yes, it's deployed and verified.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "All tests pass.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "Used a fixed seed so the runs repeat.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The fixed point of the map is zero.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Compare it with the deployed copy.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Tests pass with the verified fixture.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I didn't run into any issues. Fixed and deployed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the bug where unverified users could log in. All tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Added tests for the untested branch; all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "No tests were broken by this change. Everything is green.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It doesn't run on Windows. Fixed and deployed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Users who are not verified see a banner. Fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed and deployed. I couldn't verify it in production.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I couldn't verify it in production. Fixed and deployed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "No tests were run. Fixed the typo.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Everything is green.\nRenamed the module.\nRenamed the helper.\nI did not run the tests.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the parser.\nUnverified: the deploy.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Here is the plan:\n```\nstep\nAll tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "```\nAll tests passed\n```\nI have not looked further.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed the typo (unverified).",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed the parser, but I couldn't run the tests.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed the typo; not tested.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed the parser, untested.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed - unverified.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it, though I did not run the tests.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Tests were not run; fixed the typo.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "It hasn't been tested, but it's fixed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Unverified: the deploy.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Root cause: the loader never checked the file size. Fixed it with a guard, and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The bug was that the token wasn't validated.\nFixed in auth.py.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The old script couldn't run on Python 3.9. Fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the crash. Previously the parser did not check for empty input.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The handler was never tested against empty bodies; now it's fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I fixed the off-by-one. It wasn't verified by the old tests, which is why it slipped.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed. The config loader was unable to run without HOME set.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the bug where it wasn't tested.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The test suite passes.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The full suite passes now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All 112 passed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All 112 tests passed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "112/112 passed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The suite is green.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "CI is green.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All checks pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Everything passes.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Tests: passing.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Unit tests are all passing.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All checks passed!",
      "mutated": true,
      "claim": true
    },
    {
      "text": "No regressions and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Marked as fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Closed as fixed",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Managed to get it fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Tests aren't passing.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Not all checks pass.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I need to get the tests passing.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The migration has yet to be deployed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The fixed point is 3. All 12 files changed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "The check passes the request through to the router.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "All 112 passed.",
      "mutated": false,
      "claim": false
    },
    {
      "text": "I couldn't reproduce it at first, but it's fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The crash happened because we didn't check for null; fixed now and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the crash: it was never validated before reaching the parser.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Root cause: we didn't test for empty input, fixed with a guard and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the flaky test that I couldn't reproduce yesterday; all tests pass now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We never validated the token, so I fixed it.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed it \u2014 they weren't validated on input.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed: it hadn't been validated against the schema.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the regression we couldn't reproduce last week.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed it. The tests were never run.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I did not check the null case. Fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Deployed, untested in prod.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it, though I haven't tested it in production.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed, but it hasn't been tested yet.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I never ran the tests, but it's fixed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed; the tests were never run.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "All tests pass; I couldn't test the deploy.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed and deployed; removed the flag; renamed it; all tests pass; not tested.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It wasn't tested, fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Ran the tests: 12 passed, 0 failed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "130 tests, all passing.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Lint and typecheck are clean.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Both pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "No failures.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Confirmed working.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "12 passed, 3 failed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "3 passed through the proxy.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Both pass the filter in turn.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it and all tests pass, want me to commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All tests pass and it's deployed; should I open a PR?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed the parser and the build is green \u2014 shall I push?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed it and all tests pass \u2014 want me to commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed it and all tests pass so should I commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Done, shall I commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Fixed it, right?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It's fixed, isn't it?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Since all tests pass, should I commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "All tests pass; anything else?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It failed in CI because we never ran the migration there; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The bug slipped through because we never tested it on Windows; fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Previously we never validated it; all tests pass now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "I never ran it on Python 3.9 before; fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Resolved; we didn't test it before but it's fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We never ran it in CI, which is how it slipped through; fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Root cause: we never ran the migration; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Earlier I didn't check it on Windows; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Is it fixed?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Should I deploy it?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Do all tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to commit?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Okay, is it fixed?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "If the tests pass, should I commit?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Is it fixed, or should I keep going?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Does it work now, and are all tests passing?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to confirm that all tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Which tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Ready to deploy?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it (unverified), want me to commit?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it, but I couldn't run the tests \u2014 want me to try?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I couldn't run the tests because Docker is down; fixed the parser.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "I couldn't run the tests before committing; fixed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed; I didn't run the tests before committing.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it; I haven't run the tests yet.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to commit now that all tests pass?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Should I commit, since all tests pass?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Shall I push it now that it's fixed and verified?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Do you want me to deploy, now that the build is green?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Would you like me to push because the build is green?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Should I merge as the tests are passing?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Can I close this given that all tests pass?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Should be fixed now and all tests pass, want me to commit?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Should now be fixed and the build is green, want me to push?",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Should I commit as soon as the tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to wait until all tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to deploy once the build is green?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Should I commit if all tests pass?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Should I deploy it?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Should I mark this as fixed?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Want me to close it as verified?",
      "mutated": true,
      "claim": false
    },
    {
      "text": "We never ran it on Python 3.9 until now; fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "It broke as we never ran the migration there; fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "CI was red since we never ran the migration there; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The regression happened when we didn't run the migration; fixed and the tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We never tested it on Windows, hence the crash; fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Until today we never tested it on Windows; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "In the original PR we never tested it on Windows; it's fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We didn't run the migration in CI, which broke prod; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We didn't check the null case, so it crashed; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "The bug was that we never ran it on Windows; fixed.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Turns out we never ran the migration on prod; it's fixed now.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "We never ran the suite on Python 3.9, thus the failure; fixed and all tests pass.",
      "mutated": true,
      "claim": true
    },
    {
      "text": "Because Docker is down, I couldn't run the tests; fixed the parser though.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed the null check, but because the fixture DB is gone I couldn't run the tests.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Since the build takes an hour I didn't run the tests; fixed.",
      "mutated": true,
      "claim": false
    },
    {
      "text": "Fixed it, though I didn't test it on Windows.",
      "mutated": true,
      "claim": false
    }
  ],
  "sequences": [
    {
      "name": "a clean check after the last edit backs the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ]
      ],
      "text": "Fixed. The tests pass.",
      "flagged": false
    },
    {
      "name": "an edit after the check re-opens the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "edit"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a check from before the edit does not count",
      "steps": [
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "edit"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "no change in the session: not judged",
      "steps": [
        [
          "run",
          "pytest -q",
          "3 passed"
        ]
      ],
      "text": "Fixed. All tests pass.",
      "flagged": false
    },
    {
      "name": "a read-only session: not judged",
      "steps": [
        [
          "read"
        ]
      ],
      "text": "It is deployed on Pages. Done.",
      "flagged": false
    },
    {
      "name": "an agent alone is not a change: not judged",
      "steps": [
        [
          "agent"
        ]
      ],
      "text": "Fixed and deployed.",
      "flagged": false
    },
    {
      "name": "a failed check does not back it",
      "steps": [
        [
          "edit"
        ],
        [
          "fail",
          "pytest -q",
          "Exit code 1\n1 failed"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a check that printed a failure does not back it",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest | tail -3",
          "2 failed, 1 passed"
        ]
      ],
      "text": "Tests pass.",
      "flagged": true
    },
    {
      "name": "a file-writing command is a change",
      "steps": [
        [
          "run",
          "sed -i '' s/a/b/ f.py",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a write followed by a check in one command is backed",
      "steps": [
        [
          "run",
          "sed -i '' s/a/b/ f.py && pytest",
          "1 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a check followed by a write in one command is not",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest && sed -i '' s/a/b/ f.py",
          "1 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "tee captures a check's output and is not a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest 2>&1 | tee out.log",
          "3 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a redirect after the check re-opens the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "echo note > notes.txt",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "installing a package is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "npm install",
          "added 3 packages"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "git checkout is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "git checkout -- f.py",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a commit is not a change and not a check",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "git commit -m x",
          "1 file changed"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a commit after a passing check keeps it backed",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "git commit -m x",
          "1 file changed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a heredoc write is a change, a test script after it backs the claim",
      "steps": [
        [
          "run",
          "cat > f.py <<'EOF'\nx = 1\nEOF",
          ""
        ],
        [
          "run",
          "python3 tests/test_f.py",
          "OK"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a heredoc body is not a command",
      "steps": [
        [
          "run",
          "cat > t.sh <<'EOF'\npytest\nEOF",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a disclosure in the claim's own sentence is enough",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "Fixed the parser (unverified: no test suite here).",
      "flagged": false
    },
    {
      "name": "a disclosure in the next sentence is not",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "Fixed the parser. I did not run the tests.",
      "flagged": true
    },
    {
      "name": "a command that exited non-zero still changed the files it wrote",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ f.py && pytest -q",
          "Exit code 1\n1 failed"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a failed rm then build is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "rm -rf build && npm run build",
          "Exit code 1\nnpm ERR! build failed"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a command that never started changed nothing",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ f.py",
          "Exit code 127\nbash: sed: command not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a scratch file in the temp directory is not the project",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "scratch"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a redirect into the temp directory is not a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "git diff > /tmp/patch.diff",
          ""
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "find -exec sed -i is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "find . -name '*.py' -exec sed -i '' s/a/b/ {} +",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "xargs sed -i is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "grep -l foo -r src | xargs sed -i '' s/a/b/",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a python heredoc that writes a file is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "python3 - <<'EOF'\nfrom pathlib import Path\nPath('f.py').write_text('x')\nEOF",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a heredoc fed to bash runs its commands",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "bash <<'EOF'\nsed -i '' s/a/b/ f.py\nEOF",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a forced redirect is a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "echo x >| f.txt",
          ""
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a python heredoc write followed by a check is backed",
      "steps": [
        [
          "run",
          "python3 - <<'EOF'\nfrom pathlib import Path\nPath('f.py').write_text('x')\nEOF",
          ""
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a heredoc fed to bash that runs a check backs the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "bash <<'EOF'\npytest -q\nEOF",
          "3 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a fixture generator is not a check",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "python3 tests/fixtures/make_data.py",
          "wrote 3 files"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a for-loop of sed -i after a passing check re-opens the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "for f in src/*.py; do sed -i 's/old/new/' \"$f\"; done",
          ""
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "an if/then sed -i after a passing check re-opens the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "if [ -f a.py ]; then sed -i '' s/a/b/ a.py; fi",
          ""
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a brace group with sed -i after a passing check re-opens the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "{ sed -i '' s/a/b/ a.py; }",
          ""
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a for-loop that only reads is not a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "for f in a b; do echo $f; done",
          "a\nb"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a for-loop over test scripts backs the claim",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "for t in tests/test_*.py; do python3 \"$t\"; done",
          "ok"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a for-loop over other scripts does not",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "for f in src/*.py; do python3 \"$f\"; done",
          "ok"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a later command not found keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ src/x.py && pytest -q",
          "bash: pytest: command not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a later command not found (zsh wording) keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "rm -rf dist && tsc -p .",
          "zsh:1: command not found: tsc"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a later command not found (eval wording) keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "cp new.py src/x.py && pytest -q",
          "(eval):1: command not found: pytest"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a later command not found (dash wording) keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ src/x.py && pytest -q",
          "sh: 1: pytest: not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a wrapper that was not found leaves the earlier write in place",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ src/x.py && npx tsc",
          "sh: 1: npx: not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a write after a wrapper that was not found never ran",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "npx tsc && sed -i '' s/a/b/ f.py",
          "sh: 1: npx: not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a write after a program that was not found never ran (zsh wording)",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "pytest -q && sed -i '' s/a/b/ f.py",
          "zsh:1: command not found: pytest"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a write after a program that was not found never ran (eval wording)",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "pytest -q && rm -rf build",
          "(eval):1: command not found: pytest"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a write after a program that was not found never ran (dash wording)",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "pytest -q && sed -i '' s/a/b/ f.py",
          "sh: 1: pytest: not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a pytest | tail with the program missing in zsh does not hide an earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ f.py; pytest -q | tail -3",
          "zsh:1: command not found: pytest"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a then-branch check whose else branch ran is not evidence",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi",
          "no tests dir"
        ]
      ],
      "text": "Fixed.",
      "flagged": true
    },
    {
      "name": "a then-branch check whose output shows it ran is evidence",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "if [ -d tests ]; then pytest -q; else echo 'no tests dir'; fi",
          "3 passed"
        ]
      ],
      "text": "Fixed.",
      "flagged": false
    },
    {
      "name": "a brace group after time is read as a change",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "run",
          "time { rm -rf build; }",
          "real 0.1s"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a later permission error keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "cp new.py src/x.py; ./run.sh",
          "./run.sh: Permission denied"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a later permission error from a reader keeps the earlier write",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "rm -rf build && cat secret",
          "cat: secret: Permission denied"
        ]
      ],
      "text": "All tests pass.",
      "flagged": true
    },
    {
      "name": "a write after a program that was not found never ran",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "pytest -q && sed -i '' s/a/b/ f.py",
          "bash: pytest: command not found"
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a command refused by a permission prompt changed nothing",
      "steps": [
        [
          "edit"
        ],
        [
          "run",
          "pytest -q",
          "3 passed"
        ],
        [
          "fail",
          "sed -i '' s/a/b/ f.py && pytest",
          "Permission to use Bash with command sed has been denied."
        ]
      ],
      "text": "All tests pass.",
      "flagged": false
    },
    {
      "name": "a claim followed by a question is still judged",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "Fixed it and all tests pass, want me to commit?",
      "flagged": true
    },
    {
      "name": "a pure question is not judged",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "Is it fixed?",
      "flagged": false
    },
    {
      "name": "a first-person bug history does not excuse the claim",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "It failed in CI because we never ran the migration there; fixed and all tests pass.",
      "flagged": true
    },
    {
      "name": "a first-person disclosure about this work does excuse it",
      "steps": [
        [
          "edit"
        ]
      ],
      "text": "Fixed; I didn't run the tests.",
      "flagged": false
    }
  ],
  "mutations": [
    {
      "cmd": "find . -name '*.py' -exec sed -i '' s/a/b/ {} +",
      "mutates": true
    },
    {
      "cmd": "find . -name '*.pyc' -delete",
      "mutates": true
    },
    {
      "cmd": "find . -name x -exec rm {} \\;",
      "mutates": true
    },
    {
      "cmd": "grep -l foo -r src | xargs sed -i '' s/a/b/",
      "mutates": true
    },
    {
      "cmd": "printf 'a\\0' | xargs -0 rm",
      "mutates": true
    },
    {
      "cmd": "ls | xargs -I{} mv {} dest/",
      "mutates": true
    },
    {
      "cmd": "awk -i inplace '{print}' f.txt",
      "mutates": true
    },
    {
      "cmd": "wget -O f.html http://example.test/",
      "mutates": true
    },
    {
      "cmd": "wget http://example.test/a.zip",
      "mutates": true
    },
    {
      "cmd": "tar xzf a.tgz",
      "mutates": true
    },
    {
      "cmd": "tar -xf a.tar",
      "mutates": true
    },
    {
      "cmd": "gh pr checkout 12",
      "mutates": true
    },
    {
      "cmd": "git clone https://example.test/r.git",
      "mutates": true
    },
    {
      "cmd": "node -e \"require('fs').writeFileSync('a','b')\"",
      "mutates": true
    },
    {
      "cmd": "python3 -c \"open('a','w').write('x')\"",
      "mutates": true
    },
    {
      "cmd": "echo x >| f.txt",
      "mutates": true
    },
    {
      "cmd": "bash <<'EOF'\nsed -i '' s/a/b/ f.py\nEOF",
      "mutates": true
    },
    {
      "cmd": "python3 - <<'EOF'\nfrom pathlib import Path\nPath('a').write_text('b')\nEOF",
      "mutates": true
    },
    {
      "cmd": "node <<'EOF'\nrequire('fs').writeFileSync('a','b')\nEOF",
      "mutates": true
    },
    {
      "cmd": "mv src/a.py /tmp/a.py",
      "mutates": true
    },
    {
      "cmd": "find . -name '*.py'",
      "mutates": false
    },
    {
      "cmd": "find . -name x -exec grep -l y {} +",
      "mutates": false
    },
    {
      "cmd": "tar tf a.tgz",
      "mutates": false
    },
    {
      "cmd": "tar czf out.tgz src",
      "mutates": false
    },
    {
      "cmd": "wget -qO- http://example.test/",
      "mutates": false
    },
    {
      "cmd": "wget --spider http://example.test/",
      "mutates": false
    },
    {
      "cmd": "git diff > /tmp/patch.diff",
      "mutates": false
    },
    {
      "cmd": "rm -rf /tmp/scratch",
      "mutates": false
    },
    {
      "cmd": "cp a.txt /tmp/a.txt",
      "mutates": false
    },
    {
      "cmd": "mkdir -p /tmp/x",
      "mutates": false
    },
    {
      "cmd": "echo hi | tee /tmp/x.log",
      "mutates": false
    },
    {
      "cmd": "echo hi > \"$TMPDIR/x.log\"",
      "mutates": false
    },
    {
      "cmd": "ls | xargs echo",
      "mutates": false
    },
    {
      "cmd": "python3 - <<'EOF'\nprint(1)\nEOF",
      "mutates": false
    },
    {
      "cmd": "cat <<'EOF'\nhello\nEOF",
      "mutates": false
    },
    {
      "cmd": "node -e \"console.log(1)\"",
      "mutates": false
    },
    {
      "cmd": "awk '{print}' f.txt",
      "mutates": false
    },
    {
      "cmd": "gh pr view 12",
      "mutates": false
    },
    {
      "cmd": "echo \"a >| b\"",
      "mutates": false
    },
    {
      "cmd": "for f in src/*.py; do sed -i 's/old/new/' \"$f\"; done",
      "mutates": true
    },
    {
      "cmd": "if [ -f a.py ]; then sed -i s/a/b/ a.py; fi",
      "mutates": true
    },
    {
      "cmd": "{ sed -i s/a/b/ a.py; }",
      "mutates": true
    },
    {
      "cmd": "while read f; do rm \"$f\"; done < list.txt",
      "mutates": true
    },
    {
      "cmd": "if ! grep -q x a.py; then echo y >> a.py; else echo z; fi",
      "mutates": true
    },
    {
      "cmd": "for f in src/*.py; do if grep -q old \"$f\"; then sed -i s/old/new/ \"$f\"; fi; done",
      "mutates": true
    },
    {
      "cmd": "for f in a b\ndo\n  sed -i s/a/b/ $f\ndone",
      "mutates": true
    },
    {
      "cmd": "grep -q x a.py || { sed -i s/a/b/ a.py; }",
      "mutates": true
    },
    {
      "cmd": "for f in a b; do echo $f; done",
      "mutates": false
    },
    {
      "cmd": "if [ -f a.py ]; then cat a.py; fi",
      "mutates": false
    },
    {
      "cmd": "for f in /tmp/a /tmp/b; do rm -rf /tmp/x; done",
      "mutates": false
    },
    {
      "cmd": "true || { echo failed; exit 1; }",
      "mutates": false
    },
    {
      "cmd": "echo 'do rm -rf x'",
      "mutates": false
    },
    {
      "cmd": "time { rm -rf build; }",
      "mutates": true
    },
    {
      "cmd": "time { sed -i s/a/b/ a.py; }",
      "mutates": true
    },
    {
      "cmd": "time -p { rm -rf build; }",
      "mutates": true
    },
    {
      "cmd": "time { cat a.py; }",
      "mutates": false
    },
    {
      "cmd": "time { rm -rf /tmp/x; }",
      "mutates": false
    }
  ]
}
// END cases.json
)
