"""
Config Manager - Automated Configuration Management.

Safely applies parameters and switches strategies without manual editing.
"""

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger

logger = setup_logger("CONFIG_MGR")


class ConfigManager:
    """Manages bot configuration file modifications."""

    def __init__(self, config_file: str = "bot/config.py"):
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

    def backup_config(self) -> Path:
        """
        Create a timestamped backup of the config file.

        Returns:
            Path to backup file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path("bot/config_backups")
        backup_dir.mkdir(exist_ok=True)

        backup_file = backup_dir / f"config_backup_{timestamp}.py"
        shutil.copy2(self.config_file, backup_file)

        logger.info(f"Created config backup: {backup_file}")
        return backup_file

    def apply_parameters(
        self,
        params: Dict[str, Any],
        backup: bool = True,
        dry_run: bool = False
    ) -> bool:
        """
        Apply parameters to STRATEGY_CONFIG in config file.

        Args:
            params: Dictionary of parameter names and values.
            backup: Whether to create backup before modifying.
            dry_run: If True, only show what would be changed.

        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Applying {len(params)} parameters to config")

        # Read current config
        with open(self.config_file, 'r') as f:
            content = f.read()

        # Create backup if requested
        if backup and not dry_run:
            self.backup_config()

        # Apply each parameter
        modified_content = content
        changes = []

        for param_name, param_value in params.items():
            # Find the parameter line in STRATEGY_CONFIG
            # Pattern: '    'param_name': value,
            pattern = rf"(\s*['\"]?{re.escape(param_name)}['\"]?\s*:\s*)([^,\n]+)(,?)"

            # Format the new value based on type
            if isinstance(param_value, str):
                new_value = f"'{param_value}'"
            elif isinstance(param_value, bool):
                new_value = str(param_value)
            elif isinstance(param_value, (int, float)):
                new_value = str(param_value)
            else:
                new_value = str(param_value)

            # Check if parameter exists
            match = re.search(pattern, modified_content)
            if match:
                old_value = match.group(2).strip()
                replacement = f"{match.group(1)}{new_value}{match.group(3)}"
                modified_content = re.sub(pattern, replacement, modified_content)
                changes.append(f"  {param_name}: {old_value} -> {new_value}")
                logger.info(f"Updated {param_name}: {old_value} -> {new_value}")
            else:
                logger.warning(f"Parameter not found in config: {param_name}")

        if not changes:
            logger.warning("No parameters were updated")
            return False

        # Show changes
        logger.info("=" * 60)
        logger.info("PARAMETER CHANGES:")
        logger.info("=" * 60)
        for change in changes:
            logger.info(change)
        logger.info("=" * 60)

        if dry_run:
            logger.info("DRY RUN - No changes were made")
            return True

        # Write modified config
        with open(self.config_file, 'w') as f:
            f.write(modified_content)

        logger.info(f"Successfully updated {len(changes)} parameters in {self.config_file}")
        return True

    def set_active_strategy(
        self,
        strategy_name: str,
        backup: bool = True,
        dry_run: bool = False
    ) -> bool:
        """
        Set the active strategy in config file.

        Args:
            strategy_name: Name of strategy (elastic_band, fvg, macd_rsi, elastic_bb).
            backup: Whether to create backup before modifying.
            dry_run: If True, only show what would be changed.

        Returns:
            True if successful, False otherwise.
        """
        # Validate strategy name
        valid_strategies = ['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb']
        if strategy_name.lower() not in valid_strategies:
            logger.error(f"Invalid strategy: {strategy_name}. Must be one of: {valid_strategies}")
            return False

        strategy_name = strategy_name.lower()
        strategy_enum_map = {
            'elastic_band': 'ELASTIC_BAND',
            'fvg': 'FVG',
            'macd_rsi': 'MACD_RSI',
            'elastic_bb': 'ELASTIC_BB'
        }

        logger.info(f"Setting active strategy to: {strategy_name}")

        # Read current config
        with open(self.config_file, 'r') as f:
            content = f.read()

        # Create backup if requested
        if backup and not dry_run:
            self.backup_config()

        # Find current strategy
        pattern = r"(ACTIVE_STRATEGY\s*=\s*StrategyType\.)(\w+)"
        match = re.search(pattern, content)

        if not match:
            logger.error("Could not find ACTIVE_STRATEGY in config file")
            return False

        old_strategy = match.group(2)
        new_strategy = strategy_enum_map[strategy_name]

        logger.info(f"Changing strategy: {old_strategy} -> {new_strategy}")

        if dry_run:
            logger.info("DRY RUN - No changes were made")
            return True

        # Replace strategy
        modified_content = re.sub(
            pattern,
            rf"\1{new_strategy}",
            content
        )

        # Write modified config
        with open(self.config_file, 'w') as f:
            f.write(modified_content)

        logger.info(f"Successfully set active strategy to {strategy_name}")
        return True

    def get_current_strategy(self) -> str:
        """
        Get the currently active strategy from config file.

        Returns:
            Strategy name (elastic_band, fvg, macd_rsi, elastic_bb).
        """
        with open(self.config_file, 'r') as f:
            content = f.read()

        pattern = r"ACTIVE_STRATEGY\s*=\s*StrategyType\.(\w+)"
        match = re.search(pattern, content)

        if not match:
            logger.error("Could not find ACTIVE_STRATEGY in config file")
            return None

        strategy_map = {
            'ELASTIC_BAND': 'elastic_band',
            'FVG': 'fvg',
            'MACD_RSI': 'macd_rsi',
            'ELASTIC_BB': 'elastic_bb'
        }

        return strategy_map.get(match.group(1), match.group(1).lower())

    def apply_from_file(
        self,
        params_file: str,
        param_type: str = 'best',
        backup: bool = True,
        dry_run: bool = False
    ) -> bool:
        """
        Apply parameters from a JSON file (from grid search results).

        Args:
            params_file: Path to JSON file with parameters.
            param_type: Type of params to apply ('best', 'profit', 'win_rate', 'drawdown', 'risk_adjusted').
            backup: Whether to create backup before modifying.
            dry_run: If True, only show what would be changed.

        Returns:
            True if successful, False otherwise.
        """
        params_path = Path(params_file)
        if not params_path.exists():
            logger.error(f"Parameters file not found: {params_file}")
            return False

        # Load parameters
        with open(params_path, 'r') as f:
            data = json.load(f)

        # Handle different file formats
        params = None

        # Check if it's a recommended_params.json file
        if param_type in data:
            params = data[param_type].get('parameters', data[param_type])
        # Check if it's a best_params.json file
        elif 'parameters' in data:
            params = data['parameters']
        # Direct parameter dictionary
        else:
            params = data

        if not params:
            logger.error(f"Could not find parameters in file: {params_file}")
            return False

        logger.info(f"Loaded parameters from: {params_file}")
        if param_type != 'best':
            logger.info(f"Using parameter type: {param_type}")

        return self.apply_parameters(params, backup=backup, dry_run=dry_run)

    def restore_backup(self, backup_file: str) -> bool:
        """
        Restore config from a backup file.

        Args:
            backup_file: Path to backup file.

        Returns:
            True if successful, False otherwise.
        """
        backup_path = Path(backup_file)
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False

        # Create a backup of current config before restoring
        self.backup_config()

        # Restore from backup
        shutil.copy2(backup_path, self.config_file)
        logger.info(f"Restored config from backup: {backup_file}")
        return True

    def list_backups(self) -> list:
        """
        List all available config backups.

        Returns:
            List of backup file paths.
        """
        backup_dir = Path("bot/config_backups")
        if not backup_dir.exists():
            return []

        backups = sorted(backup_dir.glob("config_backup_*.py"), reverse=True)
        return [str(b) for b in backups]


