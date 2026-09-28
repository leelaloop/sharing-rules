"""Runnable scenario — prints a holdings-vs-visibility matrix.

    python3 -m sharing_rules.demo

Four instances A, B, C, D. A has handshakes with B and C; D is untrusted. A
creates records under each scope x mode. The matrix shows, per instance:

    origin  = created here
    copy    = a duplicate PHYSICALLY held here  (subpoena reaches it)
    ref     = readable by reference from the origin (nothing held here)
    ·       = cannot see it
"""
try:
    from .core import Network, SharingRule
except ImportError:  # run as a plain script, not a package
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sharing_rules.core import Network, SharingRule

CELL = {'origin': 'origin', 'copy': 'COPY', 'reference': 'ref', None: '·'}
INSTANCES = ['A', 'B', 'C', 'D']

# scope, mode, allow, and a human label
RECORDS = [
    ('priv_ref',  'private',   'reference', (),    'private / reference'),
    ('hs_ref',    'handshake', 'reference', (),    'handshake / reference'),
    ('hs_dup',    'handshake', 'duplicate', (),    'handshake / DUPLICATE'),
    ('allow_dup', 'allowlist', 'duplicate', ('C',),'allowlist{C} / DUPLICATE'),
    ('pub_ref',   'public',    'reference', (),    'public / reference'),
    ('pub_dup',   'public',    'duplicate', (),    'public / DUPLICATE'),
]


def build():
    net = Network()
    for i in INSTANCES:
        net.add_instance(i)
    net.add_handshake('A', 'B')
    net.add_handshake('A', 'C')          # D stays untrusted
    for rid, scope, mode, allow, _ in RECORDS:
        net.add_record(rid, origin='A', payload={'note': rid},
                       rule=SharingRule.of(scope, mode, allow))
    return net


def matrix(net, title):
    seen = {i: net.visible_to(i) for i in INSTANCES}
    print(f'\n{title}')
    print('  record'.ljust(28) + ''.join(i.center(9) for i in INSTANCES))
    print('  ' + '-' * (26 + 9 * len(INSTANCES)))
    for rid, _, _, _, label in RECORDS:
        row = '  ' + label.ljust(26)
        for i in INSTANCES:
            row += CELL[seen[i].get(rid)].center(9)
        print(row)
    # subpoena view: what each operator physically holds
    print('\n  subpoena exposure — records a subpoena to each operator could compel:')
    for i in INSTANCES:
        held = net.holdings(i)
        items = ', '.join(f'{r}({k})' for r, k in sorted(held.items())) or '(nothing)'
        print(f'    {i}: {items}')


def main():
    net = build()
    matrix(net, 'INITIAL — A shares to its trusted instances (B, C); D untrusted')

    print('\n' + '=' * 70)
    print('Now A revokes its handshake with B, then unshares the public records.')
    net.remove_handshake('A', 'B')
    net.unshare('pub_ref')
    net.unshare('pub_dup')
    matrix(net, 'AFTER REVOCATION (no purge yet)')
    print('\n  → Note B: the handshake/reference record vanished immediately, but')
    print('    the DUPLICATE copies (hs_dup, pub_dup) still sit in B — a copy')
    print("    cannot be recalled. They remain subpoena-reachable at B.")

    removed = net.purge_duplicates()
    matrix(net, f'AFTER purge_duplicates()  (best-effort recall removed {removed} copies)')
    print("\n  → Only now are the stranded copies gone — and in the real world a")
    print("    purge request is not guaranteed to succeed. That gap is the whole")
    print("    reason 'reference' and 'duplicate' are different legal postures.")


if __name__ == '__main__':
    main()
