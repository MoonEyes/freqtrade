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
from technical.indicators import ichimoku



# This class is a sample. Feel free to customize it.
class lapin(IStrategy):
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 1
        }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.1

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.15
    trailing_stop_positive_offset = 0.20
    trailing_only_offset_is_reached = True

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
                'tenkan': {'color': 'yellow'},
                'kijun': {'color': 'orange'},
                'senkou_a': {'color': 'green'},
                'senkou_b': {'color': 'red'},
                'cloud_green': {'color': 'green'},
                'cloud_red': {'color': 'red'},
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

        # Ichimoku Indicators
        ichi=ichimoku(dataframe)
        dataframe['tenkan']=ichi['tenkan_sen']
        dataframe['kijun']=ichi['kijun_sen']
        dataframe['senkou_a']=ichi['senkou_span_a']
        dataframe['senkou_b']=ichi['senkou_span_b']
        dataframe['cloud_green']=ichi['cloud_green']
        dataframe['cloud_red']=ichi['cloud_red']
        dataframe['lagging_span']=ichi['lagging_span']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['kijun']) &
                (dataframe['close'] > dataframe['senkou_a']) &
                (dataframe['lagging_span'] > dataframe['cloud_green'])
                (dataframe['cloud_green']==True)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['kijun']) &
                (dataframe['close'] < dataframe['senkou_a']) &
                (dataframe['lagging_span'] > dataframe['cloud_red'])
                (dataframe['cloud_red']==True)
                
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
