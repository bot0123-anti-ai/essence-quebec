"""Télécharge le fichier des stations le plus récent de Régie essence Québec
et le convertit en stations.json pour la page.

Le nom du fichier contient l'heure UTC, par tranches de 5 minutes :
https://regieessencequebec.ca/data/stations-AAAAMMJJHHMMSS.xlsx
On essaie la tranche actuelle, puis on recule jusqu'à 2 heures.
"""
import datetime as dt
import io
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request

import openpyxl

BASE = "https://regieessencequebec.ca/data/stations-{:%Y%m%d%H%M%S}.xlsx"
COLS = ["banniere", "nom", "adresse", "code postal", "latitude", "longitude",
        "prix regulier", "prix super", "prix diesel", "region"]


def norm(s):
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def price(v):
    if v is None or v == "N/D":
        return None
    try:
        x = float(v) if isinstance(v, (int, float)) else float(str(v).replace("¢", "").replace(",", "."))
    except ValueError:
        return None
    if x <= 0:
        return None
    return round(x * 100, 1) if x < 10 else x


def convert(data):
    ws = openpyxl.load_workbook(io.BytesIO(data), read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows[:10]) if r and any(norm(c) == "latitude" for c in r))
    head = [norm(c) for c in rows[hi]]
    ix = [head.index(k) if k in head else -1 for k in COLS]
    out = []
    for r in rows[hi + 1:]:
        if not r:
            continue
        get = lambda i: r[i] if 0 <= i < len(r) else None
        lat, lon = get(ix[4]), get(ix[5])
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if not (44 < lat < 63 and -80 < lon < -56):
            continue
        out.append([str(get(ix[0]) or ""), str(get(ix[1]) or ""), str(get(ix[2]) or ""),
                    str(get(ix[3]) or ""), round(lat, 5), round(lon, 5),
                    price(get(ix[6])), price(get(ix[7])), price(get(ix[8])),
                    str(get(ix[9]) or "")])
    return out


def main(dest):
    now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    slot = now - dt.timedelta(minutes=now.minute % 5)
    for k in range(25):
        t = slot - dt.timedelta(minutes=5 * k)
        url = BASE.format(t)
        req = urllib.request.Request(url, headers={"User-Agent": "essence-quebec (projet personnel)"})
        try:
            data = urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            print(f"Refusé ({e.code}) : {url}")
            return 1
        except Exception as e:  # réseau
            print(f"Erreur réseau : {e}")
            continue
        if not data.startswith(b"PK"):  # pas un fichier Excel
            continue
        stations = convert(data)
        if len(stations) < 500:
            print(f"Fichier trop court ({len(stations)} stations) : {url}")
            continue
        with open(dest, "w", encoding="utf-8") as f:
            f.write('{"ts":"%s","source":"%s","stations":[\n' % (t.strftime("%Y-%m-%dT%H:%M:%SZ"), url))
            f.write(",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in stations))
            f.write("\n]}\n")
        print(f"{len(stations)} stations — {url}")
        return 0
    print("Aucun fichier trouvé dans les 2 dernières heures.")
    garder_version_en_ligne(dest)
    return 1


def garder_version_en_ligne(dest):
    """Si la Régie ne répond pas, on garde les prix déjà publiés (plus récents que ceux du dépôt)."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        return
    owner, name = repo.split("/", 1)
    url = f"https://{owner.lower()}.github.io/{name}/stations.json?t={int(time.time())}"
    try:
        live = json.load(urllib.request.urlopen(url, timeout=20))
        with open(dest, encoding="utf-8") as f:
            local = json.load(f)
        if live.get("ts", "") > local.get("ts", "") and len(live.get("stations", [])) > 500:
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(live, f, ensure_ascii=False, separators=(",", ":"))
            print("Prix déjà publiés conservés :", live["ts"])
    except Exception as e:
        print("Version en ligne indisponible :", e)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
