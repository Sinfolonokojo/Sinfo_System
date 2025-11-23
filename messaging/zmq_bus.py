"""
ZeroMQ Publisher-Subscriber message bus for trade signals.
"""

import json
import zmq
from typing import Optional, Dict, Any
import config


class Publisher:
    """
    ZeroMQ Publisher for broadcasting trade signals.

    Uses PUB socket pattern for one-to-many communication.
    """

    def __init__(self, address: str = None):
        """
        Initialize the publisher.

        Args:
            address: ZeroMQ bind address. Defaults to config.ZMQ_PUB_ADDRESS.
        """
        self.address = address or config.ZMQ_PUB_ADDRESS
        self.context: zmq.Context = None
        self.socket: zmq.Socket = None

    def start(self):
        """Start the publisher and bind to address."""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.setsockopt(zmq.SNDHWM, 1000)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.bind(self.address)

    def publish(self, message: Dict[str, Any], topic: str = "TRADE"):
        """
        Publish a message to the bus.

        Args:
            message: Dictionary containing trade signal data.
            topic: Message topic for filtering. Defaults to "TRADE".
        """
        if self.socket is None:
            raise RuntimeError("Publisher not started. Call start() first.")

        payload = json.dumps(message)
        self.socket.send_string(f"{topic} {payload}")

    def publish_open(
        self,
        ticket: int,
        symbol: str,
        order_type: int,
        volume: float,
        price: float,
        sl: float,
        tp: float
    ):
        """
        Publish an OPEN trade signal.

        Args:
            ticket: Master ticket ID.
            symbol: Trading symbol.
            order_type: MT5 order type (0=BUY, 1=SELL).
            volume: Lot size.
            price: Entry price.
            sl: Stop loss price.
            tp: Take profit price.
        """
        message = {
            'action': 'OPEN',
            'ticket': ticket,
            'symbol': symbol,
            'type': order_type,
            'volume': volume,
            'price': price,
            'sl': sl,
            'tp': tp
        }
        self.publish(message)

    def publish_close(self, ticket: int, symbol: str):
        """
        Publish a CLOSE trade signal.

        Args:
            ticket: Master ticket ID to close.
            symbol: Trading symbol.
        """
        message = {
            'action': 'CLOSE',
            'ticket': ticket,
            'symbol': symbol
        }
        self.publish(message)

    def stop(self):
        """Stop the publisher and release resources."""
        if self.socket:
            self.socket.close()
            self.socket = None
        if self.context:
            self.context.term()
            self.context = None


class Subscriber:
    """
    ZeroMQ Subscriber for receiving trade signals.

    Uses SUB socket pattern with topic filtering.
    """

    def __init__(self, address: str = None, timeout_ms: int = 100):
        """
        Initialize the subscriber.

        Args:
            address: ZeroMQ connect address. Defaults to config.ZMQ_PUB_ADDRESS.
            timeout_ms: Receive timeout in milliseconds.
        """
        self.address = address or config.ZMQ_PUB_ADDRESS
        self.timeout_ms = timeout_ms
        self.context: zmq.Context = None
        self.socket: zmq.Socket = None

    def start(self, topic: str = "TRADE"):
        """
        Start the subscriber and connect to publisher.

        Args:
            topic: Topic to subscribe to. Empty string for all messages.
        """
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.RCVHWM, 1000)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.connect(self.address)

    def receive(self) -> Optional[Dict[str, Any]]:
        """
        Receive a message from the bus.

        Returns:
            Parsed message dictionary, or None if timeout.
        """
        if self.socket is None:
            raise RuntimeError("Subscriber not started. Call start() first.")

        try:
            message = self.socket.recv_string()
            # Split topic from payload
            parts = message.split(' ', 1)
            if len(parts) == 2:
                payload = json.loads(parts[1])
                return payload
            return None
        except zmq.Again:
            # Timeout - no message available
            return None
        except json.JSONDecodeError:
            return None

    def stop(self):
        """Stop the subscriber and release resources."""
        if self.socket:
            self.socket.close()
            self.socket = None
        if self.context:
            self.context.term()
            self.context = None
