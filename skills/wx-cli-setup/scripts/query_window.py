#!/usr/bin/env python3
"""Authorized bounded history query. Freezes bounds and preserves coverage warnings."""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
from wx_common import WxClient, WxError, account_match, cli_common, output


def resolve_chat(client, query):
    if query.endswith('@chatroom') or query.startswith('wxid_') or query == 'filehelper': return query
    found = {}
    contacts = client.run('contacts', '--query', query, '--json', '-n', '1000')
    contacts = contacts if isinstance(contacts, list) else contacts.get('contacts', [])
    for c in contacts:
        if c.get('username'): found[c['username']] = c.get('display', '')
    sessions = client.run('sessions', '--json', '-n', '10000')
    rows = sessions.get('sessions', [])
    for s in rows:
        if query.casefold().strip() in s.get('chat', '').casefold().strip():
            found[s['username']] = s.get('chat', '')
    exact = {k: v for k, v in found.items()
             if k == query or v.casefold().strip() == query.casefold().strip()}
    chosen = exact or found
    if len(chosen) == 1: return next(iter(chosen))
    if len(chosen) > 1: raise WxError('ambiguous_chat_choose_exact_id')
    if len(contacts) >= 1000 or len(rows) >= 10000:
        raise WxError('chat_lookup_truncated_supply_exact_id')
    raise WxError('chat_not_in_local_contacts_or_sessions')


def parse_time(value, zone):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        a, b = dt.replace(tzinfo=zone, fold=0), dt.replace(tzinfo=zone, fold=1)
        if a.timestamp() != b.timestamp():
            raise ValueError('ambiguous_or_nonexistent_local_time_use_explicit_offset')
        dt = a
    return int(dt.timestamp())


def query_window(client, chat, start, end, page_size=500, max_messages=10000):
    if start >= end or page_size <= 0 or max_messages <= 0: raise WxError('invalid_time_window_or_limit')
    username = resolve_chat(client, chat)
    messages, offset, statuses, unknown = [], 0, set(), set()
    freshness = {}
    truncated = False
    while True:
        count = min(page_size, max_messages - len(messages))
        # --before is newer-than; --after is older-than. [start,end) in Unix seconds.
        data = client.run('history', username, '--before', str(start - 1), '--after', str(end),
                          '--offset', str(offset), '-n', str(count), '--json', '--with-meta')
        batch, meta = data.get('messages', []), data.get('meta', {})
        statuses.add(meta.get('status', 'unreported'))
        unknown.update(meta.get('unknown_shards', []))
        for k in ('chat_latest_timestamp', 'session_last_timestamp'):
            if meta.get(k) is not None: freshness[k] = meta[k]
        for m in batch:
            ts = m.get('timestamp')
            if not isinstance(ts, int) or not start <= ts < end: raise WxError('out_of_window_response')
            # IDs are local to shards. Identical rows may be separate real messages.
            messages.append(m)
        offset += len(batch)
        if len(batch) < count: break
        if len(messages) >= max_messages or offset >= max_messages:
            truncated = True; break
    messages.sort(key=lambda m: (m['timestamp'], m.get('local_id', 0)))
    warnings = []
    if unknown: warnings.append('unknown_message_shards')
    if statuses - {'ok', 'windowed'}: warnings.append('source_reports_possible_incompleteness')
    if truncated: warnings.append('message_limit_reached')
    if not messages: warnings.append('no_local_messages_not_proof_of_no_group_activity')
    return {'chat_id': username, 'window': {'start_unix': start, 'end_unix_exclusive': end},
            'count': len(messages), 'messages': messages,
            'coverage': {'scope': 'local_synced_data_only', 'statuses': sorted(statuses),
                         'unknown_shards': sorted(unknown), 'truncated': truncated,
                         'warnings': warnings, **freshness}}


def main():
    p = argparse.ArgumentParser(description='读取用户授权的聊天时间窗口')
    cli_common(p)
    p.add_argument('--chat', required=True)
    p.add_argument('--minutes', type=int)
    p.add_argument('--since', help='ISO 日期时间，与 --until 一起使用')
    p.add_argument('--until', help='ISO 日期时间，结束边界不包含')
    p.add_argument('--timezone', help='IANA 时区；默认系统当地时区')
    p.add_argument('--max-messages', type=int, default=10000)
    a = p.parse_args()
    try:
        zone = ZoneInfo(a.timezone) if a.timezone else None
        if a.since or a.until:
            if not (a.since and a.until) or a.minutes is not None:
                p.error('--since 和 --until 必须成对，不能同时使用 --minutes')
            start, end = parse_time(a.since, zone), parse_time(a.until, zone)
        else:
            minutes = a.minutes if a.minutes is not None else 60
            if minutes <= 0: p.error('--minutes 必须大于 0')
            end = int(datetime.now().timestamp()); start = end - minutes * 60
        client = WxClient(a.wx, a.state_dir)
        match = account_match(client)
        if match == 'mismatch_or_multiple_active_accounts': raise WxError('select_active_account_before_query')
        data = query_window(client, a.chat, start, end, max_messages=a.max_messages)
        data['account_match'] = match
        data['window']['start'] = datetime.fromtimestamp(start, zone).astimezone(zone).isoformat()
        data['window']['end_exclusive'] = datetime.fromtimestamp(end, zone).astimezone(zone).isoformat()
        output(data)
    except (WxError, ValueError, KeyError) as e:
        output({'error': e.code if isinstance(e, WxError) else 'invalid_time_or_timezone'})
        return 2
    return 0


if __name__ == '__main__': raise SystemExit(main())
