"""Searchable public place evidence, never conversations or personal query state."""

import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager

from roambot.domain.discovery_text import venue_paragraphs
from roambot.providers.discovery import safe_public_url, source_mentions_place

PLACE_FIELDS = ("id", "name", "address", "city", "coordinate", "map_type", "map_url", "facts")
SOURCE_FIELDS = ("url", "title", "excerpt", "kind", "retrieved_at")


def tokens(text):
    """Unicode character grams allow Chinese search without a scenery vocabulary."""
    result = set()
    for word in re.findall(r"[\u3400-\u9fff]+|[a-z0-9]+", text.casefold()):
        if re.fullmatch(r"[a-z0-9]+", word):
            if len(word) >= 2:
                result.add(word)
        else:
            for size in (2, 3):
                result.update(word[i : i + size] for i in range(len(word) - size + 1))
    return sorted(result)


class DiscoveryKnowledge:
    def __init__(self, path, *, capacity=2000, clock=time.time):
        self.path, self.capacity, self.clock = path, capacity, clock
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS venues "
                "(id TEXT PRIMARY KEY, place TEXT NOT NULL, sources TEXT NOT NULL, updated REAL)"
            )
            db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS venue_text USING fts5(id UNINDEXED, terms)"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def remember(self, place, sources):
        # The caller supplies actual map records; no free-form inferred model facts are stored.
        if not re.fullmatch(r"amap:[a-zA-Z0-9]+", place.get("id", "")):
            return
        facts = {key: place[key] for key in PLACE_FIELDS if key in place}
        if len(facts) != len(PLACE_FIELDS):
            return
        facts["parent_id"] = place.get("parent_id")
        valid = [
            {key: source.get(key, "") for key in SOURCE_FIELDS}
            for source in sources
            if source.get("kind") in {"web_page", "search_excerpt"}
            and safe_public_url(source.get("url", ""))
            and source_mentions_place(place, source)
        ]
        if not valid:
            return
        valid = [
            {**source, "excerpt": "\n\n".join(venue_paragraphs(place, source))[:4000]}
            for source in valid
        ]
        valid = [source for source in valid if source["excerpt"] and source_mentions_place(place, source)]
        if not valid:
            return
        with self.connect() as db:
            prior = db.execute(
                "SELECT sources,place,updated FROM venues WHERE id=?", (place["id"],)
            ).fetchone()
            old_place = json.loads(prior[1]) if prior else {}
            facts["verified_at"] = (
                place.get("verified_at")
                or old_place.get("verified_at")
                or (prior[2] if prior else self.clock())
            )
            merged = {s["url"]: s for s in json.loads(prior[0])} if prior else {}
            for source in valid:
                source["retrieved_at"] = (
                    source.get("retrieved_at")
                    or merged.get(source["url"], {}).get("retrieved_at")
                    or (prior[2] if prior else self.clock())
                )
            merged.update({s["url"]: s for s in valid})
            valid = list(merged.values())[-6:]
            content = (
                place["city"]
                + " "
                + place["address"]
                + " "
                + place["name"]
                + " "
                + place["map_type"]
                + " "
                + " ".join(s["title"] + " " + s["excerpt"][:1200] for s in valid)
            )
            db.execute(
                "INSERT OR REPLACE INTO venues VALUES (?, ?, ?, ?)",
                (
                    place["id"],
                    json.dumps(facts, ensure_ascii=False),
                    json.dumps(valid, ensure_ascii=False),
                    self.clock(),
                ),
            )
            db.execute("DELETE FROM venue_text WHERE id=?", (place["id"],))
            db.execute(
                "INSERT INTO venue_text VALUES (?, ?)", (place["id"], " ".join(tokens(content)))
            )
            expired = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM venues ORDER BY updated DESC LIMIT -1 OFFSET ?",
                    (self.capacity,),
                )
            ]
            db.executemany("DELETE FROM venue_text WHERE id=?", [(key,) for key in expired])
            db.executemany("DELETE FROM venues WHERE id=?", [(key,) for key in expired])

    def sources_for(self, places):
        """Enrich current map identities; never inject cached candidate places."""
        by_id = {place["id"]: place for place in places}
        if not by_id:
            return {}
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,sources,updated FROM venues WHERE id IN ("
                + ",".join("?" for _ in by_id) + ") AND updated>?",
                (*by_id, self.clock() - 86400),
            ).fetchall()
        return {key: [source for source in json.loads(raw)
                      if (source.get("retrieved_at") or updated) > self.clock() - 86400
                      and source_mentions_place(by_id[key], source)]
                for key, raw, updated in rows}

    def find(self, query, *, region=None, center=None, radius=None, limit=12):
        if region:
            for alias in (region, region.removesuffix("市")):
                if alias:
                    query = query.replace(alias, " ")
        terms = tokens(query)[:100]
        if not terms:
            return []
        expression = " OR ".join('"' + term + '"' for term in terms)
        with self.connect() as db:
            rows = db.execute(
                "SELECT v.place,v.sources,v.updated FROM venue_text f "
                "JOIN venues v ON f.id=v.id WHERE venue_text MATCH ? "
                "AND v.updated>? ORDER BY bm25(venue_text) LIMIT 100",
                (expression, self.clock() - 86400),
            ).fetchall()
        result = []
        for place_raw, sources_raw, updated in rows:
            place = json.loads(place_raw)
            if (place.get("verified_at") or updated) <= self.clock() - 86400:
                continue
            sources = [
                s
                for s in json.loads(sources_raw)
                if (s.get("retrieved_at") or updated) > self.clock() - 86400
                and source_mentions_place(place, s)
            ]
            if not sources:
                continue
            if region and region.removesuffix("市") not in place["city"] + place["address"]:
                continue
            if center and radius is not None:
                p = place["coordinate"]
                lat = math.radians(center.latitude)
                distance = 6371 * math.hypot(
                    math.radians(p["latitude"] - center.latitude),
                    math.cos(lat) * math.radians(p["longitude"] - center.longitude),
                )
                # This only prunes impossible retrievals; actual routes still enforce the cap.
                if distance > radius:
                    continue
            result.append({"place": place, "sources": sources, "updated": updated})
            if len(result) == limit:
                break
        return result
