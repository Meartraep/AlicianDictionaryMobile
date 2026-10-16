# -*- coding: utf-8 -*-
"""Signing scheme that lets the phone prove a publication came from its device key.

The pull request carries a signature made by a non-exportable Android Keystore key.
CI verifies it against the public key that is registered on the target branch, so a
stolen GitHub token alone cannot publish anything: the attacker cannot forge a
signature, and cannot register a key of their own without a reviewed change to a
protected file.

The signed message binds the publication to the repository state it was built on
(previous version and sha1) and to the exact bytes being published, which makes an
old signed payload useless as a replay.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

PUBLIC_KEY_PATH = '.github/db-publish-pubkey.pem'
SIGNATURE_PATH = 'database-publish-signature.json'
ALGORITHM = 'ECDSA-P256-SHA256'
MESSAGE_HEADER = 'alician-db-publish-v1'


def notes_digest(notes: str) -> str:
    return hashlib.sha256(str(notes).encode('utf-8')).hexdigest()


def build_message(previous: Dict[str, Any], entry: Dict[str, Any]) -> str:
    """The exact bytes the phone signs (keep in sync with PublishLogic.buildSignatureMessage)."""
    lines = [
        MESSAGE_HEADER,
        'prev_version=%d' % int(previous['db_version']),
        'prev_sha1=%s' % str(previous['sha1']).lower(),
        'version=%d' % int(entry['db_version']),
        'sha1=%s' % str(entry['sha1']).lower(),
        'size=%d' % int(entry['size']),
        'published_at=%s' % entry['published_at'],
        'notes_sha256=%s' % notes_digest(entry.get('notes', '')),
    ]
    return '\n'.join(lines) + '\n'


def key_id(public_key_pem: str) -> str:
    """Stable fingerprint of a registered key, shown in the app and in the commit."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
    der = key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def load_signature(path: Path) -> Dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('发布签名文件必须是 JSON 对象')
    return document


def verify_signature(public_key_pem: str, message: str, signature_base64: str) -> Optional[str]:
    """Returns None when the signature is valid, otherwise the reason it is not."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    try:
        key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
    except (ValueError, TypeError) as error:
        return '登记的发布公钥无法解析：%s' % error
    if not isinstance(key, ec.EllipticCurvePublicKey):
        return '登记的发布公钥不是 EC 公钥'
    if not isinstance(key.curve, ec.SECP256R1):
        return '登记的发布公钥不是 P-256 曲线'

    try:
        signature = base64.b64decode(signature_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        return '签名不是合法的 base64：%s' % error

    try:
        key.verify(signature, message.encode('utf-8'), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return '签名校验失败：内容或签名不匹配'
    except (ValueError, TypeError) as error:
        return '签名格式无法解析：%s' % error
    return None


def check_publication_signature(
    public_key_pem: Optional[str],
    signature_document: Optional[Dict[str, Any]],
    previous: Dict[str, Any],
    entry: Dict[str, Any],
) -> list:
    """Every reason the signature fails, empty when the publication is authenticated."""
    problems = []
    if not public_key_pem:
        problems.append(
            'main 上没有登记发布公钥（%s）。请先在 App 里生成签名密钥并复制公钥，'
            '然后用一个普通 PR 把它提交到 main。' % PUBLIC_KEY_PATH)
        return problems
    if signature_document is None:
        problems.append(
            '发布提交里没有 %s。手机端需要用签名密钥对本次发布签名。' % SIGNATURE_PATH)
        return problems

    algorithm = str(signature_document.get('algorithm') or '')
    if algorithm != ALGORITHM:
        problems.append('签名算法必须是 %s，实际为 %r' % (ALGORITHM, algorithm))
        return problems

    expected_key_id = key_id(public_key_pem)
    actual_key_id = str(signature_document.get('key_id') or '')
    if actual_key_id != expected_key_id:
        problems.append(
            '签名使用的密钥（%s）与 main 上登记的公钥（%s）不一致；'
            '请确认用的是同一台手机的密钥' % (actual_key_id or '未知', expected_key_id))
        return problems

    signature = str(signature_document.get('signature') or '')
    if not signature:
        problems.append('签名内容为空')
        return problems

    message = build_message(previous, entry)
    reason = verify_signature(public_key_pem, message, signature)
    if reason:
        problems.append(reason)
    return problems
