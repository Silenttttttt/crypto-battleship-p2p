"""
Transport Adapter Abstraction
Abstract interface for different transport mechanisms (socket, WebRTC, etc.)
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Any, Dict
from enum import Enum
import threading


class TransportState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting" 
    CONNECTED = "connected"
    ERROR = "error"


class TransportAdapter(ABC):
    """
    Abstract base class for transport adapters
    Provides a unified interface for different transport mechanisms
    """
    
    def __init__(self):
        self.state = TransportState.DISCONNECTED
        self.on_data_received: Optional[Callable[[bytes], None]] = None
        self.on_state_changed: Optional[Callable[[TransportState, TransportState], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self._lock = threading.Lock()
    
    def _set_state(self, new_state: TransportState):
        """Thread-safe state change with callback notification"""
        with self._lock:
            if self.state != new_state:
                old_state = self.state
                self.state = new_state
                if self.on_state_changed:
                    try:
                        self.on_state_changed(old_state, new_state)
                    except Exception as e:
                        print(f"Error in state change callback: {e}")
    
    def _notify_error(self, error_msg: str):
        """Notify error callback"""
        if self.on_error:
            try:
                self.on_error(error_msg)
            except Exception as e:
                print(f"Error in error callback: {e}")
    
    def _notify_data_received(self, data: bytes):
        """Notify data received callback"""
        if self.on_data_received:
            try:
                self.on_data_received(data)
            except Exception as e:
                print(f"Error in data received callback: {e}")
    
    @abstractmethod
    def start_host(self, host: str = "localhost", port: int = 12345, **kwargs) -> bool:
        """Start as host/server waiting for connections"""
        pass
    
    @abstractmethod
    def connect_to_host(self, host: str, port: int, **kwargs) -> bool:
        """Connect to a host as client"""
        pass
    
    @abstractmethod
    def send_data(self, data: bytes) -> bool:
        """Send data to connected peer"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from peer"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to peer"""
        pass
    
    @abstractmethod
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        pass


class SocketTransportAdapter(TransportAdapter):
    """
    Socket-based transport adapter implementation
    True P2P - no client/server distinction after connection
    """
    
    def __init__(self):
        super().__init__()
        import socket
        self.socket_module = socket
        self.listen_socket: Optional[socket.socket] = None
        self.connect_socket: Optional[socket.socket] = None
        self.peer_socket: Optional[socket.socket] = None
        self.peer_address: Optional[tuple] = None
        self.connection_role = None  # Just for initial TCP setup
        
        # Threading
        self.network_thread: Optional[threading.Thread] = None
        self.stop_network = False
        
        # Constants
        self.MAX_PACKET_SIZE = 8192
        self.CONNECTION_TIMEOUT = 30.0
    
    def start_host(self, host: str = "localhost", port: int = 12345, **kwargs) -> bool:
        """Listen for incoming P2P connections"""
        try:
            self._set_state(TransportState.CONNECTING)
            self.connection_role = "listener"
            
            # Create listening socket
            self.listen_socket = self.socket_module.socket(
                self.socket_module.AF_INET, 
                self.socket_module.SOCK_STREAM
            )
            self.listen_socket.setsockopt(
                self.socket_module.SOL_SOCKET, 
                self.socket_module.SO_REUSEADDR, 
                1
            )
            self.listen_socket.bind((host, port))
            self.listen_socket.listen(1)
            
            print(f"P2P peer listening on {host}:{port}")
            
            # Start network thread
            self.stop_network = False
            self.network_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.network_thread.start()
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to start P2P listener: {e}"
            print(error_msg)
            self._set_state(TransportState.ERROR)
            self._notify_error(error_msg)
            return False
    
    def connect_to_host(self, host: str, port: int, **kwargs) -> bool:
        """Connect to another P2P peer"""
        try:
            self._set_state(TransportState.CONNECTING)
            self.connection_role = "connector"
            
            # Create connection socket
            self.connect_socket = self.socket_module.socket(
                self.socket_module.AF_INET,
                self.socket_module.SOCK_STREAM
            )
            self.connect_socket.settimeout(self.CONNECTION_TIMEOUT)
            
            print(f"Connecting to P2P peer at {host}:{port}")
            self.connect_socket.connect((host, port))
            
            self.peer_socket = self.connect_socket
            self.peer_address = (host, port)
            
            print(f"Connected to P2P peer at {host}:{port}")
            self._set_state(TransportState.CONNECTED)
            
            # Start network thread
            self.stop_network = False
            self.network_thread = threading.Thread(target=self._peer_loop, daemon=True)
            self.network_thread.start()
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to P2P peer: {e}"
            print(error_msg)
            self._set_state(TransportState.ERROR)
            self._notify_error(error_msg)
            return False
    
    def send_data(self, data: bytes) -> bool:
        """Send data to connected peer"""
        try:
            if not self.peer_socket or self.state != TransportState.CONNECTED:
                return False
            
            self.peer_socket.sendall(data)
            return True
            
        except Exception as e:
            error_msg = f"Failed to send data: {e}"
            print(error_msg)
            self._notify_error(error_msg)
            return False
    
    def disconnect(self):
        """Disconnect from peer"""
        print("Disconnecting socket transport...")
        
        # Stop network operations
        self.stop_network = True
        
        # Wait for network thread
        if self.network_thread and self.network_thread.is_alive():
            self.network_thread.join(timeout=2.0)
        
        # Close sockets
        self._cleanup_sockets()
        
        self._set_state(TransportState.DISCONNECTED)
    
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.state == TransportState.CONNECTED and self.peer_socket is not None
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "transport_type": "socket",
            "connection_role": self.connection_role,
            "state": self.state.value,
            "peer_address": self.peer_address,
            "local_address": self.peer_socket.getsockname() if self.peer_socket else None
        }
    
    def _listen_loop(self):
        """Network loop for listening peer"""
        try:
            while not self.stop_network:
                try:
                    # Accept connection
                    peer_socket, peer_address = self.listen_socket.accept()
                    print(f"P2P peer connected from {peer_address}")
                    
                    self.peer_socket = peer_socket
                    self.peer_address = peer_address
                    self._set_state(TransportState.CONNECTED)
                    
                    # Handle communication (both peers are now equal)
                    self._handle_peer_communication()
                    
                except self.socket_module.timeout:
                    continue
                except Exception as e:
                    if not self.stop_network:
                        error_msg = f"Listen loop error: {e}"
                        print(error_msg)
                        self._notify_error(error_msg)
                    break
                    
        except Exception as e:
            error_msg = f"Listen network loop error: {e}"
            print(error_msg)
            self._set_state(TransportState.ERROR)
            self._notify_error(error_msg)
        finally:
            self._cleanup_sockets()
    
    def _peer_loop(self):
        """Network loop for connecting peer"""
        try:
            # Handle communication (both peers are now equal)
            self._handle_peer_communication()
        except Exception as e:
            error_msg = f"Peer loop error: {e}"
            print(error_msg)
            self._set_state(TransportState.ERROR)
            self._notify_error(error_msg)
        finally:
            self._cleanup_sockets()
    
    def _handle_peer_communication(self):
        """Handle communication with peer"""
        if not self.peer_socket:
            return
        
        self.peer_socket.settimeout(1.0)  # Non-blocking with timeout
        
        try:
            while not self.stop_network and self.peer_socket:
                try:
                    data = self.peer_socket.recv(self.MAX_PACKET_SIZE)
                    if not data:
                        print("Peer disconnected")
                        break
                    
                    # Notify data received
                    self._notify_data_received(data)
                    
                except self.socket_module.timeout:
                    continue
                except ConnectionResetError:
                    print("Connection reset by peer")
                    break
                except Exception as e:
                    error_msg = f"Receive error: {e}"
                    print(error_msg)
                    self._notify_error(error_msg)
                    break
                
        except Exception as e:
            error_msg = f"Peer communication error: {e}"
            print(error_msg)
            self._notify_error(error_msg)
        finally:
            self._handle_peer_disconnect()
    
    def _handle_peer_disconnect(self):
        """Handle peer disconnection"""
        print("Peer disconnected")
        self._set_state(TransportState.DISCONNECTED)
        self.peer_socket = None
        self.peer_address = None
    
    def _cleanup_sockets(self):
        """Clean up all sockets"""
        try:
            if self.peer_socket:
                self.peer_socket.close()
                self.peer_socket = None
            
            if self.connect_socket and self.connect_socket != self.peer_socket:
                self.connect_socket.close()
                self.connect_socket = None
            
            if self.listen_socket:
                self.listen_socket.close()
                self.listen_socket = None
                
        except Exception as e:
            print(f"Error cleaning up sockets: {e}")


# Future transport adapters can be added here
# class WebRTCTransportAdapter(TransportAdapter):
#     """WebRTC-based transport adapter"""
#     pass

# class UDPTransportAdapter(TransportAdapter):
#     """UDP-based transport adapter"""
#     pass


def main():
    """Test the transport adapter"""
    import sys
    import time
    
    if len(sys.argv) < 2:
        print("Usage: python transport_adapter.py [host|client] [host_ip]")
        return
    
    role = sys.argv[1].lower()
    host_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    
    def on_state_changed(old_state, new_state):
        print(f"Transport state: {old_state.value} -> {new_state.value}")
    
    def on_data_received(data):
        print(f"Received data: {data}")
    
    def on_error(error):
        print(f"Transport error: {error}")
    
    # Create transport
    transport = SocketTransportAdapter()
    transport.on_state_changed = on_state_changed
    transport.on_data_received = on_data_received
    transport.on_error = on_error
    
    try:
        if role == "host":
            print("Starting as host...")
            if transport.start_host():
                print("Host started successfully")
                while transport.is_connected() or transport.state == TransportState.CONNECTING:
                    time.sleep(1)
            else:
                print("Failed to start host")
                
        elif role == "client":
            print(f"Connecting to {host_ip}...")
            if transport.connect_to_host(host_ip, 12345):
                print("Connected successfully")
                
                # Send test message
                time.sleep(1)
                transport.send_data(b"Hello from client!")
                
                while transport.is_connected():
                    time.sleep(1)
            else:
                print("Failed to connect")
        
        else:
            print("Invalid role. Use 'host' or 'client'")
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        transport.disconnect()


if __name__ == "__main__":
    main()
