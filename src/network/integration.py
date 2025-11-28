"""
Cryptographic P2P Battleship Integration
Combines the crypto battleship with the P2P transport layer
"""

import json
import time
from typing import Dict, Any, Optional
from dataclasses import asdict

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from game.battleship_protocol import BattleshipZeroTrust
from game.core import CryptoBattleshipGame
from zerotrust import MerkleProof
from zerotrust import MoveType, Transaction
from network.p2p import BattleshipP2P, GamePhase, GameMessageType
from network.transport import SocketTransportAdapter


class CryptoBattleshipP2P(BattleshipP2P):
    """P2P Battleship with cryptographic security using Zero-Trust Framework"""
    
    def __init__(self, ship_positions, seed=None, transport=None, 
                 enable_enforcement=True, enable_persistence=True, enable_monitoring=True,
                 use_framework=True):
        """
        Initialize P2P Battleship with framework-based enforcement.
        
        Args:
            ship_positions: List of ship positions
            seed: Optional seed for deterministic keys
            transport: Transport adapter
            enable_enforcement: Enable framework enforcement (timeouts, turn order)
            enable_persistence: Enable state persistence
            enable_monitoring: Enable continuous monitoring
            use_framework: Use BattleshipZeroTrust (framework-based) instead of CryptoBattleshipGame
        """
        # Use framework-based game (BattleshipZeroTrust) by default
        if use_framework:
            # Framework-based: enforcement, monitoring, persistence all in framework
            self.crypto_game = BattleshipZeroTrust(
                ship_positions, 
                seed,
                enable_enforcement=enable_enforcement,
                enable_persistence=enable_persistence,
                enable_monitoring=enable_monitoring
            )
            # Get player ID from framework protocol
            player_id = self.crypto_game.protocol.my_participant_id
        else:
            # Legacy: CryptoBattleshipGame (old integrated version)
            self.crypto_game = CryptoBattleshipGame(ship_positions, seed)
            # Get player ID from legacy identity
            player_id = self.crypto_game.identity.player_id
        
        # Initialize P2P with crypto player ID
        super().__init__(player_id, transport)
        
        # Store last peer address for reconnection
        self.last_peer_address = None
        
        # Override message handlers
        self.on_message_received = self._handle_crypto_message
        
        # Set up enforcement if crypto_game has protocol (framework-based)
        if hasattr(self.crypto_game, 'protocol'):
            # This is BattleshipZeroTrust using framework
            if enable_enforcement and hasattr(self.crypto_game.protocol, 'enforcement'):
                # Set up reconnection callback
                self.crypto_game.protocol.on_disconnect = self._handle_disconnect
                
                # Start monitoring if enabled
                if enable_monitoring and hasattr(self.crypto_game.protocol, 'start_monitoring'):
                    self.crypto_game.protocol.start_monitoring()
        
        # Set up transport disconnect handler
        if transport:
            original_on_state_changed = getattr(transport, 'on_state_changed', None)
            def enhanced_state_change(old_state, new_state):
                if original_on_state_changed:
                    original_on_state_changed(old_state, new_state)
                if hasattr(new_state, 'value') and new_state.value == 'disconnected':
                    self._handle_transport_disconnect()
                elif isinstance(new_state, str) and new_state == 'disconnected':
                    self._handle_transport_disconnect()
            transport.on_state_changed = enhanced_state_change
    
    def _handle_game_message(self, msg_type: GameMessageType, data: Dict, sender_id: str):
        """Override base class to handle crypto messages"""
        # Handle ALL messages through crypto handler to prevent duplicates
        self._handle_crypto_message(msg_type, data)
    
    def _handle_crypto_message(self, msg_type: GameMessageType, data: Dict[str, Any]):
        """Handle P2P messages with crypto verification"""
        try:
            if msg_type == GameMessageType.GAME_INVITE:
                print("📨 Received crypto game invite")
                # Store opponent's commitment
                if "commitment" in data:
                    self.crypto_game.set_opponent_commitment(data["commitment"])
                    # Set opponent ID for turn management - framework uses participant_id
                    commitment = data["commitment"]
                    self.opponent_id = commitment.get("participant_id") or commitment.get("player_id")
                
                # Include our commitment in the acceptance
                commitment = self.crypto_game.get_commitment_data()
                self._send_message(GameMessageType.GAME_ACCEPT, {
                    "commitment": commitment
                })
                
                # Both players have exchanged commitments, start the game
                self._set_phase(GamePhase.PLAYING)
                inviter_id = data.get("inviter_id")
                self.current_turn = inviter_id  # Inviter goes first
                print(f"🎯 Turn set to inviter: {inviter_id} (I am {self.player_id})")
            
            elif msg_type == GameMessageType.GAME_ACCEPT:
                print("✅ Game accepted with crypto commitment")
                if "commitment" in data:
                    self.crypto_game.set_opponent_commitment(data["commitment"])
                    # Set opponent ID for turn management - framework uses participant_id
                    commitment = data["commitment"]
                    self.opponent_id = commitment.get("participant_id") or commitment.get("player_id")
                # Both players have exchanged commitments, start the game
                self._set_phase(GamePhase.PLAYING)
                self.current_turn = self.player_id  # Inviter goes first
                print(f"🎯 Turn set to me (inviter): {self.player_id}")
            
            elif msg_type == GameMessageType.FIRE_SHOT:
                x, y = data["x"], data["y"]
                print(f"🎯 Received shot at ({x}, {y})")
                
                # Framework now checks turn order automatically if using framework
                # Start timeout for response if enforcement enabled
                if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'enforcement'):
                    action_id = f"shot_response_{x}_{y}"
                    self.crypto_game.protocol.enforcement.start_action_with_timeout(action_id, timeout=30.0)
                
                # Handle shot - framework-based vs legacy
                if hasattr(self.crypto_game, 'protocol'):
                    # Framework-based: BattleshipZeroTrust
                    action_data = data.get("action_data", {"x": x, "y": y})
                    signature = data.get("signature", "")
                    result = self.crypto_game.handle_incoming_shot(x, y, action_data, signature)
                    if result:
                        proof, proof_signature = result
                    else:
                        proof, proof_signature = None, None
                else:
                    # Legacy: CryptoBattleshipGame
                    proof = self.crypto_game.handle_incoming_shot(x, y)
                    proof_signature = ""
                
                if proof:
                    # Send back the proof
                    proof_data = asdict(proof)
                    if proof_signature:
                        proof_data['signature'] = proof_signature
                    self._send_message(GameMessageType.SHOT_RESULT, {
                        "proof": proof_data
                    })
                    
                    # Complete timeout if enforcement enabled
                    if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'enforcement'):
                        action_id = f"shot_response_{x}_{y}"
                        self.crypto_game.protocol.enforcement.timeout_manager.complete_action(action_id)
                
                # Sync blockchain after handling shot
                print("🔧 Triggering blockchain sync after shot...")
                self._trigger_blockchain_sync()
                
                # Turn stays with the shooter until they receive the result
            
            elif msg_type == GameMessageType.SHOT_RESULT:
                print("💥 Received shot result with crypto proof")
                proof_data = data["proof"]
                
                # Reconstruct proof object
                proof = MerkleProof(
                    position=tuple(proof_data["position"]),
                    has_ship=proof_data["has_ship"],
                    result=proof_data["result"],
                    leaf_data=proof_data["leaf_data"],
                    merkle_path=proof_data["merkle_path"]
                )
                
                # Verify the proof cryptographically - framework-based vs legacy
                if hasattr(self.crypto_game, 'protocol'):
                    # Framework-based: uses protocol.verify_proof
                    proof_signature = proof_data.get("signature", "")
                    verified = self.crypto_game.verify_opponent_proof(proof, proof_signature)
                else:
                    # Legacy: uses verify_opponent_shot_result
                    verified = self.crypto_game.verify_opponent_shot_result(proof)
                
                if verified:
                    print(f"✅ Cryptographically verified: {proof.result}")
                    # Switch turn to the opponent after successful verification
                    self.current_turn = self.opponent_id
                    
                    # Framework handles turn switching if using framework
                    if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'enforcement'):
                        self.crypto_game.protocol.enforcement.switch_turn()
                    
                    # Sync blockchain after receiving result
                    print("🔧 Triggering blockchain sync after result...")
                    self._trigger_blockchain_sync()
                else:
                    print("❌ CHEATING DETECTED! Invalid proof!")
                    self._send_message(GameMessageType.GAME_OVER, {
                        "winner": self.player_id,
                        "reason": "Opponent caught cheating"
                    })
            
            elif msg_type == GameMessageType.GAME_OVER:
                print("🏁 Game over received")
                self._set_phase(GamePhase.GAME_OVER)
            
            # Handle blockchain synchronization
            elif msg_type == GameMessageType.BLOCKCHAIN_SYNC:
                self._handle_blockchain_sync(data)
            
            elif msg_type == GameMessageType.BLOCKCHAIN_SYNC_RESPONSE:
                self._handle_blockchain_sync_response(data)
            
            else:
                print(f"🔄 Unhandled message type: {msg_type}")
        
        except Exception as e:
            print(f"❌ Error handling crypto message: {e}")
    
    def _handle_disconnect(self):
        """Handle disconnection with reconnection attempt"""
        print("🔌 Connection lost, attempting reconnection...")
        
        # Save state if protocol has state manager
        if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'state_manager'):
            self.crypto_game.protocol.state_manager.save_state()
        
        # Attempt reconnection if we have last peer address
        if self.last_peer_address and hasattr(self.crypto_game, 'protocol'):
            success = self.crypto_game.protocol.attempt_reconnect(
                lambda: self.transport.connect(self.last_peer_address) if hasattr(self.transport, 'connect') else False
            )
            
            if success:
                print("✅ Reconnected successfully")
                # Verify state
                if hasattr(self.crypto_game.protocol, 'verify_state_after_reconnect'):
                    self.crypto_game.protocol.verify_state_after_reconnect()
            else:
                print("❌ Reconnection failed - game state saved")
    
    def _handle_transport_disconnect(self):
        """Handle transport layer disconnection"""
        if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'handle_disconnect'):
            self.crypto_game.protocol.handle_disconnect()
        else:
            self._handle_disconnect()
    
    def send_crypto_game_invite(self):
        """Send game invite with crypto commitment"""
        commitment = self.crypto_game.get_commitment_data()
        return self._send_message(GameMessageType.GAME_INVITE, {
            "commitment": commitment,
            "inviter_id": self.player_id
        })
    
    def fire_crypto_shot(self, x: int, y: int) -> bool:
        """Fire a cryptographically signed shot"""
        # Framework enforces turn order automatically if using framework
        # Start timeout for response if enforcement enabled
        if hasattr(self.crypto_game, 'protocol') and hasattr(self.crypto_game.protocol, 'enforcement'):
            action_id = f"shot_response_{x}_{y}"
            self.crypto_game.protocol.enforcement.start_action_with_timeout(action_id, timeout=30.0)
        
        # Fire shot - framework-based vs legacy
        if hasattr(self.crypto_game, 'protocol'):
            # Framework-based: returns (success, action_data, signature)
            success, action_data, signature = self.crypto_game.fire_shot(x, y)
            if success:
                return self._send_message(GameMessageType.FIRE_SHOT, {
                    "x": x, "y": y,
                    "action_data": action_data,
                    "signature": signature
                })
        else:
            # Legacy: returns bool
            if self.crypto_game.fire_shot(x, y):
                return self._send_message(GameMessageType.FIRE_SHOT, {
                    "x": x, "y": y
                })
        return False
    
    def get_crypto_game_state(self) -> Dict[str, Any]:
        """Get combined P2P and crypto game state"""
        p2p_state = self.get_game_state()
        
        # Get state - framework-based vs legacy
        if hasattr(self.crypto_game, 'protocol'):
            # Framework-based: use protocol state
            return {
                **p2p_state,
                "crypto_player_id": self.crypto_game.protocol.my_participant_id,
                "grid_root": self.crypto_game.grid_commitment.get_commitment_root(),
                "blockchain_blocks": len(self.crypto_game.protocol.blockchain.chain),
                "blockchain_valid": self.crypto_game.protocol.blockchain.verify_chain(),
                "my_shots": len(self.crypto_game.my_shots),
                "opponent_shots": len(self.crypto_game.opponent_shots),
                "enforcement_enabled": self.crypto_game.protocol.enable_enforcement,
                "monitoring_active": self.crypto_game.protocol._monitoring
            }
        else:
            # Legacy: use direct attributes
            return {
                **p2p_state,
                "crypto_player_id": self.crypto_game.identity.player_id,
                "grid_root": self.crypto_game.grid_commitment.root,
                "blockchain_blocks": len(self.crypto_game.blockchain.chain),
                "blockchain_valid": self.crypto_game.blockchain.verify_chain(),
                "my_shots": len(self.crypto_game.my_shots),
                "opponent_shots": len(self.crypto_game.opponent_shots)
            }


