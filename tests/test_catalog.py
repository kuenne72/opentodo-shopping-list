from app import config
from tests.conftest import SECTION_IDS
from app.catalog import read_catalog
from app.db import Database


def test_seed_readable_and_complete():
    rows = read_catalog()
    assert len(rows) > 200
    assert all(r["section_id"] for r in rows), "Artikel ohne Abschnitt"
    assert all(r["unit"] in config.EINHEITEN for r in rows)
    names = [r["name"].lower() for r in rows]
    assert len(names) == len(set(names)), "doppelte Namen"


def test_import_merges_not_overwrites(tmp_path):
    db = Database(tmp_path / "c.db")
    db.upsert_item("Milch", default_qty=2, unit="l", section_id=SECTION_IDS["Kühlregal"], aliases=["Frischmilch"])
    r = db.import_catalog(read_catalog())
    assert r["added"] > 200 and r["updated"] == 1
    m = db.find_item("milch")
    assert m["default_qty"] == 2 and "Frischmilch" in m["aliases"] and "Vollmilch" in m["aliases"]
    r2 = db.import_catalog(read_catalog())
    assert r2["added"] == 0


def test_both_catalogs_are_consistent():
    import csv
    from app import config
    from app.catalog import SEED_DIR, read_catalog
    from app.sections import DEFAULT_SECTIONS

    for lang in ("de", "en"):
        path = SEED_DIR / f"items.{lang}.csv"
        names = [n for n, _, _ in DEFAULT_SECTIONS[lang]]
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        assert len(rows) >= 230
        assert {r["section"] for r in rows} <= set(names), lang
        assert all(r["unit"] in config.EINHEITEN for r in rows), lang
        keys = [r["name"].lower() for r in rows]
        assert len(keys) == len(set(keys)), f"duplicate names in {lang}"
    assert len(read_catalog(SEED_DIR / "items.en.csv")) == len(read_catalog(SEED_DIR / "items.de.csv"))
