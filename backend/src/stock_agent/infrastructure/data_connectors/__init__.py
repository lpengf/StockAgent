"""Market-data connectors. Every implementation adapts an external source to
`MarketInput`. Callers depend on `DataConnector` — never on a concrete impl.
"""

from stock_agent.infrastructure.data_connectors.base import DataConnector, FetchRequest
from stock_agent.infrastructure.data_connectors.demo import DemoConnector
from stock_agent.infrastructure.data_connectors.factory import get_data_connector

__all__ = ["DataConnector", "FetchRequest", "DemoConnector", "get_data_connector"]
