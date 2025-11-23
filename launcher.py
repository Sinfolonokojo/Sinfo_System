"""
Launcher - Orchestrator for the Copy Trading System.

Single entry point to boot all master and slave processes.
"""

import sys
import subprocess
import signal
import time
from typing import List, Dict, Any

import config
from db import get_database, AccountModel
from utils import setup_logger


class Launcher:
    """
    Orchestrator that spawns and manages all trading processes.
    """

    def __init__(self):
        """Initialize the launcher."""
        self.logger = setup_logger("LAUNCHER")
        self.processes: Dict[str, subprocess.Popen] = {}
        self._running = False

    def verify_database_connection(self) -> bool:
        """
        Verify MongoDB is accessible.

        Returns:
            True if connection successful.
        """
        try:
            db = get_database()
            # Ping to verify
            db.client.admin.command('ping')
            self.logger.info(f"Connected to MongoDB: {config.MONGO_URI}")
            return True
        except Exception as e:
            self.logger.error(f"MongoDB connection failed: {e}")
            return False

    def load_accounts(self) -> List[Dict[str, Any]]:
        """
        Load all enabled accounts from database.

        Returns:
            List of account configurations.
        """
        accounts = AccountModel.get_all_enabled()
        self.logger.info(f"Loaded {len(accounts)} enabled accounts")
        return accounts

    def spawn_process(self, account: Dict[str, Any]) -> subprocess.Popen:
        """
        Spawn a subprocess for an account.

        Args:
            account: Account configuration document.

        Returns:
            The spawned process.
        """
        name = account['name']
        account_type = account['type']
        terminal_path = account['path']

        # Determine script to run
        if account_type == 'MASTER':
            script = 'nodes/master.py'
        else:
            script = 'nodes/slave.py'

        # Build command
        cmd = [
            sys.executable,
            script,
            '--name', name,
            '--path', terminal_path
        ]

        # Spawn process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        self.logger.info(
            f"Spawned {account_type} process | "
            f"Name: {name} | PID: {process.pid}"
        )

        return process

    def monitor_output(self, name: str, process: subprocess.Popen):
        """
        Print process output to console.

        Args:
            name: Account name.
            process: The subprocess.
        """
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line, end='')
        except Exception:
            pass

    def start(self):
        """Start all trading processes."""
        if not self.verify_database_connection():
            sys.exit(1)

        accounts = self.load_accounts()
        if not accounts:
            self.logger.warning("No enabled accounts found")
            sys.exit(1)

        # Spawn master processes first
        masters = [a for a in accounts if a['type'] == 'MASTER']
        slaves = [a for a in accounts if a['type'] == 'SLAVE']

        self.logger.info(f"Starting {len(masters)} master(s) and {len(slaves)} slave(s)")

        # Spawn masters
        for account in masters:
            process = self.spawn_process(account)
            self.processes[account['name']] = process

        # Small delay to let master initialize publisher
        time.sleep(1)

        # Spawn slaves
        for account in slaves:
            process = self.spawn_process(account)
            self.processes[account['name']] = process

        self._running = True
        self.logger.info("All processes started")

        # Monitor processes
        self.monitor()

    def monitor(self):
        """Monitor running processes and restart if needed."""
        try:
            while self._running:
                for name, process in list(self.processes.items()):
                    # Check if process is still running
                    retcode = process.poll()
                    if retcode is not None:
                        self.logger.warning(
                            f"Process {name} exited with code {retcode}"
                        )
                        # Remove from active processes
                        del self.processes[name]

                        # Print any remaining output
                        if process.stdout:
                            remaining = process.stdout.read()
                            if remaining:
                                print(remaining)

                # Check every second
                time.sleep(1)

                # Output from processes
                for name, process in self.processes.items():
                    if process.stdout:
                        try:
                            # Non-blocking read
                            import select
                            if sys.platform == 'win32':
                                # Windows doesn't support select on pipes
                                pass
                            else:
                                readable, _, _ = select.select(
                                    [process.stdout], [], [], 0
                                )
                                if readable:
                                    line = process.stdout.readline()
                                    if line:
                                        print(line, end='')
                        except Exception:
                            pass

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested")
            self.stop()

    def stop(self):
        """Stop all running processes."""
        self._running = False

        for name, process in self.processes.items():
            self.logger.info(f"Terminating {name} (PID: {process.pid})")
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Force killing {name}")
                process.kill()

        self.processes.clear()
        self.logger.info("All processes stopped")


def main():
    """Entry point for the launcher."""
    launcher = Launcher()

    # Handle SIGINT and SIGTERM
    def signal_handler(signum, frame):
        launcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)

    launcher.start()


if __name__ == '__main__':
    main()
