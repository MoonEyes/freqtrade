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
class abeille(IStrategy):
    
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
    stoploss = -0.328

    # Trailing stoploss
    #trailing_stop = True
    #trailing_stop_positive = 0.05
    #trailing_stop_positive_offset = 0.144
    #trailing_only_offset_is_reached = False

    # Optimal timeframe for the strategy.
    timeframe = '1h'

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = False

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
  
    buy_m1 = IntParameter(1, 7, default=3)
    buy_m2 = IntParameter(1, 7, default=1)
    buy_m3 = IntParameter(1, 7, default=2)
    buy_p1 = IntParameter(7, 21, default=12)
    buy_p2 = IntParameter(7, 21, default=10)
    buy_p3 = IntParameter(7, 21, default=11)
    ema = IntParameter(1, 361, default=200,space='sell', optimize=True, load=True)




    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

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
                'supertrend_1_buy_ST': {'color': 'red'},
                'supertrend_2_buy_ST': {'color': 'green'},
                'supertrend_3_buy_ST': {'color': 'blue'},
                'ema200': {'color': 'orange'},
        },
        'subplots': {
        }
    }

    def informative_pairs(self):
       
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # Momentum Indicators
        # -----------------------------------

        dataframe['ema200'] = ta.EMA(dataframe['close'], timeperiod=self.ema.value)

        dataframe['supertrend_1_buy'] = self.supertrend(dataframe, self.buy_m1.value, self.buy_p1.value)['STX']
        dataframe['supertrend_2_buy'] = self.supertrend(dataframe, self.buy_m2.value, self.buy_p2.value)['STX']
        dataframe['supertrend_3_buy'] = self.supertrend(dataframe, self.buy_m3.value, self.buy_p3.value)['STX']
        dataframe['supertrend_1_buy_ST'] = self.supertrend(dataframe, self.buy_m1.value, self.buy_p1.value)['ST']
        dataframe['supertrend_2_buy_ST'] = self.supertrend(dataframe, self.buy_m2.value, self.buy_p2.value)['ST']
        dataframe['supertrend_3_buy_ST'] = self.supertrend(dataframe, self.buy_m3.value, self.buy_p3.value)['ST']
       
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
               (dataframe['supertrend_1_buy'] == 'up') &
               (dataframe['supertrend_2_buy'] == 'up') & 
               (dataframe['supertrend_3_buy'] == 'up') & 
               (dataframe['close'] > dataframe['ema200'] )& # The three indicators are 'up' for the current candle
               (dataframe['volume'] > 0) # There is at least some trading volume
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
               (dataframe['close'] < dataframe['ema200'] )
            ),

            'exit_long'] = 1

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