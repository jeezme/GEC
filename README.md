# Glisse en Coeur - Monitor

Application de monitoring de cagnotte caritative pour l'evenement "Glisse en Coeur".
Scrappe les donnees de https://glisse-en.coeur-fde.fr toutes les 5 minutes via Make
et genere un rapport HTML live avec 6 cards telechargeables en PNG.

---

## Deploiement sur Render

1. Poussez ce dossier dans un **repo GitHub** (public ou prive).
2. Sur [render.com](https://render.com), cliquez **New > Web Service**.
3. Connectez votre compte GitHub et selectionnez le repo.
4. Render detecte automatiquement `render.yaml` — verifiez :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn main:app --bind 0.0.0.0:$PORT`
5. Cliquez **Create Web Service**.
6. Une fois deploye, allez dans **Environment** pour copier la valeur  
   de `SECRET_TOKEN` (generee automatiquement) — vous en aurez besoin pour Make.

L'URL publique de votre service ressemble a :  
`https://gec-monitor.onrender.com`

---

## Configurer Make pour le declenchement toutes les 5 minutes

1. Creez un nouveau scenario sur **make.com**.
2. **Module 1** - Declencheur : `Schedule`
   - Every **5 minutes**
3. **Module 2** - `HTTP > Make a request`
   - URL    : `https://gec-monitor.onrender.com/run`
   - Method : `POST`
   - Headers : ajouter `X-Token` = `[votre SECRET_TOKEN depuis Render]`
4. Activez le scenario -> **Save**.

> Le rapport est accessible directement a la racine :  
> `https://gec-monitor.onrender.com/`

---

## Tester en local

```bash
pip install -r requirements.txt
python run_once.py
```

Cela :
1. Initialise la base SQLite (`data/glisse.db`)
2. Scrappe toutes les equipes
3. Genere `reports/rapport_YYYY-MM-DD.html`

Pour lancer le serveur en local :
```bash
python main.py
```
Puis ouvrez `http://localhost:8080/`.

---

## Corriger les genres non reconnus

Apres le premier scraping, un fichier `genders_overrides.json` est cree  
avec les prenoms non reconnus automatiquement (valeur `"?"`).

Remplacez `"?"` par `"M"` ou `"F"` :
```json
{
  "Alex": "M",
  "Camille": "F",
  "Claude": "M"
}
```

---

## Changer les equipes du duel (Card 4)

Editez `config.py` :

```python
DUEL_TEAM_1 = "polytech-annecy-chambery"    # slug de la 1re equipe
DUEL_TEAM_2 = "polytech-annecy-chambery-2"  # slug de la 2e equipe
```

Les slugs sont visibles dans l'URL : `https://glisse-en.coeur-fde.fr/equipe/{slug}`.

---

## Structure du projet

```
glisse-monitor/
├── main.py           # serveur Flask / gunicorn (point d'entree Render)
├── run_once.py       # scrape + genere le rapport (usage local)
├── scraper.py        # scraping BeautifulSoup
├── report.py         # generation du rapport HTML
├── gender.py         # detection du genre par prenom
├── config.py         # configuration (equipes, duel, timings)
├── db.py             # couche SQLite
├── render.yaml       # configuration Render
├── genders_overrides.json  # corrections manuelles de genre
├── requirements.txt
├── data/
│   └── glisse.db     # base SQLite (cree automatiquement)
└── reports/
    └── rapport_YYYY-MM-DD.html
```

---

## Endpoints Flask

| Methode | URL | Description |
|---------|-----|-------------|
| `GET`  | `/` | Sert le dernier rapport HTML disponible |
| `POST` | `/run` | Declenche scraping + rapport (header `X-Token` requis) |
| `GET`  | `/rapport/<fichier>` | Sert un rapport HTML specifique |
| `GET`  | `/rapport/latest` | Sert le rapport du jour |
