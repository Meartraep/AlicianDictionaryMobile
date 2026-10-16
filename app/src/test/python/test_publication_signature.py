# -*- coding: utf-8 -*-
"""The device signature is what makes a leaked GitHub token useless.

The tests sign exactly like the phone does (ECDSA P-256 / SHA-256, DER signature,
base64) and check that CI accepts only a publication signed by the registered key
over the message that describes this very publication.
"""
from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa  # noqa: E402

import verify_publication_signature as signature  # noqa: E402
import verify_published_database as verify  # noqa: E402

PREVIOUS = {
    'db_version': 1,
    'sha1': '5f5cb1389bae746327ce385b2f5b7d6c010aff82',
    'size': 2854912,
    'published_at': '2026-10-14',
    'notes': '上一个版本',
}
ENTRY = {
    'db_version': 2,
    'sha1': 'c98419801d2c1e9d6f6c4a4f4d3b0f1e2a3b4c5d',
    'size': 2859008,
    'published_at': '2026-10-17',
    'notes': '手机端发布',
}


def pem_of(key) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')


def sign(key, message: str) -> str:
    return base64.b64encode(
        key.sign(message.encode('utf-8'), ec.ECDSA(hashes.SHA256()))).decode('ascii')


def document(key, message: str, **overrides) -> dict:
    payload = {
        'algorithm': signature.ALGORITHM,
        'key_id': signature.key_id(pem_of(key)),
        'signature': sign(key, message),
    }
    payload.update(overrides)
    return payload


class PublicationSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.other_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key_pem = pem_of(self.key)
        self.message = signature.build_message(PREVIOUS, ENTRY)

    def check(self, public_key_pem=None, document_value=None, previous=None, entry=None):
        return signature.check_publication_signature(
            self.public_key_pem if public_key_pem is None else public_key_pem,
            document(self.key, self.message) if document_value is None else document_value,
            PREVIOUS if previous is None else previous,
            ENTRY if entry is None else entry,
        )

    # ---- contract -------------------------------------------------------
    def test_message_format_is_frozen(self) -> None:
        self.assertEqual(self.message, (
            'alician-db-publish-v1\n'
            'prev_version=1\n'
            'prev_sha1=5f5cb1389bae746327ce385b2f5b7d6c010aff82\n'
            'version=2\n'
            'sha1=c98419801d2c1e9d6f6c4a4f4d3b0f1e2a3b4c5d\n'
            'size=2859008\n'
            'published_at=2026-10-17\n'
            'notes_sha256=' + signature.notes_digest(ENTRY['notes']) + '\n'))

    def test_key_id_is_stable_and_short(self) -> None:
        first = signature.key_id(self.public_key_pem)
        self.assertEqual(first, signature.key_id(self.public_key_pem))
        self.assertEqual(len(first), 16)
        self.assertNotEqual(first, signature.key_id(pem_of(self.other_key)))

    # ---- accepted -------------------------------------------------------
    def test_signature_from_the_registered_key_is_accepted(self) -> None:
        self.assertEqual(self.check(), [])

    # ---- refused --------------------------------------------------------
    def test_signature_from_another_key_is_refused(self) -> None:
        problems = self.check(document_value=document(self.other_key, self.message))
        self.assertIn('与 main 上登记的公钥', ' '.join(problems))

    def test_signature_over_other_content_is_refused(self) -> None:
        tampered = dict(ENTRY, sha1='a' * 40)
        problems = self.check(entry=tampered)
        self.assertIn('签名校验失败', ' '.join(problems))

    def test_replay_of_an_earlier_publication_is_refused(self) -> None:
        # A signature made when v1 was the tip must not authorise a later publication.
        old_document = document(self.key, signature.build_message(PREVIOUS, ENTRY))
        later_previous = dict(PREVIOUS, db_version=2, sha1=ENTRY['sha1'])
        problems = self.check(document_value=old_document, previous=later_previous)
        self.assertIn('签名校验失败', ' '.join(problems))

    def test_release_note_is_bound_to_the_signature(self) -> None:
        problems = self.check(entry=dict(ENTRY, notes='被改写的说明'))
        self.assertIn('签名校验失败', ' '.join(problems))

    def test_tampered_signature_is_refused(self) -> None:
        raw = bytearray(base64.b64decode(document(self.key, self.message)['signature']))
        raw[-1] ^= 0x01
        problems = self.check(document_value=document(
            self.key, self.message, signature=base64.b64encode(bytes(raw)).decode('ascii')))
        self.assertIn('签名校验失败', ' '.join(problems))

    def test_unpadded_or_broken_base64_is_refused(self) -> None:
        problems = self.check(document_value=document(
            self.key, self.message, signature='not base64 ***'))
        self.assertIn('base64', ' '.join(problems))

    def test_wrong_algorithm_is_refused(self) -> None:
        problems = self.check(document_value=document(
            self.key, self.message, algorithm='RSA-PKCS1'))
        self.assertIn('签名算法', ' '.join(problems))

    def test_missing_public_key_explains_the_setup(self) -> None:
        problems = self.check(public_key_pem='')
        self.assertIn('没有登记发布公钥', ' '.join(problems))

    def test_missing_signature_is_refused(self) -> None:
        problems = signature.check_publication_signature(
            self.public_key_pem, None, PREVIOUS, ENTRY)
        self.assertIn(signature.SIGNATURE_PATH, ' '.join(problems))

    def test_non_ec_key_is_refused(self) -> None:
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = rsa_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode('utf-8')
        # key_id matches the registered key, so the check reaches the key type itself.
        problems = signature.check_publication_signature(
            pem,
            {'algorithm': signature.ALGORITHM, 'key_id': signature.key_id(pem),
             'signature': sign(self.key, self.message)},
            PREVIOUS, ENTRY)
        self.assertIn('不是 EC 公钥', ' '.join(problems))

    def test_other_curves_are_refused(self) -> None:
        secp384 = ec.generate_private_key(ec.SECP384R1())
        pem = pem_of(secp384)
        problems = signature.check_publication_signature(
            pem,
            {'algorithm': signature.ALGORITHM, 'key_id': signature.key_id(pem),
             'signature': sign(self.key, self.message)},
            PREVIOUS, ENTRY)
        self.assertIn('P-256', ' '.join(problems))

    # ---- allowlist ------------------------------------------------------
    def test_signature_file_may_change_but_the_public_key_may_not(self) -> None:
        self.assertEqual(verify.check_allowlist([
            'app/src/main/assets/translated.db',
            'database-versions.json',
            'database-manifest.json',
            signature.SIGNATURE_PATH,
        ]), [])
        violations = verify.check_allowlist(['.github/db-publish-pubkey.pem'])
        self.assertEqual(violations, ['.github/db-publish-pubkey.pem'])


if __name__ == '__main__':
    unittest.main()
