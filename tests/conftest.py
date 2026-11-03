"""Shared test setup: fake project/field/section IDs instead of a live OpenTodo."""

import pytest

from app import config, sections

SECTION_IDS = {
    "Obst/Gemüse": "sec-obst", "Brot/Backwaren": "sec-brot", "Kühlregal": "sec-kuehl",
    "Fleisch/Fisch": "sec-fleisch", "Getränke": "sec-getr", "Drogerie": "sec-drog",
    "Trockenware": "sec-trocken", "Sonstiges": "sec-sonst",
}


@pytest.fixture(autouse=True)
def fake_instance():
    old = (config.settings.project_id, config.FIELD_MENGE, config.FIELD_EINHEIT, config.FIELD_PREIS)
    config.settings.project_id = "P1"
    config.FIELD_MENGE, config.FIELD_EINHEIT, config.FIELD_PREIS = "f-menge", "f-einheit", "f-preis"
    sections._sections[:] = [{"id": sid, "name": n, "position": i} for i, (n, sid) in enumerate(SECTION_IDS.items())]
    yield
    config.settings.project_id, config.FIELD_MENGE, config.FIELD_EINHEIT, config.FIELD_PREIS = old
    sections._sections[:] = []
