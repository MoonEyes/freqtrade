# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# This class is a sample. Feel free to customize it.
class rino(IStrategy):

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = True


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 0.814,
        "4633": 0.36,
        "19238": 0.139,
        "28330": 0
        }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.02

    # Trailing stoploss
    trailing_stop = True  # value loaded from strategy
    trailing_stop_positive = 0.05  # value loaded from strategy
    trailing_stop_positive_offset = 0.0  # value loaded from strategy
    trailing_only_offset_is_reached = False  # value loaded from strategy

    # Optimal timeframe for the strategy.
    timeframe = '1d'

    # Run "populate_indicators()" only for new candle.
    #process_only_new_candles = False

    # These values can be overridden in the config.
    #use_exit_signal = False
    #exit_profit_only = False
    #ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 9

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    plot_config = {
        'main_plot': {
        },
        'subplots': {
            "TRIX": {
            'trix13': {'color': 'blue'},
            'trix34': {'color': 'red'},
            },
            "RSI": {
            'rsi': {'color': 'orange'},
            }
        }
    }


    def informative_pairs(self):
    
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        # Momentum Indicators
        # ------------------------------------
        # EMA - Exponential Moving Average
        dataframe['ema5'] = ta.EMA(dataframe['close'], timeperiod=5)
        dataframe['ema8'] = ta.EMA(dataframe['close'], timeperiod=8)
        dataframe['ema13'] = ta.EMA(dataframe['close'], timeperiod=13)
        dataframe['ema200'] = ta.EMA(dataframe['close'], timeperiod=200)
        dataframe['ema100'] = ta.EMA(dataframe['close'], timeperiod=100)

        # Trix - Triple Exponential Average
        dataframe['trix14'] = ta.TRIX(dataframe['close'], timeperiod=14)
        dataframe['trix8'] = ta.TRIX(dataframe['close'], timeperiod=8)
        dataframe['trix9'] = ta.TRIX(dataframe['close'], timeperiod=9)
        dataframe['trix34'] = ta.TRIX(dataframe['close'], timeperiod=34)
        dataframe['trix13'] = ta.TRIX(dataframe['close'], timeperiod=13)

        # RSI - Relative Strength Index
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    
        dataframe.loc[
            (
                (dataframe['trix13'] > dataframe['trix34']) &
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi.value)) 
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['trix13'] < dataframe['trix34']) &
                (qtpylib.crossed_above(dataframe['rsi'], self.short_rsi.value)) 
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
               (dataframe['trix13'] < dataframe['trix34']) &
               (qtpylib.crossed_above(dataframe['rsi'], self.sell_rsi.value)) 
            ),

            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['trix13'] > dataframe['trix34']) &
                (qtpylib.crossed_above(dataframe['rsi'], self.exit_short_rsi.value)) 
            ),
            'exit_short'] = 1

        return dataframe
