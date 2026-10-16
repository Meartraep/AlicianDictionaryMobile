# -*- coding: utf-8 -*-
"""Keep the "required status checks" rule of the main ruleset in sync.

The GitHub ruleset UI does not always offer the job in its picker (the list comes
from recently executed checks and is cached), so this sets it through the API.

Usage:
    python scripts/github_ruleset_required_check.py --status
    python scripts/github_ruleset_required_check.py --add
    python scripts/github_ruleset_required_check.py --remove
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPOSITORY = 'Meartraep/AlicianDictionaryMobile'
CONTEXT = 'Ledger, manifest and database agree'
DEFAULT_BRANCH_PATTERN = '~DEFAULT_BRANCH'


def gh(*args: str, body: str | None = None) -> str:
    result = subprocess.run(['gh', *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', input=body)
    if result.returncode != 0:
        raise SystemExit('gh %s failed:\n%s%s' % (' '.join(args), result.stdout, result.stderr))
    return result.stdout


def main_ruleset() -> dict:
    rulesets = json.loads(gh('api', 'repos/%s/rulesets' % REPOSITORY))
    for ruleset in rulesets:
        if ruleset['target'] != 'branch':
            continue
        detail = json.loads(gh('api', 'repos/%s/rulesets/%d' % (REPOSITORY, ruleset['id'])))
        include = detail.get('conditions', {}).get('ref_name', {}).get('include') or []
        if DEFAULT_BRANCH_PATTERN in include:
            return detail
    raise SystemExit('no active ruleset targets the default branch')


def save(ruleset: dict, rules: list) -> dict:
    body = json.dumps({'rules': rules}, ensure_ascii=False)
    gh('api', '--method', 'PUT',
       'repos/%s/rulesets/%d' % (REPOSITORY, ruleset['id']), '--input', '-', body=body)
    return json.loads(gh('api', 'repos/%s/rulesets/%d' % (REPOSITORY, ruleset['id'])))


def describe(ruleset: dict) -> None:
    print('ruleset %d (%s), enforcement=%s, include=%s'
          % (ruleset['id'], ruleset['name'], ruleset['enforcement'],
             ruleset['conditions']['ref_name']['include']))
    print('rules:', ', '.join(rule['type'] for rule in ruleset['rules']))
    checks = [rule for rule in ruleset['rules'] if rule['type'] == 'required_status_checks']
    if not checks:
        print('required checks: (none)')
        return
    parameters = checks[0]['parameters']
    for item in parameters['required_status_checks']:
        print('required check : %s' % item['context'])
    print('strict (branch must be up to date): %s'
          % parameters.get('strict_required_status_checks_policy'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--status', action='store_true', help='show the current configuration')
    group.add_argument('--add', action='store_true', help='require %s' % CONTEXT)
    group.add_argument('--remove', action='store_true', help='stop requiring it')
    args = parser.parse_args()

    ruleset = main_ruleset()
    rules = [rule for rule in ruleset['rules'] if rule['type'] != 'required_status_checks']

    if args.status:
        describe(ruleset)
        return 0

    if args.remove:
        describe(save(ruleset, rules))
        return 0

    rules.append({
        'type': 'required_status_checks',
        'parameters': {
            'required_status_checks': [{'context': CONTEXT}],
            'strict_required_status_checks_policy': False,
            'do_not_enforce_on_create': False,
        },
    })
    describe(save(ruleset, rules))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
