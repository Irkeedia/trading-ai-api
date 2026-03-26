# Trading IA API

Backend FastAPI pour un moteur de trading crypto assiste par IA.

Ce service expose:
- une API REST pour le dashboard Next.js
- le controle du moteur (start/stop)
- la lecture des metriques, trades, signaux, analyses et news
- la connexion exchange par utilisateur avec validation reelle via CCXT

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- asyncpg (PostgreSQL / Neon)
- CCXT (Binance, Kraken, Bybit, OKX, ...)
- Google Gemini (google-genai SDK)

## Structure

```text
trading_ia/
|- config/
|  |- config.yaml
|- src/
|  |- api/main.py
|  |- core/
|  |- exchange/
|  |- analysis/
|  |- strategy/
|  |- utils/{config,database,logger}.py
|- run.py
|- run_api.py
|- seed_demo.py
|- requirements.txt
|- .env.example
```

## Installation locale

```bash
cd trading_ia
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Remplir ensuite `.env` au minimum avec:
- `GEMINI_API_KEY`
- `DATABASE_URL`
- `API_SECRET_KEY`

## Lancer le backend API

Option simple:

```bash
cd trading_ia
source venv/bin/activate
python run_api.py
```

Option dev (reload):

```bash
cd trading_ia
source venv/bin/activate
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs Swagger:
- `http://localhost:8000/docs`

## Endpoints principaux

Health:
- `GET /api/health`

Dashboard:
- `GET /api/dashboard`
- `GET /api/portfolio`
- `GET /api/portfolio/history?days=30`

Trading data:
- `GET /api/trades?symbol=BTC/USDT&limit=50`
- `GET /api/trades/stats`
- `GET /api/signals?symbol=BTC/USDT&limit=20`
- `GET /api/analyses?symbol=BTC/USDT&limit=10`
- `GET /api/news?limit=30`

Engine:
- `GET /api/engine/status`
- `POST /api/engine/control`
	- body: `{ "action": "start", "mode": "PAPER", "exchange": "binance" }`
	- body: `{ "action": "stop" }`

Config:
- `GET /api/config`

Exchange keys (par utilisateur):
- `POST /api/exchange/keys`
	- body: `{ "email": "user@mail.com", "exchange": "binance", "api_key": "...", "api_secret": "..." }`
	- comportement: teste la connexion reelle via `fetch_balance` CCXT, puis sauvegarde en base
- `GET /api/exchange/keys?email=user@mail.com`
	- retourne les cles masquees
- `DELETE /api/exchange/keys`
	- body: `{ "email": "user@mail.com", "exchange": "binance" }`

## Base de donnees

Le projet est configure pour PostgreSQL (Neon recommande en cloud).

Tables principales:
- `trades`
- `signals`
- `portfolio_snapshots`
- `ai_analyses`
- `news_items`
- `engine_status`
- `user_api_keys`

## Donnees de demo

Tu peux injecter des donnees pour remplir le dashboard avec un script de seed personnalise (exemple utilise pendant le dev), puis verifier les endpoints `/api/dashboard`, `/api/trades`, `/api/signals`.

## Deploiement

Ce backend est pret pour Railway (Dockerfile + railway.toml presents).

Variables importantes en production:
- `DATABASE_URL`
- `GEMINI_API_KEY`
- `API_SECRET_KEY`
- `CORS_ORIGINS`

## Securite

- Ne jamais commiter `.env`
- Utiliser des permissions minimales sur les cles exchange (read + spot trade uniquement)
- Interdire withdraw
- Ajouter whitelist IP cote exchange

## Avertissement

Le trading crypto comporte un risque eleve. Ce projet est un moteur technique, pas un conseil financier.
