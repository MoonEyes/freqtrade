# Stratégies freqtrade — long+short pour marché baissier

Collection de stratégies [freqtrade](https://www.freqtrade.io/) orientées
**futures long+short (levier 1x)**, conçues pour **préserver le capital et
profiter des marchés baissiers** plutôt que pour suivre un bull market.

> Ce dépôt ne contient **que les stratégies** (`user_data/strategies/*.py`).
> Le moteur freqtrade s'installe via pip ; configs, clés API et données de
> marché ne sont **pas** versionnés.

## Stratégies

| Fichier | Description |
|---|---|
| **`ours_regime.py`** | ⭐ Recommandée. Ruban EMA trend-following (futures long+short 1x) + **filtre de régime** (pente EMA200 : long si l'ancre monte, short si elle descend) + stop ATR. |
| `ours.py` | La base de `ours_regime`, sans le filtre de régime. |
| `ichimoku.py` | Ichimoku futures long+short. |
| `ichimoku_double.py` | Double Ichimoku : timeframe lent = filtre de tendance, rapide = déclencheur (sélectif, faible drawdown). |
| `abeille.py`, `koala.py`, `hibou.py`, `rino.py`, `lapin.py` | Anciennes stratégies (archive). |
| `stratninja.py` | Stratégie additionnelle. |
| `sample_strategy.py` | Template freqtrade de référence. |

**Thèse :** ces stratégies long+short sont des outils de **bear / préservation
de capital**, pas des compounders de bull — le short saigne en marché haussier.
`ours_regime` ajoute un filtre de régime pour atténuer ce bleed.

## Utilisation

```bash
# 1. Installer freqtrade (une fois)
python3 -m venv ~/ftvenv
~/ftvenv/bin/pip install freqtrade TA-Lib

# 2. Initialiser un user_data freqtrade puis y copier les stratégies
~/ftvenv/bin/freqtrade create-userdir --userdir user_data
# (les .py de ce repo vont dans user_data/strategies/)

# 3. Backtester (futures long+short → trading_mode: futures, margin_mode: isolated)
~/ftvenv/bin/freqtrade backtesting --strategy ours_regime --userdir user_data \
    --config <ta_config.json> --timeframe 1h

# 4. Dry-run
~/ftvenv/bin/freqtrade trade --strategy ours_regime --userdir user_data \
    --config <ta_config.json>
```

`can_short=True` exige une config en `"trading_mode": "futures"` +
`"margin_mode": "isolated"` (refusé en spot).

## Sécurité

Aucun secret n'est versionné. Crée ta propre config (`config.json`) avec tes
clés exchange / token Telegram — elle est ignorée par git. Ne committe jamais
une config réelle.
