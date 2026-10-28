"""Phase D: club honours, managers and club facts from Wikidata (public SPARQL endpoint, CC0 data).

Run from the project root:  python -m src.collect.legacy

Club items are listed in data/reference/clubs_wikidata.csv. Raw query results go to data/raw/legacy/;
src.process.build_legacy cleans them. The endpoint is queried in batches with a pause between requests,
as Wikimedia's rate-limit guidance asks.
"""
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
REF, OUT = ROOT / "data" / "reference", ROOT / "data" / "raw" / "legacy"
ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "FYP-TacticalProfiles/0.1 (academic project; "
                         "https://github.com/NITIYAHSELVAN/fyp-attacking-philosophies)"}
BATCH, PAUSE = 12, 2.0

# Events (seasons, finals, matches) whose winner (P1346) is the club, with the competition they belong to.
HONOURS = """SELECT ?club ?ev ?evLabel ?comp ?compLabel ?parentComp ?parentCompLabel ?date ?start WHERE {
  VALUES ?club { %s } ?ev wdt:P1346 ?club .
  OPTIONAL { ?ev wdt:P3450 ?comp }
  OPTIONAL { ?ev wdt:P361 ?par . ?par wdt:P3450 ?parentComp }
  OPTIONAL { ?ev wdt:P585 ?date } OPTIONAL { ?ev wdt:P580 ?start }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""

# Head coaches (P286) with their tenure qualifiers.
MANAGERS = """SELECT ?club ?m ?mLabel ?start ?end ?end_precision ?countryLabel ?born WHERE {
  VALUES ?club { %s } ?club p:P286 ?st . ?st ps:P286 ?m .
  OPTIONAL { ?st pq:P580 ?start }
  OPTIONAL { ?st pq:P582 ?end . ?st pqv:P582 [ wikibase:timePrecision ?end_precision ] }
  OPTIONAL { ?m wdt:P27 ?country } OPTIONAL { ?m wdt:P569 ?born }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""

CLUB_INFO = """SELECT ?club ?clubLabel ?inception ?venueLabel ?capacity ?cityLabel ?nickname WHERE {
  VALUES ?club { %s }
  OPTIONAL { ?club wdt:P571 ?inception }
  OPTIONAL { ?club wdt:P115 ?venue . OPTIONAL { ?venue wdt:P1083 ?capacity } }
  OPTIONAL { ?club wdt:P159 ?city }
  OPTIONAL { ?club wdt:P1449 ?nickname FILTER(lang(?nickname) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""


def sparql(query: str, retries: int = 4) -> list[dict]:
    for attempt in range(retries):
        r = requests.get(ENDPOINT, params={"query": query, "format": "json"}, headers=HEADERS, timeout=180)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(int(r.headers.get("Retry-After", 10 * (attempt + 1))))
            continue
        r.raise_for_status()
        return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]
    raise RuntimeError(f"Wikidata query failed after {retries} attempts")


def run_batched(template: str, qids: list[str]) -> pd.DataFrame:
    rows = []
    for i in range(0, len(qids), BATCH):
        rows += sparql(template % " ".join(f"wd:{q}" for q in qids[i:i + BATCH]))
        time.sleep(PAUSE)
    df = pd.DataFrame(rows)
    for col in df.columns:  # entity URIs -> QIDs
        vals = df[col].dropna().astype(str)
        if len(vals) and vals.str.startswith("http://www.wikidata.org/entity/").all():
            df[col] = df[col].str.rsplit("/", n=1).str[1]
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(REF / "clubs_wikidata.csv")
    qids = ref.wikidata.tolist()
    for name, template in (("honours", HONOURS), ("managers", MANAGERS), ("club_info", CLUB_INFO)):
        df = run_batched(template, qids)
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name}: {len(df):,} rows")
    (OUT / "retrieved.txt").write_text(pd.Timestamp.now(tz="UTC").isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()