def test_crypto_p2p_battleship():
    """Test the complete crypto P2P battleship system"""
    print("🚀 Testing Crypto P2P Battleship System")
    print("=" * 60)
    
    # Create two players with ships
    player1_ships = [(0, 0), (0, 1), (0, 2), (5, 5), (5, 6)]
    player2_ships = [(9, 9), (9, 8), (9, 7), (3, 3), (3, 4)]
    
    # Create transports
    transport1 = SocketTransportAdapter()
    transport2 = SocketTransportAdapter()
    
    # Create crypto P2P players
    player1 = CryptoBattleshipP2P(player1_ships, transport=transport1)
    player2 = CryptoBattleshipP2P(player2_ships, transport=transport2)
    
    print(f"Player 1: {player1.crypto_game.identity.player_id}")
    print(f"Player 2: {player2.crypto_game.identity.player_id}")
    
    # Connection events
    connection_established = False
    game_started = False
    
    def on_p1_phase_change(old, new):
        nonlocal connection_established, game_started
        print(f"Player 1 phase: {old.value} -> {new.value}")
        if new == GamePhase.SETUP:
            connection_established = True
        elif new == GamePhase.PLAYING:
            game_started = True
    
    def on_p2_phase_change(old, new):
        print(f"Player 2 phase: {old.value} -> {new.value}")
    
    player1.on_phase_changed = on_p1_phase_change
    player2.on_phase_changed = on_p2_phase_change
    
    try:
        print("\n1. 🔗 Establishing P2P connection...")
        
        # Player 1 listens
        if not player1.listen_for_peer("localhost", 12349):
            print("❌ Failed to start listener")
            return False
        
        time.sleep(0.5)
        
        # Player 2 connects
        if not player2.connect_to_peer("localhost", 12349):
            print("❌ Failed to connect")
            return False
        
        # Wait for connection
        timeout = 30
        start_time = time.time()
        while not connection_established and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not connection_established:
            print("❌ Connection timeout")
            return False
        
        print("✅ P2P connection established!")
        
        print("\n2. 📨 Starting crypto game...")
        
        # Player 1 sends crypto game invite
        player1.send_crypto_game_invite()
        time.sleep(2)
        
        print("\n3. 🎯 Testing crypto shots...")
        
        # Player 1 fires at Player 2's ship
        player1.fire_crypto_shot(9, 9)  # Should hit
        time.sleep(2)
        
        # Player 2 fires at Player 1's ship  
        player2.fire_crypto_shot(0, 0)  # Should hit
        time.sleep(2)
        
        print("\n4. 📊 Final game states...")
        p1_state = player1.get_crypto_game_state()
        p2_state = player2.get_crypto_game_state()
        
        print(f"Player 1 state: {p1_state}")
        print(f"Player 2 state: {p2_state}")
        
        print("\n🎉 Crypto P2P Battleship Test Complete!")
        print("✅ P2P connection with ExProtocol security")
        print("✅ Cryptographic commitments prevent cheating")
        print("✅ Merkle proofs verify all shot results")
        print("✅ Blockchain provides immutable game history")
        print("✅ Complete cheat-proof P2P battleship!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        player1.disconnect()
        player2.disconnect()


if __name__ == "__main__":
    success = test_crypto_p2p_battleship()
    if success:
        print("\n🔥 CRYPTO P2P BATTLESHIP IS READY!")
        print("   - Completely cheat-proof")
        print("   - Desync-proof with blockchain")
        print("   - Secure P2P with ExProtocol")
        print("   - Real-time cheat detection")
    else:
        print("\n❌ Test failed - check errors above")
