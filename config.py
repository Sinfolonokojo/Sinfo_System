"""
Configuration constants for the Prop Firm Copy Trading System.
"""

# MongoDB Configuration
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "prop_copy_trader"

# ZeroMQ Configuration
ZMQ_PUB_PORT = 5555
ZMQ_PUB_ADDRESS = f"tcp://127.0.0.1:{ZMQ_PUB_PORT}"

# Polling Configuration
MASTER_POLL_INTERVAL_MS = 100  # Milliseconds between position checks
SLAVE_RECONNECT_DELAY_S = 5   # Seconds to wait before reconnecting

# Trading Configuration
DEFAULT_SLIPPAGE_TOLERANCE = 50  # Points
DEFAULT_MAGIC_NUMBER = 234000

# Logging
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
