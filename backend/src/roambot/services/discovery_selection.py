"""Bounded model input selection, without a place vocabulary or rating ranking.

This is lexical relevance and redundancy control, not a semantic recommender.
Selected objects retain their original identities and evidence identifiers.
"""

from urllib.parse import urlsplit

from roambot.persistence.discovery_knowledge import tokens


def _select(items, queries, *, limit, text, identity, group, recent=()):
    unique = {}
    for item in items:
        unique.setdefault(identity(item), item)
    remaining = list(unique.values())
    terms = [set(tokens(q)) for q in queries if q]
    terms = [q for q in terms if q]
    vocabulary = set().union(*terms) if terms else set()
    features = {id(item): set(tokens(text(item))) for item in remaining}
    selected, covered, groups = [], set(), set()
    recent = set(recent)
    while remaining and len(selected) < limit:

        def score(item):
            words = features[id(item)]
            relevant = max((len(words & q) / len(q) for q in terms), default=0)
            new_coverage = len((words & vocabulary) - covered) / max(1, len(vocabulary))
            redundant = max(
                (
                    len(words & features[id(other)]) / max(1, len(words | features[id(other)]))
                    for other in selected
                ),
                default=0,
            )
            # Similar evidence cannot fill the entire bounded window just by arriving first.
            novelty = 0.25 if group(item) and group(item) not in groups else 0
            return 3 * relevant + new_coverage + novelty - 0.5 * redundant

        # A newly paid retrieval must be assessed rather than disappearing behind
        # cached text. This preserves evidence, not a category or publication quota.
        fresh = [item for item in remaining if identity(item) in recent]
        best = max(fresh or remaining, key=score)  # Stable ties retain provider order.
        remaining.remove(best)
        selected.append(best)
        covered.update(features[id(best)] & vocabulary)
        groups.add(group(best))
    return selected


def select_sources(sources, queries, *, limit=18, recent_urls=()):
    return _select(
        sources,
        queries,
        limit=limit,
        text=lambda s: s.get("title", "") + " " + s.get("excerpt", ""),
        identity=lambda s: s["url"],
        group=lambda s: urlsplit(s["url"]).hostname,
        recent=recent_urls,
    )


def select_places(places, queries, *, limit=48):
    return _select(
        places,
        queries,
        limit=limit,
        text=lambda p: " ".join(p.get(k, "") for k in ("name", "address", "map_type")),
        identity=lambda p: p["id"],
        group=lambda p: p.get("map_type", ""),
    )


def select_retrieved_places(query_results, *, limit=12, preserve_provider_order=False):
    """Preserve coverage of actual retrievals without a fixed experience taxonomy.

    Lexical scores from different queries aren't comparable: an exact provider
    category match must not exhaust the window ahead of all other retrievals.
    Rank within each query, then merge unique entities in stable rounds.
    """
    groups = [places[:limit] if preserve_provider_order else select_places(places, [query], limit=limit)
              for query, places in query_results]
    selected, seen = [], set()
    for offset in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if offset < len(group) and group[offset]["id"] not in seen:
                place = group[offset]
                selected.append(place)
                seen.add(place["id"])
                if len(selected) >= limit:
                    return selected
    return selected
