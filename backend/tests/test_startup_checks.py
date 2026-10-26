from app.startup_checks import parse_origins, secret_problems


def test_dev_and_test_allow_default_secrets():
    assert secret_problems("dev", "change-me-too") == []
    assert secret_problems("TEST", "") == []


def test_production_rejects_default_or_short_secret():
    for bad in ("vistaar-demo-secret-change-me", "change-me-too", "", "short"):
        assert secret_problems("production", bad), bad
    assert secret_problems("production", "x" * 16 + "-real-random-value") == []


def test_any_non_dev_env_name_is_strict():
    assert secret_problems("staging", "change-me")


def test_parse_origins():
    assert parse_origins("https://a.app/, https://b.app") == ["https://a.app", "https://b.app"]
    assert parse_origins("") == ["http://localhost:3000"]