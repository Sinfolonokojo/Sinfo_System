"""
MongoDB connection manager with singleton pattern.
"""

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure
import config

_client: MongoClient = None
_database: Database = None


def get_client() -> MongoClient:
    """
    Get or create MongoDB client singleton.

    Returns:
        MongoClient: The MongoDB client instance.

    Raises:
        ConnectionFailure: If unable to connect to MongoDB.
    """
    global _client

    if _client is None:
        _client = MongoClient(
            config.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        # Verify connection
        try:
            _client.admin.command('ping')
        except ConnectionFailure as e:
            _client = None
            raise ConnectionFailure(f"Failed to connect to MongoDB: {e}")

    return _client


def get_database() -> Database:
    """
    Get the trading database instance.

    Returns:
        Database: The prop_copy_trader database.
    """
    global _database

    if _database is None:
        client = get_client()
        _database = client[config.DATABASE_NAME]

    return _database


def close_connection():
    """Close the MongoDB connection."""
    global _client, _database

    if _client is not None:
        _client.close()
        _client = None
        _database = None
