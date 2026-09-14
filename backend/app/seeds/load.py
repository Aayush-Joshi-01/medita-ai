"""Idempotent seed data loader.

`make seed` runs this inside the backend container as
`python -m app.seeds.load`. Safe to re-run — only inserts rows that don't
already exist by name.
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models.specialization import Specialization

SPECIALIZATIONS = [
    "Cardiology",
    "Dermatology",
    "Gastroenterology",
    "Neurology",
    "General Medicine",
]


def load() -> None:
    db = SessionLocal()
    try:
        existing = {name for (name,) in db.query(Specialization.name).all()}
        created = 0
        for name in SPECIALIZATIONS:
            if name not in existing:
                db.add(Specialization(name=name))
                created += 1
        db.commit()
        print(
            f"Seed complete: {created} specialization(s) added, "
            f"{len(SPECIALIZATIONS) - created} already present."
        )
    finally:
        db.close()


if __name__ == "__main__":
    load()
