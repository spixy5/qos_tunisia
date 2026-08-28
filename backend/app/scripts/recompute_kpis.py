"""
Forces a full KPI recompute over every existing (secteur, operator,
technology) combination, without needing to re-upload a file.

Useful after fixing a bug in a KPI's compute() logic (e.g. tai.py's band-
prefix or position-tolerance fixes) - the old wrong values sitting in
kpi_results won't update themselves, since nothing re-runs the engine
until the next upload. This just calls the exact same run_kpi_engine()
the upload router calls, so the upsert-in-place logic in engine.py
handles overwriting the stale rows - no manual SQL needed.

Run from the backend project root, same convention as your other
one-off scripts:
    python -m app.scripts.recompute_kpis
"""
import logging

from app.database import SessionLocal
from app.kpi_engine.engine import run_kpi_engine

logging.basicConfig(level=logging.INFO)


def main():
    db = SessionLocal()
    try:
        result = run_kpi_engine(db)
        print(f"Recomputed {result['kpi_rows_upserted']} KPI rows "
              f"across {result['combinations']} combinations.")
    finally:
        db.close()


if __name__ == "__main__":
    main()