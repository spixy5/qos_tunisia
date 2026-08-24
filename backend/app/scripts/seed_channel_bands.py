"""
Seeds config_channel_band_mapping from the operator-provided reference
table (channel numbers -> band, per operator). Idempotent - safe to
re-run (updates existing rows by operator+channel rather than erroring).

Usage:
    python -m app.scripts.seed_channel_bands
"""
import logging

from app.database import SessionLocal
from app.models.config_models import ChannelBandMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (operator, technology, band, [channel numbers])
# technology here is descriptive only (see ChannelBandMapping docstring).
# 2G entries added from the updated reference table - TT/OO are true
# RANGES (e.g. "0-62"), expanded here via range(). OR's 2G cell was a
# single merged cell spanning both the 900 and 1800 columns reading
# "975,1024" (no dash) - read as 975->2G/900, 1024->2G/1800, following the
# same "first channel -> first band, second -> second" pattern as every
# other multi-channel cell in the table. FLAG FOR CONFIRMATION if that's
# not what was meant - easy to fix, just edit the two lines below.
CHANNEL_TABLE = [
    ("TT", "4G", "L2100", [251, 276]),
    ("TT", "4G", "L1800", [1350, 1375]),
    ("TT", "4G", "L800", [6200]),
    ("TT", "3G", "U2100", [10738]),
    ("TT", "3G", "U900", [3024]),
    ("TT", "2G", "G900", list(range(0, 63))),      # "0-62"
    ("TT", "2G", "G1800", list(range(512, 536))),  # "512-535"

    ("OO", "4G", "L2100", [151]),
    ("OO", "4G", "L1800", [1800, 101]),
    ("OO", "4G", "L800", [6400]),
    ("OO", "3G", "U2100", [10563, 10588]),
    ("OO", "3G", "U900", [3050, 3074]),
    ("OO", "2G", "G900", [ch for ch in range(63, 125) if ch != 101]),  # "63-124", minus 101 (that's OO's explicit L1800 channel - confirmed via real file: Ch=101 rows all show Serving band=1800)
    ("OO", "2G", "G1800", list(range(858, 886))),  # "858-885"

    ("OR", "4G", "L2100", [450]),
    ("OR", "4G", "L1800", [1600, 1475]),
    ("OR", "4G", "L800", [6300]),
    ("OR", "3G", "U2100", [10838]),
    ("OR", "3G", "U900", [2959]),
    ("OR", "2G", "G900", [975]),    # merged cell "975,1024" - see note above
    ("OR", "2G", "G1800", [1024]),  # merged cell "975,1024" - see note above
]


def main():
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for operator, technology, band, channels in CHANNEL_TABLE:
            for channel in channels:
                existing = db.query(ChannelBandMapping).filter_by(
                    operator=operator, channel=channel
                ).one_or_none()
                if existing:
                    existing.technology = technology
                    existing.band = band
                    updated += 1
                else:
                    db.add(ChannelBandMapping(
                        operator=operator, channel=channel, technology=technology, band=band,
                    ))
                    created += 1
        db.commit()
        logger.info("Channel-band mapping seeded: %d created, %d updated", created, updated)
    finally:
        db.close()


if __name__ == "__main__":
    main()
