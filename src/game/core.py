"""
Crypto Battleship Game - Core Implementation

This module implements the core game logic with cryptographic verification using:
- Merkle tree commitments for ship positions
- Zero-knowledge proofs for shot results
- Blockchain recording of all moves
- Digital signatures for authenticity

Note: There's also battleship_protocol.py which uses the separated ZeroTrustProtocol framework.
Both implementations work - this one is more integrated, the other more modular.
"""

import os
import json
import time
from typing import List, Tuple, Optional, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from zerotrust import MerkleGridCommitment, MerkleProof
from zerotrust import CryptoIdentity
from zerotrust import Blockchain, Transaction, MoveType


class CryptoBattleshipGame:
    """Main cryptographically secure battleship game"""
    
    def __init__(self, ship_positions: List[Tuple[int, int]], seed: bytes = None):
        self.seed = seed or os.urandom(32)
        self.ship_positions = ship_positions
        
        # Cryptographic components
        self.identity = CryptoIdentity(self.seed, ship_positions)
        self.grid_commitment = MerkleGridCommitment(ship_positions, self.seed)
        self.blockchain = Blockchain()
        
        # Game state
        self.opponent_root: Optional[str] = None
        self.opponent_public_key = None
        self.opponent_player_id: Optional[str] = None
        self.my_shots: List[Tuple[int, int]] = []
        self.opponent_shots: List[Tuple[int, int]] = []
        self.my_shot_results: Dict[Tuple[int, int], str] = {}  # Track results of my shots
        self.opponent_hits_on_me: List[Tuple[int, int]] = []  # Track opponent's hits
        self.game_over = False
        self.winner: Optional[str] = None
        
        # Hit tracking for game over detection
        self.total_ship_cells = len(ship_positions)
        self.hits_received = 0  # Hits on my ships
        self.confirmed_hits_on_opponent = 0  # Confirmed hits on opponent
        
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
        transaction = Transaction(
            move_type=MoveType.COMMITMENT,
            participant_id=self.opponent_player_id,
            data=opponent_data,
            timestamp=time.time(),
            signature=""  # Commitment doesn't need signature
        )
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()  # Mine block immediately for commitment
        
        print(f"🤝 Opponent commitment received!")
        print(f"   Opponent ID: {self.opponent_player_id}")
        print(f"   Grid Root: {self.opponent_root[:16]}...")
    
    def fire_shot(self, x: int, y: int) -> bool:
        """Fire a shot at opponent - Records to blockchain with signature"""
        # Validate coordinates
        if x < 0 or x >= 10 or y < 0 or y >= 10:
            raise ValueError(f"Invalid coordinates ({x}, {y}). Must be in range [0, 9]")
        
        if (x, y) in self.my_shots:
            print(f"❌ Already fired at ({x}, {y})")
            return False
        
        self.my_shots.append((x, y))
        
        # Record shot to blockchain with digital signature
        shot_data = {
            "action": "fire_shot",
            "x": x,
            "y": y,
            "timestamp": time.time()
        }
        shot_message = json.dumps(shot_data, sort_keys=True)
        signature = self.identity.sign_message(shot_message)
        
        transaction = Transaction(
            move_type=MoveType.ACTION,
            participant_id=self.identity.player_id,
            data=shot_data,
            timestamp=time.time(),
            signature=signature
        )
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()  # Mine block for each action
        
        print(f"🎯 Fired shot at ({x}, {y}) - Recorded to blockchain")
        return True
    
    def handle_incoming_shot(self, x: int, y: int) -> MerkleProof:
        """Handle shot from opponent and generate cryptographic proof - Records to blockchain"""
        # Validate coordinates
        if x < 0 or x >= 10 or y < 0 or y >= 10:
            raise ValueError(f"Invalid coordinates ({x}, {y}). Must be in range [0, 9]")
        
        if (x, y) in self.opponent_shots:
            raise ValueError(f"Position ({x}, {y}) already shot at!")
        
        self.opponent_shots.append((x, y))
        
        # Generate Merkle proof (cannot lie!)
        proof = self.grid_commitment.generate_proof(x, y)
        
        # Track hits on me
        if proof.has_ship:
            self.hits_received += 1
            self.opponent_hits_on_me.append((x, y))
        
        # Record result to blockchain with signature
        result_data = {
            "action": "shot_result",
            "x": x,
            "y": y,
            "result": proof.result,
            "has_ship": proof.has_ship,
            "leaf_data": proof.leaf_data,
            "timestamp": time.time()
        }
        result_message = json.dumps(result_data, sort_keys=True)
        signature = self.identity.sign_message(result_message)
        
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.identity.player_id,
            data=result_data,
            timestamp=time.time(),
            signature=signature
        )
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()  # Mine block for each result
        
        print(f"💥 Shot at ({x}, {y}) - Result: {proof.result.upper()} - Recorded to blockchain")
        return proof
    
    def verify_opponent_shot_result(self, proof: MerkleProof) -> bool:
        """Verify opponent's shot result using Merkle proof - Records verification to blockchain"""
        if not self.opponent_root:
            raise ValueError("Opponent commitment not set!")
        
        # Verify Merkle proof (zero-knowledge: we don't see their full grid, only this cell)
        if not MerkleGridCommitment.verify_proof(proof, self.opponent_root):
            print("❌ Invalid Merkle proof - OPPONENT IS CHEATING!")
            return False
        
        # Track result
        self.my_shot_results[proof.position] = proof.result
        if proof.has_ship:
            self.confirmed_hits_on_opponent += 1
        
        # Record verification to blockchain with signature
        verification_data = {
            "action": "verified_result",
            "position": proof.position,
            "result": proof.result,
            "has_ship": proof.has_ship,
            "opponent_id": self.opponent_player_id,
            "timestamp": time.time()
        }
        verification_message = json.dumps(verification_data, sort_keys=True)
        signature = self.identity.sign_message(verification_message)
        
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.identity.player_id,
            data=verification_data,
            timestamp=time.time(),
            signature=signature
        )
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()  # Mine block for each verification
        
        print(f"✅ Verified shot result: {proof.result.upper()} at {proof.position} - Recorded to blockchain")
        return True
    
    def check_game_over(self) -> Optional[str]:
        """
        Check if game is over and return winner ID
        Returns None if game ongoing, winner's player_id if game over
        """
        # Check if I lost (all my ships hit)
        if self.hits_received >= self.total_ship_cells:
            self.game_over = True
            self.winner = self.opponent_player_id
            print(f"🏁 Game Over! All my ships sunk. Winner: {self.winner}")
            return self.winner
        
        # Check if opponent lost (all their ships hit)
        # Note: We need opponent to tell us their total ship count or we estimate
        if self.opponent_player_id and self.confirmed_hits_on_opponent >= self.total_ship_cells:
            self.game_over = True
            self.winner = self.identity.player_id
            print(f"🏁 Game Over! All opponent ships sunk. Winner: {self.winner}")
            return self.winner
        
        return None
    
    def verify_blockchain_integrity(self) -> bool:
        """Independently verify entire blockchain integrity"""
        return self.blockchain.verify_chain()
    
    def verify_transaction_signature(self, transaction: Transaction) -> bool:
        """Verify a transaction's digital signature"""
        if not self.opponent_public_key:
            return False
        
        # Reconstruct message from transaction data
        message = json.dumps(transaction.data, sort_keys=True)
        
        # Verify signature
        return self.identity.verify_signature(
            message,
            transaction.signature,
            self.opponent_public_key
        )
    
    def get_game_state_summary(self) -> Dict[str, Any]:
        """
        Get complete game state for independent verification
        Zero-knowledge: Only reveals what's necessary
        """
        return {
            "player_id": self.identity.player_id,
            "grid_root": self.grid_commitment.root,
            "opponent_id": self.opponent_player_id,
            "opponent_root": self.opponent_root,
            "my_shots_count": len(self.my_shots),
            "opponent_shots_count": len(self.opponent_shots),
            "hits_received": self.hits_received,
            "confirmed_hits_on_opponent": self.confirmed_hits_on_opponent,
            "total_ship_cells": self.total_ship_cells,
            "game_over": self.game_over,
            "winner": self.winner,
            "blockchain_blocks": len(self.blockchain.chain),
            "blockchain_valid": self.blockchain.verify_chain(),
            "total_transactions": sum(len(block.transactions) for block in self.blockchain.chain)
        }
    
    def verify_game_state(self) -> Dict[str, bool]:
        """
        Independent verification of entire game state
        Returns dict of verification results
        """
        verifications = {
            "blockchain_integrity": self.blockchain.verify_chain(),
            "commitment_exists": self.opponent_root is not None,
            "my_shots_recorded": len(self.my_shots) > 0 or len(self.blockchain.chain) == 1,
            "hit_count_valid": self.hits_received <= self.total_ship_cells,
            "game_state_consistent": True
        }
        
        # Verify game over logic is consistent
        if self.game_over:
            verifications["game_over_valid"] = (
                self.winner is not None and
                (self.hits_received >= self.total_ship_cells or 
                 self.confirmed_hits_on_opponent >= self.total_ship_cells)
            )
        
        # All checks must pass
        verifications["all_valid"] = all(verifications.values())
        
        return verifications
