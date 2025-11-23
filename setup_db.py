"""
Database Setup Script - Initialize MongoDB collections and indexes.

Run this script once before first use to set up the database structure.
"""

from pymongo import ASCENDING
from db import get_database, AccountModel, TradeModel
from utils import setup_logger


def setup_indexes():
    """Create indexes for optimal query performance."""
    db = get_database()

    # Accounts collection indexes
    accounts = db['accounts']
    accounts.create_index([('name', ASCENDING)], unique=True)
    accounts.create_index([('type', ASCENDING)])
    accounts.create_index([('enabled', ASCENDING)])

    # Trades collection indexes
    trades = db['trades']
    trades.create_index([('master_ticket', ASCENDING)])
    trades.create_index([('slave_ticket', ASCENDING)])
    trades.create_index([('slave_name', ASCENDING)])
    trades.create_index([('status', ASCENDING)])
    trades.create_index([
        ('master_ticket', ASCENDING),
        ('slave_name', ASCENDING),
        ('status', ASCENDING)
    ])

    return True


def insert_sample_accounts():
    """Insert sample account configurations for testing."""
    accounts = AccountModel.get_collection()

    # Sample Master Account (FTMO)
    master_account = {
        'name': 'FTMO_Master',
        'type': 'MASTER',
        'path': 'C:/Program Files/FTMO MT5/terminal64.exe',
        'enabled': True
    }

    # Sample Slave Accounts
    slave_accounts = [
        {
            'name': 'Apex_Slave_01',
            'type': 'SLAVE',
            'path': 'C:/Program Files/Apex MT5/terminal64.exe',
            'enabled': True,
            'suffix': '.c',
            'symbol_map': {
                'XAUUSD': 'GOLD',
                'US30': 'DJ30'
            },
            'slippage_tolerance': 50
        },
        {
            'name': 'FundedEngineer_Slave_01',
            'type': 'SLAVE',
            'path': 'C:/Program Files/FE MT5/terminal64.exe',
            'enabled': True,
            'suffix': '.pro',
            'symbol_map': {},
            'slippage_tolerance': 30
        },
        {
            'name': 'MyForexFunds_Slave_01',
            'type': 'SLAVE',
            'path': 'C:/Program Files/MFF MT5/terminal64.exe',
            'enabled': False,  # Disabled by default
            'suffix': '.i',
            'symbol_map': {
                'NAS100': 'USTEC'
            },
            'slippage_tolerance': 50
        }
    ]

    # Insert if not exists
    for account in [master_account] + slave_accounts:
        existing = accounts.find_one({'name': account['name']})
        if not existing:
            accounts.insert_one(account)
            print(f"  Inserted: {account['name']}")
        else:
            print(f"  Exists: {account['name']}")


def main():
    """Main setup routine."""
    logger = setup_logger("SETUP")

    logger.info("Setting up database...")

    # Create indexes
    logger.info("Creating indexes...")
    setup_indexes()
    logger.info("Indexes created")

    # Insert sample data
    logger.info("Inserting sample accounts...")
    insert_sample_accounts()
    logger.info("Sample accounts inserted")

    logger.info("Database setup complete!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Update account paths in MongoDB to match your MT5 installations")
    logger.info("2. Configure symbol_map and suffix for each slave account")
    logger.info("3. Set slippage_tolerance as needed")
    logger.info("4. Enable/disable accounts with the 'enabled' field")
    logger.info("5. Run 'python launcher.py' to start the system")


if __name__ == '__main__':
    main()
