###############################################################################
# Strategy "ours_regime" - "ours" + FILTRE DE REGIME (pente EMA200)
# -----------------------------------------------------------------------------
# Identique a "ours" (ruban EMA, futures long+short 1x, stop ATR) MAIS on
# n'autorise une direction que si la tendance de fond va dans ce sens :
#   - LONG  seulement si l'EMA200 MONTE (ema_anchor > ema_anchor il y a N bougies)
#   - SHORT seulement si l'EMA200 DESCEND
#
# Pourquoi : le test multi-annees a montre que "ours" se fait saigner en SHORT
# pendant les marches haussiers (le short perd -15% sur 2020-2024). Exiger que la
# tendance de fond descende vraiment avant de shorter coupe ce saignement, tout en
# gardant la capacite a profiter des vrais bear markets (ou l'EMA200 descend).
#
# La pente est mesuree par un shift() POSITIF (donnees passees) -> pas de lookahead.
###############################################################################

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
from datetime import datetime
from functools import reduce

import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (DecimalParameter, IStrategy, IntParameter,
                                stoploss_from_absolute)

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class ours_regime(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    minimal_roi = {}
    stoploss = -0.15
    use_custom_stoploss = True
    trailing_stop = False

    timeframe = '1h'
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperopt (identique a "ours")
    buy_ema_fast = IntParameter(5, 50, default=21, space='buy', optimize=True, load=True)
    buy_ema_mid = IntParameter(20, 120, default=55, space='buy', optimize=True, load=True)
    buy_adx = IntParameter(15, 40, default=25, space='buy', optimize=True, load=True)

    sell_ema_exit = IntParameter(3, 30, default=9, space='sell', optimize=True, load=True)
    atr_mult = DecimalParameter(1.5, 4.0, decimals=1, default=3.0, space='sell',
                                optimize=True, load=True)

    rsi_max = 70
    rsi_min = 30

    ema_anchor = 200
    atr_period = 14

    # Filtre de regime : sur combien de bougies on mesure la pente de l'EMA200.
    # 50 = compromis (sur 1d = ~7 semaines de tendance de fond ; sur 1h = ~2 jours).
    regime_lookback = 50

    # EMA200 (400) + recul de pente (50) -> 450 bougies de chauffe.
    startup_candle_count: int = 450

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

    # --- Protections (garde-fous "vie reelle") ---
    # Le backtest sous-estime les series de pertes ; ces protections coupent le
    # bot quand ca tourne mal. Actives en live/dry-run ; en backtest il faut
    # l'option --enable-protections.
    @property
    def protections(self):
        return [
            # Pas de re-entree immediate sur une paire qu'on vient de quitter.
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 2,
            },
            # Stoppe une paire si elle enchaine les stoploss (marche qui part contre nous).
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 12,
                "only_per_pair": False,
            },
            # Coupe TOUT le bot si le drawdown global devient trop fort.
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 96,
                "trade_limit": 10,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.15,
            },
        ]

    def informative_pairs(self):
        return []

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag,
                 side: str, **kwargs) -> float:
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for val in self.buy_ema_fast.range:
            dataframe[f'ema_fast_{val}'] = ta.EMA(dataframe, timeperiod=val)
        for val in self.buy_ema_mid.range:
            dataframe[f'ema_mid_{val}'] = ta.EMA(dataframe, timeperiod=val)
        for val in self.sell_ema_exit.range:
            dataframe[f'ema_exit_{val}'] = ta.EMA(dataframe, timeperiod=val)

        dataframe['ema_anchor'] = ta.EMA(dataframe, timeperiod=self.ema_anchor)
        # Valeur de l'EMA200 il y a `regime_lookback` bougies (shift positif = passe)
        dataframe['ema_anchor_past'] = dataframe['ema_anchor'].shift(self.regime_lookback)

        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)

        dataframe['ema_fast'] = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        dataframe['ema_mid'] = dataframe[f'ema_mid_{self.buy_ema_mid.value}']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        ema_mid = dataframe[f'ema_mid_{self.buy_ema_mid.value}']

        # Regime de fond : tendance de l'EMA200
        regime_up = dataframe['ema_anchor'] > dataframe['ema_anchor_past']
        regime_down = dataframe['ema_anchor'] < dataframe['ema_anchor_past']

        # --- LONG : ruban haussier ET regime de fond haussier ---
        long_cond = [
            regime_up,
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
        ] = (1, 'ribbon_long_reg')

        # --- SHORT : ruban baissier ET regime de fond baissier ---
        short_cond = [
            regime_down,
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
        ] = (1, 'ribbon_short_reg')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = dataframe[f'ema_fast_{self.buy_ema_fast.value}']
        ema_mid = dataframe[f'ema_mid_{self.buy_ema_mid.value}']
        ema_exit = dataframe[f'ema_exit_{self.sell_ema_exit.value}']

        exit_long = (
            qtpylib.crossed_below(ema_exit, ema_fast)
            | (dataframe['close'] < ema_mid)
        )
        dataframe.loc[
            exit_long & (dataframe['volume'] > 0),
            ['exit_long', 'exit_tag']
        ] = (1, 'long_fade')

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
        """Stop ATR adaptatif, gere long ET short (identique a 'ours')."""
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
