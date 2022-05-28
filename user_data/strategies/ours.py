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
        "0": 0.3
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.10

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
    startup_candle_count: int = 30

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
                'trix9': {'color': 'blue'},
                'trix15': {'color': 'orange'},
            }
        }
    }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        # Momentum Indicators
        # ------------------------------------

        # TRIX
        dataframe['trix9'] = ta.TRIX(dataframe['close'], timeperiod=9)
        dataframe['trix15'] = ta.TRIX(dataframe['close'], timeperiod=15)

        # # SMA - Simple Moving Average
        dataframe['sma20'] = ta.SMA(dataframe['close'], timeperiod=20)
        dataframe['sma60'] = ta.SMA(dataframe['close'], timeperiod=60)
        dataframe['sma200'] = ta.SMA(dataframe['close'], timeperiod=200)
        dataframe['sma250'] = ta.SMA(dataframe['close'], timeperiod=250)
        

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                # Trix signals (9, 15)
                (dataframe['trix9'] > dataframe['trix15'])  # Make sure it's increasing
                #(dataframe['sma20'] > 26000) & # Make sure it's above 26000
                #(dataframe['sma60'] > 20) & # Make sure it's above 20
                #(dataframe['close'] > dataframe['sma200']) & # Make sure it's above 200
                #(dataframe['volume'] > dataframe['sma250']) &  # Make sure Volume is not 0
                #(dataframe['trix9'] > 0) &  # Make sure it's above 0
                #(dataframe['trix15'] > 0) 
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['trix9'] < dataframe['trix15']) &
                (dataframe['trix9'] < 0) &
                (dataframe['trix15'] < 0)
                # Signal: RSI crosses above 70
                #(qtpylib.crossed_above(dataframe['rsi'], self.short_rsi.value)) &
                #(dataframe['tema'] > dataframe['bb_middleband']) &  # Guard: tema above BB middle
                #(dataframe['tema'] < dataframe['tema'].shift(1)) &  # Guard: tema is falling
                #(dataframe['volume'] > 0)  # Make sure Volume is not 0
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
                (dataframe['trix15'] > dataframe['trix9']) 
                # Signal: RSI crosses above 70
                #(qtpylib.crossed_above(dataframe['rsi'], self.sell_rsi.value)) &
                #(dataframe['tema'] > dataframe['bb_middleband']) &  # Guard: tema above BB middle
                #(dataframe['tema'] < dataframe['tema'].shift(1)) &  # Guard: tema is falling
                #(dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),

            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['trix15'] < dataframe['trix9'])
                # Signal: RSI crosses above 30
                #(qtpylib.crossed_above(dataframe['rsi'], self.exit_short_rsi.value)) &
                # Guard: tema below BB middle
                #(dataframe['tema'] <= dataframe['bb_middleband']) &
                #(dataframe['tema'] > dataframe['tema'].shift(1)) &  # Guard: tema is raising
                #(dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            'exit_short'] = 1

        return dataframe
