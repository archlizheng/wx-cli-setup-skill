#!/usr/bin/env python3
"""Status-only diagnostics: no keys, account paths, or message bodies."""
import argparse
from wx_common import WxClient, WxError, account_match, cli_common, output, permission_state


def diagnose(client, match_fn=account_match):
    report = {'account': match_fn(client), 'checks': [], 'queries': {}, 'content_included': False}
    report['permissions'] = {
        'state_directory': permission_state(client.state_dir, 0o700),
        'config': permission_state(client.state_dir / 'config.json', 0o600),
        'keys': permission_state(client.state_dir / 'all_keys.json', 0o600),
    }
    try:
        report['version'] = client.run('--version', json_output=False)
        doctor = client.run('doctor', '--json')
        report['checks'] = [{'name': c.get('name'), 'ok': bool(c.get('ok'))}
                            for c in doctor.get('checks', [])]
    except WxError as e:
        report['error'] = e.code
        return report
    if report['account'] == 'mismatch_or_multiple_active_accounts':
        report['error'] = 'select_active_account_before_query'
        return report
    for command in ['sessions', 'contacts']:
        try:
            data = client.run(command, '--json', '-n', '1')
            meta = data.get('meta', {}) if isinstance(data, dict) else {}
            report['queries'][command] = {'ok': True, 'status': meta.get('status'),
                                         'unknown_shards': len(meta.get('unknown_shards', []))}
        except WxError as e:
            report['queries'][command] = {'ok': False, 'error': e.code}
    report['basic_queries_available'] = all(x.get('ok') for x in report['queries'].values())
    return report


def main():
    p = argparse.ArgumentParser(description='只输出状态的本机微信诊断')
    cli_common(p)
    a = p.parse_args()
    report = diagnose(WxClient(a.wx, a.state_dir))
    output(report)
    return 0 if report.get('basic_queries_available') else 2


if __name__ == '__main__': raise SystemExit(main())
