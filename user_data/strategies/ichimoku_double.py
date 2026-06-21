###############################################################################
# Strategy "ichimoku_double" - Double Ichimoku (FUTURES long & short, 1x)
# -----------------------------------------------------------------------------
# Deux Ichimoku superposes sur la meme unite de temps :
#   - LENT  (18/52/104, displacement 52) = FILTRE de tendance de fond.
#       Long autorise si prix AU-DESSUS du nuage lent ET nuage lent haussier.
#       Short autorise si prix EN-DESSOUS ET nuage lent baissier.
#   - RAPIDE (9/26/52, displacement 26)  = DECLENCHEUR (timing).
#       Entree sur croisement Tenkan/Kijun rapide, dans le sens autorise par le
#       filtre lent, prix du bon cote du nuage rapide.
#
# Meme ossature que "ours"/"ichimoku" : futures long+short 1x, stop ATR adaptatif,
# filtre ADX, gestion du risque. Periodes fixes (anti-overfit) ; seuls buy_adx et
# atr_mult sont hyperoptables.
#
# /!\ LOOKAHEAD : Ichimoku calcule a la main avec uniquement des shift() POSITIFS
# (le nuage au temps t derive de donnees de t-displacement = passe). A confirmer
# via : freqtrade lookahead-analysis --strategy ichimoku_double
###############################################################################

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
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


def add_ichimoku(df: DataFrame, tenkan: int, kijun: int, senkou_b: int,
                 disp: int, prefix: str) -> DataFrame:
    """Ajoute un jeu Ichimoku (colonnes prefixees). shift() POSITIF = pas de lookahead."""
    high, low = df['high'], df['low']
    df[f'{prefix}_tenkan'] = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    df[f'{prefix}_kijun'] = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    df[f'{prefix}_sa'] = ((df[f'{prefix}_tenkan'] + df[f'{prefix}_kijun']) / 2).shift(disp)
    df[f'{prefix}_sb'] = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(disp)
    df[f'{prefix}_top'] = df[[f'{prefix}_sa', f'{prefix}_sb']].max(axis=1)
    df[f'{prefix}_bottom'] = df[[f'{prefix}_sa', f'{prefix}_sb']].min(axis=1)
    return df


class ichimoku_double(IStrategy):

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

    # Ichimoku RAPIDE (declencheur) et LENT (filtre)
    f_tenkan, f_kijun, f_senkou_b, f_disp = 9, 26, 52, 26
    s_tenkan, s_kijun, s_senkou_b, s_disp = 18, 52, 104, 52

    # Hyperopt (jeu reduit)
    buy_adx = IntParameter(15, 40, default=25, space='buy', optimize=True, load=True)
    atr_mult = DecimalParameter(1.5, 4.0, decimals=1, default=3.0, space='sell',
                                optimize=True, load=True)
    atr_period = 14

    # Lent : senkou_b 104 + displacement 52 = ~156 -> 200 bougies de chauffe.
    startup_candle_count: int = 200

    order_types = {
        'entry': 'limit', 'exit': 'limit',
        'stoploss': 'market', 'stoploss_on_exchange': False
    }
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}

    plot_config = {
        'main_plot': {
            'f_tenkan': {'color': 'blue'},
            'f_kijun': {'color': 'red'},
            's_sa': {'color': 'green', 'fill_to': 's_sb',
                     'fill_label': 'Kumo lent', 'fill_color': 'rgba(0,150,80,0.2)'},
            's_sb': {'color': 'orange'},
        },
        'subplots': {"ADX": {'adx': {'color': 'purple'}}}
    }

    def informative_pairs(self):
        return []

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = add_ichimoku(dataframe, self.f_tenkan, self.f_kijun,
                                 self.f_senkou_b, self.f_disp, 'f')
        dataframe = add_ichimoku(dataframe, self.s_tenkan, self.s_kijun,
                                 self.s_senkou_b, self.s_disp, 's')
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FILTRE lent (tendance de fond)
        slow_bull = (dataframe['close'] > dataframe['s_top']) & (dataframe['s_sa'] > dataframe['s_sb'])
        slow_bear = (dataframe['close'] < dataframe['s_bottom']) & (dataframe['s_sa'] < dataframe['s_sb'])

        # DECLENCHEUR rapide (croisement Tenkan/Kijun) + prix du bon cote du nuage rapide
        long_cond = [
            slow_bull,
            qtpylib.crossed_above(dataframe['f_tenkan'], dataframe['f_kijun']),
            dataframe['adx'] > self.buy_adx.value,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, long_cond),
                      ['enter_long', 'enter_tag']] = (1, 'dbl_ichi_long')

        short_cond = [
            slow_bear,
            qtpylib.crossed_below(dataframe['f_tenkan'], dataframe['f_kijun']),
            dataframe['adx'] > self.buy_adx.value,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, short_cond),
                      ['enter_short', 'enter_tag']] = (1, 'dbl_ichi_short')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Sortie sur le RAPIDE : croisement TK inverse OU cassure de la Kijun rapide.
        exit_long = (
            qtpylib.crossed_below(dataframe['f_tenkan'], dataframe['f_kijun'])
            | (dataframe['close'] < dataframe['f_kijun'])
        )
        dataframe.loc[exit_long & (dataframe['volume'] > 0),
                      ['exit_long', 'exit_tag']] = (1, 'long_exit')

        exit_short = (
            qtpylib.crossed_above(dataframe['f_tenkan'], dataframe['f_kijun'])
            | (dataframe['close'] > dataframe['f_kijun'])
        )
        dataframe.loc[exit_short & (dataframe['volume'] > 0),
                      ['exit_short', 'exit_tag']] = (1, 'short_exit')

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs):
        """Stop ATR adaptatif, gere long ET short."""
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
