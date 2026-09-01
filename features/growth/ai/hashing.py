"""Canonical Evidence Packet / runtime signature hashing."""
from __future__ import annotations

import hashlib
import json


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def packet_hash(packet) -> str:
    return sha256_hex(canonical_json(packet))


def runtime_signature(parts) -> str:
    return sha256_hex(canonical_json(parts))
