# 🤖 Trading IA - Système de Trading Autonome Intelligent

Système de trading crypto autonome utilisant l'intelligence artificielle (Google Gemini) pour analyser les marchés, interpréter les actualités, et exécuter des trades de manière autonome.

## 🏗️ Architecture

```
trading_ia/
├── config/
│   └── config.yaml           # Configuration principale
├── src/
│   ├── core/
│   │   ├── engine.py          # 🔥 Moteur de trading principal
│   │   ├── portfolio.py       # Gestion du portfolio
│   │   └── risk_manager.py    # 🛡️ Gestionnaire de risque
│   ├── exchange/
│   │   ├── base.py            # Interface abstraite
│   │   └── ccxt_exchange.py   # Connexion universelle CCXT
│   ├── analysis/
│   │   ├── technical.py       # 📊 Analyse technique (11+ indicateurs)
│   │   ├── ai_analyst.py      # 🧠 Analyse IA Gemini
│   │   └── sentiment.py       # 📰 Analyse du sentiment/news
│   ├── strategy/
│   │   └── ai_strategy.py     # 🎯 Stratégie combinée TA+IA+Sentiment
│   └── utils/
│       ├── config.py          # Configuration centralisée
│       ├── database.py        # SQLite async
│       └── logger.py          # Logging avancé
├── .env.example               # Template des variables d'environnement
├── requirements.txt           # Dépendances Python
└── run.py                     # Point d'entrée
```

## 🚀 Installation

### 1. Prérequis
- Python 3.11+
- Un compte sur un exchange crypto (Binance recommandé)
- Une clé API Google Gemini

### 2. Installation des dépendances

```bash
cd trading_ia
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copier le template
cp .env.example .env

# Éditer .env avec vos clés API
nano .env
```

**Variables essentielles:**
- `GEMINI_API_KEY` - Clé API Google Gemini (obligatoire pour l'IA)
- `BINANCE_API_KEY` + `BINANCE_SECRET_KEY` - Clés API Binance
- `TRADING_MODE` - `PAPER` (simulation) ou `LIVE` (réel)

### 4. Personnaliser la configuration

Éditez `config/config.yaml` pour:
- La watchlist de symboles
- Les timeframes d'analyse
- Les paramètres de risque
- Les seuils de trading

## 📖 Utilisation

### Mode Paper Trading (simulation)
```bash
python run.py --mode paper
```

### Mode Live (ATTENTION: argent réel!)
```bash
python run.py --mode live
```

### Avec dashboard web
```bash
python run.py --dashboard
```

### Choisir l'exchange
```bash
python run.py --exchange binance
python run.py --exchange kraken
```

## 🧠 Comment ça fonctionne

### Cycle de Trading (toutes les 60s par défaut)

1. **Collecte des données** - Prix, OHLCV, volume via CCXT
2. **Analyse technique** - 11+ indicateurs (RSI, MACD, BB, EMA, Ichimoku, etc.)
3. **Analyse des news** - Flux RSS crypto (CoinTelegraph, CoinDesk, Decrypt)
4. **Analyse IA Gemini** - L'IA interprète toutes les données et donne une recommandation
5. **Décision combinée** - Score pondéré: IA (45%) + Technique (35%) + Sentiment (20%)
6. **Validation du risque** - Stop loss, take profit, taille de position, R/R ratio
7. **Exécution** - Achat/vente automatique si toutes les conditions sont remplies

### Indicateurs Techniques
| Indicateur | Rôle |
|-----------|------|
| RSI | Zones de surachat/survente |
| MACD | Momentum et croisements |
| Bollinger Bands | Volatilité et extremes |
| EMA (9/21/50/200) | Tendance court/moyen/long terme |
| SMA (50/200) | Golden/Death Cross |
| Stochastic | Momentum oscillateur |
| ADX | Force de la tendance |
| ATR | Volatilité (sizing) |
| OBV | Volume et accumulation |
| VWAP | Prix moyen pondéré par volume |
| Ichimoku | Analyse multi-dimensionnelle |

### Gestion du Risque
- **Max risque par trade**: 2% du portfolio
- **Max taille position**: 10% du portfolio
- **Stop Loss automatique**: 3%
- **Take Profit**: 6%
- **Trailing Stop**: 2%
- **Perte max journalière**: 5%
- **Ratio R/R minimum**: 2:1
- **Cooldown après perte**: 30 minutes
- **Max positions simultanées**: 5

## 🔒 Sécurité

- Les clés API sont stockées dans `.env` (jamais commitées)
- Mode sandbox/paper par défaut
- Le mode LIVE requiert une confirmation de 10 secondes
- Le risk manager peut bloquer tout trade jugé trop risqué
- Toutes les décisions sont loguées en base de données

## 📊 Exchanges Supportés (via CCXT)

- Binance ✅
- Kraken ✅
- Coinbase ✅
- Et 100+ autres exchanges crypto

## ⚠️ Avertissements

- **Le trading de cryptomonnaies comporte des risques significatifs**
- Commencez TOUJOURS en mode Paper pour tester
- Ne tradez jamais avec de l'argent que vous ne pouvez pas vous permettre de perdre
- Les performances passées ne garantissent pas les résultats futurs
- L'IA peut faire des erreurs - surveillez régulièrement le système

## 📝 License

Usage personnel uniquement. Pas de conseil financier.
