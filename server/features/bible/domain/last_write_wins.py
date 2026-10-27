"""Which offline progress changes win (specs/025-bible-videos FR-018, FR-023).

Pure: the service hands in what is stored and what arrived, and writes only the winners.
"""

from collections.abc import Hashable, Mapping, Sequence
from datetime import datetime
from typing import Protocol


class TimedChange(Protocol):
    @property
    def changed_at(self) -> datetime: ...


def winning_changes[K: Hashable, C: TimedChange](
    stored: Mapping[K, datetime], incoming: Sequence[tuple[K, C]]
) -> list[C]:
    """The incoming changes to write, folded in order: a change wins only when its target has
    nothing stored or its ``changed_at`` is strictly later. Equal times keep what is stored, so
    a replayed change is a no-op. One winner per target.

    >>> winning_changes({"Gn 1": t(10, 5)}, [("Gn 1", mark(t(10, 0)))])
    []
    """
    newest = dict(stored)
    winners: dict[K, C] = {}
    for target, change in incoming:
        current = newest.get(target)
        if current is not None and change.changed_at <= current:
            continue
        newest[target] = change.changed_at
        winners[target] = change
    return list(winners.values())