def main():
    parser = argparse.ArgumentParser(
        description='Manage bot configuration without manual editing'
    )
    parser.add_argument(
        '--apply',
        type=str,
        help='Apply parameters from JSON file (best_params.json or recommended_params.json)'
    )
    parser.add_argument(
        '--param-type',
        choices=['best', 'profit', 'win_rate', 'drawdown', 'risk_adjusted'],
        default='best',
        help='Which parameter set to apply from recommended_params.json (default: best)'
    )
    parser.add_argument(
        '--set-strategy',
        choices=['elastic_band', 'fvg', 'macd_rsi', 'elastic_bb'],
        help='Set active strategy'
    )
    parser.add_argument(
        '--get-strategy',
        action='store_true',
        help='Show current active strategy'
    )
    parser.add_argument(
        '--restore',
        type=str,
        help='Restore config from backup file'
    )
    parser.add_argument(
        '--list-backups',
        action='store_true',
        help='List all config backups'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup before modifying config'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without actually modifying files'
    )

    args = parser.parse_args()

    manager = ConfigManager()

    if args.list_backups:
        backups = manager.list_backups()
        if backups:
            print("\nAvailable config backups:")
            for backup in backups:
                print(f"  - {backup}")
        else:
            print("\nNo config backups found")
        return

    if args.get_strategy:
        strategy = manager.get_current_strategy()
        print(f"\nCurrent active strategy: {strategy}")
        return

    if args.restore:
        success = manager.restore_backup(args.restore)
        if not success:
            sys.exit(1)
        return

    if args.apply:
        success = manager.apply_from_file(
            args.apply,
            param_type=args.param_type,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )
        if not success:
            sys.exit(1)

    if args.set_strategy:
        success = manager.set_active_strategy(
            args.set_strategy,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )
        if not success:
            sys.exit(1)

    if not any([args.apply, args.set_strategy, args.restore, args.list_backups, args.get_strategy]):
        parser.print_help()


if __name__ == '__main__':
    main()
