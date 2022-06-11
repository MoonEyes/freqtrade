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
class lapin(IStrategy):
    """
    This is a sample strategy to inspire you.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 0.283,
        "256": 0.072,
        "730": 0.04,
        "1500": 0
        }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.333

    # Trailing stoploss
    #trailing_stop = True
    #trailing_only_offset_is_reached = False
    #trailing_stop_positive = 0.05
    #trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = '1h'

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
    startup_candle_count: int = 10

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
                #'ema5': {'color': 'blue'},
                #'ema8': {'color': 'red'},
                #'ema13': {'color': 'green'},
                'ema100': {'color': 'blue'},
                'ema200': {'color': 'orange'},
        },
        'subplots': {
            
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

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    
        dataframe.loc[
            (
                ##(dataframe['ema5'] > dataframe['ema8']) &
                #(dataframe['ema8'] > dataframe['ema13']) &
                #(dataframe['high'] > dataframe['ema5']) &
                (dataframe['close'] > dataframe['ema200'])
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                #(dataframe['ema5'] < dataframe['ema8']) &
                #(dataframe['ema8'] < dataframe['ema13']) &
                #(dataframe['low'] < dataframe['ema5']) 
                (dataframe['close'] < dataframe['ema200']) 
                
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (   
               # (dataframe['close'] < dataframe['ema5']) 
                (dataframe['close'] < dataframe['ema100'])
            ),

            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema100'])
                #(dataframe['close'] > dataframe['ema5']) 
                
            ),
            'exit_short'] = 1

        return dataframe
