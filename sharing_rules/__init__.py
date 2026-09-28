"""sharing_rules — make "who physically holds this record?" a queryable fact.

Federated instances share records under a rule of *scope* (who may see it) and
*mode* (reference: origin-held, or duplicate: a copy lands on the viewer). The
payoff query is ``Network.holdings(instance)``: exactly what an operator stores,
and therefore what legal process served on that operator can reach.

See core.py for the model. Pure standard library; no network, no database.
"""
from .core import Instance, Mode, Network, Record, Scope, SharingRule

__all__ = ['Instance', 'Mode', 'Network', 'Record', 'Scope', 'SharingRule']
