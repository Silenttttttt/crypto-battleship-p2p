"""
Battleship P2P Game
Fully utilizes ExProtocol with transport adapter abstraction
"""

import json
import time
import threading
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

# Import ExProtocol from published package
from ExProtocol import ProtocolWrapper

# Import transport abstraction
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from network.transport import TransportAdapter, TransportState


class GameMessageType(Enum):
    """Battleship-specific message types"""
    # Game setup
    GAME_INVITE = "game_invite"
    GAME_ACCEPT = "game_accept" 
    GAME_REJECT = "game_reject"
    
    # Ship placement
    SHIPS_READY = "ships_ready"
    START_GAME = "start_game"
    
    # Gameplay
    FIRE_SHOT = "fire_shot"
    SHOT_RESULT = "shot_result"
    TURN_CHANGE = "turn_change"
    
    # Game end
    GAME_OVER = "game_over"
    SURRENDER = "surrender"
    
    # Connection management
    PING = "ping"
    PONG = "pong"
    
    # Blockchain synchronization
    BLOCKCHAIN_SYNC = "blockchain_sync"
    BLOCKCHAIN_SYNC_RESPONSE = "blockchain_sync_response"


class ShotResult(Enum):
    MISS = "miss"
    HIT = "hit" 
    SUNK = "sunk"


