from __future__ import annotations

"""Pure rules for ABADDON v10.7.0 social card expansion.

No Discord dependency: these helpers are intentionally unit-testable offline.
"""

from collections import Counter
from itertools import combinations
from typing import Iterable, List, Sequence, Tuple

Card = Tuple[int, str]


def card_points(card: Card) -> int:
    rank, _ = card
    if rank == 14:
        return 15
    if rank >= 11:
        return 10
    return rank


def _ace_variants(ranks: Sequence[int]) -> List[List[int]]:
    base = sorted(ranks)
    variants = [base]
    if 14 in base:
        variants.append(sorted(1 if r == 14 else r for r in base))
    return variants


def is_set(cards: Sequence[Card]) -> bool:
    return 3 <= len(cards) <= 4 and len({r for r, _ in cards}) == 1 and len({s for _, s in cards}) == len(cards)


def is_run(cards: Sequence[Card]) -> bool:
    if len(cards) < 3 or len({s for _, s in cards}) != 1:
        return False
    ranks = [r for r, _ in cards]
    if len(set(ranks)) != len(ranks):
        return False
    for candidate in _ace_variants(ranks):
        if all(candidate[i] + 1 == candidate[i + 1] for i in range(len(candidate) - 1)):
            return True
    return False


def is_valid_meld(cards: Sequence[Card]) -> bool:
    return is_set(cards) or is_run(cards)


def meld_points(cards: Sequence[Card]) -> int:
    return sum(card_points(c) for c in cards)


def greedy_melds(hand: Sequence[Card]) -> List[List[int]]:
    """Return disjoint useful meld index groups, largest/highest first."""
    remaining = set(range(len(hand)))
    groups: List[List[int]] = []
    candidates: List[Tuple[int, int, Tuple[int, ...]]] = []
    for size in range(min(7, len(hand)), 2, -1):
        for combo in combinations(range(len(hand)), size):
            cards = [hand[i] for i in combo]
            if is_valid_meld(cards):
                candidates.append((size, meld_points(cards), combo))
    candidates.sort(reverse=True)
    for _size, _points, combo in candidates:
        if set(combo) <= remaining:
            groups.append(list(combo))
            remaining.difference_update(combo)
    return groups


PRESIDENT_ORDER = {rank: idx for idx, rank in enumerate(list(range(3, 15)) + [2])}


def president_strength(rank: int, revolution: bool = False) -> int:
    strength = PRESIDENT_ORDER[int(rank)]
    return -strength if revolution else strength


def president_play_valid(
    ranks: Sequence[int],
    current_rank: int | None,
    current_count: int,
    revolution: bool = False,
) -> bool:
    if not ranks or len(set(ranks)) != 1:
        return False
    if current_rank is None:
        return True
    if len(ranks) != int(current_count):
        return False
    return president_strength(ranks[0], revolution) > president_strength(current_rank, revolution)


def dice_card_score(cards: Sequence[Card], dice: Sequence[int]) -> Tuple[int, ...]:
    """ABADDON hybrid: compare five rank symbols from two cards + three dice.

    Categories mirror poker without suits: five-kind, four-kind, full house,
    straight, three-kind, two pair, pair, high card.
    """
    ranks = [min(14, max(2, int(r))) for r, _ in cards] + [int(d) + 1 for d in dice]
    counts = Counter(ranks)
    ordered = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    unique = sorted(set(ranks))
    straight = len(unique) == 5 and unique[-1] - unique[0] == 4
    if ordered[0][1] == 5:
        return (8, ordered[0][0])
    if ordered[0][1] == 4:
        return (7, ordered[0][0], ordered[1][0])
    if sorted(counts.values()) == [2, 3]:
        return (6, ordered[0][0], ordered[1][0])
    if straight:
        return (5, unique[-1])
    if ordered[0][1] == 3:
        kickers = sorted((r for r in ranks if r != ordered[0][0]), reverse=True)
        return (4, ordered[0][0], *kickers)
    pairs = sorted((r for r, c in counts.items() if c == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(r for r in ranks if r not in pairs)
        return (3, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        kickers = sorted((r for r in ranks if r != pairs[0]), reverse=True)
        return (2, pairs[0], *kickers)
    return (1, *sorted(ranks, reverse=True))


def dori_rank(months: Sequence[int]) -> Tuple[Tuple[int, ...], str, Tuple[int, int] | None]:
    """Rank a five-card Dori-jitgo-ttaeng hand.

    Select a two-card 'made' whose month sum is divisible by ten. The remaining
    three cards are ranked by triples, pairs, then total kkeut. Best split wins.
    """
    if len(months) != 5:
        raise ValueError("Dori-jitgo-ttaeng requires five cards")
    best: Tuple[int, ...] | None = None
    best_name = "노메이드"
    best_pair = None
    for a, b in combinations(range(5), 2):
        if (months[a] + months[b]) % 10 != 0:
            continue
        rest = [months[i] for i in range(5) if i not in {a, b}]
        counts = Counter(rest)
        if 3 in counts.values():
            rank = (4, max(counts))
            name = f"{max(counts)}삼땡"
        elif 2 in counts.values():
            pair = max(r for r, c in counts.items() if c == 2)
            kicker = max(r for r, c in counts.items() if c == 1)
            rank = (3, pair, kicker)
            name = f"{pair}땡-{kicker}"
        else:
            kkeut = sum(rest) % 10
            high = tuple(sorted(rest, reverse=True))
            rank = (2, kkeut, *high)
            name = "갑오" if kkeut == 9 else ("망통" if kkeut == 0 else f"{kkeut}끗")
        made_high = max(months[a], months[b])
        full = (*rank, made_high)
        if best is None or full > best:
            best, best_name, best_pair = full, name, (a, b)
    if best is None:
        return ((0, sum(months) % 10, *sorted(months, reverse=True)), "노메이드", None)
    return best, best_name, best_pair


def hwatu_capture_points(categories: Iterable[str], months: Iterable[int]) -> int:
    """Point total used by Minhwatu/600 table variants."""
    values = {
        "bright": 50, "bright_rain": 50,
        "animal": 10, "animal_godori": 50, "animal_doublejunk": 10,
        "ribbon_blue": 10, "ribbon_red_poetry": 10, "ribbon_red_plain": 10,
        "ribbon": 10, "junk": 0,
    }
    score = sum(values.get(str(cat), 0) for cat in categories)
    month_counts = Counter(int(m) for m in months)
    score += sum(50 for m in (1, 2, 3, 4, 8, 11, 12) if month_counts.get(m, 0) >= 4)
    return score


def roppyakken_round_valid(scores: Sequence[int]) -> bool:
    """Standard 600 draw rule: a player at 30 or below voids the round."""
    return bool(scores) and all(int(score) > 30 for score in scores)


def ai_risk(difficulty: str, personality: str) -> float:
    base = {"쉬움": 0.25, "보통": 0.5, "어려움": 0.72, "악몽": 0.9}.get(difficulty, 0.5)
    mod = {"안정형": -0.18, "공격형": 0.16, "블러프형": 0.08, "도박형": 0.28, "복수형": 0.12}.get(personality, 0.0)
    return max(0.05, min(0.98, base + mod))
