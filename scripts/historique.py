"""Garde l'historique des prix moyens par région.

- Un point par heure pendant 31 jours, puis une moyenne par jour pendant 400 jours.
- L'historique vit dans la page publiée (site/historique.json). On le relit au début
  de chaque exécution, avec une copie de secours dans le dépôt (data/historique.json),
  enregistrée une fois par jour.
"""
import datetime as dt
import json
import os
import time
import urllib.request

STATIONS = "site/stations.json"
SORTIE = "site/historique.json"
SECOURS = "data/historique.json"
JOURS_HORAIRES = 31
JOURS_QUOTIDIENS = 400


def vide():
    return {"regions": [], "h": [], "d": []}


def dernier(h):
    return (h["h"][-1]["t"] if h.get("h") else "", len(h.get("h", [])) + len(h.get("d", [])))


def charger():
    candidats = []
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        url = f"https://{owner.lower()}.github.io/{name}/historique.json?t={int(time.time())}"
        try:
            candidats.append(json.load(urllib.request.urlopen(url, timeout=20)))
        except Exception as e:
            print("Historique en ligne indisponible :", e)
    try:
        with open(SECOURS, encoding="utf-8") as f:
            candidats.append(json.load(f))
    except Exception:
        pass
    candidats = [c for c in candidats if isinstance(c, dict) and "h" in c]
    return max(candidats, key=dernier) if candidats else vide()


def moyennes(stations, regions):
    somme, nb = {}, {}
    tot, ntot = [0.0, 0.0, 0.0], [0, 0, 0]
    for s in stations:
        reg = s[9] if len(s) > 9 else ""
        for f in range(3):
            p = s[6 + f]
            if p is None:
                continue
            tot[f] += p
            ntot[f] += 1
            if reg:
                somme.setdefault(reg, [0.0, 0.0, 0.0])[f] += p
                nb.setdefault(reg, [0, 0, 0])[f] += 1
    for reg in sorted(somme):
        if reg not in regions:
            regions.append(reg)
    r = []
    for reg in regions:
        if reg in somme:
            r.append([round(somme[reg][f] / nb[reg][f], 1) if nb[reg][f] else None for f in range(3)])
        else:
            r.append([None, None, None])
    q = [round(tot[f] / ntot[f], 1) if ntot[f] else None for f in range(3)]
    return r, q


def moyenne_points(points, n_regions):
    r = []
    for i in range(n_regions):
        row = []
        for f in range(3):
            v = [p["r"][i][f] for p in points if i < len(p["r"]) and p["r"][i][f] is not None]
            row.append(round(sum(v) / len(v), 1) if v else None)
        r.append(row)
    q = []
    for f in range(3):
        v = [p["q"][f] for p in points if p["q"][f] is not None]
        q.append(round(sum(v) / len(v), 1) if v else None)
    return r, q


def main():
    hist = charger()
    with open(STATIONS, encoding="utf-8") as f:
        data = json.load(f)
    ts = data.get("ts", "")
    heure = ts[:13] + ":00Z" if ts else ""
    if heure and (not hist["h"] or heure >= hist["h"][-1]["t"]):
        r, q = moyennes(data.get("stations", []), hist["regions"])
        point = {"t": heure, "r": r, "q": q}
        if hist["h"] and hist["h"][-1]["t"] == heure:
            hist["h"][-1] = point
        else:
            hist["h"].append(point)
        print(f"Point {heure} ajouté ({len(hist['h'])} points horaires)")
    else:
        print("Pas de nouveaux prix : historique inchangé")

    # Les points horaires de plus de 31 jours deviennent une moyenne par jour.
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=JOURS_HORAIRES)).strftime("%Y-%m-%dT%H")
    vieux = [p for p in hist["h"] if p["t"] < limite]
    hist["h"] = [p for p in hist["h"] if p["t"] >= limite]
    jours = {}
    for p in vieux:
        jours.setdefault(p["t"][:10], []).append(p)
    deja = {d["t"] for d in hist["d"]}
    for jour, pts in sorted(jours.items()):
        if jour not in deja:
            r, q = moyenne_points(pts, len(hist["regions"]))
            hist["d"].append({"t": jour, "r": r, "q": q})
    hist["d"] = sorted(hist["d"], key=lambda d: d["t"])[-JOURS_QUOTIDIENS:]

    def ecrire(chemin, contenu):
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write('{"regions":' + json.dumps(contenu["regions"], ensure_ascii=False))
            for cle in ("h", "d"):
                f.write(',\n"%s":[\n' % cle)
                f.write(",\n".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in contenu[cle]))
                f.write("\n]")
            if "sauvegarde" in contenu:
                f.write(',\n"sauvegarde":"%s"' % contenu["sauvegarde"])
            f.write("}\n")

    ecrire(SORTIE, hist)

    # Copie de secours dans le dépôt, une fois par jour.
    aujourdhui = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(SECOURS, encoding="utf-8") as f:
            ancien = json.load(f).get("sauvegarde", "")
    except Exception:
        ancien = ""
    if ancien != aujourdhui and hist["h"]:
        ecrire(SECOURS, dict(hist, sauvegarde=aujourdhui))
        print("Copie de secours enregistrée")


if __name__ == "__main__":
    main()
