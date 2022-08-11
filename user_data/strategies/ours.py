###############################################################################
# Strategy EMA
###############################################################################

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
class ours(IStrategy):
    
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = True


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 1
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.348

    # Trailing stoploss
    #trailing_stop = True  # value loaded from strategy
    #trailing_stop_positive = 0.019  # value loaded from strategy
    #trailing_stop_positive_offset = 0.11  # value loaded from strategy
    #trailing_only_offset_is_reached = True  # value loaded from strategy

    # Optimal timeframe for the strategy.
    timeframe = '1h'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    emalow = IntParameter(low=1, high=55, default=21, space='buy', optimize=True, load=True)
    emahigh = IntParameter(low=10, high=200, default=55, space='buy', optimize=True, load=True)
    emalong = IntParameter(low=55, high=361, default=200, space='buy', optimize=True, load=True)
    emaverylow = IntParameter(low=9, high=90, default=15, space='sell', optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 55

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
                'emalow': {'color': 'red'},
                'emahigh': {'color': 'green'},
                'emalong': {'color': 'blue'},
                'emaverylow': {'color' : 'orange'},
        },
        'subplots': {
        }
    }

    def informative_pairs(self):
       
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Momentum Indicators
        # ------------------------------------

        # TRIX
        dataframe['trix9'] = ta.TRIX(dataframe['close'], timeperiod=15)
        dataframe['trix15'] = ta.TRIX(dataframe['close'], timeperiod=21)

        # EMA - Exponential Moving Average
        dataframe['emaverylow'] = ta.EMA(dataframe['close'], timeperiod=9)
        dataframe['emalow'] = ta.EMA(dataframe['close'], timeperiod=21)
        dataframe['emahigh'] = ta.EMA(dataframe['close'], timeperiod=55)
        dataframe['emalong'] = ta.EMA(dataframe['close'], timeperiod=200)

        

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['emalow'] > dataframe['emahigh']) &
                (dataframe['emahigh'] > dataframe['emalong']) &
                (dataframe['low'] > dataframe['emahigh'] )
            ),
            'enter_long'] = 1
        
        dataframe.loc[
            (
                (dataframe['emalow'] < dataframe['emahigh']) &
                (dataframe['emahigh'] < dataframe['emalong']) &
                (dataframe['low'] < dataframe['emahigh'] )
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['emaverylow'] < dataframe['emalow']) 
            ),

            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['emaverylow'] > dataframe['emalow']) 
            ),
            'exit_short'] = 1

        return dataframe
