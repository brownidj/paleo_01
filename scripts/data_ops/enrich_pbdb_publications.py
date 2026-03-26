#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from scripts.data_ops.pbdb_publication_enrichment_lib import (
    enrich_references,
    load_occurrence_rows,
    write_enriched_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich PBDB occurrences with publication title/authors/year/institutions/abstract."
    )
    parser.add_argument("--input-csv", default="data/pbdb_data-2.csv")
    parser.add_argument("--output-csv", default="data/pbdb_data-2_publication_enriched.csv")
    parser.add_argument("--sleep-seconds", type=float, default=0.03)
    parser.add_argument("--min-match-score", type=float, default=0.65)
    parser.add_argument("--limit-refs", type=int, default=0)
    parser.add_argument("--dump-ref-cache", default="")
    args = parser.parse_args()

    rows = load_occurrence_rows(Path(args.input_csv))
    ref_map = enrich_references(
        rows=rows,
        sleep_seconds=max(0.0, args.sleep_seconds),
        min_match_score=args.min_match_score,
        limit_refs=args.limit_refs if args.limit_refs > 0 else None,
    )
    write_enriched_rows(rows, ref_map, Path(args.output_csv))

    if args.dump_ref_cache:
        Path(args.dump_ref_cache).write_text(
            json.dumps({k: vars(v) for k, v in ref_map.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Input rows: {len(rows)}")
    print(f"Unique references resolved: {len(ref_map)}")
    print(f"Wrote: {args.output_csv}")


if __name__ == "__main__":
    main()
