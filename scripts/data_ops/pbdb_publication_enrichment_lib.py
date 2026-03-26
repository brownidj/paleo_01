import csv
import html
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

PBDB_REF_URL = "https://paleobiodb.org/data1.2/refs/single.json"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PALEO_KEYWORDS = (
    "paleo", "palaeo", "fossil", "devonian", "carboniferous", "permian", "triassic", "jurassic", "cretaceous",
    "conodont", "brachiopod", "gastropod", "bivalv", "stratigraph", "biostrat", "geolog", "paleobiol", "palaeobiol",
)


@dataclass
class RefEnrichment:
    reference_no: str
    title: str
    authors: str
    publication_year: str
    institutions: str
    abstract: str
    sources: str
    best_match_score: str


def _find_occurrence_header(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip('"')
        if stripped.startswith("occurrence_no,") or stripped.startswith("occurrence_no\","):
            return i
    raise ValueError("Could not find occurrence header row.")


def load_occurrence_rows(csv_path: Path) -> list[dict[str, str]]:
    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    return [dict(row) for row in csv.DictReader(lines[_find_occurrence_header(lines):])]


def _norm_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _similarity(a: str, b: str) -> float:
    return 0.0 if not a or not b else SequenceMatcher(None, _norm_text(a), _norm_text(b)).ratio()


def _is_paleo_relevant(*texts: str) -> bool:
    blob = _norm_text(" ".join(texts))
    return any(k in blob for k in PALEO_KEYWORDS)


def _clean_abstract(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def _decode_openalex_abstract(inverted: dict[str, list[int]] | None) -> str:
    if not isinstance(inverted, dict):
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for idx in idxs:
            positions[int(idx)] = word
    return " ".join(positions[i] for i in sorted(positions)).strip() if positions else ""


def _extract_pbdb_authors(record: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for idx in range(1, 7):
        init = str(record.get(f"ai{idx}") or "").strip()
        last = str(record.get(f"al{idx}") or "").strip()
        if init or last:
            authors.append(" ".join(f"{init} {last}".split()))
    other = str(record.get("oa") or "").strip()
    if other:
        authors.extend([x for x in re.split(r"\s*;\s*|\s*,\s*", other) if x])
    seen: set[str] = set()
    out: list[str] = []
    for author in authors:
        key = author.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(" ".join(author.split()))
    return out


def _fetch_pbdb_reference(session: requests.Session, reference_no: str) -> dict[str, Any] | None:
    response = session.get(PBDB_REF_URL, params={"id": reference_no}, timeout=30)
    response.raise_for_status()
    records = (response.json() or {}).get("records") or []
    return dict(records[0]) if records else None


def _score_candidate(query_title: str, query_year: str, cand_title: str, cand_year: str, relevant: bool) -> float:
    title_score = _similarity(query_title, cand_title)
    year_score = 0.0
    if query_year.isdigit() and cand_year.isdigit():
        year_score = 1.0 if query_year == cand_year else (0.5 if abs(int(query_year) - int(cand_year)) <= 1 else 0.0)
    return title_score * 0.8 + year_score * 0.15 + (0.05 if relevant else 0.0)


def _fetch_openalex_candidates(session: requests.Session, title: str, publication_year: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"search": title, "per-page": 5}
    if publication_year.isdigit():
        y = int(publication_year)
        params["filter"] = f"from_publication_date:{y:04d}-01-01,to_publication_date:{y:04d}-12-31"
    response = session.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    response.raise_for_status()
    out: list[dict[str, Any]] = []
    for work in (response.json() or {}).get("results") or []:
        institutions: list[str] = []
        authors: list[str] = []
        for authorship in work.get("authorships") or []:
            name = str(((authorship.get("author") or {}).get("display_name") or "")).strip()
            if name:
                authors.append(name)
            for inst in authorship.get("institutions") or []:
                inst_name = str(inst.get("display_name") or "").strip()
                if inst_name:
                    institutions.append(inst_name)
        out.append(
            {
                "source": "openalex",
                "title": str(work.get("display_name") or "").strip(),
                "year": str(work.get("publication_year") or "").strip(),
                "authors": authors,
                "institutions": sorted(set(institutions), key=str.lower),
                "abstract": _decode_openalex_abstract(work.get("abstract_inverted_index")),
                "venue": str(((work.get("primary_location") or {}).get("source") or {}).get("display_name") or "").strip(),
            }
        )
    return out


def _fetch_crossref_candidates(session: requests.Session, title: str) -> list[dict[str, Any]]:
    response = session.get(CROSSREF_WORKS_URL, params={"query.title": title, "rows": 5}, timeout=30)
    response.raise_for_status()
    out: list[dict[str, Any]] = []
    for work in (response.json() or {}).get("message", {}).get("items", []):
        cand_title = str(work.get("title", [""])[0] if isinstance(work.get("title"), list) and work.get("title") else "").strip()
        issued = (work.get("issued") or {}).get("date-parts") or []
        year = str(issued[0][0]) if issued and issued[0] else ""
        authors: list[str] = []
        institutions: list[str] = []
        for author in work.get("author") or []:
            full = " ".join(f"{str(author.get('given') or '').strip()} {str(author.get('family') or '').strip()}".split())
            if full:
                authors.append(full)
            for affiliation in author.get("affiliation") or []:
                aff_name = str((affiliation or {}).get("name") or "").strip()
                if aff_name:
                    institutions.append(aff_name)
        venue = str(work.get("container-title", [""])[0] if isinstance(work.get("container-title"), list) and work.get("container-title") else "").strip()
        out.append(
            {
                "source": "crossref",
                "title": cand_title,
                "year": year,
                "authors": authors,
                "institutions": sorted(set(institutions), key=str.lower),
                "abstract": _clean_abstract(str(work.get("abstract") or "")),
                "venue": venue,
            }
        )
    return out


def _fetch_semantic_scholar_candidates(session: requests.Session, title: str) -> list[dict[str, Any]]:
    response = session.get(
        SEMANTIC_SCHOLAR_SEARCH_URL,
        params={"query": title, "limit": 5, "fields": "title,year,authors,abstract,venue"},
        timeout=30,
    )
    response.raise_for_status()
    out: list[dict[str, Any]] = []
    for work in (response.json() or {}).get("data") or []:
        authors: list[str] = []
        institutions: list[str] = []
        for author in work.get("authors") or []:
            name = str(author.get("name") or "").strip()
            if name:
                authors.append(name)
            for affiliation in author.get("affiliations") or []:
                if isinstance(affiliation, str) and affiliation.strip():
                    institutions.append(affiliation.strip())
        out.append(
            {
                "source": "semantic_scholar",
                "title": str(work.get("title") or "").strip(),
                "year": str(work.get("year") or "").strip(),
                "authors": authors,
                "institutions": sorted(set(institutions), key=str.lower),
                "abstract": _clean_abstract(str(work.get("abstract") or "")),
                "venue": str(work.get("venue") or "").strip(),
            }
        )
    return out


def _best_external_match(session: requests.Session, query_title: str, query_year: str, min_score: float) -> tuple[dict[str, Any] | None, float]:
    candidates: list[dict[str, Any]] = []
    fetchers = (
        lambda s, t, y: _fetch_openalex_candidates(s, t, y),
        lambda s, t, _y: _fetch_crossref_candidates(s, t),
        lambda s, t, _y: _fetch_semantic_scholar_candidates(s, t),
    )
    for fetcher in fetchers:
        try:
            candidates.extend(fetcher(session, query_title, query_year))
        except Exception:
            pass
    best: dict[str, Any] | None = None
    best_score = 0.0
    for candidate in candidates:
        relevant = _is_paleo_relevant(candidate.get("title", ""), candidate.get("venue", ""))
        score = _score_candidate(query_title, query_year, candidate.get("title", ""), candidate.get("year", ""), relevant)
        if score > best_score:
            best = dict(candidate)
            best["relevant"] = relevant
            best_score = score
    if not best or best_score < min_score or not bool(best.get("relevant")):
        return None, best_score
    return best, best_score


def enrich_references(rows: list[dict[str, str]], sleep_seconds: float, min_match_score: float, limit_refs: int | None) -> dict[str, RefEnrichment]:
    by_ref: dict[str, tuple[str, str]] = {}
    for row in rows:
        ref_no = (row.get("reference_no") or "").strip()
        if ref_no:
            by_ref.setdefault(ref_no, ((row.get("ref_author") or "").strip(), (row.get("ref_pubyr") or "").strip()))
    items = sorted(by_ref.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0])
    if isinstance(limit_refs, int) and limit_refs > 0:
        items = items[:limit_refs]
    session = requests.Session()
    session.headers.update({"User-Agent": "Paleo_01 publication enricher"})
    out: dict[str, RefEnrichment] = {}
    for ref_no, (row_authors, row_year) in items:
        pbdb = _fetch_pbdb_reference(session, ref_no)
        pbdb_title = str((pbdb or {}).get("tit") or "").strip()
        pbdb_year = str((pbdb or {}).get("pby") or row_year).strip()
        authors = "; ".join(_extract_pbdb_authors(pbdb or {})) or row_authors
        sources = ["pbdb_ref"] if pbdb else ["pbdb_row"]
        institutions = ""
        abstract = ""
        best_match, score = _best_external_match(session, pbdb_title, pbdb_year, min_match_score)
        if best_match:
            pbdb_title = pbdb_title or str(best_match.get("title") or "").strip()
            authors = authors or "; ".join(best_match.get("authors") or [])
            institutions = "; ".join(best_match.get("institutions") or [])
            abstract = str(best_match.get("abstract") or "").strip()
            sources.append(str(best_match.get("source") or "external"))
        out[ref_no] = RefEnrichment(ref_no, pbdb_title, authors, pbdb_year, institutions, abstract, ";".join(sources), f"{score:.3f}")
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return out


def write_enriched_rows(rows: list[dict[str, str]], ref_map: dict[str, RefEnrichment], output_csv: Path) -> None:
    fields = ["occurrence_no", "reference_no", "ref_author", "ref_pubyr", "paper_title", "paper_authors", "paper_publication_year", "author_institutions", "paper_abstract", "enrichment_sources", "best_match_score"]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            ref_no = (row.get("reference_no") or "").strip()
            e = ref_map.get(ref_no)
            writer.writerow(
                {
                    "occurrence_no": (row.get("occurrence_no") or "").strip(),
                    "reference_no": ref_no,
                    "ref_author": (row.get("ref_author") or "").strip(),
                    "ref_pubyr": (row.get("ref_pubyr") or "").strip(),
                    "paper_title": e.title if e else "",
                    "paper_authors": e.authors if e else "",
                    "paper_publication_year": e.publication_year if e else "",
                    "author_institutions": e.institutions if e else "",
                    "paper_abstract": e.abstract if e else "",
                    "enrichment_sources": e.sources if e else "",
                    "best_match_score": e.best_match_score if e else "",
                }
            )
