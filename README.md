# Essence au meilleur prix

Trouve la station la moins chère et la plus proche, à partir des prix publiés par la Régie de l'énergie du Québec (Régie essence Québec).

- `site/` : la page (GPS, tri par prix, distance ou meilleur choix).
- `scripts/maj.py` : télécharge le fichier Excel le plus récent de la Régie et le convertit en `site/stations.json`.
- `.github/workflows/maj-prix.yml` : roule aux 15 minutes et republie la page avec les nouveaux prix.

Réglage requis une seule fois : **Settings → Pages → Source : GitHub Actions**.
