"""
Database models for accounts and trades collections.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo.collection import Collection
from .connection import get_database


class AccountModel:
    """Model for managing account documents."""

    @staticmethod
    def get_collection() -> Collection:
        """Get the accounts collection."""
        return get_database()['accounts']

    @classmethod
    def get_all_enabled(cls) -> List[Dict[str, Any]]:
        """
        Fetch all enabled accounts.

        Returns:
            List of account documents where enabled=True.
        """
        return list(cls.get_collection().find({'enabled': True}))

    @classmethod
    def get_by_name(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch account by name.

        Args:
            name: Unique account identifier.

        Returns:
            Account document or None if not found.
        """
        return cls.get_collection().find_one({'name': name})

    @classmethod
    def get_master_accounts(cls) -> List[Dict[str, Any]]:
        """Fetch all enabled master accounts."""
        return list(cls.get_collection().find({
            'enabled': True,
            'type': 'MASTER'
        }))

    @classmethod
    def get_slave_accounts(cls) -> List[Dict[str, Any]]:
        """Fetch all enabled slave accounts."""
        return list(cls.get_collection().find({
            'enabled': True,
            'type': 'SLAVE'
        }))

    @classmethod
    def create(cls, account_data: Dict[str, Any]) -> str:
        """
        Create a new account document.

        Args:
            account_data: Account configuration dict.

        Returns:
            Inserted document ID as string.
        """
        result = cls.get_collection().insert_one(account_data)
        return str(result.inserted_id)

    @classmethod
    def update(cls, name: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an account by name.

        Args:
            name: Account identifier.
            update_data: Fields to update.

        Returns:
            True if document was modified.
        """
        result = cls.get_collection().update_one(
            {'name': name},
            {'$set': update_data}
        )
        return result.modified_count > 0


class TradeModel:
    """Model for managing trade mapping documents."""

    @staticmethod
    def get_collection() -> Collection:
        """Get the trades collection."""
        return get_database()['trades']

    @classmethod
    def create_mapping(
        cls,
        master_ticket: int,
        slave_ticket: int,
        slave_name: str,
        symbol: str,
        direction: str
    ) -> str:
        """
        Create a new trade mapping.

        Args:
            master_ticket: Ticket ID from master broker.
            slave_ticket: Ticket ID from slave broker.
            slave_name: Identifier of the slave account.
            symbol: Symbol traded on the slave.
            direction: "BUY" or "SELL".

        Returns:
            Inserted document ID as string.
        """
        trade_doc = {
            'master_ticket': master_ticket,
            'slave_ticket': slave_ticket,
            'slave_name': slave_name,
            'symbol': symbol,
            'direction': direction,
            'status': 'OPEN',
            'open_time': datetime.utcnow()
        }
        result = cls.get_collection().insert_one(trade_doc)
        return str(result.inserted_id)

    @classmethod
    def get_slave_ticket(cls, master_ticket: int, slave_name: str) -> Optional[int]:
        """
        Get slave ticket for a master ticket.

        Args:
            master_ticket: The master broker ticket ID.
            slave_name: The slave account name.

        Returns:
            Slave ticket ID or None if not found.
        """
        doc = cls.get_collection().find_one({
            'master_ticket': master_ticket,
            'slave_name': slave_name,
            'status': 'OPEN'
        })
        return doc['slave_ticket'] if doc else None

    @classmethod
    def close_trade(cls, master_ticket: int, slave_name: str) -> bool:
        """
        Mark a trade as closed.

        Args:
            master_ticket: The master broker ticket ID.
            slave_name: The slave account name.

        Returns:
            True if document was modified.
        """
        result = cls.get_collection().update_one(
            {
                'master_ticket': master_ticket,
                'slave_name': slave_name,
                'status': 'OPEN'
            },
            {
                '$set': {
                    'status': 'CLOSED',
                    'close_time': datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0

    @classmethod
    def get_open_trades_by_slave(cls, slave_name: str) -> List[Dict[str, Any]]:
        """
        Get all open trades for a slave account.

        Args:
            slave_name: The slave account name.

        Returns:
            List of open trade documents.
        """
        return list(cls.get_collection().find({
            'slave_name': slave_name,
            'status': 'OPEN'
        }))

    @classmethod
    def get_all_open_trades(cls) -> List[Dict[str, Any]]:
        """Get all open trades across all slaves."""
        return list(cls.get_collection().find({'status': 'OPEN'}))
