#!/usr/bin/env python3
"""Pinned macOS build, isolated Rust, no sudo or shell profile edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request

REPO = 'https://github.com/jackwener/wx-cli-again.git'
REVISION = '077a54cbfe679bda963cd038d8440422907fc797'


def reusable(binary):
    try:
        v = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=10)
        h = subprocess.run([str(binary), 'history', '--help'], capture_output=True, text=True, timeout=10)
        return bool(v.returncode == h.returncode == 0 and re.match(r'wx\s+\d+\.\d+\.\d+', v.stdout)
                    and all(x in h.stdout for x in ['--json', '--before', '--after', '--offset']))
    except (OSError, subprocess.SubprocessError): return False


def run(argv, **kwargs):
    subprocess.run([str(x) for x in argv], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description='构建已验证版本；复用已有可用 wx')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--build', action='store_true', help='明确要求重建，替换前备份旧二进制')
    p.add_argument('--prefix', type=Path, default=Path.home() / '.local')
    p.add_argument('--runtime-dir', type=Path, default=Path.home() / '.local/share/wx-cli-setup')
    a = p.parse_args()
    if platform.system() != 'Darwin': p.error('首版安装脚本仅支持 macOS')
    binary = a.prefix.expanduser().resolve() / 'bin/wx'
    existing = shutil.which('wx') or str(binary)
    reuse = not a.build and reusable(existing)
    plan = {'action': 'reuse' if reuse else 'build', 'binary': existing if reuse else str(binary),
            'repository': REPO, 'revision': REVISION, 'sudo': False, 'shell_profile_edits': False}
    if a.dry_run or reuse:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    if not shutil.which('git') or not shutil.which('xcrun'):
        p.error('需要 Git 与 Xcode Command Line Tools；请先在本机运行 xcode-select --install')
    os.umask(0o077)
    root = a.runtime_dir.expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
    source = root / 'source'
    if not source.exists():
        run(['git', 'clone', '--no-checkout', REPO, source])
        run(['git', '-C', source, 'checkout', '--detach', REVISION])
    else:
        remote = subprocess.check_output(['git', '-C', source, 'remote', 'get-url', 'origin'], text=True).strip()
        head = subprocess.check_output(['git', '-C', source, 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', source, 'status', '--porcelain', '--untracked-files=no'], text=True)
        if remote != REPO or head != REVISION or dirty:
            p.error('已有源码来源/提交不同或有改动；保留原目录，指定新的 --runtime-dir')
    env = os.environ.copy()
    env['CARGO_HOME'] = str(root / 'cargo'); env['RUSTUP_HOME'] = str(root / 'rustup')
    env['PATH'] = str(root / 'cargo/bin') + os.pathsep + env.get('PATH', '')
    cargo = root / 'cargo/bin/cargo'
    if not cargo.exists():
        target = {'arm64': 'aarch64-apple-darwin', 'x86_64': 'x86_64-apple-darwin'}.get(platform.machine())
        if not target: p.error('不支持的 Mac 架构')
        url = 'https://static.rust-lang.org/rustup/dist/' + target + '/rustup-init'
        body = urllib.request.urlopen(url, timeout=60).read()
        expected = urllib.request.urlopen(url + '.sha256', timeout=30).read().decode().split()[0]
        if hashlib.sha256(body).hexdigest() != expected: raise RuntimeError('rustup checksum mismatch')
        installer = root / 'rustup-init'; installer.write_bytes(body); installer.chmod(0o700)
        run([installer, '-y', '--profile', 'minimal', '--no-modify-path'], env=env)
    run([cargo, 'build', '--release', '--locked'], cwd=source, env=env)
    artifact = source / 'target/release/wx'
    if not reusable(artifact): raise RuntimeError('built binary capability check failed')
    binary.parent.mkdir(parents=True, exist_ok=True)
    if binary.exists():
        from datetime import datetime
        backup = root / ('wx-before-build-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(binary, backup)
    with tempfile.NamedTemporaryFile(dir=binary.parent, delete=False) as f: staged = Path(f.name)
    try:
        shutil.copy2(artifact, staged); staged.chmod(0o755); staged.replace(binary)
    finally: staged.unlink(missing_ok=True)
    plan['version'] = subprocess.check_output([binary, '--version'], text=True).strip()
    plan['sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    (root / 'installation.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
