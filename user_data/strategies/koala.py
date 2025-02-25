###############################################################################
# Strategy EMA + Pull back + Supertrend
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
class koala(IStrategy):
    
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False


    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "0": 1
        #"5": 0.15,
        #"10": 0.10,
        #"15": 0.05
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
    timeframe = '5m'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    emalow = IntParameter(low=1, high=55, default=20, space='buy', optimize=True, load=True)
    emahigh = IntParameter(low=10, high=200, default=55, space='buy', optimize=True, load=True)
    emalong = IntParameter(low=55, high=361, default=200, space='buy', optimize=True, load=True)
    supertrend_m = IntParameter(low=5, high=20, default=3, space='buy', optimize=True, load=True)
    supertrend_p = IntParameter(low=5, high=100, default=10, space='buy', optimize=True, load=True)
    supertrend_m_sell = IntParameter(low=5, high=20, default=supertrend_m.value, space='sell', optimize=True, load=True)
    supertrend_p_sell = IntParameter(low=5, high=100, default=supertrend_p.value, space='sell', optimize=True, load=True)

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
                'supertrend_1_ST': {'color': 'orange'}
        },
        'subplots': {
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

        # TRIX
        dataframe['trix9'] = ta.TRIX(dataframe['close'], timeperiod=9)
        dataframe['trix15'] = ta.TRIX(dataframe['close'], timeperiod=21)

        # EMA - Exponential Moving Average
        dataframe['emalow'] = ta.EMA(dataframe['close'], timeperiod=self.emalow.value)
        dataframe['emahigh'] = ta.EMA(dataframe['close'], timeperiod=self.emahigh.value)
        dataframe['emalong'] = ta.EMA(dataframe['close'], timeperiod=self.emalong.value)

        # MA - Moving Average
        dataframe['ma361'] = ta.MA(dataframe['close'], timeperiod=361)

        # RSI - Relative Strength Index
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=55)

        #SuperTrend 
        dataframe['supertrend_1'] = self.supertrend(dataframe, self.supertrend_m.value, self.supertrend_p.value)['STX']
        dataframe['supertrend_1_ST'] = self.supertrend(dataframe, self.supertrend_m.value, self.supertrend_p.value)['ST']
        

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['emalow'] > dataframe['supertrend_1_ST']) &
                (dataframe['supertrend_1'] == 'up') &
                (dataframe['close'] > dataframe['emalow'])

            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['emalow'] < dataframe['supertrend_1_ST']) &
                (dataframe['supertrend_1'] == 'down') &
                (dataframe['close'] < dataframe['emalow'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['supertrend_1'] == 'down')  
            ),

            'exit_long'] = 1

        dataframe.loc[
            (   
                (dataframe['supertrend_1'] == 'up')  
            ),

            'exit_short'] = 1

        return dataframe


    def supertrend(self, dataframe: DataFrame, multiplier, period):
        df = dataframe.copy()

        df['TR'] = ta.TRANGE(df)
        df['ATR'] = ta.SMA(df['TR'], period)

        st = 'ST_' + str(period) + '_' + str(multiplier)
        stx = 'STX_' + str(period) + '_' + str(multiplier)

        # Compute basic upper and lower bands
        df['basic_ub'] = (df['high'] + df['low']) / 2 + multiplier * df['ATR']
        df['basic_lb'] = (df['high'] + df['low']) / 2 - multiplier * df['ATR']

        # Compute final upper and lower bands
        df['final_ub'] = 0.00
        df['final_lb'] = 0.00
        for i in range(period, len(df)):
            df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else df['final_ub'].iat[i - 1]
            df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else df['final_lb'].iat[i - 1]

        # Set the Supertrend value
        df[st] = 0.00
        for i in range(period, len(df)):
            df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] <= df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] >  df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] >= df['final_lb'].iat[i] else \
                            df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] <  df['final_lb'].iat[i] else 0.00
        # Mark the trend direction up/down
        df[stx] = np.where((df[st] > 0.00), np.where((df['close'] < df[st]), 'down',  'up'), np.NaN)

        # Remove basic and final bands from the columns
        df.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb'], inplace=True, axis=1)

        df.fillna(0, inplace=True)

        return DataFrame(index=df.index, data={
            'ST' : df[st],
            'STX' : df[stx]
        })