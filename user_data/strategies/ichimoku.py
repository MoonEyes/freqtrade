###############################################################################
# Strategy "ichimoku" - Ichimoku Kinko Hyo (FUTURES long & short, 1x)
# -----------------------------------------------------------------------------
# Variante Ichimoku de la strategie "ours". Meme ossature (futures long+short 1x,
# stop ATR adaptatif, filtre ADX, gestion du risque) mais la TENDANCE est donnee
# par le systeme Ichimoku au lieu du ruban EMA.
#
# Ichimoku = 5 lignes :
#   - Tenkan-sen (conversion, 9)  : (plus haut 9 + plus bas 9) / 2
#   - Kijun-sen  (base, 26)       : (plus haut 26 + plus bas 26) / 2
#   - Senkou A   (nuage, +26)     : (Tenkan + Kijun) / 2, projete 26 en avant
#   - Senkou B   (nuage, +26)     : (plus haut 52 + plus bas 52)/2, projete +26
#   - Chikou     (retard, -26)    : cours, projete 26 en arriere
# Le "nuage" (Kumo) = zone entre Senkou A et B : prix au-dessus = haussier,
# en-dessous = baissier.
#
# /!\ LOOKAHEAD : on n'utilise QUE des shift() POSITIFS (donnees passees).
#   - Senkou A/B au temps t sont calcules a partir de donnees de t-26 -> OK.
#   - Confirmation Chikou : close > close.shift(26) (cours vs cours d'il y a 26)
#     -> comparaison de deux valeurs passees, jamais le futur.
# A verifier avec : freqtrade lookahead-analysis --strategy ichimoku
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


class ichimoku(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    minimal_roi = {}            # laisser courir les gains (suivi de tendance)
    stoploss = -0.15            # plancher "catastrophe"
    use_custom_stoploss = True
    trailing_stop = False

    timeframe = '1h'
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # --- Parametres Ichimoku (standards 9/26/52 ; non optimises = anti-overfit) ---
    tenkan_period = 9
    kijun_period = 26
    senkou_b_period = 52
    displacement = 26

    # --- Hyperopt (jeu reduit) ---
    buy_adx = IntParameter(15, 40, default=25, space='buy', optimize=True, load=True)
    atr_mult = DecimalParameter(1.5, 4.0, decimals=1, default=3.0, space='sell',
                                optimize=True, load=True)
    atr_period = 14

    # 52 (Senkou B) + 26 (displacement) + marge -> ~120 bougies de chauffe.
    startup_candle_count: int = 120

    order_types = {
        'entry': 'limit', 'exit': 'limit',
        'stoploss': 'market', 'stoploss_on_exchange': False
    }
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}

    plot_config = {
        'main_plot': {
            'tenkan': {'color': 'blue'},
            'kijun': {'color': 'red'},
            'senkou_a': {'color': 'green', 'fill_to': 'senkou_b',
                         'fill_label': 'Kumo', 'fill_color': 'rgba(0,200,100,0.2)'},
            'senkou_b': {'color': 'orange'},
        },
        'subplots': {"ADX": {'adx': {'color': 'purple'}}}
    }

    def informative_pairs(self):
        return []

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        high, low, close = dataframe['high'], dataframe['low'], dataframe['close']

        # Tenkan-sen / Kijun-sen (moyennes de canaux Donchian)
        dataframe['tenkan'] = (high.rolling(self.tenkan_period).max()
                               + low.rolling(self.tenkan_period).min()) / 2
        dataframe['kijun'] = (high.rolling(self.kijun_period).max()
                              + low.rolling(self.kijun_period).min()) / 2

        # Nuage (Kumo) : projete 26 en AVANT via shift(+26) -> au temps t, derive
        # de donnees de t-26 (passe) => pas de lookahead.
        dataframe['senkou_a'] = ((dataframe['tenkan'] + dataframe['kijun']) / 2
                                 ).shift(self.displacement)
        dataframe['senkou_b'] = ((high.rolling(self.senkou_b_period).max()
                                  + low.rolling(self.senkou_b_period).min()) / 2
                                 ).shift(self.displacement)

        # Confirmation type "Chikou" sans lookahead : cours vs cours d'il y a 26.
        dataframe['close_past'] = close.shift(self.displacement)

        # Bornes du nuage (haut / bas) pour les tests prix-vs-nuage
        dataframe['kumo_top'] = dataframe[['senkou_a', 'senkou_b']].max(axis=1)
        dataframe['kumo_bottom'] = dataframe[['senkou_a', 'senkou_b']].min(axis=1)

        # Filtres / risque
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- LONG : prix au-dessus du nuage + Tenkan>Kijun + momentum + cloud vert ---
        long_cond = [
            dataframe['close'] > dataframe['kumo_top'],          # au-dessus du Kumo
            dataframe['tenkan'] > dataframe['kijun'],            # croisement TK haussier
            dataframe['senkou_a'] > dataframe['senkou_b'],       # nuage vert (haussier)
            dataframe['close'] > dataframe['close_past'],        # confirmation Chikou
            dataframe['adx'] > self.buy_adx.value,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, long_cond),
                      ['enter_long', 'enter_tag']] = (1, 'ichimoku_long')

        # --- SHORT : miroir (prix sous le nuage, cloud rouge) ---
        short_cond = [
            dataframe['close'] < dataframe['kumo_bottom'],
            dataframe['tenkan'] < dataframe['kijun'],
            dataframe['senkou_a'] < dataframe['senkou_b'],       # nuage rouge (baissier)
            dataframe['close'] < dataframe['close_past'],
            dataframe['adx'] > self.buy_adx.value,
            dataframe['volume'] > 0,
        ]
        dataframe.loc[reduce(lambda a, b: a & b, short_cond),
                      ['enter_short', 'enter_tag']] = (1, 'ichimoku_short')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Sortie LONG : la Tenkan repasse sous la Kijun (TK cross baissier) OU le
        # prix casse sous la Kijun (perte de la base).
        exit_long = (
            qtpylib.crossed_below(dataframe['tenkan'], dataframe['kijun'])
            | (dataframe['close'] < dataframe['kijun'])
        )
        dataframe.loc[exit_long & (dataframe['volume'] > 0),
                      ['exit_long', 'exit_tag']] = (1, 'long_exit')

        # Sortie SHORT : symetrique.
        exit_short = (
            qtpylib.crossed_above(dataframe['tenkan'], dataframe['kijun'])
            | (dataframe['close'] > dataframe['kijun'])
        )
        dataframe.loc[exit_short & (dataframe['volume'] > 0),
                      ['exit_short', 'exit_tag']] = (1, 'short_exit')

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool = False, **kwargs):
        """Stop ATR adaptatif, gere long ET short (cf. strategie 'ours')."""
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
