"""Tests for POST /api/v1/rules/upload endpoint."""

import json
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_upload_rules_rejects_invalid_extension():
    files = {"file": ("bad.txt", b"x", "text/plain")}
    r = client.post("/api/v1/rules/upload", files=files)
    assert r.status_code == 400


def test_upload_rules_ba_friendly_csv_success(monkeypatch):
    class DummyConverter:
        def from_csv(self, path):
            self.rules_config = {"metadata": {"name": "test_rules"}, "rules": []}
            return self.rules_config
        def save(self, output_path):
            import os; os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"metadata": {"name": "test_rules"}, "rules": []}, f)

    monkeypatch.setattr("src.api.routers.rules.BARulesTemplateConverter", DummyConverter)

    files = {"file": ("rules.csv", b"Rule ID,Rule Name\n", "text/csv")}
    r = client.post("/api/v1/rules/upload?rules_name=test_rules&rules_type=ba_friendly", files=files)
    assert r.status_code == 200
    payload = r.json()
    assert payload["rules_id"] == "test_rules"
    assert "created" in payload["message"].lower()

    import os
    p = "config/rules/test_rules.json"
    if os.path.exists(p): os.remove(p)


def test_upload_rules_technical_xlsx_success(monkeypatch):
    class DummyConverter:
        def from_excel(self, path):
            self.rules_config = {"metadata": {"name": "tech_rules"}, "rules": []}
            return self.rules_config
        def save(self, output_path):
            import os; os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"metadata": {"name": "tech_rules"}, "rules": []}, f)

    monkeypatch.setattr("src.api.routers.rules.RulesTemplateConverter", DummyConverter)

    files = {"file": ("rules.xlsx", b"PK", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/v1/rules/upload?rules_name=tech_rules&rules_type=technical", files=files)
    assert r.status_code == 200
    payload = r.json()
    assert payload["rules_id"] == "tech_rules"

    import os
    p = "config/rules/tech_rules.json"
    if os.path.exists(p): os.remove(p)


def test_upload_rules_defaults_to_ba_friendly(monkeypatch):
    called_with = {}

    class DummyConverter:
        def from_csv(self, path):
            called_with['converter'] = 'ba_friendly'
            self.rules_config = {"metadata": {"name": "default_rules"}, "rules": []}
            return self.rules_config
        def save(self, output_path):
            import os; os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({}, f)

    monkeypatch.setattr("src.api.routers.rules.BARulesTemplateConverter", DummyConverter)

    files = {"file": ("rules.csv", b"x", "text/csv")}
    r = client.post("/api/v1/rules/upload?rules_name=default_rules", files=files)
    assert r.status_code == 200
    assert called_with.get('converter') == 'ba_friendly'

    import os
    p = "config/rules/default_rules.json"
    if os.path.exists(p): os.remove(p)
