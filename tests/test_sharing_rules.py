"""sharing_rules — scope, mode, holdings, and the legal-process distinction.

Pure stdlib. Run: python3 tests/test_sharing_rules.py
Asserts the model behaves the way the federation + legal-process design needs:
scope decides WHO, mode decides whether a viewing instance HOLDS a copy (and is
thus subpoena-reachable) or merely sees a reference, and a copy cannot be
recalled by revocation alone.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sharing_rules import Mode, Network, Scope, SharingRule  # noqa: E402

fails = []


def check(label, cond, extra=''):
    print(('  ok  ' if cond else '  FAIL') + '  ' + label
          + (f'  → {extra}' if not cond and extra != '' else ''))
    if not cond:
        fails.append(label)


def fresh(handshakes=(('A', 'B'), ('A', 'C'))):
    net = Network()
    for i in ('A', 'B', 'C', 'D'):
        net.add_instance(i)
    for a, b in handshakes:
        net.add_handshake(a, b)
    return net


R = SharingRule.of  # (scope, mode, allow=())

print('── scope decides WHO can see a record ──')
net = fresh()
net.add_record('priv', 'A', 1, R('private', 'reference'))
net.add_record('hs', 'A', 1, R('handshake', 'reference'))
net.add_record('allow', 'A', 1, R('allowlist', 'reference', ('C',)))
net.add_record('pub', 'A', 1, R('public', 'reference'))
check('private reaches only the origin',
      net.can_read('A', 'priv') and not any(net.can_read(i, 'priv') for i in 'BCD'))
check('handshake reaches trusted B and C, never untrusted D',
      net.can_read('B', 'hs') and net.can_read('C', 'hs') and not net.can_read('D', 'hs'))
check('allowlist reaches exactly the listed instance (C only)',
      net.can_read('C', 'allow') and not net.can_read('B', 'allow')
      and not net.can_read('D', 'allow'))
check('public reaches everyone', all(net.can_read(i, 'pub') for i in 'ABCD'))

print('\n── mode decides whether a viewer HOLDS a copy (the subpoena crux) ──')
net = fresh()
net.add_record('ref', 'A', 1, R('handshake', 'reference'))
net.add_record('dup', 'A', 1, R('handshake', 'duplicate'))
check('reference: B can READ it', net.can_read('B', 'ref'))
check('reference: B holds NOTHING (subpoena to B misses it)',
      'ref' not in net.subpoena_exposure('B'))
check('reference: only the origin A holds it',
      net.holdings('A').get('ref') == 'origin')
check('duplicate: B can read it', net.can_read('B', 'dup'))
check('duplicate: B PHYSICALLY holds a copy (subpoena to B reaches it)',
      net.subpoena_exposure('B').get('dup') == 'copy')
check('duplicate: the copy is marked as a copy, origin keeps the original',
      net.instances['B'].copies['dup'].is_copy is True
      and net.holdings('A').get('dup') == 'origin')

print('\n── a new handshake lets existing DUPLICATE shares flow to the new peer ──')
net = fresh(handshakes=(('A', 'B'),))          # C not yet trusted
net.add_record('dup', 'A', 1, R('handshake', 'duplicate'))
check('C has no copy before the handshake', 'dup' not in net.holdings('C'))
net.add_handshake('A', 'C')
check('C receives the copy once handshaked', net.holdings('C').get('dup') == 'copy')

print('\n── revocation: reference is immediate; a copy LINGERS until purged ──')
net = fresh()
net.add_record('ref', 'A', 1, R('handshake', 'reference'))
net.add_record('dup', 'A', 1, R('handshake', 'duplicate'))
net.remove_handshake('A', 'B')
check('reference access to B disappears immediately on revocation',
      not net.can_read('B', 'ref'))
check('the duplicate copy still sits in B after revocation (cannot be recalled)',
      net.subpoena_exposure('B').get('dup') == 'copy')
check('C, still handshaked, keeps both',
      net.can_read('C', 'ref') and net.holdings('C').get('dup') == 'copy')
removed = net.purge_duplicates()
check('purge_duplicates removes exactly the now-disallowed copy (B only)',
      removed == 1 and 'dup' not in net.holdings('B')
      and net.holdings('C').get('dup') == 'copy')

print('\n── unshare: reference vanishes everywhere; duplicates need a purge ──')
net = fresh()
net.add_record('ref', 'A', 1, R('public', 'reference'))
net.add_record('dup', 'A', 1, R('public', 'duplicate'))
net.unshare('ref')
net.unshare('dup')
check('unshared reference is unreadable everywhere at once',
      not any(net.can_read(i, 'ref') for i in 'BCD'))
check('unshared duplicate copies persist until purged',
      all(net.subpoena_exposure(i).get('dup') == 'copy' for i in 'BCD'))
n = net.purge_duplicates('dup')
check('purge clears all stray duplicate copies',
      n == 3 and not any('dup' in net.holdings(i) for i in 'BCD'))
check('origin A still holds both after unsharing (origin never loses its own)',
      net.holdings('A').get('ref') == 'origin' and net.holdings('A').get('dup') == 'origin')

print('\n── subpoena_exposure returns ONLY physically-held records ──')
net = fresh()
net.add_record('ref', 'A', 1, R('public', 'reference'))
net.add_record('dup', 'A', 1, R('public', 'duplicate'))
exp_b = net.subpoena_exposure('B')
check('B is exposed to the duplicate but NOT the reference it can read',
      exp_b.get('dup') == 'copy' and 'ref' not in exp_b and net.can_read('B', 'ref'))
check('holdings and subpoena_exposure are the same view',
      net.subpoena_exposure('B') == net.holdings('B'))

print()
if fails:
    print(f'FAILED ({len(fails)}): ' + ', '.join(fails))
    raise SystemExit(1)
print('all sharing-rules checks passed')
