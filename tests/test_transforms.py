"""Tests unitaires des transformations métier (sans base de données)."""

from pipeline import transforms

RATES = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17}


def test_normalize_currency_symbols():
    assert transforms.normalize_currency("€40k", RATES) == 40000.0
    assert transforms.normalize_currency("$50,000", RATES) == round(50000 * 0.92, 2)
    assert transforms.normalize_currency("GBP60k", RATES) == round(60000 * 1.17, 2)


def test_normalize_currency_invalid_returns_none():
    assert transforms.normalize_currency("non communiqué", RATES) is None
    assert transforms.normalize_currency(None, RATES) is None


def test_map_country_iso2():
    assert transforms.map_country_iso2("France") == "FR"
    assert transforms.map_country_iso2("us") == "US"
    assert transforms.map_country_iso2("DEU") == "DE"
    assert transforms.map_country_iso2(None) is None


def test_parse_salary_range():
    assert transforms.parse_salary_range("40k–60k€") == (40000.0, 60000.0)
    assert transforms.parse_salary_range("50000-70000") == (50000.0, 70000.0)
    assert transforms.parse_salary_range(None) == (None, None)


def test_normalize_skill_label():
    assert transforms.normalize_skill_label("Node.js") == "node_js"
    assert transforms.normalize_skill_label("Python/C++") == "python_c"
    assert transforms.normalize_skill_label("  AWS ") == "aws"
