"""
Diagnostic for TD showing null/0%. Prints:
  1. Every configured TechnologyThreshold row (what TD compares against).
  2. Every distinct `technology` value actually present in
     test_http_attempt, with count/min/avg/max of download_duration_seconds,
     and - if a threshold exists for that technology - the max duration
     that would still count as a "success" under that threshold.

Run from the backend project root:
    python -m app.scripts.diagnose_td
"""
from app.database import SessionLocal
from app.models.config_models import TechnologyThreshold
from app.models.raw_data import TestHTTPAttempt
from sqlalchemy import select, func, distinct

FILE_SIZE_MEGABITS = 2.0 * 8.0  # matches td.py


def main():
    db = SessionLocal()
    try:
        print("=== Configured TechnologyThreshold rows ===")
        thresholds = {t.technology: t.debit_exige_mbps for t in db.query(TechnologyThreshold).all()}
        if not thresholds:
            print("  (none configured at all)")
        for tech, mbps in thresholds.items():
            print(f"  {tech!r}: debit_exige_mbps={mbps}")

        print()
        print("=== Technologies actually present in test_http_attempt ===")
        techs = db.execute(
            select(distinct(TestHTTPAttempt.technology))
        ).scalars().all()

        for tech in techs:
            stats = db.execute(
                select(
                    func.count(TestHTTPAttempt.id),
                    func.min(TestHTTPAttempt.download_duration_seconds),
                    func.avg(TestHTTPAttempt.download_duration_seconds),
                    func.max(TestHTTPAttempt.download_duration_seconds),
                ).where(
                    TestHTTPAttempt.technology == tech,
                    TestHTTPAttempt.download_duration_seconds.is_not(None),
                )
            ).one()
            count, min_d, avg_d, max_d = stats

            threshold = thresholds.get(tech)
            if threshold:
                max_duration_for_success = FILE_SIZE_MEGABITS / threshold
                note = f"-> needs duration < {max_duration_for_success:.3f}s to count as success"
            elif tech in thresholds:
                note = "-> threshold row exists but debit_exige_mbps is NULL (never computed)"
            else:
                note = f"-> NO TechnologyThreshold row for {tech!r} at all - TD will be null for this technology"

            print(f"  technology={tech!r}: n={count}, "
                  f"min={min_d}, avg={avg_d}, max={max_d} seconds {note}")
    finally:
        db.close()


if __name__ == "__main__":
    main()