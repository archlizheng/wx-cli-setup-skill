import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/wx-cli-setup/scripts'
sys.path.insert(0, str(SCRIPTS))
from diagnose import diagnose
from install import reusable
import install
from job_prompt import KINDS, render
from query_window import parse_time, query_window, resolve_chat
from wx_common import WxClient, WxError, account_match

START = 1700000000


class FakeWx:
    def __init__(self, messages=None, contacts=None, sessions=None, meta=None):
        self.messages = messages or []
        self.contacts = contacts or []
        self.sessions = sessions if sessions is not None else [{'username': 'test@chatroom', 'chat': '示例群 '}]
        self.meta = meta or {'status': 'windowed', 'unknown_shards': []}
        self.calls = []
        self.state_dir = Path('/nonexistent-test-state')

    def run(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == '--version': return 'wx 0.6.3'
        if args[0] == 'doctor':
            return {'checks': [{'name': '数据库密钥', 'ok': False, 'detail': 'PRIVATE_KEY_SENTINEL'}]}
        if args[0] == 'contacts': return self.contacts
        if args[0] == 'sessions': return {'sessions': self.sessions, 'meta': self.meta}
        if args[0] == 'history':
            before = int(args[args.index('--before') + 1]); after = int(args[args.index('--after') + 1])
            count = int(args[args.index('-n') + 1]); offset = int(args[args.index('--offset') + 1])
            rows = sorted([m for m in self.messages if before < m['timestamp'] < after],
                          key=lambda m: (m['timestamp'], m['local_id']), reverse=True)
            return {'messages': rows[offset:offset + count], 'meta': self.meta}
        raise AssertionError('unexpected command')


def message(i, ts=START):
    return {'timestamp': ts, 'local_id': i, 'sender_username': 'test-user', 'content': 'synthetic-' + str(i), 'type_code': 1}


class WorkflowTests(unittest.TestCase):
    def test_group_lookup_falls_back_to_sessions(self):
        self.assertEqual(resolve_chat(FakeWx(), '示例群'), 'test@chatroom')

    def test_exact_match_beats_fuzzy_contact(self):
        c = FakeWx(contacts=[{'username': 'someone', 'display': '示例群管理员'}])
        self.assertEqual(resolve_chat(c, '示例群'), 'test@chatroom')

    def test_duplicate_group_names_require_id(self):
        c = FakeWx(sessions=[{'username': 'a@chatroom', 'chat': '群'}, {'username': 'b@chatroom', 'chat': '群'}])
        with self.assertRaisesRegex(WxError, 'ambiguous_chat'): resolve_chat(c, '群')

    def test_half_open_boundaries(self):
        c = FakeWx([message(1, START - 1), message(2), message(3, START + 9), message(4, START + 10)])
        r = query_window(c, 'test@chatroom', START, START + 10)
        self.assertEqual([m['local_id'] for m in r['messages']], [2, 3])

    def test_pagination_does_not_lose_same_second_messages(self):
        c = FakeWx([message(i) for i in range(12)])
        r = query_window(c, 'test@chatroom', START, START + 10, page_size=3)
        self.assertEqual(r['count'], 12)
        self.assertFalse(r['coverage']['truncated'])
        bounds = {(x[x.index('--before') + 1], x[x.index('--after') + 1]) for x in c.calls if x[0] == 'history'}
        self.assertEqual(len(bounds), 1)

    def test_cap_is_reported_as_truncated(self):
        r = query_window(FakeWx([message(i) for i in range(20)]), 'test@chatroom', START, START + 10, page_size=3, max_messages=5)
        self.assertEqual(r['count'], 5)
        self.assertTrue(r['coverage']['truncated'])

    def test_identical_rows_not_lost_when_ids_collide_across_shards(self):
        r = query_window(FakeWx([message(1), message(1)]), 'test@chatroom', START, START + 10, page_size=1)
        self.assertEqual(r['count'], 2)

    def test_stable_user_id_skips_name_lookup(self):
        c = FakeWx()
        self.assertEqual(resolve_chat(c, 'wxid_synthetic'), 'wxid_synthetic')
        self.assertEqual(c.calls, [])

    def test_empty_is_local_only(self):
        r = query_window(FakeWx(), 'test@chatroom', START, START + 10)
        self.assertEqual(r['count'], 0)
        self.assertIn('no_local_messages_not_proof_of_no_group_activity', r['coverage']['warnings'])

    def test_missing_shard_staleness_preserved(self):
        c = FakeWx(meta={'status': 'possibly_stale_unknown_shards', 'unknown_shards': ['message/test.db']})
        r = query_window(c, 'test@chatroom', START, START + 10)
        self.assertIn('unknown_message_shards', r['coverage']['warnings'])
        self.assertIn('source_reports_possible_incompleteness', r['coverage']['warnings'])

    def test_missing_key_is_error_not_empty(self):
        class Missing(FakeWx):
            def run(self, *args, **kwargs):
                if args[0] == 'history': raise WxError('database_unavailable')
                return super().run(*args, **kwargs)
        with self.assertRaisesRegex(WxError, 'database_unavailable'):
            query_window(Missing(), 'test@chatroom', START, START + 10)

    def test_diagnostic_never_prints_private_detail(self):
        c = FakeWx(contacts=[{'display': 'PRIVATE_NAME'}])
        r = diagnose(c, lambda _: 'matched')
        self.assertNotIn('PRIVATE', json.dumps(r))
        self.assertTrue(r['basic_queries_available'])
        self.assertFalse(r['checks'][0]['ok'])

    def test_diagnostic_account_mismatch_prevents_queries(self):
        c = FakeWx(); r = diagnose(c, lambda _: 'mismatch_or_multiple_active_accounts')
        self.assertEqual(r['queries'], {})
        self.assertFalse(any(x[0] == 'history' for x in c.calls))

    def test_open_account_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p / 'config.json').write_text(json.dumps({'db_dir': '/tmp/xwechat_files/selected/db_storage'}))
            client = WxClient(state_dir=d)
            ps = subprocess.CompletedProcess([], 0, '123 /Applications/WeChat.app/Contents/MacOS/WeChat\n', '')
            ls = subprocess.CompletedProcess([], 0, 'n/tmp/xwechat_files/other/db_storage/session/session.db\n', '')
            with patch('wx_common.subprocess.run', side_effect=[ps, ls]):
                self.assertEqual(account_match(client), 'mismatch_or_multiple_active_accounts')

    def test_timezone_explicit_offsets_agree(self):
        zone = ZoneInfo('Asia/Shanghai')
        self.assertEqual(parse_time('2026-10-12T09:00:00', zone), parse_time('2026-10-12T01:00:00+00:00', zone))

    def test_dst_ambiguous_time_rejected(self):
        with self.assertRaises(ValueError): parse_time('2026-11-01T01:30:00', ZoneInfo('America/New_York'))

    def test_all_task_kinds_self_contained_and_experimental_labeled(self):
        for kind in KINDS:
            r = render(kind, chat='synthetic-group', keywords=['synthetic-word'])
            self.assertIn('SKILL.md', r['prompt'])
            self.assertIn('Asia/Shanghai', r['prompt'])
            self.assertIn('[开始,结束)', r['prompt'])
            if kind in {'sns', 'articles', 'favorites'}: self.assertEqual(r['validation'], 'experimental')

    def test_keyword_requires_explicit_scope_and_words(self):
        with self.assertRaises(ValueError): render('keyword', chat='synthetic-group')
        with self.assertRaises(ValueError): render('group-summary')

    def test_broken_binary_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / 'wx'; bad.write_text('#!/bin/sh\nprintf "not wx"\n'); bad.chmod(0o700)
            self.assertFalse(reusable(bad))

    def test_install_dry_run_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'new-runtime'
            r = subprocess.run([sys.executable, str(SCRIPTS / 'install.py'), '--dry-run', '--runtime-dir', str(path)], capture_output=True, text=True)
            if sys.platform == 'darwin': self.assertEqual(r.returncode, 0)
            else: self.assertNotEqual(r.returncode, 0)
            self.assertFalse(path.exists())

    def test_command_error_does_not_echo_secret(self):
        with tempfile.TemporaryDirectory() as d:
            client = WxClient(state_dir=d)
            error = subprocess.CompletedProcess([], 1, '', '无法解密 PRIVATE_KEY_SENTINEL')
            with patch('wx_common.subprocess.run', return_value=error):
                with self.assertRaisesRegex(WxError, '^database_unavailable$'): client.run('sessions', '--json')

    def test_build_preserves_old_binary_and_isolates_rust(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'runtime'; source = root / 'source'
            (source / 'target/release').mkdir(parents=True)
            (root / 'cargo/bin').mkdir(parents=True)
            (root / 'cargo/bin/cargo').touch()
            artifact = source / 'target/release/wx'
            artifact.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then printf "wx 0.6.3"; else printf -- "--json --before --after --offset"; fi\n')
            artifact.chmod(0o700)
            prefix = Path(d) / 'prefix'; (prefix / 'bin').mkdir(parents=True)
            binary = prefix / 'bin/wx'; binary.write_text('old-binary')
            captured = []
            def fake_check_output(argv, **kwargs):
                if argv[0] == 'git':
                    if 'get-url' in argv: return install.REPO + '\n'
                    if 'rev-parse' in argv: return install.REVISION + '\n'
                    return ''
                return 'wx 0.6.3\n'
            def fake_run(argv, **kwargs): captured.append((argv, kwargs))
            argv = ['install.py', '--build', '--prefix', str(prefix), '--runtime-dir', str(root)]
            previous_umask = __import__('os').umask(0o022)
            try:
                with patch.object(sys, 'argv', argv), patch('install.platform.system', return_value='Darwin'), \
                     patch('install.shutil.which', return_value='/synthetic/tool'), \
                     patch('install.subprocess.check_output', side_effect=fake_check_output), \
                     patch('install.run', side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()):
                    install.main()
            finally: __import__('os').umask(previous_umask)
            self.assertEqual(binary.read_bytes(), artifact.read_bytes())
            self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
            self.assertEqual(next(root.glob('wx-before-build-*')).read_text(), 'old-binary')
            env = captured[0][1]['env']
            self.assertEqual(env['CARGO_HOME'], str(root.resolve() / 'cargo'))
            self.assertEqual(env['RUSTUP_HOME'], str(root.resolve() / 'rustup'))
            self.assertNotIn('sudo', captured[0][0])
            self.assertTrue((root / 'installation.json').exists())


if __name__ == '__main__': unittest.main()