class GamePhase(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INVITING = "inviting"
    SETUP = "setup"
    PLAYING = "playing"
    GAME_OVER = "game_over"


@dataclass
class Ship:
    name: str
    size: int
    positions: List[Tuple[int, int]]
    hits: List[bool]
    
    def is_sunk(self) -> bool:
        return all(self.hits)


@dataclass
class GameConfig:
    grid_size: int = 10
    ships: List[Dict[str, Any]] = None
    time_limit: Optional[int] = None  # seconds per turn
    
    def __post_init__(self):
        if self.ships is None:
            self.ships = [
                {"name": "Carrier", "size": 5, "count": 1},
                {"name": "Battleship", "size": 4, "count": 1}, 
                {"name": "Cruiser", "size": 3, "count": 1},
                {"name": "Submarine", "size": 3, "count": 1},
                {"name": "Destroyer", "size": 2, "count": 1}
            ]


class BattleshipP2P:
    """
    Battleship P2P game using ExProtocol with transport abstraction
    """
    
    def __init__(self, player_id: str = None, transport: TransportAdapter = None):
        self.player_id = player_id or str(uuid.uuid4())
        self.transport = transport
        
        # ExProtocol integration
        # Create protocol wrapper and disable Hamming (can enable if binary is available)
        self.protocol_wrapper = ProtocolWrapper()
        # Disable Hamming to avoid requiring binary (can enable if needed)
        self.protocol_wrapper.protocol.use_hamming = False
        self.connection_established = False
        self.connection_role = None  # "listener" or "connector" - just for initial setup
        
        # Game state
        self.phase = GamePhase.DISCONNECTED
        self.game_config = GameConfig()
        self.opponent_id: Optional[str] = None
        self.current_turn: Optional[str] = None
        
        # Game data
        self.player_ships: Dict[str, Ship] = {}
        self.enemy_grid_shots: Dict[Tuple[int, int], ShotResult] = {}
        self.player_grid_shots: Dict[Tuple[int, int], ShotResult] = {}
        self.ships_ready = False
        self.opponent_ships_ready = False
        
        # Threading and synchronization
        self.message_lock = threading.Lock()
        self.pending_responses: Dict[str, Any] = {}
        
        # Callbacks
        self.on_phase_changed: Optional[Callable[[GamePhase, GamePhase], None]] = None
        self.on_message_received: Optional[Callable[[GameMessageType, Dict], None]] = None
        self.on_shot_fired: Optional[Callable[[int, int, ShotResult], None]] = None
        self.on_shot_received: Optional[Callable[[int, int, ShotResult], None]] = None
        self.on_game_over: Optional[Callable[[str, str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Setup transport callbacks if provided
        if self.transport:
            self._setup_transport()
    
    def set_transport(self, transport: TransportAdapter):
        """Set transport adapter"""
        self.transport = transport
        self._setup_transport()
    
    def _setup_transport(self):
        """Setup transport adapter callbacks"""
        self.transport.on_data_received = self._handle_transport_data
        self.transport.on_state_changed = self._handle_transport_state_change
        self.transport.on_error = self._handle_transport_error
    
    def _set_phase(self, new_phase: GamePhase):
        """Change game phase with callback notification"""
        if self.phase != new_phase:
            old_phase = self.phase
            self.phase = new_phase
            print(f"Game phase: {old_phase.value} -> {new_phase.value}")
            
            if self.on_phase_changed:
                try:
                    self.on_phase_changed(old_phase, new_phase)
                except Exception as e:
                    print(f"Error in phase change callback: {e}")
    
    def _handle_transport_state_change(self, old_state: TransportState, new_state: TransportState):
        """Handle transport state changes"""
        if new_state == TransportState.CONNECTED:
            self._set_phase(GamePhase.CONNECTED)
            # Start ExProtocol handshake
            self._initiate_protocol_handshake()
        elif new_state == TransportState.DISCONNECTED:
            self._set_phase(GamePhase.DISCONNECTED)
            self.connection_established = False
        elif new_state == TransportState.ERROR:
            self._handle_error("Transport error occurred")
    
    def _handle_transport_data(self, data: bytes):
        """Handle incoming transport data"""
        try:
            if not self.connection_established:
                # Handle ExProtocol handshake
                self._handle_protocol_handshake(data)
            else:
                # Handle game messages through ExProtocol
                self._handle_protocol_message(data)
                
        except Exception as e:
            self._handle_error(f"Error handling transport data: {e}")
    
    def _handle_transport_error(self, error: str):
        """Handle transport errors"""
        self._handle_error(f"Transport error: {error}")
    
    def _initiate_protocol_handshake(self):
        """Initiate ExProtocol handshake"""
        try:
            if self.connection_role == "listener":
                # Listener waits for connector to initiate
                print("Waiting for peer to initiate ExProtocol handshake...")
            else:
                # Connector initiates handshake
                print("Initiating ExProtocol handshake...")
                pow_request = self.protocol_wrapper.create_handshake_request()
                self.transport.send_data(pow_request)
                
        except Exception as e:
            self._handle_error(f"Failed to initiate protocol handshake: {e}")
    
    def _handle_protocol_handshake(self, data: bytes):
        """Handle ExProtocol handshake messages"""
        try:
            if self.connection_role == "listener":
                # Listener side handshake
                if not hasattr(self, '_handshake_step'):
                    self._handshake_step = 0
                
                if self._handshake_step == 0:
                    # Respond to PoW request
                    print("Responding to PoW request...")
                    pow_challenge = self.protocol_wrapper.respond_handshake(data)
                    self.transport.send_data(pow_challenge)
                    self._handshake_step = 1
                    
                elif self._handshake_step == 1:
                    # Complete handshake
                    print("Completing handshake...")
                    response = self.protocol_wrapper.perform_handshake_response(data)
                    self.transport.send_data(response)
                    self.connection_established = True
                    self._set_phase(GamePhase.SETUP)
                    print("✅ ExProtocol handshake completed! Both peers are now equal.")
                    
            else:
                # Connector side handshake
                if not hasattr(self, '_handshake_step'):
                    self._handshake_step = 0
                
                if self._handshake_step == 0:
                    # Complete PoW and send handshake request
                    print("Solving PoW challenge...")
                    handshake_request = self.protocol_wrapper.complete_handshake_request(data)
                    self.transport.send_data(handshake_request)
                    self._handshake_step = 1
                    
                elif self._handshake_step == 1:
                    # Complete handshake
                    print("Finalizing handshake...")
                    self.protocol_wrapper.complete_handshake(data)
                    self.connection_established = True
                    self._set_phase(GamePhase.SETUP)
                    print("✅ ExProtocol handshake completed! Both peers are now equal.")
                    
        except Exception as e:
            self._handle_error(f"Protocol handshake error: {e}")
    
    def _handle_protocol_message(self, encrypted_data: bytes):
        """Handle encrypted game messages through ExProtocol"""
        try:
            # Decrypt message using ExProtocol
            data, header, packet_uuid = self.protocol_wrapper.decrypt_data(encrypted_data)
            
            # Extract game message
            message_type = GameMessageType(data.get("message_type"))
            message_data = data.get("message_data", {})
            sender_id = data.get("sender_id")
            
            # Set opponent ID if not set
            if not self.opponent_id:
                self.opponent_id = sender_id
            
            print(f"Received {message_type.value}: {message_data}")
            
            # Handle message based on type
            self._handle_game_message(message_type, message_data, sender_id)
            
            # Send response if needed
            if data.get("requires_response"):
                response_data = self._generate_response(message_type, message_data)
                if response_data:
                    self._send_response(response_data, packet_uuid)
            
            # Notify callback
            if self.on_message_received:
                self.on_message_received(message_type, message_data)
                
        except Exception as e:
            self._handle_error(f"Error handling protocol message: {e}")
    
    def _handle_game_message(self, msg_type: GameMessageType, data: Dict, sender_id: str):
        """Handle specific game message types"""
        if msg_type == GameMessageType.GAME_INVITE:
            self._handle_game_invite(data)
        elif msg_type == GameMessageType.GAME_ACCEPT:
            self._handle_game_accept(data)
        elif msg_type == GameMessageType.GAME_REJECT:
            self._handle_game_reject(data)
        elif msg_type == GameMessageType.SHIPS_READY:
            self._handle_ships_ready(data)
        elif msg_type == GameMessageType.START_GAME:
            self._handle_start_game(data)
        elif msg_type == GameMessageType.FIRE_SHOT:
            self._handle_fire_shot(data)
        elif msg_type == GameMessageType.SHOT_RESULT:
            self._handle_shot_result(data)
        elif msg_type == GameMessageType.GAME_OVER:
            self._handle_game_over_message(data)
        elif msg_type == GameMessageType.PING:
            self._send_message(GameMessageType.PONG, {"timestamp": time.time()})
        elif msg_type == GameMessageType.BLOCKCHAIN_SYNC:
            self._handle_blockchain_sync(data)
        elif msg_type == GameMessageType.BLOCKCHAIN_SYNC_RESPONSE:
            self._handle_blockchain_sync_response(data)
    
    def _send_message(self, msg_type: GameMessageType, data: Dict, requires_response: bool = False) -> bool:
        """Send a game message through ExProtocol"""
        try:
            if not self.connection_established:
                return False
            
            # Prepare message data
            message_data = {
                "message_type": msg_type.value,
                "message_data": data,
                "sender_id": self.player_id,
                "timestamp": time.time(),
                "requires_response": requires_response
            }
            
            # Encrypt and send through ExProtocol
            encrypted_message, packet_uuid = self.protocol_wrapper.send_data(message_data)
            
            # Send through transport
            success = self.transport.send_data(encrypted_message)
            
            if success:
                print(f"Sent {msg_type.value}: {data}")
            
            return success
            
        except Exception as e:
            self._handle_error(f"Failed to send message: {e}")
            return False
    
    def _send_response(self, data: Dict, original_packet_uuid: str):
        """Send response to a message"""
        try:
            encrypted_response = self.protocol_wrapper.send_response(data, original_packet_uuid)
            self.transport.send_data(encrypted_response)
            
        except Exception as e:
            self._handle_error(f"Failed to send response: {e}")
    
    def _generate_response(self, msg_type: GameMessageType, data: Dict) -> Optional[Dict]:
        """Generate response for messages that require one"""
        # Most messages don't require responses in this implementation
        return None
    
    def _handle_error(self, error_msg: str):
        """Handle errors"""
        print(f"Error: {error_msg}")
        if self.on_error:
            try:
                self.on_error(error_msg)
            except Exception as e:
                print(f"Error in error callback: {e}")
    
    # Game message handlers
    def _handle_game_invite(self, data: Dict):
        """Handle game invitation"""
        self.game_config = GameConfig(**data.get("config", {}))
        print(f"Received game invite with config: {asdict(self.game_config)}")
        # Auto-accept for now (in UI this would be user choice)
        self.accept_game_invite()
    
    def _handle_game_accept(self, data: Dict):
        """Handle game acceptance"""
        print("Game invite accepted!")
        self._set_phase(GamePhase.SETUP)
    
    def _handle_game_reject(self, data: Dict):
        """Handle game rejection"""
        reason = data.get("reason", "No reason given")
        print(f"Game invite rejected: {reason}")
        self._set_phase(GamePhase.CONNECTED)
    
    def _handle_ships_ready(self, data: Dict):
        """Handle opponent ships ready"""
        self.opponent_ships_ready = True
        print("Opponent ships are ready")
        self._check_start_game()
    
    def _handle_start_game(self, data: Dict):
        """Handle game start"""
        self.current_turn = data.get("first_turn")
        self._set_phase(GamePhase.PLAYING)
        print(f"Game started! {self.current_turn} goes first")
    
    def _handle_fire_shot(self, data: Dict):
        """Handle incoming shot"""
        x, y = data["x"], data["y"]
        result = self._process_shot(x, y)
        
        # Send result back
        self._send_message(GameMessageType.SHOT_RESULT, {
            "x": x, "y": y, "result": result.value
        })
        
        # Check game over
        if self._all_ships_sunk():
            self._send_message(GameMessageType.GAME_OVER, {
                "winner": self.opponent_id,
                "reason": "All ships sunk"
            })
            self._set_phase(GamePhase.GAME_OVER)
        else:
            self.current_turn = self.player_id
        
        if self.on_shot_received:
            self.on_shot_received(x, y, result)
        
        # Sync blockchain after handling shot
        self._trigger_blockchain_sync()
    
    def _handle_shot_result(self, data: Dict):
        """Handle shot result"""
        x, y = data["x"], data["y"]
        result = ShotResult(data["result"])
        
        # Record shot result
        self.enemy_grid_shots[(x, y)] = result
        
        # Check game over
        if self._enemy_ships_all_sunk():
            self._send_message(GameMessageType.GAME_OVER, {
                "winner": self.player_id,
                "reason": "All enemy ships sunk"
            })
            self._set_phase(GamePhase.GAME_OVER)
        else:
            self.current_turn = self.opponent_id
        
        if self.on_shot_fired:
            self.on_shot_fired(x, y, result)
        
        # Sync blockchain after receiving result
        self._trigger_blockchain_sync()
    
    def _handle_game_over_message(self, data: Dict):
        """Handle game over message"""
        winner = data.get("winner")
        reason = data.get("reason", "")
        self._set_phase(GamePhase.GAME_OVER)
        
        if self.on_game_over:
            self.on_game_over(winner, reason)
    
    def _trigger_blockchain_sync(self):
        """Trigger blockchain synchronization after game actions"""
        # Get the actual blockchain - might be nested in crypto_game or protocol
        blockchain = None
        
        # Check for crypto_game first (integration layer)
        if hasattr(self, 'crypto_game'):
            # Framework-based: blockchain is in protocol
            if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'blockchain'):
                blockchain = self.crypto_game.protocol.blockchain
            # Legacy: blockchain is direct attribute
            elif hasattr(self.crypto_game, 'blockchain'):
                blockchain = self.crypto_game.blockchain
        # Then check for game (base layer)
        elif hasattr(self, 'game') and self.game:
            if hasattr(self.game, 'blockchain'):
                blockchain = self.game.blockchain
            elif hasattr(self.game, 'crypto_game') and hasattr(self.game.crypto_game, 'blockchain'):
                blockchain = self.game.crypto_game.blockchain
        
        if not blockchain:
            print("⚠️  No blockchain found for sync")
            return
        
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from crypto import create_sync_message
            
            # Create sync message
            sync_msg = create_sync_message(blockchain)
            
            # Send via P2P
            print(f"📡 Triggering blockchain sync (blocks: {len(blockchain.chain)})...")
            self._send_message(GameMessageType.BLOCKCHAIN_SYNC, sync_msg)
            
        except Exception as e:
            import traceback
            print(f"⚠️  Blockchain sync trigger error: {e}")
            traceback.print_exc()
    
    def _handle_blockchain_sync(self, data: Dict):
        """Handle blockchain sync request from opponent"""
        print(f"📡 Received blockchain sync request")
        
        # Get the actual blockchain - might be nested in crypto_game or protocol
        blockchain = None
        
        # Check for crypto_game first (integration layer)
        if hasattr(self, 'crypto_game'):
            # Framework-based: blockchain is in protocol
            if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'blockchain'):
                blockchain = self.crypto_game.protocol.blockchain
            # Legacy: blockchain is direct attribute
            elif hasattr(self.crypto_game, 'blockchain'):
                blockchain = self.crypto_game.blockchain
        # Then check for game (base layer)
        elif hasattr(self, 'game') and self.game:
            if hasattr(self.game, 'blockchain'):
                blockchain = self.game.blockchain
            elif hasattr(self.game, 'crypto_game') and hasattr(self.game.crypto_game, 'blockchain'):
                blockchain = self.game.crypto_game.blockchain
        
        if not blockchain:
            print(f"⚠️  No blockchain found to sync")
            return
        
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from crypto import handle_sync_message
            
            # Process sync message and get response
            response = handle_sync_message(blockchain, data)
            
            # Send response
            self._send_message(GameMessageType.BLOCKCHAIN_SYNC_RESPONSE, response)
            
            if response.get('needs_sync'):
                print(f"📡 Blockchain sync: {response['reason']}")
            else:
                print(f"📡 Blockchains already synchronized")
            
        except Exception as e:
            import traceback
            print(f"⚠️  Blockchain sync handler error: {e}")
            traceback.print_exc()
    
    def _handle_blockchain_sync_response(self, data: Dict):
        """Handle blockchain sync response from opponent"""
        print(f"📡 Received blockchain sync response")
        
        # Get the actual blockchain - might be nested in crypto_game or protocol
        blockchain = None
        
        # Check for crypto_game first (integration layer)
        if hasattr(self, 'crypto_game'):
            # Framework-based: blockchain is in protocol
            if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'blockchain'):
                blockchain = self.crypto_game.protocol.blockchain
            # Legacy: blockchain is direct attribute
            elif hasattr(self.crypto_game, 'blockchain'):
                blockchain = self.crypto_game.blockchain
        # Then check for game (base layer)
        elif hasattr(self, 'game') and self.game:
            if hasattr(self.game, 'blockchain'):
                blockchain = self.game.blockchain
            elif hasattr(self.game, 'crypto_game') and hasattr(self.game.crypto_game, 'blockchain'):
                blockchain = self.game.crypto_game.blockchain
        
        if not blockchain:
            print(f"⚠️  No blockchain found to sync")
            return
        
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from crypto import BlockchainSync, Transaction, MoveType
            
            needs_sync = data.get('needs_sync', False)
            
            if needs_sync and 'transactions' in data:
                # Merge incoming transactions
                sync = BlockchainSync(blockchain)
                
                # Convert transaction dicts back to Transaction objects
                transactions = []
                for tx_dict in data['transactions']:
                    tx = Transaction(
                        move_type=MoveType(tx_dict['move_type']),
                        participant_id=tx_dict['participant_id'],
                        data=tx_dict['data'],
                        timestamp=tx_dict['timestamp'],
                        signature=tx_dict['signature'],
                        sequence_number=tx_dict.get('sequence_number', 0)
                    )
                    transactions.append(tx)
                
                success, message = sync.merge_transactions(transactions)
                print(f"📡 {message}")
                print(f"📡 Blockchain now has {len(blockchain.chain)} blocks")
            else:
                print(f"📡 Blockchains already synchronized")
                
        except Exception as e:
            import traceback
            print(f"⚠️  Blockchain sync response error: {e}")
            traceback.print_exc()
    
    # Public API methods
    def listen_for_peer(self, host: str = "localhost", port: int = 12345) -> bool:
        """Listen for incoming P2P connections"""
        if not self.transport:
            self._handle_error("No transport adapter set")
            return False
        
        self.connection_role = "listener"
        self._set_phase(GamePhase.CONNECTING)
        return self.transport.start_host(host, port)
    
    def connect_to_peer(self, host: str, port: int = 12345) -> bool:
        """Connect to another P2P peer"""
        if not self.transport:
            self._handle_error("No transport adapter set")
            return False
        
        self.connection_role = "connector"
        self._set_phase(GamePhase.CONNECTING)
        return self.transport.connect_to_host(host, port)
    
    def send_game_invite(self, config: GameConfig = None) -> bool:
        """Send game invitation"""
        if self.phase != GamePhase.SETUP:
            return False
        
        config = config or self.game_config
        self._set_phase(GamePhase.INVITING)
        
        return self._send_message(GameMessageType.GAME_INVITE, {
            "config": asdict(config)
        })
    
    def accept_game_invite(self) -> bool:
        """Accept game invitation"""
        return self._send_message(GameMessageType.GAME_ACCEPT, {})
    
    def reject_game_invite(self, reason: str = "") -> bool:
        """Reject game invitation"""
        return self._send_message(GameMessageType.GAME_REJECT, {
            "reason": reason
        })
    
    def set_ships_ready(self, ships: Dict[str, Ship]) -> bool:
        """Set ships as ready"""
        self.player_ships = ships
        self.ships_ready = True
        
        success = self._send_message(GameMessageType.SHIPS_READY, {
            "ship_count": len(ships)
        })
        
        if success:
            self._check_start_game()
        
        return success
    
    def fire_shot(self, x: int, y: int) -> bool:
        """Fire shot at enemy grid"""
        if self.phase != GamePhase.PLAYING or self.current_turn != self.player_id:
            return False
        
        if (x, y) in self.enemy_grid_shots:
            return False  # Already shot here
        
        return self._send_message(GameMessageType.FIRE_SHOT, {
            "x": x, "y": y
        })
    
    def surrender(self) -> bool:
        """Surrender the game"""
        success = self._send_message(GameMessageType.SURRENDER, {})
        if success:
            self._set_phase(GamePhase.GAME_OVER)
        return success
    
    def disconnect(self):
        """Disconnect from game"""
        if self.transport:
            self.transport.disconnect()
        self._set_phase(GamePhase.DISCONNECTED)
    
    # Game logic helpers
    def _process_shot(self, x: int, y: int) -> ShotResult:
        """Process incoming shot and return result"""
        # Record shot
        if (x, y) in self.player_grid_shots:
            return self.player_grid_shots[(x, y)]
        
        # Check if shot hits a ship
        hit_ship = None
        for ship in self.player_ships.values():
            if (x, y) in ship.positions:
                hit_ship = ship
                break
        
        if hit_ship:
            # Mark hit on ship
            pos_index = hit_ship.positions.index((x, y))
            hit_ship.hits[pos_index] = True
            
            # Check if ship is sunk
            if hit_ship.is_sunk():
                result = ShotResult.SUNK
            else:
                result = ShotResult.HIT
        else:
            result = ShotResult.MISS
        
        self.player_grid_shots[(x, y)] = result
        return result
    
    def _all_ships_sunk(self) -> bool:
        """Check if all player ships are sunk"""
        return all(ship.is_sunk() for ship in self.player_ships.values())
    
    def _enemy_ships_all_sunk(self) -> bool:
        """Estimate if all enemy ships are sunk based on shots"""
        # This is a simplified check - in a real game you'd track this better
        total_ship_cells = sum(ship["size"] * ship["count"] for ship in self.game_config.ships)
        sunk_cells = sum(1 for result in self.enemy_grid_shots.values() 
                        if result in [ShotResult.HIT, ShotResult.SUNK])
        return sunk_cells >= total_ship_cells
    
    def _check_start_game(self):
        """Check if game can start"""
        if self.ships_ready and self.opponent_ships_ready:
            # Randomly decide who goes first
            import random
            first_turn = random.choice([self.player_id, self.opponent_id])
            
            self._send_message(GameMessageType.START_GAME, {
                "first_turn": first_turn
            })
            
            self.current_turn = first_turn
            self._set_phase(GamePhase.PLAYING)
    
    def get_game_state(self) -> Dict[str, Any]:
        """Get current game state"""
        return {
            "phase": self.phase.value,
            "player_id": self.player_id,
            "opponent_id": self.opponent_id,
            "current_turn": self.current_turn,
            "ships_ready": self.ships_ready,
            "opponent_ships_ready": self.opponent_ships_ready,
            "player_ships": {k: asdict(v) for k, v in self.player_ships.items()},
            "enemy_shots": {f"{k[0]},{k[1]}": v.value for k, v in self.enemy_grid_shots.items()},
            "player_shots": {f"{k[0]},{k[1]}": v.value for k, v in self.player_grid_shots.items()},
            "game_config": asdict(self.game_config),
            "connection_established": self.connection_established
        }


def main():
    """Test the battleship P2P system"""
    import sys
    from transport_adapter import SocketTransportAdapter
    
    if len(sys.argv) < 2:
        print("Usage: python battleship_p2p.py [listen|connect] [peer_ip]")
        return
    
    role = sys.argv[1].lower()
    peer_ip = sys.argv[2] if len(sys.argv) > 2 else "localhost"
    
    # Create transport and game
    transport = SocketTransportAdapter()
    game = BattleshipP2P(transport=transport)
    
    def on_phase_changed(old_phase, new_phase):
        print(f"Game phase: {old_phase.value} -> {new_phase.value}")
    
    def on_message_received(msg_type, data):
        print(f"Game message: {msg_type.value} - {data}")
    
    game.on_phase_changed = on_phase_changed
    game.on_message_received = on_message_received
    
    try:
        if role == "listen":
            print("Listening for P2P connections...")
            if game.listen_for_peer():
                print("Listening started, waiting for peer...")
                while game.phase == GamePhase.CONNECTING:
                    time.sleep(0.1)
                
                if game.phase == GamePhase.SETUP:
                    print("P2P connection established! Both peers are equal.")
                    print("Either peer can send game invite...")
                
                # Keep running
                while game.phase != GamePhase.DISCONNECTED:
                    time.sleep(1)
            
        elif role == "connect":
            print(f"Connecting to peer at {peer_ip}...")
            if game.connect_to_peer(peer_ip):
                print("Connected to peer!")
                
                # Keep running
                while game.phase != GamePhase.DISCONNECTED:
                    time.sleep(1)
        
        else:
            print("Invalid role. Use 'listen' or 'connect'")
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        game.disconnect()


if __name__ == "__main__":
    main()
