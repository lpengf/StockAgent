"""Infrastructure adapters: DB, object storage, market data, LLM.

Everything in this package touches IO. Domain and application layers must
import from here only through explicit dependency injection.
"""
