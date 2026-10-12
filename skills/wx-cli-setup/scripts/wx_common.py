"""Standard-library bridge; never extracts keys or changes permissions."""
import json
from pathlib import Path
import shutil
import subprocess


class WxError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class WxClient:
    def __init__(self, wx=None, state_dir=None):
        self.binary = wx or shutil.which('wx') or str(Path.home() / '.local/bin/wx')
        self.state_dir = Path(state_dir or Path.home() / '.wx-cli').expanduser().resolve()

    def run(self, *args, json_output=True):
        if not self.state_dir.is_dir():
            raise WxError('state_directory_missing')
        try:
            r = subprocess.run([self.binary, *args], cwd=self.state_dir,
                               capture_output=True, text=True, timeout=45)
        except FileNotFoundError:
            raise WxError('wx_not_found')
        except (subprocess.TimeoutExpired, OSError):
            raise WxError('command_unavailable_or_timed_out')
        if r.returncode:
            err = r.stderr.lower()
            code = 'command_failed'
            if '解密' in err or 'decrypt' in err: code = 'database_unavailable'
            elif '找不到' in err or 'not found' in err: code = 'query_source_unavailable'
            # Do not echo raw stderr: it can include private paths or content.
            raise WxError(code)
        if not json_output: return r.stdout.strip()
        try: return json.loads(r.stdout)
        except ValueError: raise WxError('invalid_json_response')


def account_match(client):
    """Return a state, without account IDs or filesystem paths."""
    try:
        cfg = json.loads((client.state_dir / 'config.json').read_text())
        configured = Path(cfg['db_dir']).expanduser().resolve()
        ps = subprocess.run(['/bin/ps', '-axo', 'pid=,comm='], capture_output=True,
                            text=True, timeout=10, check=True)
        pids = []
        for line in ps.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and Path(parts[1]).name == 'WeChat': pids.append(parts[0])
        if not pids: return 'wechat_not_running'
        opened = set()
        for pid in pids:
            r = subprocess.run(['/usr/sbin/lsof', '-p', pid, '-Fn'], capture_output=True,
                               text=True, timeout=15)
            for line in r.stdout.splitlines():
                if line.startswith('n') and '/xwechat_files/' in line and '/db_storage/' in line:
                    opened.add(Path(line[1:].split('/db_storage/')[0] + '/db_storage').resolve())
        if not opened: return 'unverifiable'
        return 'matched' if opened == {configured} else 'mismatch_or_multiple_active_accounts'
    except (ValueError, KeyError, OSError, subprocess.SubprocessError):
        return 'unverifiable'


def permission_state(path, mode):
    try: return 'ok' if path.stat().st_mode & 0o777 == mode else 'needs_review'
    except OSError: return 'missing'


def cli_common(parser):
    parser.add_argument('--wx', help='wx 可执行文件绝对路径')
    parser.add_argument('--state-dir', help='配置工作目录，默认 ~/.wx-cli')


def output(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))
