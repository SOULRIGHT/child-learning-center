"""Setup status에 기존 endpoint href만 붙인다. 새 form/계산은 하지 않는다."""
from __future__ import annotations

from flask import url_for


def attach_setup_hrefs(status):
    presented = {
        'sections': [_with_hrefs(item) for item in status.get('sections') or ()],
        'next': None,
    }
    nxt = status.get('next')
    if nxt is not None:
        presented['next'] = dict(nxt)
        presented['next']['href'] = url_for(nxt['destination'])
    return presented


def _with_hrefs(item):
    row = dict(item)
    row['href'] = url_for(item['destination'])
    extras = []
    for extra in item.get('extra_actions') or ():
        action = dict(extra)
        action['href'] = url_for(extra['destination'])
        extras.append(action)
    row['extra_actions'] = extras
    return row
