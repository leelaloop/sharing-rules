# sharing-rules

**Where does a shared record physically live?** In a federated network the answer
decides who can be compelled to hand it over, who can take it back, and who has to
protect it. Most federation protocols leave it implicit. This library makes it a
queryable fact.

Every shared record carries a **rule** made of two parts:

| | Question it answers | Values |
|---|---|---|
| **scope** | Who may see it? | `private` · `handshake` (instances with mutual trust) · `allowlist` · `public` |
| **mode** | How does it reach them? | `reference` (stays on its origin, read live) · `duplicate` (a copy lands on the viewer) |

Then one query, `Network.holdings(instance)`, returns exactly what an operator
stores. That is also the set that legal process served on that operator can reach.

## Why mode matters

| Mode | On the viewer's server | After the owner revokes | Reachable at the viewer |
|---|---|---|---|
| reference | nothing | access ends immediately | nothing |
| duplicate | a full copy | the copy stays until a best-effort purge | the copy |

A copy cannot be recalled. The model refuses to pretend otherwise:
`remove_handshake` and `unshare` leave delivered copies in place. Only
`purge_duplicates()` removes them, and in a real network a purge request can fail.

## Try it

```sh
python3 -m sharing_rules.demo        # prints a holdings-vs-visibility matrix
python3 tests/test_sharing_rules.py  # the checks that pin the model's behaviour
```

```
INITIAL — A shares to its trusted instances (B, C); D untrusted
  record                        A        B        C        D
  handshake / reference       origin    ref      ref       ·
  handshake / DUPLICATE       origin    COPY     COPY      ·
  public / reference          origin    ref      ref      ref
  public / DUPLICATE          origin    COPY     COPY     COPY

  subpoena exposure — records a subpoena to each operator could compel:
    B: hs_dup(copy), pub_dup(copy)
    D: pub_dup(copy)
```

```python
from sharing_rules import Network, SharingRule

net = Network()
net.add_handshake('garden-coop', 'city-map')
net.add_record('seed-library', origin='garden-coop', payload={'name': 'Seed library'},
               rule=SharingRule.of('handshake', 'reference'))

net.can_read('city-map', 'seed-library')   # True: resolved live from the origin
net.holdings('city-map')                   # {}: nothing stored on city-map
```

## Status

This is a **reference model**: pure standard library, in memory, no network code.
It exists to pin down the semantics before they're wired into real systems. The
planned work:

- a serialisable rule format that can travel with a record (for example as an
  ActivityPub extension);
- an origin-side resolver for references;
- a purge protocol with acknowledgements;
- a holdings report that generates a plain-language disclosure statement for an
  operator's users;
- integration with [LeelaMaps](https://leelamaps.com), a community map for local
  notes, events and fundraisers.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
