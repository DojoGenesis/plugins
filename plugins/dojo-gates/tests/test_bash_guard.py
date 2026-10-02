import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _payloads as P  # noqa: E402

sys.path.insert(0, P.HOOKS)
import _guards  # noqa: E402
import _shell  # noqa: E402


NEUTRAL = tempfile.mkdtemp(prefix="dgn")  # a directory that is not inside any git repository


def tearDownModule():
    P.rmtree(NEUTRAL)


class GuardCase(unittest.TestCase):
    def run_cmd(self, cmd, cwd=None, env=None, session="s-test"):
        cwd = cwd or NEUTRAL
        return P.run_hook("bash_guard", P.pre_bash(cmd, cwd=cwd, session=session), env=env)

    def deny(self, cmd, gid, cwd=None, env=None):
        r = self.run_cmd(cmd, cwd=cwd, env=env)
        self.assertEqual(r.code, 0, cmd)
        self.assertEqual(r.err, "", cmd)
        self.assertEqual(r.decision, "deny", "expected deny: %r -> %r" % (cmd, r.out))
        self.assertTrue(r.reason.startswith("dojo-gates: %s " % gid), "%r -> %r" % (cmd, r.reason))
        self.assertIsNone(P.TRIGGER.search(r.reason), r.reason)
        self.assertNotIn("systemMessage", r.json)
        return r

    def allow(self, cmd, cwd=None, env=None):
        r = self.run_cmd(cmd, cwd=cwd, env=env)
        self.assertEqual(r.code, 0, cmd)
        self.assertEqual(r.out, "", "expected silence: %r -> %r" % (cmd, r.out))
        self.assertEqual(r.err, "", cmd)
        return r

    def warn(self, cmd, gid, env=None):
        r = self.run_cmd(cmd, env=env)
        self.assertEqual(r.code, 0, cmd)
        self.assertIsNone(r.decision, "a warning must not carry a decision: %r" % r.out)
        self.assertNotIn("permissionDecision", r.out)
        self.assertEqual(r.hso.get("hookEventName"), "PreToolUse")
        self.assertTrue(r.context.startswith("dojo-gates: %s " % gid), r.out)
        self.assertEqual(r.json.get("systemMessage"), r.context)
        self.assertIsNone(P.TRIGGER.search(r.context), r.context)
        return r


# --------------------------------------------------------------------------------
class StagingTests(GuardCase):
    DENY = [
        "git add -A",
        "git add .",
        "git add --all",
        "git add --al",
        "git add --a",
        "git add -Av",
        "git add -fA",
        "git add -- .",
        "git add ./",
        "git add src .",
        "git -C sub add -A",
        "git -c core.x=y add .",
        "/usr/bin/git add -A",
        "\\git add .",
        '"git" add -A',
        "sudo git add -A",
        "FOO=1 git add .",
        "cd x && git add .",
        "(cd x; git add -A)",
        "echo $(git add -A)",
        "git status\ngit add -A",
        "cat <<EOF\nit's\nEOF\ngit add -A",
        "bash -c 'git add -A'",
        'eval "git add -A"',
        "git commit -a -m x",
        "git commit -am x",
        "git commit -qam x",
        "git commit --all -m x",
        "git commit -m x -a",
        "git add . > /dev/null 2>&1",
        "git add -A>/dev/null",
        "timeout 5 git add -A",
        "git add -A \\\n  && echo done",
        "git stage -A",
        "git stage --all",
        "git stage .",
        "git -C . stage .",
        "git add :/",
        "git add :/.",
        "git add -- :/",
        "git add ':(top)'",
        "git add ':(top).'",
        "git stage -- :/",
        "cat <<< hi\ngit add -A",
        'jq . <<< "$x"\ngit add .',
        'read -r v <<< "$(date)"\ngit commit -am x',
        'cat <<< "$(git add -A)"',
        ">/dev/null git add -A",
        "2>&1 git add -A",
        "</dev/null git add -A",
        "function f { git add -A; }",
        "xargs git add -A",
        "xargs -n 1 git add -A",
        "find . -name x -exec git add -A \\;",
        "watch -n 5 git add -A",
        "caffeinate -t 5 git add -A",
        "arch -arm64 git add -A",
        # ANSI-C quoting: an escaped quote does not close it
        "echo $'\\'' ; git add -A ; echo \\'",
        "echo $'it\\'s' ; git add -A",
        "echo $(echo $'\\'' ; git add -A ; echo \\')",
        "git $'add' -A",
        # an unquoted word that can expand to nothing leaves the next word as the verb
        "$(true) git add -A",
        "`true` git add -A",
        "$EMPTY git add -A",
        "${EMPTY} git add .",
        "$(true) $(true) git commit -am x",
    ]
    ALLOW = [
        "git stage src/a.py",
        "git add :/src",
        "git add ':(top)src'",
        "xargs -I{} git add {}",
        "cat <<< hi\ngit status",
        "git add src/a.py",
        "git add -p",
        "git add -u",
        "git add src/a.py src/b.py",
        'git commit -m "add ."',
        'git commit -m "git add -A was wrong"',
        "git commit -ma",
        "git commit -m '-a'",
        'echo "git add -A"',
        "grep -rn 'git add -A' docs/",
        "# git add -A",
        "cat <<EOF\ngit add -A\nEOF",
        "git commit --amend",
        "git status",
        "ls -la",
        "git add ./src",
        # ANSI-C quotes that stay balanced, and a leading substitution that does not vanish into a verb
        "echo $'a\\nb'",
        "echo $'it\\'s fine' && git status",
        "git add $'src/a.py'",
        "echo $'\\'' ; git status ; echo \\'",
        "$(git rev-parse --show-toplevel)/bin/tool status",
        # the standard heredoc commit form, with an apostrophe and a backticked command in the text
        "git commit -m \"$(cat <<'EOF'\nThe release script now avoids `git add .`; it's safer.\nEOF\n)\"",
    ]

    def test_deny(self):
        for cmd in self.DENY:
            with self.subTest(cmd=cmd):
                self.deny(cmd, "staging")

    def test_allow(self):
        for cmd in self.ALLOW:
            with self.subTest(cmd=cmd):
                self.allow(cmd)

    def test_reason_names_the_fix_and_the_override(self):
        r = self.deny("git add -A", "staging")
        self.assertIn("explicit paths", r.reason)
        self.assertIn("DOJO_GATES_SKIP=staging", r.reason)


