"""Market-data providers.

All providers implement the :class:`~xau_ai.data.base.DataProvider` protocol, so
new sources (MT5, OANDA, TwelveData, ...) plug in without changing callers.
"""

from xau_ai.data.base import DataProvider
from xau_ai.data.csv_provider import CsvDataProvider

__all__ = ["CsvDataProvider", "DataProvider"]
