"""Transformations métier réutilisables (devises, pays, salaires, compétences).

Cœur de l'extraction/transformation des multiples sources hétérogènes.
"""

import json
import re
from functools import lru_cache

import pandas as pd
import pycountry


def load_exchange_rates(path) -> dict:
    """Charge le fichier JSON des taux de change (cible : EUR)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_currency(amount_str, rates: dict) -> float | None:
    """Convertit une chaîne de salaire ('€40k', '$50,000', 'GBP60k', '45 000') en EUR.

    `rates` mappe un code ISO3 vers son taux EUR (ex. {'USD': 0.92}).
    """
    if pd.isna(amount_str):
        return None
    s = str(amount_str).replace("\xa0", "").replace(" ", "")
    symbol_map = {"€": "EUR", "£": "GBP", "$": "USD"}
    currency = "EUR"
    for sym, code in symbol_map.items():
        if sym in s:
            currency = code
            s = s.replace(sym, "")
            break
    m = re.match(r"^([A-Za-z]{3})(.*)$", s)
    if m:
        currency = m.group(1).upper()
        s = m.group(2)
    # Retire les libellés type "paran" / "/an" / "k€" résiduels
    s = s.replace(",", "")
    s = re.sub(r"(?i)k(?=$|[^0-9])", "000", s)
    s = re.sub(r"[^0-9.]", "", s)
    try:
        value = float(s)
    except ValueError:
        return None
    rate = rates.get(currency, 1.0)
    return round(value * rate, 2)


def map_country_iso2(name_or_code) -> str | None:
    """Mappe un nom de pays ou un code ISO2/ISO3 vers un code ISO2 (via pycountry)."""
    if pd.isna(name_or_code):
        return None
    return _map_country_cached(str(name_or_code).strip())


@lru_cache(maxsize=512)
def _map_country_cached(key: str) -> str | None:
    """Résolution mémoïsée : `search_fuzzy` est coûteux et très répétitif sur un DW
    (peu de pays distincts) → cache LRU = optimisation de pipeline."""
    if not key:
        return None
    country = pycountry.countries.get(alpha_2=key.upper())
    if country:
        return country.alpha_2
    country = pycountry.countries.get(alpha_3=key.upper())
    if country:
        return country.alpha_2
    try:
        matches = pycountry.countries.search_fuzzy(key)
        if matches:
            return matches[0].alpha_2
    except LookupError:
        pass
    return None


def parse_salary_range(range_str) -> tuple:
    """Parse une fourchette '40k–60k€' ou '50000-70000' → (min, max) en nombres."""
    if pd.isna(range_str):
        return (None, None)
    s = str(range_str).replace(" ", "")
    s = re.sub(r"[€£$]", "", s)
    parts = re.split(r"[–\-]", s)
    vals = []
    for part in parts:
        try:
            if part.lower().endswith("k"):
                vals.append(float(part[:-1]) * 1000)
            else:
                vals.append(float(part))
        except ValueError:
            continue
    if len(vals) == 2:
        return (vals[0], vals[1])
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (None, None)


def normalize_skill_label(label) -> str | None:
    """Normalise un label de compétence ('Python/C++' → 'python_c', 'Node.js' → 'node_js')."""
    if pd.isna(label):
        return None
    s = str(label).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or None
