"""Phase C+: fill in player photos that the Wikidata P18 match missed. Freely licensed images only.

Run from the project root after src.process.build_players:  python -m src.collect.photos

1. Players linked to Wikidata but without a P18 image: the lead image of their Wikipedia article (English first,
   then Spanish, Italian, Portuguese, French, German), requested with pilicense=free so only free images return.
2. Players not linked to Wikidata: Wikidata's name search, kept only when the hit is a footballer born in the
   same year as FBref says; then P18 or the Wikipedia lead image as above.

Writes data/raw/players/photos_extra.csv (wikidata, photo, source); src.process.build_players uses it as a fallback.
Requests are batched and paced, as Wikimedia's API etiquette asks.
"""
import time
from pathlib import Path

import pandas as pd
import requests

from src.collect.legacy import HEADERS

ROOT = Path(__file__).resolve().parents[2]
PLAYERS = ROOT / "data" / "processed" / "players" / "players.csv"
OUT = ROOT / "data" / "raw" / "players" / "photos_extra.csv"
WIKIS = ["enwiki", "eswiki", "itwiki", "ptwiki", "frwiki", "dewiki"]
PAUSE = 1.0


CACHE = ROOT / "data" / "raw" / "players" / "wikimedia_cache"


def get(url: str, params: dict, retries: int = 4) -> dict:
    """GET with a disk cache, so an interrupted run resumes without repeating requests."""
    import hashlib
    import json
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    body = _fetch(url, params, retries)
    if body:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body), encoding="utf-8")
    return body


def _fetch(url: str, params: dict, retries: int) -> dict:
    for attempt in range(retries):
        r = requests.get(url, params={**params, "format": "json"}, headers=HEADERS, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(int(r.headers.get("Retry-After", 5 * (attempt + 1))))
            continue
        r.raise_for_status()
        time.sleep(PAUSE)  # pace live requests only; cache hits are free
        return r.json()
    return {}


def entities(qids: list[str]) -> dict:
    """Sitelinks, P18 image, P569 birth date and P106 occupations for up to 50 items per request."""
    out = {}
    for i in range(0, len(qids), 50):
        data = get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                                                          "props": "sitelinks|claims"})
        out.update(data.get("entities", {}))
    return out


def claim(entity: dict, prop: str) -> list:
    vals = []
    for c in entity.get("claims", {}).get(prop, []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if v is not None:  # "unknown value" / "no value" statements carry no datavalue
            vals.append(v.get("id") if isinstance(v, dict) and "id" in v else v)
    return vals


def lead_images(titles_by_wiki: dict[str, dict[str, str]]) -> dict[str, str]:
    """qid -> free-licence thumbnail URL from the first wiki whose article has one."""
    found = {}
    for wiki in WIKIS:
        todo = {q: t for q, t in titles_by_wiki.get(wiki, {}).items() if q not in found}
        items = list(todo.items())
        lang = wiki.removesuffix("wiki")
        for i in range(0, len(items), 50):
            chunk = dict(items[i:i + 50])
            data = get(f"https://{lang}.wikipedia.org/w/api.php", {
                "action": "query", "titles": "|".join(chunk.values()), "prop": "pageimages", "piprop": "thumbnail",
                "pithumbsize": 240, "pilicense": "free", "redirects": 1})
            q = data.get("query", {})
            rename = {r["from"]: r["to"] for r in q.get("redirects", []) + q.get("normalized", [])}
            thumbs = {p["title"]: p["thumbnail"]["source"] for p in q.get("pages", {}).values() if "thumbnail" in p}
            for qid, title in chunk.items():
                t = rename.get(title, title)
                t = rename.get(t, t)
                if t in thumbs:
                    found[qid] = thumbs[t]
    return found


def search(name: str) -> list[str]:
    data = get("https://www.wikidata.org/w/api.php", {"action": "wbsearchentities", "search": name, "language": "en",
                                                      "type": "item", "limit": 7})
    return [h["id"] for h in data.get("search", [])]


def main() -> None:
    p = pd.read_csv(PLAYERS)
    need = p[p.photo.isna()]
    linked = need.dropna(subset=["wikidata"]).wikidata.unique().tolist()
    unlinked = need[need.wikidata.isna()].drop_duplicates("name")[["name", "born_year"]]
    print(f"{len(linked)} linked players without a photo, {len(unlinked)} unlinked names", flush=True)

    # Step 2 first: find Wikidata items for unlinked players (footballer, same birth year when known).
    found_q = {}
    cands = {name: search(name) for name in unlinked.name}
    ents = entities(sorted({q for qs in cands.values() for q in qs}))
    for r in unlinked.itertuples():
        ok = []
        for q in cands.get(r.name, []):
            e = ents.get(q, {})
            if "Q937857" not in claim(e, "P106"):  # association football player
                continue
            born = [str(b.get("time", ""))[1:5] for b in claim(e, "P569") if isinstance(b, dict)]
            if pd.notna(r.born_year) and str(int(r.born_year)) not in born:
                continue
            ok.append(q)
        if len(ok) == 1:
            found_q[r.name] = ok[0]
    print(f"Wikidata search: {len(found_q)} of {len(unlinked)} unlinked players identified", flush=True)

    qids = sorted(set(linked) | set(found_q.values()))
    ents.update(entities([q for q in qids if q not in ents]))
    rows, titles = {}, {w: {} for w in WIKIS}
    for q in qids:
        e = ents.get(q, {})
        img = claim(e, "P18")
        if img:
            rows[q] = ("https://commons.wikimedia.org/wiki/Special:FilePath/" + img[0].replace(" ", "_"), "wikidata P18")
            continue
        for w in WIKIS:
            if w in e.get("sitelinks", {}):
                titles[w][q] = e["sitelinks"][w]["title"]
    for q, url in lead_images(titles).items():
        rows.setdefault(q, (url, "wikipedia lead image"))
    out = pd.DataFrame([{"wikidata": q, "photo": u, "source": s} for q, (u, s) in rows.items()])
    names = pd.DataFrame([{"name": n, "wikidata": q} for n, q in found_q.items()])
    out = out.merge(names, on="wikidata", how="left") if len(out) else out
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Photos found: {len(out)} ({out.source.value_counts().to_dict() if len(out) else {}})", flush=True)


if __name__ == "__main__":
    main()
