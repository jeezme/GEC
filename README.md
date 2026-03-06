# Glisse en Coeur Monitor

Application de monitoring de cagnotte pour l'evenement skiable caritatif **Glisse en Coeur**.

## Fonctionnement

- Scraping de [glisse-en.coeur-fde.fr](https://glisse-en.coeur-fde.fr) toutes les 5 minutes via Make
- Stockage des donnees dans SQLite (persistant sur Replit avec Always On)
- Generation d'un rapport HTML avec 6 cards telechargeable en PNG

## Deploiement sur Replit

1. Creer un nouveau Repl (Python)
2. Importer ce repo GitHub
3. Activer **Always On** (onglet Settings)
4. Cliquer **Run** — le serveur Flask demarre sur le port 8080
5. Copier l'URL du Repl (ex: `https://gec.username.repl.co`)

## Configuration Make

Creer un scenario Make avec un declencheur **Schedule** toutes les 5 minutes :

- Module : **HTTP > Make a request**
- URL : `https://gec.username.repl.co/run`
- Methode : `POST`
- Header : `X-Token: <votre_token_secret>`

Le token secret est defini par la variable d'environnement `SECRET_TOKEN` dans les Secrets Replit.
Par defaut (si non defini) : `changeme`.

## Routes

| Route | Description |
|-------|-------------|
| `GET /` | Dernier rapport HTML du jour |
| `POST /run` | Declenche scraping + generation rapport |
| `GET /rapport/latest` | Rapport du jour |
| `GET /rapport/<fichier>` | Rapport par nom de fichier |

## Structure

```
config.py        # 18 equipes, config duel, constantes
scraper.py       # Scraping BeautifulSoup
db.py            # Couche SQLite
gender.py        # Detection genre prenom
report.py        # Generateur rapport HTML (6 cards)
main.py          # Serveur Flask
run_once.py      # Execution locale manuelle
```

## Execution locale

```bash
pip install -r requirements.txt
python run_once.py   # scrape + genere rapport une fois
python main.py       # demarre le serveur Flask
```
