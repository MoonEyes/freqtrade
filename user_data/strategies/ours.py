###############################################################################
# Strategy "ours" - EMA ribbon trend-following (FUTURES long & short, 1x)
# -----------------------------------------------------------------------------
# Objectif : faire du benefice AUSSI en marche baissier. En spot long-only on ne
# gagne que si ca monte ; ici on passe en futures pour pouvoir SHORTER les
# tendances baissieres (levier 1x = aucune amplification, juste le droit de
# vendre a decouvert).
#
# Principes :
#   - Cablage hyperopt correct via le "range trick" (EMA precalculees par periode
#     candidate dans populate_indicators, selectionnees avec .value).
#   - Ruban EMA symetrique :
#       LONG  : ema_fast > ema_mid > ema200  ET prix au-dessus du ruban
#       SHORT : ema_fast < ema_mid < ema200  ET prix en-dessous du ruban
#     (ema200 = ancre de regime, NON optimisee, pour limiter l'overfitting)
#   - Filtres anti-whipsaw : ADX (force de tendance) + RSI (ni surachat pour les
#     longs, ni survente pour les shorts) + garde volume > 0.
#   - Stop adaptatif a la volatilite (ATR/Chandelier) via custom_stoploss,
#     gere les DEUX sens, avec plancher dur -15% en filet.
#   - ROI desactive pour laisser courir les gains (suivi de tendance).
#
# IMPORTANT (futures) : la config doit etre en "trading_mode": "futures" +
# "margin_mode": "isolated", et les paires au format "ETH/USDT:USDT". Penser au
# cout de funding sur les positions tenues longtemps (verse toutes les 8h).
###############################################################################

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
from datetime import datetime
from functools import reduce

import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (DecimalParameter, IStrategy, IntParameter,
                                stoploss_from_absolute)

# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class ours(IStrategy):

    INTERFACE_VERSION = 3

    # Futures : on autorise le short pour profiter des baisses.
    can_short: bool = True

    # ROI desactive : on laisse courir les gains, sorties par signal + stop ATR.
    minimal_roi = {}

    # Plancher de perte "catastrophe". Le vrai stop (adaptatif) est gere par
    # custom_stoploss ; ce stoploss-ci n'est qu'un filet absolu.
    stoploss = -0.15
    use_custom_stoploss = True
    trailing_stop = False

    # Timeframe (1h conserve ; 4h = moins de bruit/frais si data dispo).
    timeframe = '1h'

    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # ----------------------------- Hyperopt -----------------------------------
    # Jeu de parametres reduit (anti-overfitting). EMA 200 = ancre, non optimisee.
    buy_ema_fast = IntParameter(5, 50, default=21, space='buy', optimize=True, load=True)
    buy_ema_mid = IntParameter(20, 120, default=55, space='buy', optimize=True, load=True)
    buy_adx = IntParameter(15, 40, default=25, space='buy', optimize=True, load=True)

    sell_ema_exit = IntParameter(3, 30, default=9, space='sell', optimize=True, load=True)
    atr_mult = DecimalParameter(1.5, 4.0, decimals=1, default=3.0, space='sell',
                                optimize=True, load=True)

    # RSI : pas d'entree long en surachat ni de short en survente.
    rsi_max = 70   # plafond pour les longs
    rsi_min = 30   # plancher pour les shorts

    ema_anchor = 200
    atr_period = 14

    # EMA200 converge apres ~4x sa periode (~800 bougies) ; 400 = compromis.
    # Verifier avec : freqtrade recursive-analysis --strategy ours
    startup_candle_count: int = 400

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    plot_config = {
        'main_plot': {
            'ema_fast': {'color': 'orange'},
            'ema_mid': {'color': 'green'},
            'ema_anchor': {'color': 'blue'},
        },
        'subplots': {
            "ADX": {'adx': {'color': 'red'}},
            "RSI": {'rsi': {'color': 'purple'}},
        }
    }

    def informative_pairs(self):
        return []

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag,
                 side: str, **kwargs) -> float:
        # Levier 1x : aucune amplification, juste le droit de shorter.
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # "Range trick" : precalcule une EMA par periode candidate (hyperopt ne
        # recalcule pas populate_indicators a chaque epoch). En backtest/live,
        # .range se reduit a la seule valeur choisie.
        for val in self.buy_ema_fast.range:
            dataframe[f'ema_fast_{val}'] = ta.EMA(dataframe, timeperiod=val)
        for val in self.buy_ema_mid.range:
            dataframe[f'ema_mid_{val}'] = ta.EMA(dataframe, timeperiod=val)
        for val in self.sell_ema_exit.range:
            dataframe[f'ema_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)

        dataframe['ema_anchor'] = ta.EMA(dataframe, timeperiod=self.ema_anchor)

        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)

        # Colonnes "actives" pour le plot/lisibilite
        dataframe['ema_fast'] = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        dataframe['ema_mid'] = dataframe[f'ema_mid_{self.buy_ema_mid.value}']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        ema_mid = dataframe[f'ema_mid_{self.buy_ema_mid.value}']

        # --- LONG : ruban empile a la hausse, prix au-dessus ---
        long_cond = [
            ema_fast > ema_mid,
            ema_mid > dataframe['ema_anchor'],
            dataframe['close'] > ema_fast,
            dataframe['adx'] > self.buy_adx.value,
            dataframe['rsi'] < self.rsi_max,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[
            reduce(lambda a, b: a & b, long_cond),
            ['enter_long', 'enter_tag']
        ] = (1, 'ribbon_long')

        # --- SHORT : ruban empile a la baisse, prix en-dessous ---
        short_cond = [
            ema_fast < ema_mid,
            ema_mid < dataframe['ema_anchor'],
            dataframe['close'] < ema_fast,
            dataframe['adx'] > self.buy_adx.value,
            dataframe['rsi'] > self.rsi_min,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[
            reduce(lambda a, b: a & b, short_cond),
            ['enter_short', 'enter_tag']
        ] = (1, 'ribbon_short')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        ema_mid = dataframe[f'ema_mid_{self.buy_ema_mid.value}']
        ema_exit = dataframe[f'ema_exit_{self.sell_ema_exit.value}']

        # Sortie LONG : momentum qui retombe (EMA tres rapide repasse sous la
        # rapide) OU prix qui casse sous l'EMA moyenne.
        exit_long = (
            qtpylib.crossed_below(ema_exit, ema_fast)
            | (dataframe['close'] < ema_mid)
        )
        dataframe.loc[
            exit_long & (dataframe['volume'] > 0),
            ['exit_long', 'exit_tag']
        ] = (1, 'long_fade')

        # Sortie SHORT : symetrique (EMA tres rapide repasse au-dessus de la
        # rapide) OU prix qui repasse au-dessus de l'EMA moyenne.
        exit_short = (
            qtpylib.crossed_above(ema_exit, ema_fast)
            | (dataframe['close'] > ema_mid)
        )
        dataframe.loc[
            exit_short & (dataframe['volume'] > 0),
            ['exit_short', 'exit_tag']
        ] = (1, 'short_fade')

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs):
        """Stop adaptatif a la volatilite (ATR/Chandelier), gere long ET short.

        - LONG  : stop = prix - atr_mult*ATR (en-dessous du prix)
        - SHORT : stop = prix + atr_mult*ATR (au-dessus du prix)
        freqtrade ne resserre le stop que dans le sens favorable (ratchet) : le
        stop "suit" donc la tendance. Le `stoploss` dur (-15%) reste un plancher.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle['atr']
        if atr is None or np.isnan(atr) or atr <= 0:
            return None

        if trade.is_short:
            stop_price = current_rate + (self.atr_mult.value * atr)
            if stop_price <= current_rate:
                return None
        else:
            stop_price = current_rate - (self.atr_mult.value * atr)
            if stop_price >= current_rate:
                return None

        return stoploss_from_absolute(stop_price, current_rate,
                                      is_short=trade.is_short,
                                      leverage=trade.leverage)