# --------------------------------------------------------------------------------
class PushedRewriteTests(GuardCase):
    def setUp(self):
        self.tmp = P.tmpdir()
        self.addCleanup(P.rmtree, self.tmp)

    def repo(self, factory, name):
        root = os.path.join(self.tmp, name)
        os.makedirs(root)
        r, shas = factory(root)
        return root, r, shas

    def env(self):
        return P.base_env(HOME=self.tmp)

    def d(self, cmd, cwd):
        return self.deny(cmd, "pushed-rewrite", cwd=cwd, env=self.env())

    def a(self, cmd, cwd):
        return self.allow(cmd, cwd=cwd, env=self.env())

    def test_deny_when_head_is_pushed(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        for cmd in [
            "git commit --amend --no-edit",
            "git commit --amen",
            "git commit --amend -m x",
            "git rebase main",
            "git rebase -i HEAD~1",
            "git rebase --onto main HEAD~1",
            "git reset --hard HEAD~1",
            "git reset --hard HEAD^",
        ]:
            with self.subTest(cmd=cmd):
                self.d(cmd, root)

    def test_deny_with_dash_c_and_cd(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        self.d("git -C %s commit --amend" % root, elsewhere)
        self.d("cd %s && git rebase -i HEAD~2" % root, elsewhere)
        self.d("(cd %s; git commit --amend)" % root, elsewhere)

    def test_leading_redirect_pushd_and_git_dir_do_not_hide_the_rewrite(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        self.d("pushd %s && git commit --amend" % root, elsewhere)
        self.d("pushd %s >/dev/null; git rebase -i HEAD~2" % root, elsewhere)
        self.d("GIT_DIR=%s/.git git commit --amend" % root, elsewhere)
        self.d("git --git-dir=%s/.git commit --amend" % root, elsewhere)
        self.d("env GIT_DIR=%s/.git git commit --amend" % root, elsewhere)
        self.d("2>&1 git commit --amend", root)
        # popd returns to where the command started
        self.a("pushd %s >/dev/null; popd >/dev/null; git commit --amend" % root, elsewhere)

    def test_abbreviated_long_options_are_still_the_same_option(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        self.d("git reset --h HEAD~1", root)
        self.d("git reset --ha HEAD~1", root)
        self.d("git reset --har HEAD~1", root)
        self.d("git reset --hard HEAD~1", root)
        self.d("git commit --am --no-edit", root)

    def test_cd_inside_a_subshell_does_not_leak(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        # the group ends, so the amend runs where the command started
        self.d("(cd %s) ; git commit --amend" % plain, root)
        self.d("(cd %s; ls) && git commit --amend" % plain, root)
        self.d("(cd %s)\ngit commit --amend" % plain, root)
        self.d("( (cd %s) ); git commit --amend" % plain, root)
        # inside the group the cd still counts
        self.d("(cd %s; git commit --amend)" % root, plain)
        self.a("(cd %s; git commit --amend)" % plain, root)
        # outside any group a cd persists, as before
        self.a("cd %s && git commit --amend" % plain, root)

    def test_kill_switches(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        cmd = "git commit --amend --no-edit"
        self.d(cmd, root)
        for name, extra in [
            ("DOJO_OFF", {"DOJO_OFF": "1"}),
            ("DOJO_GATES_OFF", {"DOJO_GATES_OFF": "1"}),
            ("skip pushed-rewrite", {"DOJO_GATES_SKIP": "pushed-rewrite"}),
            ("skip among others", {"DOJO_GATES_SKIP": " Staging , PUSHED-REWRITE "}),
        ]:
            with self.subTest(switch=name):
                self.allow(cmd, cwd=root, env=P.base_env(HOME=self.tmp, **extra))
        # a switch that names some other guard, or an off value that is not on, leaves it denied
        for name, extra in [
            ("skip staging only", {"DOJO_GATES_SKIP": "staging"}),
            ("unknown id", {"DOJO_GATES_SKIP": "no-such-guard"}),
            ("OFF=0", {"DOJO_OFF": "0"}),
            ("GATES_OFF empty", {"DOJO_GATES_OFF": ""}),
            ("SKIP empty", {"DOJO_GATES_SKIP": ""}),
        ]:
            with self.subTest(switch=name):
                self.deny(cmd, "pushed-rewrite", cwd=root, env=P.base_env(HOME=self.tmp, **extra))
        # the same switches cover rebase and a forced push
        amended, _, _ = self.repo(P.make_amended_repo, "amended")
        for c, where in [("git rebase -i HEAD~1", root), ("git push --force", amended)]:
            with self.subTest(cmd=c):
                self.d(c, where)
                self.allow(c, cwd=where, env=P.base_env(HOME=self.tmp, DOJO_GATES_SKIP="pushed-rewrite"))
                self.allow(c, cwd=where, env=P.base_env(HOME=self.tmp, DOJO_GATES_OFF="1"))
                self.allow(c, cwd=where, env=P.base_env(HOME=self.tmp, DOJO_OFF="1"))

    def test_leading_redirect_before_a_force_push(self):
        root, _, _ = self.repo(P.make_amended_repo, "amended")
        self.d(">/dev/null git push -f", root)
        self.d("2>&1 git push --force", root)
        self.a("2>&1 git push", root)

    def test_rebase_range_reaching_pushed_history(self):
        root, _, _ = self.repo(P.make_half_pushed_repo, "half")
        self.d("git rebase -i HEAD~2", root)
        self.a("git rebase -i HEAD~1", root)
        self.a("git commit --amend", root)
        self.a("git reset --hard HEAD~1", root)

    def test_allow_when_nothing_is_pushed(self):
        for factory, name in [(P.make_local_repo, "local")]:
            root, _, _ = self.repo(factory, name)
            for cmd in [
                "git commit --amend --no-edit",
                "git rebase -i HEAD~2",
                "git reset --hard HEAD~1",
                "git push --force",
                "git push -f origin main",
            ]:
                with self.subTest(cmd=cmd):
                    self.a(cmd, root)

    def test_allow_outside_a_repository(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        for cmd in ["git commit --amend", "git rebase -i HEAD~2", "git reset --hard HEAD~1", "git push -f"]:
            with self.subTest(cmd=cmd):
                self.a(cmd, plain)

    def test_allow_controls_and_recovery_paths_with_pushed_head(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        for cmd in [
            "git rebase --abort",
            "git rebase --quit",
            "git rebase --continue",
            "git rebase --skip",
            "git rebase --edit-todo",
            "git reset --hard",
            "git reset --hard HEAD",
            "git reset --hard origin/main",
            "git reset --soft HEAD~1",
            "git reset --mixed HEAD~1",
            "git reset HEAD~1",
            "git push",
            "git commit -m x",
            "git status",
        ]:
            with self.subTest(cmd=cmd):
                self.a(cmd, root)

    def test_force_push_that_drops_remote_commits(self):
        root, _, _ = self.repo(P.make_amended_repo, "amended")
        for cmd in [
            "git push --force",
            "git push -f",
            "git push -fu origin main",
            "git push --forc",
            "git push --force-with-lease",
            "git push --force-if-includes",
            "git push origin +main",
            "git push origin +HEAD:main",
            "git push origin main --force",
        ]:
            with self.subTest(cmd=cmd):
                self.d(cmd, root)

    def test_force_push_allowed_when_it_cannot_drop_anything(self):
        amended, _, _ = self.repo(P.make_amended_repo, "amended")
        self.a("git push", amended)
        self.a("git push origin main", amended)
        self.a("git push -f origin main:other", amended)  # no such remote branch
        ff, _, _ = self.repo(P.make_fastforward_repo, "ff")
        for cmd in ["git push --force", "git push -f", "git push --force-with-lease", "git push origin +main"]:
            with self.subTest(cmd=cmd):
                self.a(cmd, ff)

    def test_skip_staging_still_lets_pushed_rewrite_decide(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        env = P.base_env(HOME=self.tmp, DOJO_GATES_SKIP="staging")
        self.deny("git commit -a --amend -m x", "pushed-rewrite", cwd=root, env=env)

    def test_git_missing_fails_open(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        empty = os.path.join(self.tmp, "emptybin")
        os.makedirs(empty)
        env = P.base_env(HOME=self.tmp, PATH=empty)
        self.allow("git commit --amend", cwd=root, env=env)

    def test_hanging_git_fails_open_within_budget(self):
        root, _, _ = self.repo(P.make_pushed_repo, "pushed")
        fakebin = os.path.join(self.tmp, "fakebin")
        os.makedirs(fakebin)
        fake = os.path.join(fakebin, "git")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\nsleep 10\n")
        os.chmod(fake, 0o755)
        env = P.base_env(HOME=self.tmp, PATH=fakebin + ":/usr/bin:/bin")
        t0 = time.monotonic()
        r = self.run_cmd("git commit --amend", cwd=root, env=env)
        elapsed = time.monotonic() - t0
        self.assertEqual(r.out, "")
        self.assertEqual(r.code, 0)
        self.assertLess(elapsed, 4.8)

    def test_no_git_process_for_non_rewrite_commands(self):
        started = []

        class Spy(object):
            def __init__(self, *a, **k):
                started.append(1)

            def run(self, *a, **k):
                return None

        cmds = [
            "ls -la",
            "git status",
            "git add src/a.py",
            "git commit -m x",
            "git push",
            "git push origin main",
            "git reset --soft HEAD~1",
            "git reset --hard",
            "git rebase --abort",
            "echo git commit --amend",
        ]
        with mock.patch.object(_guards, "_Git", Spy):
            for c in cmds:
                ctx = _guards.Ctx(c, _shell.all_segments(c), {"cwd": self.tmp})
                _guards.pushed_rewrite(ctx)
        self.assertEqual(started, [])


# --------------------------------------------------------------------------------
class SecretPrintTests(GuardCase):
    DENY = [
        "echo ${API_KEY:+SET}${API_KEY:-UNSET}",
        "${API_KEY:+SET}${API_KEY:-UNSET}",
        "echo $API_KEY",
        'echo "$MY_SECRET"',
        'echo "${OPENAI_API_KEY}"',
        "echo ${API_KEY:0:4}",
        "echo $api_key",
        "echo $PGPASSWORD",
        "printf '%s' \"$DB_PASSWORD\"",
        'printf "$GITHUB_TOKEN"',
        "echo $API_KEY | base64",
        "echo $(printenv API_KEY)",
        "printenv",
        "printenv | grep X",
        "printenv OPENAI_API_KEY",
        "env",
        "env | head",
        "env | grep -i key",
        "env -0",
        "sudo env",
        "cat .env",
        "cat ./config/.env.local",
        "bat .env.production",
        "less .env",
        "head .env",
        "tail -n 3 .env",
        "cat .envrc",
        'cat "$HOME/.env"',
        "cat < .env",
        "< .env cat",
        "2>&1 cat .env",
        "grep API_KEY .env",
        "rg SECRET .env.local",
        "jq . <<< \"$x\"\necho $GITHUB_TOKEN",
        "read v <<< \"$x\"\necho $GITHUB_TOKEN",
        "cat <<< hi\ncat .env",
        "2>&1 echo $API_KEY",
        "echo $MASTERKEY",
        "echo $LICENSEKEY",
        "echo $API_KEY >&2",
        "echo $API_KEY > /dev/stdout",
        "echo $API_KEY | tee out.txt",
        "echo $API_KEY > out.txt | cat",
        "printf '%s' \"$DB_PASSWORD\" | pbcopy | cat",
        "function f { echo $API_KEY; }",
        "xargs echo $API_KEY",
        # a file or the clipboard is no exemption: the next command reads it back
        "echo $NPM_TOKEN > .npmrc",
        "echo $API_KEY >> out.txt",
        "printf '//r/:_authToken=%s\\n' \"$NPM_TOKEN\" > .npmrc",
        "printf '%s' \"$DB_PASSWORD\" | pbcopy",
        "echo $API_KEY | xclip -selection clipboard",
        "echo $GITHUB_TOKEN > /tmp/t.txt; cat /tmp/t.txt",
        "echo $GITHUB_TOKEN > /tmp/t.txt\ncat /tmp/t.txt",
        # a process-substitution target is not a regular file
        "echo $GITHUB_TOKEN > >(cat)",
        "printf '%s' \"$GITHUB_TOKEN\" > >(cat)",
        "echo $GITHUB_TOKEN | tee >(cat)",
        # the literal .env* glob and other patterns that expand to a secrets file
        "cat .env*",
        "cat ./.env*",
        "less .env?",
        "head .env.[a-z]*",
        "bat .env.*",
        "cat .e?v",
        "cat .*",
        "tail -n 2 .env.local*",
        "grep KEY .env*",
        # a secret on stdin, handed to a program that writes it back out
        "cat <<EOF\n$GITHUB_TOKEN\nEOF",
        "cat <<EOF\ntoken is ${GITHUB_TOKEN}\nEOF",
        "cat <<-EOF\n\t$API_KEY\n\tEOF",
        "cat <<EOF | tr a-z A-Z\n$API_KEY\nEOF",
        "cat <<EOF > out.txt\n$API_KEY\nEOF",
        "cat <<EOF\nit's $GITHUB_TOKEN\nEOF",
        "cat <<< \"$GITHUB_TOKEN\"",
        "cat <<< $GITHUB_TOKEN",
        "cat <<< \"token: ${GITHUB_TOKEN}\"",
        "tee <<< \"$API_KEY\"",
        "sed p <<< \"$API_KEY\"",
        "base64 <<< \"$API_KEY\"",
        "jq -R . <<< \"$API_KEY\"",
        "xargs echo <<< \"$API_KEY\"",
        "bash <<< \"echo $API_KEY\"",
        "python3 -c 'import sys; print(sys.stdin.read())' <<< \"$API_KEY\"",
        "grep . <<< \"$API_KEY\"",
        "ls\ncat <<< \"$GITHUB_TOKEN\"",
        # a here-string with an fd prefix is still a here-string
        "cat 0<<<\"$GITHUB_TOKEN\"",
        "cat 0<<< $GITHUB_TOKEN",
        "tee 0<<< \"$API_KEY\"",
        "cat 0<<< \"token: ${GITHUB_TOKEN}\"",
        # ANSI-C quoting and a vanishing leading word do not hide the print
        "echo $'\\'' ; echo $GITHUB_TOKEN ; echo \\'",
        "$(true) echo $GITHUB_TOKEN",
        "$EMPTY cat .env",
        # true positives that the narrower name rule must keep
        "echo $API_KEY_VALUE",
        "echo $SECRET_KEY_BASE",
        "echo $AWS_SECRET_ACCESS_KEY",
        "echo $CLIENT_SECRET",
        "echo $GITHUB_AUTH",
        "echo $DB_CREDENTIALS",
        "echo $SSH_KEY",
        "echo $SERVICE_PRIVATE_KEY",
        "echo $GH_PAT",
        "echo $githubToken",
        "echo $apiKey",
        "echo $NPM_TOKEN_2",
        "printf '%s\\n' \"$STRIPE_SECRET\"",
        "printenv AWS_SECRET_ACCESS_KEY",
        "echo $PUBLIC_KEY_SECRET",
    ]
    ALLOW = [
        "echo ${API_KEY:+set}",
        '[ -n "$TOKEN" ] && echo set',
        '[ -n "${API_KEY:-}" ] && echo set',
        'test -n "$API_KEY"',
        "echo ${#API_KEY}",
        "echo '$API_KEY'",
        'echo "\\$API_KEY"',
        "echo $HOME",
        "echo $MONKEY_COUNT",
        "echo $KEYCHAIN_PATH",
        "echo $KEYBOARD_LAYOUT",
        "cat <<< .env",
        # ordinary variables whose names only mention a token or a key
        "echo $MAX_TOKENS",
        'printf "%s\n" "$TOKEN_LIMIT"',
        'echo "$PUBLIC_KEY_PATH"',
        "echo $KEY_COUNT",
        "echo $TOKEN_TTL",
        "echo $API_KEY_FILE",
        "echo $SSH_KEY_PATH",
        "echo ${MAX_TOKENS:-4096}",
        'echo "$PUBLIC_KEY"',
        "printenv MAX_TOKENS",
        'cat 0<<< "$TOKEN_LIMIT"',
        # a secret handed to a program that does not print its input is fine
        'gh auth login --with-token <<< "$GH_TOKEN"',
        'read -r v <<< "$API_KEY"',
        'docker login --password-stdin <<< "$DOCKER_TOKEN"',
        'grep -q x <<< "$API_KEY"',
        "cat <<'EOF'\n$GITHUB_TOKEN\nEOF",
        'cat <<"EOF"\n$GITHUB_TOKEN\nEOF',
        "cat <<EOF\n\\$GITHUB_TOKEN\nEOF",
        "cat <<EOF\n${GITHUB_TOKEN:+set}\nEOF",
        "cat <<EOF\n$HOME\nEOF",
        'cat <<< "$HOME"',
        "cat .env.example*",
        "cat .gitignore*",
        "cat .git*",
        # the standard heredoc commit and PR forms never run their text as commands
        "git commit -m \"$(cat <<'EOF'\nDon't print `env` or `cat .env`; it's unsafe\nEOF\n)\"",
        "gh pr create --body \"$(cat <<'EOF'\n- Don't dump `env` in CI logs\nEOF\n)\"",
        "cat < .env.example",
        "echo $SSH_AUTH_SOCK",
        "echo $TOKENIZERS_PARALLELISM",
        "printenv PATH",
        "env FOO=1 cmd",
        "env -u X cmd",
        "env -i PATH=/bin ls",
        "cat .env.example",
        "cat .env.sample",
        "cat .env.template",
        "cat .env.dist",
        "cat .environment.md",
        "grep -q API_KEY .env",
        "grep -c '^API_KEY=' .env",
        "grep -l API_KEY .env",
        'git commit -m "document printenv usage"',
        "echo KEY_NAME",
        "cat README.md",
        "ls | head",
    ]

    def test_deny(self):
        for cmd in self.DENY:
            with self.subTest(cmd=cmd):
                self.deny(cmd, "secret-print")

    def test_allow(self):
        for cmd in self.ALLOW:
            with self.subTest(cmd=cmd):
                self.allow(cmd)

    def test_reason_recommends_the_safe_check(self):
        r = self.deny("echo $API_KEY", "secret-print")
        self.assertIn('[ -n "$NAME" ] && echo set', r.reason)

    def test_name_matching(self):
        yes = ["API_KEY", "GITHUB_TOKEN", "MY_SECRET", "DB_PASSWORD", "PGPASSWORD", "GH_PAT",
               "OPENAI_APIKEY", "aws_secret_access_key", "PRIVATE_KEY", "DB_PASSWD", "MASTERKEY",
               "LICENSEKEY", "TOKEN", "KEY", "PASSWORD", "AUTH", "CREDENTIALS", "CLIENT_SECRET",
               "ACCESS_KEY", "SECRET_KEY_BASE", "API_TOKEN_VALUE", "NPM_TOKEN2", "SSH_KEY", "apiKey",
               "githubToken", "STRIPE_SECRET", "OPENAI_API_KEY_2"]
        no = ["HOME", "PATH", "MONKEY_COUNT", "KEYCHAIN_PATH", "SSH_AUTH_SOCK", "TOKENIZERS_PARALLELISM",
              "PATTERN", "SHELL", "KEYBOARD", "KEYMAP", "TURKEY_PORT", "SIGNINGKEY_ID", "KEYS_DIR"]
        for n in yes:
            self.assertTrue(_guards.is_secret_name(n), n)
        for n in no:
            self.assertFalse(_guards.is_secret_name(n), n)

    def test_metadata_about_a_secret_is_not_a_secret(self):
        # (name, secret?): a secret noun, then a metadata suffix or a MAX_/MIN_/NUM_ prefix
        table = [
            ("MAX_TOKENS", False), ("MAX_TOKEN", False), ("MIN_PASSWORD_LENGTH", False),
            ("NUM_KEYS", False), ("TOKEN_LIMIT", False), ("TOKEN_COUNT", False), ("TOKEN_TTL", False),
            ("TOKEN_SIZE", False), ("TOKEN_LEN", False), ("TOKEN_MAX", False), ("TOKEN_MIN", False),
            ("TOKEN_TYPE", False), ("TOKEN_URL", False), ("TOKEN_HOST", False), ("TOKEN_PORT", False),
            ("TOKEN_ENV", False), ("TOKEN_NAME", False), ("TOKEN_ID", False), ("TOKEN_PATH", False),
            ("TOKEN_FILE", False), ("TOKEN_DIR", False), ("PUBLIC_KEY_PATH", False),
            ("PUBLIC_KEY", False), ("MY_PUBLIC_KEY", False), ("publicKey", False), ("KEY_COUNT", False),
            ("KEY_NAME", False), ("KEY_ID", False), ("API_KEY_FILE", False), ("API_KEY_NAME", False),
            ("API_KEY_ID", False), ("SSH_KEY_PATH", False), ("SSH_KEY_FILE", False),
            ("SECRET_NAME", False), ("SECRET_ID", False), ("SECRET_PATH", False),
            ("PASSWORD_FILE", False), ("PASSWORD_MIN_LENGTH", False), ("AUTH_URL", False),
            ("AUTH_HOST", False), ("CREDENTIALS_FILE", False), ("CLIENT_SECRET_PATH", False),
            ("GITHUB_TOKEN_FILE", False), ("maxTokens", False), ("tokenLimit", False),
            ("keyCount", False), ("max_tokens", False),
            # the same words, as a secret
            ("TOKEN", True), ("SSH_KEY", True), ("CLIENT_SECRET", True), ("GITHUB_TOKEN", True),
            ("PRIVATE_KEY", True), ("API_KEY", True), ("AUTH", True), ("CREDENTIALS", True),
        ]
        for name, secret in table:
            with self.subTest(name=name):
                self.assertEqual(_guards.is_secret_name(name), secret, name)


# --------------------------------------------------------------------------------
class TokenUrlTests(GuardCase):
    def test_deny(self):
        cases = [
            "git push https://u:%s@github.com/a/b" % P.tok_github(),
            "git remote set-url origin https://u:%s@github.com/a/b" % P.tok_github(),
            "git clone https://x:%s@github.com/a/b" % P.tok_github_oauth(),
            "git clone https://x:${GITHUB_TOKEN}@github.com/a/b",
            "git clone https://user:hunter2@example.com/a/b",
            "curl -H \"Authorization: Bearer %s\" https://api.example.com" % P.tok_sk(),
            "curl -H 'X-Key: %s' https://api.example.com" % P.tok_sk_ant(),
            "curl https://api.example.com -d token=%s" % P.tok_github_pat(),
            "gh api -H 'Authorization: token %s' /user" % P.tok_github(),
            "wget --header='PRIVATE-TOKEN: %s' https://gitlab.example/api" % P.tok_gitlab(),
            "curl -u x:y https://hooks.example.com/%s" % P.tok_slack(),
            'git commit -m "%s"' % P.tok_github(),
            # a token split across adjacent quotes is joined by the shell
            "git push 'https://u:gh'\"p_%s\"@github.com/a/b" % ("A" * 36),
            "sudo curl https://u:%s@host/x" % P.tok_sk(),
            # a token in an assignment prefix still lands in history and the transcript
            "GITHUB_TOKEN=%s git push" % P.tok_github(),
            "env GH_TOKEN=%s gh api /user" % P.tok_github(),
            "TOKEN=%s curl https://api.example.com" % P.tok_sk(),
        ]
        for cmd in cases:
            with self.subTest(cmd=cmd[:40]):
                r = self.deny(cmd, "token-url")
                for tok in (P.tok_github(), P.tok_github_oauth(), P.tok_github_pat(), P.tok_gitlab(),
                            P.tok_sk(), P.tok_sk_ant(), P.tok_slack(), "hunter2"):
                    self.assertNotIn(tok, r.out)

    def test_allow(self):
        for cmd in [
            "git clone https://github.com/a/b",
            "git clone https://user@host.example/a",
            "git clone ssh://git@github.com/a/b",
            "git clone git@github.com:a/b.git",
            "curl https://host.example:8443/p@x",
            "curl -H \"Authorization: Bearer $API_TOKEN\" https://api.example.com",
            "echo sk-",
            "GITHUB_TOKEN=$GITHUB_TOKEN git push",
            "FOO=sk-short git push",
            "git commit -m 'sk-short is a prefix'",
            "git commit -m 'remove the ask-for-long-names-in-the-ui-everywhere option'",
            "echo %s" % P.tok_github(),  # not git/curl: secret-print doesn't fire on literals
            "ls -la",
        ]:
            with self.subTest(cmd=cmd[:40]):
                self.allow(cmd)


# --------------------------------------------------------------------------------
class MacTimeoutTests(GuardCase):
    def setUp(self):
        self.tmp = P.tmpdir()
        self.addCleanup(P.rmtree, self.tmp)
        self.empty = os.path.join(self.tmp, "empty")
        os.makedirs(self.empty)

    def shim_dir(self, *names):
        d = os.path.join(self.tmp, "shim" + "".join(names))
        os.makedirs(d, exist_ok=True)
        for n in names:
            p = os.path.join(d, n)
            with open(p, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(p, 0o755)
        return d

    def check(self, cmd, path, os_name="darwin"):
        ctx = _guards.Ctx(cmd, _shell.all_segments(cmd), {})
        with mock.patch.object(sys, "platform", os_name), \
                mock.patch.object(_guards, "FALLBACK_DIRS", ()), \
                mock.patch.dict(os.environ, {"PATH": path}):
            return _guards.mac_timeout(ctx)

    def test_deny_without_any_shim(self):
        for cmd in [
            "timeout 5 make",
            "sudo timeout 5 x",
            "FOO=1 timeout 5 x",
            "ls && timeout 5 x",
            "ls | timeout 5 cat",
            "timeout -k 2 5 x",
            "timeout --signal=KILL 5 x",
            "gtimeout 5 x",
            "ls\ntimeout 5 x",
            "(timeout 5 x)",
            "bash -c 'timeout 5 x'",
        ]:
            with self.subTest(cmd=cmd):
                res = self.check(cmd, self.empty)
                self.assertIsNotNone(res, cmd)
                kind, msg = res
                self.assertEqual(kind, "deny")
                self.assertTrue(msg.startswith("dojo-gates: mac-timeout "))
                self.assertIn("gtimeout", msg)
                self.assertIn("alarm", msg)
                self.assertIsNone(P.TRIGGER.search(msg))

    def test_allow_with_a_shim(self):
        self.assertIsNone(self.check("timeout 5 make", self.shim_dir("timeout")))
        self.assertIsNone(self.check("gtimeout 5 x", self.shim_dir("gtimeout")))

    def test_timeout_when_only_gtimeout_exists_says_use_gtimeout(self):
        res = self.check("timeout 5 x", self.shim_dir("gtimeout"))
        self.assertEqual(res[0], "deny")
        self.assertIn("Use `gtimeout`", res[1])

    def test_allow_when_timeout_is_not_the_verb(self):
        for cmd in [
            "grep timeout f",
            "kubectl wait --timeout=5s",
            "command -v timeout",
            'git commit -m "add timeout 5"',
            'echo "timeout 5 x"',
            "ls",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.check(cmd, self.empty), cmd)

    def test_allow_outside_macos(self):
        self.assertIsNone(self.check("timeout 5 make", self.empty, os_name="linux"))

    def test_fallback_locations_count(self):
        d = self.shim_dir("gtimeout")
        ctx = _guards.Ctx("gtimeout 5 x", _shell.all_segments("gtimeout 5 x"), {})
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(_guards, "FALLBACK_DIRS", (d,)), \
                mock.patch.dict(os.environ, {"PATH": self.empty}):
            self.assertIsNone(_guards.mac_timeout(ctx))

    def test_end_to_end_allow_with_shim(self):
        env = P.base_env(PATH=self.shim_dir("timeout") + ":/usr/bin:/bin")
        self.allow("timeout 5 make", env=env)

    @unittest.skipUnless(
        sys.platform == "darwin"
        and not any(os.path.exists(os.path.join(d, n))
                    for d in _guards.FALLBACK_DIRS for n in ("timeout", "gtimeout")),
        "needs macOS with no timeout or gtimeout installed",
    )
    def test_end_to_end_deny(self):
        env = P.base_env(PATH=self.empty + ":/usr/bin:/bin")
        self.deny("timeout 5 make", "mac-timeout", env=env)


# --------------------------------------------------------------------------------
class MaskedExitTests(GuardCase):
    WARN = [
        "pytest | tail && git commit -m x",
        "pytest -q 2>&1 | tail -n 20 && git commit -m x",
        "npm test | grep -v warn && git add a && git commit -m x",
        "go test ./... | head -5 && git push",
        "uv run pytest | tail && git push",
        "npm run build:prod | tail && git commit -m x",
        "python3 -m pytest | tail && git commit -m x",
        "cargo test | grep ok && git push",
        "make check | tee out.log && git commit -m x",
        "(pytest | tail) && git commit -m x",
    ]
    SILENT = [
        "pytest && git commit -m x",
        "pytest | tail; git commit -m x",
        "ls | head && git commit -m x",
        "git log | head && git push",
        "set -o pipefail; pytest | tail && git commit -m x",
        "set -euo pipefail\npytest | tail && git commit -m x",
        'pytest | tail && [ "${PIPESTATUS[0]}" = 0 ] && git commit -m x',
        "pytest | tail",
        "pytest | tail && echo done",
        "npm install | tail && git commit -m x",
    ]

    def test_warn(self):
        for cmd in self.WARN:
            with self.subTest(cmd=cmd):
                self.warn(cmd, "masked-exit")

    def test_silent(self):
        for cmd in self.SILENT:
            with self.subTest(cmd=cmd):
                self.allow(cmd)

    def test_a_deny_wins_over_a_warning(self):
        r = self.deny("pytest | tail && git add -A && git commit -m x", "staging")
        self.assertNotIn("masked-exit", r.out)

    def test_check_command_detection(self):
        def words(c):
            return _shell.tokenize(c)[0].words

        for c in ["pytest", "python -m unittest", "go test ./...", "cargo clippy", "npm test", "pnpm run lint",
                  "yarn build", "make check", "just test", "uv run pytest -q", "npx vitest", "tsc --noEmit",
                  "bun test", "deno test", "swift test", "xcodebuild test", "ruff check ."]:
            self.assertTrue(_guards.is_check_command(words(c)), c)
        for c in ["ls", "git log", "npm install", "make", "python script.py", "go mod tidy", "cat f"]:
            self.assertFalse(_guards.is_check_command(words(c)), c)


# --------------------------------------------------------------------------------
class KillSwitchTests(GuardCase):
    SAMPLES = {
        "staging": "git add -A",
        "secret-print": "echo $API_KEY",
        "token-url": "curl https://u:%s@host/x" % P.tok_sk(),
    }

    def test_every_switch(self):
        for gid, cmd in self.SAMPLES.items():
            with self.subTest(guard=gid):
                self.deny(cmd, gid)
                self.allow(cmd, env=P.base_env(DOJO_OFF="1"))
                self.allow(cmd, env=P.base_env(DOJO_GATES_OFF="1"))
                self.allow(cmd, env=P.base_env(DOJO_GATES_SKIP=gid))
                self.allow(cmd, env=P.base_env(DOJO_GATES_SKIP=" %s , big-read " % gid))
                self.allow(cmd, env=P.base_env(DOJO_GATES_SKIP="Staging,%s" % gid.upper()))
                # a different id does not skip it
                other = "big-read" if gid != "big-read" else "staging"
                self.deny(cmd, gid, env=P.base_env(DOJO_GATES_SKIP=other))
                self.deny(cmd, gid, env=P.base_env(DOJO_GATES_SKIP="no-such-guard"))
                # off values that are not on
                self.deny(cmd, gid, env=P.base_env(DOJO_OFF="0"))
                self.deny(cmd, gid, env=P.base_env(DOJO_GATES_OFF=""))
                self.deny(cmd, gid, env=P.base_env(DOJO_GATES_SKIP=""))

    def test_skip_for_masked_exit_and_mac_timeout(self):
        cmd = "pytest | tail && git commit -m x"
        self.warn(cmd, "masked-exit")
        self.allow(cmd, env=P.base_env(DOJO_GATES_SKIP="masked-exit"))
        self.allow(cmd, env=P.base_env(DOJO_OFF="1"))
        self.allow(cmd, env=P.base_env(DOJO_GATES_OFF="1"))
        with mock.patch.dict(os.environ, {"DOJO_GATES_SKIP": "mac-timeout"}):
            from _common import killed
            self.assertTrue(killed("mac-timeout"))
            self.assertFalse(killed("staging"))

    def test_skipping_one_id_leaves_the_others_running(self):
        env = P.base_env(DOJO_GATES_SKIP="staging")
        self.deny("echo $API_KEY", "secret-print", env=env)

    def test_text_in_the_command_cannot_switch_a_guard_off(self):
        for cmd in [
            "DOJO_GATES_SKIP=staging git add -A",
            "DOJO_GATES_OFF=1 git add .",
            "env DOJO_OFF=1 git add --all",
            "export DOJO_GATES_OFF=1; git add -A",
            "DOJO_OFF=1 DOJO_GATES_SKIP=staging,secret-print bash -c 'git add -A'",
        ]:
            with self.subTest(cmd=cmd):
                self.deny(cmd, "staging")
        self.deny("DOJO_GATES_SKIP=secret-print echo $API_KEY", "secret-print")


# --------------------------------------------------------------------------------
class HeredocSubstitutionTests(GuardCase):
    """Claude Code commits and opens PRs with -m "$(cat <<'EOF' ... EOF, then a newline and a
    closing paren". Whatever the message says, it is text, not a command."""

    ALLOW = [
        "git commit -m \"$(cat <<'EOF'\nThe release script now avoids `git add .`; it's safer.\nEOF\n)\"",
        "gh pr create --body \"$(cat <<'EOF'\n- Don't dump `env` in CI logs\nEOF\n)\"",
        "git commit -m \"$(cat <<'EOF'\nWe won't read `cat .env` any more\nEOF\n)\"",
        "git commit -m \"$(cat <<'EOF'\nIt's fine\n\nBody: \"quoted\" and (parens) and 'single'\nEOF\n)\"",
        "git commit -m \"$(cat <<EOF\nplain text, it's here\nEOF\n)\"",
        "git commit -m \"$(cat <<-'EOF'\n\tit's tabbed\n\tEOF\n)\"",
        "git commit -m \"$(cat <<\\EOF\nit's escaped\nEOF\n)\"",
        "git commit -m \"$(cat <<\"EOF\"\nit's dq\nEOF\n)\"",
        "gh pr create --title t --body \"$(cat <<'EOF'\n## Summary\n- it's `git add -A` safe\nEOF\n)\" && git status",
        "git commit -F - <<'EOF'\nit's `git add .` text\nEOF",
        "git commit -m \"$(cat <<'EOF'\nfirst\nEOF\n)\" -m \"$(cat <<'EOF'\nit's second\nEOF\n)\"",
        "echo \"$(cat <<'EOF'\nit's\nEOF\n)\"",
        "VAR=$(cat <<'EOF'\nit's `env`\nEOF\n)\nls",
    ]
    DENY = [
        ("git commit -m \"$(cat <<'EOF'\nIt's\nEOF\n)\" && git add -A", "staging"),
        ("git add -A && git commit -m \"$(cat <<'EOF'\nit's\nEOF\n)\"", "staging"),
        ("git commit -m \"$(cat <<'EOF'\nIt's\nEOF\n)\"; echo $API_KEY", "secret-print"),
        ("git commit -m \"$(cat <<'EOF'\nit's\nEOF\n)\" && cat .env", "secret-print"),
        ("git commit -am \"$(cat <<'EOF'\nit's\nEOF\n)\"", "staging"),
        # an unquoted heredoc runs its backticks and $( ): that is a real command
        ("git commit -m \"$(cat <<EOF\nuse `git add .` it's here\nEOF\n)\"", "staging"),
        ("git commit -m \"$(cat <<EOF\nit's $(git add -A)\nEOF\n)\"", "staging"),
        # a real command inside the substitution, ahead of the heredoc
        ("git commit -m \"$(git add -A; cat <<'EOF'\nit's\nEOF\n)\"", "staging"),
    ]

    def test_text_is_not_scanned_as_commands(self):
        for cmd in self.ALLOW:
            with self.subTest(cmd=cmd[:70]):
                self.allow(cmd)

    def test_real_commands_around_or_inside_are_still_caught(self):
        for cmd, gid in self.DENY:
            with self.subTest(cmd=cmd[:70]):
                self.deny(cmd, gid)

    def test_a_pushed_amend_after_a_heredoc_message_is_still_denied(self):
        tmp = P.tmpdir()
        self.addCleanup(P.rmtree, tmp)
        root = os.path.join(tmp, "pushed")
        os.makedirs(root)
        P.make_pushed_repo(root)
        cmd = "git commit --amend -m \"$(cat <<'EOF'\nit's reworded\nEOF\n)\""
        self.deny(cmd, "pushed-rewrite", cwd=root, env=P.base_env(HOME=tmp))


# --------------------------------------------------------------------------------
class FailOpenTests(unittest.TestCase):
    RAW = [
        "",
        "   \n",
        "not json",
        "[]",
        "null",
        "42",
        '"a string"',
        '{"tool_name":"Bash"}',
        '{"tool_name":"Bash","tool_input":"git add -A"}',
        '{"tool_name":"Bash","tool_input":{"command":123}}',
        '{"tool_name":"Bash","tool_input":{"command":["git","add","-A"]}}',
        '{"tool_name":"Bash","tool_input":{"command":null}}',
        '{"tool_name":"Bash","tool_input":{"command":""}}',
        '{"tool_name":"Bash","tool_input":null}',
        '{"tool_name":"Read","tool_input":{"file_path":123}}',
        '{"tool_name":"Edit","tool_input":{"file_path":null}}',
        '{"hook_event_name":"PostToolUse","tool_name":"Bash"}',
        '{"hook_event_name":"PostToolUseFailure","tool_name":"Bash","tool_input":{"command":"ls"},"error":42}',
        '{"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":"text"}',
        b"\xff\xfe\x00\x01 binary \x80\x81",
        b'{"tool_name":"Bash","tool_input":{"command":"ls \xff\xfe"}}',
    ]

    def env_for(self, script):
        env = P.base_env()
        if script == "claude_md_reach":
            env["CLAUDE_PLUGIN_OPTION_CLAUDE_MD_REACH"] = "true"
        return env

    def test_matrix(self):
        for script in P.SCRIPTS:
            for raw in self.RAW:
                with self.subTest(script=script, raw=str(raw)[:50]):
                    t0 = time.monotonic()
                    r = P.run_hook(script, raw=raw, env=self.env_for(script))
                    self.assertEqual(r.code, 0)
                    self.assertEqual(r.out, "")
                    self.assertEqual(r.err, "")
                    self.assertLess(time.monotonic() - t0, 3.0)

    def test_two_megabyte_command(self):
        for body in ("x" * (2 * 1024 * 1024), "echo " + "x " * (1024 * 1024), "echo '" + "y" * (2 * 1024 * 1024)):
            for script in P.SCRIPTS:
                with self.subTest(script=script, head=body[:8]):
                    payload = P.pre_bash(body)
                    t0 = time.monotonic()
                    r = P.run_hook(script, payload, env=self.env_for(script))
                    elapsed = time.monotonic() - t0
                    self.assertEqual(r.code, 0)
                    self.assertEqual(r.out, "")
                    self.assertLess(elapsed, 1.0, "took %.2fs" % elapsed)

    def test_garbage_in_a_valid_payload_still_exits_zero(self):
        for cmd in ["'", '"', "$(", "`", "<<", "<<EOF", "cat <<'EOF", "a || || b", "))((", "${", "\\"]:
            with self.subTest(cmd=cmd):
                r = P.run_hook("bash_guard", P.pre_bash(cmd))
                self.assertEqual(r.code, 0)
                self.assertEqual(r.err, "")


class LatencyTests(unittest.TestCase):
    def test_benign_command_is_quick(self):
        best = 9.0
        for _ in range(4):
            t0 = time.monotonic()
            r = P.run_hook("bash_guard", P.pre_bash("ls -la"))
            best = min(best, time.monotonic() - t0)
            self.assertEqual(r.out, "")
        self.assertLess(best, 0.3, "best of 4 was %.3fs" % best)


# --------------------------------------------------------------------------------
class ShellLexerTests(unittest.TestCase):
    def words(self, cmd):
        return [[w.text for w in s.words] for s in _shell.tokenize(cmd)]

    def test_splits_on_operators_and_newlines(self):
        self.assertEqual(self.words("a b && c | d; e\nf"), [["a", "b"], ["c"], ["d"], ["e"], ["f"]])

    def test_quotes_and_escapes(self):
        self.assertEqual(self.words("echo 'a b' \"c d\" e\\ f"), [["echo", "a b", "c d", "e f"]])
        self.assertEqual(self.words('"g""it" add'), [["git", "add"]])

    def test_heredoc_body_is_dropped_even_with_an_apostrophe(self):
        self.assertEqual(self.words("cat <<EOF\nit's here\nEOF\nls"), [["cat"], ["ls"]])
        self.assertEqual(self.words("cat <<-'EOF'\n\tx \" y\n\tEOF\nls"), [["cat"], ["ls"]])

    def test_comment_is_dropped(self):
        self.assertEqual(self.words("ls # git add -A"), [["ls"]])
        self.assertEqual(self.words("echo a#b"), [["echo", "a#b"]])

    def test_substitutions_become_segments(self):
        w = self.words("echo $(git add -A) `ls -la`")
        self.assertIn(["git", "add", "-A"], w)
        self.assertIn(["ls", "-la"], w)

    def test_redirections_are_their_own_words(self):
        self.assertEqual(self.words("ls >out 2>&1"), [["ls", ">", "out", "2>&1"]])
        self.assertEqual(self.words("ls 2>/dev/null"), [["ls", "2>", "/dev/null"]])

    def test_here_string_is_one_operator_and_later_lines_still_lex(self):
        self.assertEqual(
            self.words("cat <<< hi\ngit status"),
            [["cat", "<<<", "hi"], ["git", "status"]],
        )
        self.assertEqual(self.words('read v <<< "$x"; ls'), [["read", "v", "<<<", "$x"], ["ls"]])
        self.assertEqual(self.words("cat <<EOF\nx\nEOF\nls"), [["cat"], ["ls"]])

    def test_ansi_c_quotes_honour_backslash_escapes(self):
        self.assertEqual(self.words("echo $'a b' c"), [["echo", "a b", "c"]])
        self.assertEqual(self.words("echo $'it\\'s' ; ls"), [["echo", "it's"], ["ls"]])
        self.assertEqual(self.words("echo $'\\'' ; git status ; echo \\'"),
                         [["echo", "'"], ["git", "status"], ["echo", "'"]])
        self.assertEqual(self.words("echo $'a\\tb'"), [["echo", "a\tb"]])
        self.assertEqual(self.words("echo $(echo $'\\'' ; ls)")[0], ["echo", "$(echo $'\\'' ; ls)"])
        self.assertIn(["ls"], self.words("echo $(echo $'\\'' ; ls)"))

    def test_unwrap_skips_a_leading_word_that_can_vanish(self):
        def verb(cmd):
            return _shell.verb(_shell.tokenize(cmd)[0])

        self.assertEqual(verb("$(true) git status"), "git")
        self.assertEqual(verb("`true` git status"), "git")
        self.assertEqual(verb("$EMPTY git status"), "git")
        self.assertEqual(verb("${EMPTY} git status"), "git")
        self.assertEqual(verb('"$(true)" git status'), '$(true)')  # quoted: an empty argument, not dropped
        self.assertEqual(verb("$(pwd)/bin/tool x"), "tool")  # a path built from a substitution is a verb
        self.assertEqual(verb("$(true)"), "$(true)")  # nothing follows

    def test_here_string_with_an_fd_prefix(self):
        self.assertEqual(self.words('cat 0<<<"$T"'), [["cat", "0<<<", "$T"]])

    def test_here_string_substitution_is_scanned(self):
        w = self.words('cat <<< "$(ls -la)"')
        self.assertIn(["ls", "-la"], w)

    def test_unterminated_quote_falls_back_instead_of_failing_open(self):
        segs = _shell.tokenize_safe("echo 'oops; git add -A")
        flat = [w.text for s in segs for w in s.words]
        self.assertIn("add", flat)
        self.assertIn("-A", flat)

    def test_unwrap(self):
        def verb(c):
            return _shell.verb(_shell.tokenize(c)[0])

        self.assertEqual(verb("FOO=1 sudo -u me env X=1 nice -n 5 /usr/bin/git add"), "git")
        self.assertEqual(verb("command -v git"), "")
        self.assertEqual(verb("timeout -k 2 5 git add"), "git")
        self.assertEqual(verb("if git add x; then"), "git")
        self.assertEqual(verb("2>&1 git add x"), "git")
        self.assertEqual(verb(">/dev/null git add x"), "git")
        self.assertEqual(verb("> out 2>&1 git add x"), "git")
        self.assertEqual(verb("</dev/null cat"), "cat")
        self.assertEqual(verb("function f { git add x; }"), "git")
        self.assertEqual(verb("xargs -n 1 -I{} git add"), "git")
        self.assertEqual(verb("caffeinate -t 5 git add"), "git")
        self.assertEqual(verb("arch -arm64 git add"), "git")
        self.assertEqual(verb("> out"), "")

    def test_match_paren_follows_heredocs_quotes_and_comments(self):
        def close(body):
            s = body + ") tail"
            return s.index(") tail"), _shell._match_paren(s, 0)

        for body in [
            "cat <<'EOF'\nit's\nEOF\n",
            "cat <<EOF\nit's (here\nEOF\n",
            "cat <<-EOF\n\tit's\n\tEOF\n",
            "cat <<\\EOF\nit's\nEOF\n",
            "cat <<A <<B\none's\nA\ntwo's\nB\n",
            "cat <<'EOF'\nEOF\n",
            "echo hi # it's a comment\n",
            "echo \"$(echo \"a)b\")\"",
            "echo 'a)b'",
            "cat <<< a\nb",
            "echo $((1+2))",
        ]:
            with self.subTest(body=body):
                want, got = close(body)
                self.assertEqual(got, want)
        # a missing terminator returns the end of the string instead of looping
        self.assertEqual(_shell._match_paren("cat <<'EOF'\nno end", 0), len("cat <<'EOF'\nno end"))

    def test_expanding_heredoc_text_rides_on_the_command_that_reads_it(self):
        segs = _shell.tokenize("cat <<EOF | grep x\n$TOKEN it's \\$ESC\nEOF\nls")
        self.assertEqual([[w.text for w in s.words] for s in segs], [["cat"], ["grep", "x"], ["ls"]])
        self.assertIn("$TOKEN", segs[0].stdin)
        self.assertNotIn("$ESC", segs[0].stdin)  # an escaped dollar is no longer an expansion
        self.assertEqual(segs[1].stdin, "")
        self.assertEqual(segs[2].stdin, "")
        quoted = _shell.tokenize("cat <<'EOF'\n$TOKEN\nEOF\n")
        self.assertEqual(quoted[0].stdin, "")
        both = _shell.tokenize("cat <<A; cat <<B\n$ONE\nA\n$TWO\nB\n")
        self.assertIn("$ONE", both[0].stdin)
        self.assertNotIn("$TWO", both[0].stdin)
        self.assertIn("$TWO", both[1].stdin)

    def test_subshell_groups_are_marked(self):
        segs = _shell.tokenize("(cd /tmp) ; git status; (cd x; ls)")
        got = [(s.words[0].text, s.opens, s.closes) for s in segs]
        self.assertEqual(got, [("cd", 1, 1), ("git", 0, 0), ("cd", 1, 0), ("ls", 0, 1)])
        nested = _shell.tokenize("( (cd a) ); ls")
        self.assertEqual([(s.opens, s.closes) for s in nested], [(2, 2), (0, 0)])
        func = _shell.tokenize("f() { ls; }; ls")
        self.assertEqual(sum(s.closes for s in func), 0)

    def test_live_text_leaves_out_single_quotes(self):
        seg = _shell.tokenize("echo '$A' \"$B\" \\$C")[0]
        self.assertEqual([w.live for w in seg.words][1:], ["", "$B", "C"])


if __name__ == "__main__":
    unittest.main()
