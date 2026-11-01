from core.config import legacy_aware


def test_prefers_new_path_when_no_legacy_data(tmp_path):
    assert legacy_aware(tmp_path / ".keelway", tmp_path / ".kora") == tmp_path / ".keelway"


def test_keeps_legacy_data_until_new_path_exists(tmp_path):
    (tmp_path / ".kora").mkdir()
    assert legacy_aware(tmp_path / ".keelway", tmp_path / ".kora") == tmp_path / ".kora"
    (tmp_path / ".keelway").mkdir()
    assert legacy_aware(tmp_path / ".keelway", tmp_path / ".kora") == tmp_path / ".keelway"
