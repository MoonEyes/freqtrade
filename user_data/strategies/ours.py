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
    can_short: bool = False


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 0.5
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.2

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = '1d'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 100

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
            'ema10': {'color': 'blue'},
                'ema15': {'color': 'red'},
                'ema20': {'color': 'green'},
                'ema25': {'color': 'blue'},
                'ema30': {'color': 'red'},
                'ema40': {'color': 'green'},
                'ema50': {'color': 'red'},
                'ema100': {'color': 'blue'},
           
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
        dataframe['trix9'] = ta.TRIX(dataframe['close'], timeperiod=9)
        dataframe['trix15'] = ta.TRIX(dataframe['close'], timeperiod=15)

        # EMA - Exponential Moving Average
        dataframe['ema15'] = ta.EMA(dataframe['close'], timeperiod=15)
        dataframe['ema20'] = ta.EMA(dataframe['close'], timeperiod=20)
        dataframe['ema25'] = ta.EMA(dataframe['close'], timeperiod=25)
        dataframe['ema30'] = ta.EMA(dataframe['close'], timeperiod=30)
        dataframe['ema40'] = ta.EMA(dataframe['close'], timeperiod=40)
        dataframe['ema45'] = ta.EMA(dataframe['close'], timeperiod=45)
        dataframe['ema50'] = ta.EMA(dataframe['close'], timeperiod=50)
        dataframe['ema100'] = ta.EMA(dataframe['close'], timeperiod=100)
        

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['ema15'] > dataframe['ema20']) &
                (dataframe['ema20'] > dataframe['ema25']) &
                (dataframe['ema25'] > dataframe['ema30']) &
                (dataframe['ema30'] > dataframe['ema40']) &
                (dataframe['ema40'] > dataframe['ema45']) &
                (dataframe['ema45'] > dataframe['ema50']) &
                (dataframe['ema50'] > dataframe['ema100']) &
                (dataframe['close'] > dataframe['ema100'])
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                
                
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['close'] < dataframe['ema100']) 
            ),

            'exit_long'] = 1

        dataframe.loc[
            (
               
            ),
            'exit_short'] = 1

        return dataframe
