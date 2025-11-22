"""
Core Game Logic for Crypto Battleship
Main game class that orchestrates all cryptographic components
"""

import os
import json
import time
from typing import List, Tuple, Optional, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crypto.merkle import MerkleGridCommitment, MerkleProof
from crypto.identity import CryptoIdentity
from crypto.blockchain import BattleshipBlockchain, GameMove, MoveType


class CryptoBattleshipGame:
    """Main cryptographically secure battleship game"""
    
    def __init__(self, ship_positions: List[Tuple[int, int]], seed: bytes = None):
        self.seed = seed or os.urandom(32)
        self.ship_positions = ship_positions
        
        # Cryptographic components
        self.identity = CryptoIdentity(self.seed, ship_positions)
        self.grid_commitment = MerkleGridCommitment(ship_positions, self.seed)
        self.blockchain = BattleshipBlockchain()
        
        # Game state
        self.opponent_root: Optional[str] = None
        self.opponent_public_key = None
        self.opponent_player_id: Optional[str] = None
        self.my_shots: List[Tuple[int, int]] = []
        self.opponent_shots: List[Tuple[int, int]] = []
        self.game_over = False
        
        print(f"🎮 Crypto Battleship Player Created!")
        print(f"   Player ID: {self.identity.player_id}")
        print(f"   Grid Root: {self.grid_commitment.root[:16]}...")
        print(f"   Ships: {len(ship_positions)} placed")
    
    def get_commitment_data(self) -> Dict[str, str]:
        """Get data to share with opponent for game setup"""
        return {
            'player_id': self.identity.player_id,
            'grid_root': self.grid_commitment.root,
            'public_key': self.identity.public_key.to_string().hex()
        }
    
    def set_opponent_commitment(self, opponent_data: Dict[str, str]):
        """Set opponent's commitment data"""
        from ecdsa import VerifyingKey, SECP256k1
        
        self.opponent_player_id = opponent_data['player_id']
        self.opponent_root = opponent_data['grid_root']
        self.opponent_public_key = VerifyingKey.from_string(
            bytes.fromhex(opponent_data['public_key']), 
            curve=SECP256k1
        )
        
        # Add commitment to blockchain
        move = GameMove(
            move_type=MoveType.GRID_COMMITMENT,
            player_id=self.opponent_player_id,
            data=opponent_data,
            timestamp=time.time(),
            signature=""  # Commitment doesn't need signature
        )
        self.blockchain.add_move(move)
        
        print(f"🤝 Opponent commitment received!")
        print(f"   Opponent ID: {self.opponent_player_id}")
        print(f"   Grid Root: {self.opponent_root[:16]}...")
    
    def fire_shot(self, x: int, y: int) -> bool:
        """Fire a shot at opponent"""
        # Validate coordinates
        if x < 0 or x >= 10 or y < 0 or y >= 10:
            raise ValueError(f"Invalid coordinates ({x}, {y}). Must be in range [0, 9]")
        
        if (x, y) in self.my_shots:
            print(f"❌ Already fired at ({x}, {y})")
            return False
        
        self.my_shots.append((x, y))
        print(f"🎯 Fired shot at ({x}, {y})")
        return True
    
    def handle_incoming_shot(self, x: int, y: int) -> MerkleProof:
        """Handle shot from opponent and generate cryptographic proof"""
        # Validate coordinates
        if x < 0 or x >= 10 or y < 0 or y >= 10:
            raise ValueError(f"Invalid coordinates ({x}, {y}). Must be in range [0, 9]")
        
        if (x, y) in self.opponent_shots:
            raise ValueError(f"Position ({x}, {y}) already shot at!")
        
        self.opponent_shots.append((x, y))
        
        # Generate Merkle proof (cannot lie!)
        proof = self.grid_commitment.generate_proof(x, y)
        
        print(f"💥 Shot at ({x}, {y}) - Result: {proof.result.upper()}")
        return proof
    
    def verify_opponent_shot_result(self, proof: MerkleProof) -> bool:
        """Verify opponent's shot result using Merkle proof"""
        if not self.opponent_root:
            raise ValueError("Opponent commitment not set!")
        
        # Verify Merkle proof
        if not MerkleGridCommitment.verify_proof(proof, self.opponent_root):
            print("❌ Invalid Merkle proof - OPPONENT IS CHEATING!")
            return False
        
        print(f"✅ Verified shot result: {proof.result.upper()} at {proof.position}")
        return True
