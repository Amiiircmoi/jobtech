"""Benchmark de latence de l'API jobtech — répétable (« accès rapide »).

Mesure le temps de réponse serveur de 2 endpoints analytiques (le plus simple et
le plus lourd : salary-stats vs salary-cube multidimensionnel) sur N requêtes, et
calcule p50 / p95 / p99. Optionnellement, rend une capture PNG du tableau.

Prérequis : API lancée + DW chargé (`python -m pipeline.run all`).
Usage :
    python bench_latency.py [BASE_URL] [N]
    python bench_latency.py http://127.0.0.1:8009 200 --png
"""

import os
import statistics
import sys
import time

import requests

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8009")
N = next((int(a) for a in sys.argv[1:] if a.isdigit()), 200)
MAKE_PNG = "--png" in sys.argv
# Jeton JWT optionnel (scope authentifié 1000/j) pour rester sous le quota anonyme
# (60/min) pendant la rafale de mesure. Sur instance fraîche, le cache de throttling
# (LocMem) est vide → benchmark répétable après un redémarrage du serveur.
JWT = os.getenv("BENCH_JWT", "")
HEADERS = {"Authorization": f"Bearer {JWT}"} if JWT else {}

# (label, url) — un endpoint léger et un endpoint lourd (cube multidim agrégé)
TARGETS = [
    ("salary-stats (FR)", f"{BASE}/api/v1/salary-stats/?country=FR"),
    ("salary-stats (global)", f"{BASE}/api/v1/salary-stats/"),
    ("salary-cube country×skill", f"{BASE}/api/v1/salary-cube/?dimensions=country,skill"),
    ("salary-cube country×skill×source×year", f"{BASE}/api/v1/salary-cube/?dimensions=country,skill,source,year"),
]


def _pct(values, p):
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return s[k]


def bench(label, url, n):
    sess = requests.Session()
    sess.headers.update(HEADERS)
    sess.get(url)  # warm-up (connexion + cache plan)
    ms = []
    for _ in range(n):
        t0 = time.perf_counter()
        r = sess.get(url)
        ms.append((time.perf_counter() - t0) * 1000)
        r.raise_for_status()
    return {
        "label": label,
        "n": n,
        "p50": round(_pct(ms, 50), 1),
        "p95": round(_pct(ms, 95), 1),
        "p99": round(_pct(ms, 99), 1),
        "mean": round(statistics.fmean(ms), 1),
        "max": round(max(ms), 1),
    }


def main():
    print(f"Benchmark latence API — {BASE} — {N} requêtes/endpoint (warm-up exclu)\n")
    rows = [bench(label, url, N) for label, url in TARGETS]
    hdr = f"{'endpoint':<42}{'n':>5}{'p50':>8}{'p95':>8}{'p99':>8}{'moy':>8}{'max':>8}   (ms)"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['label']:<42}{r['n']:>5}{r['p50']:>8}{r['p95']:>8}{r['p99']:>8}{r['mean']:>8}{r['max']:>8}")

    if MAKE_PNG:
        _render_png(rows)
    return rows


def _render_png(rows):
    import pathlib

    from playwright.sync_api import sync_playwright

    out = pathlib.Path(__file__).parent / "docs" / "img" / "api-latency.png"
    trs = "".join(
        f"<tr><td style='text-align:left'>{r['label']}</td><td>{r['n']}</td>"
        f"<td>{r['p50']}</td><td>{r['p95']}</td><td>{r['p99']}</td>"
        f"<td>{r['mean']}</td><td>{r['max']}</td></tr>"
        for r in rows
    )
    html = f"""<!doctype html><meta charset='utf-8'>
    <body style="font-family:ui-monospace,Menlo,monospace;background:#0d1117;color:#e6edf3;padding:32px">
      <h2>API jobtech — latence serveur</h2>
      <div style="color:#8b949e">{BASE} · {rows[0]['n']} requêtes/endpoint · warm-up exclu · mesuré le 2026-06-17</div>
      <table style="border-collapse:collapse;margin-top:18px;font-size:15px">
        <thead><tr style="color:#58a6ff">
          <th style='text-align:left;padding:6px 14px'>endpoint</th><th>n</th>
          <th>p50</th><th>p95</th><th>p99</th><th>moy</th><th>max</th></tr>
          <tr style="color:#8b949e"><th></th><th></th><th colspan=5>millisecondes</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
      <style>td{{padding:6px 14px;text-align:right;border-top:1px solid #30363d}}</style>
    </body>"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 980, "height": 360})
        pg.set_content(html)
        pg.screenshot(path=str(out))
        b.close()
    print(f"\n✓ capture → {out}")


if __name__ == "__main__":
    main()
