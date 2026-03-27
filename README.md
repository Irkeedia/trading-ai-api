# Trading IA — API (Backend)

Backend **FastAPI** qui sert le moteur de trading crypto assisté par IA.  
Le **dashboard** (frontend Next.js) dans le dossier voisin `../dashboard` consomme cette API.

---

## Sommaire

1. [C’est quoi ce dossier ?](#cest-quoi-ce-dossier-)
2. [Pour François (débutant)](#pour-françois-débutant)
3. [Glossaire rapide](#glossaire-rapide)
4. [Stack technique](#stack-technique)
5. [Structure du code](#structure-du-code)
6. [Installation locale](#installation-locale)
7. [Lancer l’API](#lancer-lapi)
8. [Endpoints principaux](#endpoints-principaux)
9. [Base de données](#base-de-données)
10. [Données de démo](#données-de-démo)
11. [Déploiement](#déploiement)
12. [Sécurité et avertissement](#sécurité-et-avertissement)

---

## C’est quoi ce dossier ?

Ce service **ne s’affiche pas dans un navigateur tout seul** : c’est un **serveur** qui répond à des requêtes HTTP (JSON).  
Il expose notamment :

- une **API REST** pour le dashboard ;
- le **contrôle du moteur** (démarrage / arrêt) ;
- la lecture des **métriques**, **trades**, **signaux**, **analyses** et **news** ;
- la **connexion exchange** par utilisateur, avec validation réelle via **CCXT**.

**En pratique :** tu lances ce projet **en premier** (ou en parallèle) avant de tester le dashboard.

---

## Pour François (débutant)

Si tu débutes, lis cette section dans l’ordre.

### Ordre recommandé le premier jour

1. **Installer Python 3.11+** sur ta machine (vérifie avec `python3 --version`).
2. Ouvrir un terminal dans le dossier `trading_ia`.
3. Créer un **environnement virtuel** (le dossier `venv`) : ça isole les paquets Python du projet.
4. Activer le venv, puis `pip install -r requirements.txt`.
5. Copier `.env.example` vers `.env` et remplir au minimum les variables indiquées plus bas.
6. Lancer l’API avec `python run_api.py` (ou la commande uvicorn en mode reload).
7. Ouvrir **http://localhost:8000/docs** : tu dois voir **Swagger** (liste interactive des routes). Si ça s’affiche, **c’est gagné**.

### Vocabulaire pour toi

| Terme | Signification simple |
|--------|----------------------|
| **API / backend** | Programme qui tourne sur un serveur et renvoie des données au frontend. |
| **FastAPI** | Framework Python pour construire cette API rapidement. |
| **Endpoint / route** | Une URL précise (ex. `/api/trades`) + méthode GET/POST, etc. |
| **Swagger (`/docs`)** | Page web générée automatiquement pour tester l’API sans écrire de code. |
| **`.env`** | Fichier local avec des secrets (clés API) — **ne jamais le committer**. |
| **CCXT** | Bibliothèque pour parler aux exchanges (Binance, etc.) avec un code commun. |
| **PostgreSQL** | Base de données relationnelle (ici souvent hébergée sur Neon en cloud). |

### Pièges fréquents

- **« Rien ne marche dans le dashboard »** → Souvent l’API n’est pas lancée ou le port n’est pas `8000`. Vérifie `NEXT_PUBLIC_API_URL` côté dashboard.
- **Erreur base de données** → `DATABASE_URL` manquant ou incorrect dans `.env`.
- **Tu modifies le code et vois l’ancienne version** → Utilise le mode `--reload` avec uvicorn pendant le dev.

### Fichiers que tu touches le plus au début

- `.env` — tes secrets locaux (copié depuis `.env.example`).
- `run_api.py` — point d’entrée simple pour démarrer.
- `src/api/main.py` — cœur FastAPI (routes).

---

## Glossaire rapide

- **PAPER** : mode simulation / papier (sans argent réel selon la config du moteur).
- **Spot** : trading sur le marché au comptant (par opposition aux dérivés).

---

## Stack technique

- Python 3.11+
- FastAPI + Uvicorn
- asyncpg (PostgreSQL / Neon)
- CCXT (Binance, Kraken, Bybit, OKX, …)
- Google Gemini (`google-genai`)

---

## Structure du code

```text
trading_ia/
├── config/
│   └── config.yaml
├── src/
│   ├── api/main.py
│   ├── core/
│   ├── exchange/
│   ├── analysis/
│   ├── strategy/
│   └── utils/{config,database,logger}.py
├── run.py
├── run_api.py
├── seed_demo.py
├── requirements.txt
└── .env.example
```

---

## Installation locale

```bash
cd trading_ia
python3 -m venv venv
source venv/bin/activate   # Sous Windows PowerShell : .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Renseigner dans `.env` au minimum :

- `GEMINI_API_KEY`
- `DATABASE_URL`
- `API_SECRET_KEY`

---

## Lancer l’API

**Option simple :**

```bash
cd trading_ia
source venv/bin/activate
python run_api.py
```

**Option développement (rechargement auto à chaque sauvegarde) :**

```bash
cd trading_ia
source venv/bin/activate
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Documentation interactive (Swagger) :**  
[http://localhost:8000/docs](http://localhost:8000/docs)

---

## Endpoints principaux

**Santé :**

- `GET /api/health`

**Dashboard :**

- `GET /api/dashboard`
- `GET /api/portfolio`
- `GET /api/portfolio/history?days=30`

**Données trading :**

- `GET /api/trades?symbol=BTC/USDT&limit=50`
- `GET /api/trades/stats`
- `GET /api/signals?symbol=BTC/USDT&limit=20`
- `GET /api/analyses?symbol=BTC/USDT&limit=10`
- `GET /api/news?limit=30`

**Moteur :**

- `GET /api/engine/status`
- `POST /api/engine/control`
  - `{ "action": "start", "mode": "PAPER", "exchange": "binance" }`
  - `{ "action": "stop" }`

**Configuration :**

- `GET /api/config`

**Clés exchange (par utilisateur) :**

- `POST /api/exchange/keys` — body : `{ "email": "user@mail.com", "exchange": "binance", "api_key": "...", "api_secret": "..." }`  
  Teste la connexion via `fetch_balance` (CCXT), puis enregistre en base.
- `GET /api/exchange/keys?email=user@mail.com` — clés masquées.
- `DELETE /api/exchange/keys` — body : `{ "email": "user@mail.com", "exchange": "binance" }`

---

## Base de données

PostgreSQL (Neon recommandé en cloud).

Tables principales : `trades`, `signals`, `portfolio_snapshots`, `ai_analyses`, `news_items`, `engine_status`, `user_api_keys`.

---

## Données de démo

Tu peux injecter des données avec le script de seed (ex. `seed_demo.py` selon le flux du projet) pour remplir le dashboard, puis vérifier les routes `/api/dashboard`, `/api/trades`, `/api/signals`.

---

## Déploiement

Prêt pour Railway (Dockerfile + `railway.toml` présents).

Variables importantes en production : `DATABASE_URL`, `GEMINI_API_KEY`, `API_SECRET_KEY`, `CORS_ORIGINS`.

---

## Sécurité et avertissement

- Ne jamais commiter `.env`.
- Clés exchange : permissions minimales (lecture + spot trade), **pas de retrait (withdraw)**.
- Ajouter une **liste d’IP autorisées** côté exchange si possible.

**Avertissement :** le trading crypto comporte un risque élevé. Ce projet est un **moteur technique**, pas un conseil financier.

---

*Suite logique : une fois l’API OK sur le port 8000, configure et lance le frontend décrit dans [../dashboard/README.md](../dashboard/README.md).*
