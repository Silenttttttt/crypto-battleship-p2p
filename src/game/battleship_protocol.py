"""
Battleship Game Using Zero-Trust Framework

This is a THIN LAYER over the framework - just game-specific logic.
All crypto/verification is handled by the framework.
"""

import os
import json
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crypto import (ZeroTrustProtocol, VerificationResult, GridCommitment,
                    CheatDetector, CheatType, CheatInvalidator)
from crypto.merkle import MerkleProof


@dataclass
class Ship:
    """Ship with hit tracking"""
    positions: List[Tuple[int, int]]
    hits: List[bool]
    name: str = "Ship"
    
    def is_sunk(self) -> bool:
        return all(self.hits)
    
    def mark_hit(self, position: Tuple[int, int]) -> bool:
        """Mark a position as hit if it's part of this ship"""
        if position in self.positions:
            idx = self.positions.index(position)
            self.hits[idx] = True
            return True
        return False


class BattleshipZeroTrust:
    """
    Battleship Game using Zero-Trust Protocol Framework
    
    This class USES the framework - it doesn't implement crypto itself.
    All cryptographic operations are delegated to ZeroTrustProtocol.
    """
    
    def __init__(self, ship_positions: List[Tuple[int, int]], seed: bytes = None,
                 enable_enforcement: bool = True, enable_persistence: bool = True,
                 enable_monitoring: bool = True, save_path: str = None):
        self.seed = seed or os.urandom(32)
        self.ship_positions = ship_positions
        
        # Create grid commitment (domain-specific)
        self.grid_commitment = GridCommitment(ship_positions, self.seed)
        
        # Initialize Zero-Trust Protocol (framework does the crypto)
        self.protocol = ZeroTrustProtocol(
            my_commitment_data=ship_positions,
            seed=self.seed,
            enable_enforcement=enable_enforcement,
            enable_persistence=enable_persistence,
            save_path=save_path
        )
        
        # Start monitoring if enabled
        if enable_monitoring and enable_enforcement:
            self.protocol.start_monitoring()
        
        # Cheat detection
        self.cheat_detector = CheatDetector(self.protocol.my_participant_id)
        self.cheat_invalidator = CheatInvalidator()
        
        # Game-specific state (not crypto)
        self.ships: List[Ship] = []
        self.my_shots: List[Tuple[int, int]] = []
        self.opponent_shots: List[Tuple[int, int]] = []
        self.my_shot_results: Dict[Tuple[int, int], str] = {}
        
        # Hit tracking for game over
        self.total_ship_cells = len(ship_positions)
        self.hits_received = 0
        self.confirmed_hits_on_opponent = 0
        
        # Create ships from positions (simple grouping for now)
        self._initialize_ships()
        
        print(f"🎮 Battleship Player Created (using Zero-Trust Framework)!")
        print(f"   Player ID: {self.protocol.my_participant_id}")
        print(f"   Commitment Root: {self.grid_commitment.get_commitment_root()[:16]}...")
        print(f"   Ships: {len(ship_positions)} cells")
    
    def _initialize_ships(self):
        """Initialize ship objects by grouping adjacent positions"""
        if not self.ship_positions:
            return
        
        # Group adjacent positions into ships
        remaining = set(self.ship_positions)
        ship_num = 1
        
        while remaining:
            # Start a new ship
            start_pos = remaining.pop()
            ship_positions = [start_pos]
            
            # Find all adjacent positions (horizontal or vertical)
            changed = True
            while changed:
                changed = False
                for pos in list(remaining):
                    # Check if adjacent to any position in current ship
                    for ship_pos in ship_positions:
                        # Adjacent if same row and consecutive columns, or same column and consecutive rows
                        if ((pos[0] == ship_pos[0] and abs(pos[1] - ship_pos[1]) == 1) or
                            (pos[1] == ship_pos[1] and abs(pos[0] - ship_pos[0]) == 1)):
                            ship_positions.append(pos)
                            remaining.remove(pos)
                            changed = True
                            break
                    if changed:
                        break
            
            # Sort positions for consistent ordering
            ship_positions.sort()
            
            # Create ship object
            ship = Ship(
                positions=ship_positions,
                hits=[False] * len(ship_positions),
                name=f"Ship_{ship_num}" if len(ship_positions) > 1 else f"Boat_{ship_num}"
            )
            self.ships.append(ship)
            ship_num += 1
        
        print(f"   Initialized {len(self.ships)} ships: {[len(s.positions) for s in self.ships]}")
    
    def get_commitment_data(self) -> Dict[str, str]:
        """Get commitment data to share with opponent"""
        commitment = self.protocol.get_my_commitment()
        commitment['commitment_root'] = self.grid_commitment.get_commitment_root()
        return commitment
    
    def set_opponent_commitment(self, commitment: Dict[str, str]) -> bool:
        """
        Set opponent's commitment.
        Framework verifies and records it.
        """
        result = self.protocol.set_opponent_commitment(commitment)
        
        if result.valid:
            # Store opponent's commitment root for proof verification
            self.opponent_commitment_root = commitment.get('commitment_root')
            print(f"✅ {result.reason}")
            return True
        else:
            print(f"❌ {result.reason}")
            return False
    
    def fire_shot(self, x: int, y: int) -> Tuple[bool, Dict[str, Any], str]:
        """
        Fire a shot - Framework handles signing and recording.
        Returns (success, action_data, signature) tuple.
        """
        if (x, y) in self.my_shots:
            return False, {}, ""
        
        self.my_shots.append((x, y))
        
        # Framework records action with signature
        action_data = {"x": x, "y": y}
        complete_action_data, signature = self.protocol.record_my_action("fire_shot", action_data)
        
        print(f"🎯 Fired at ({x}, {y}) - Framework recorded with signature")
        return True, complete_action_data, signature
    
    def handle_incoming_shot(self, 
                            x: int, y: int,
                            action_data: Dict[str, Any],
                            signature: str) -> Optional[Tuple[MerkleProof, str]]:
        """
        Handle opponent's shot - Framework verifies signature first.
        Returns (proof, proof_signature) tuple if valid.
        
        Args:
            x, y: Shot coordinates
            action_data: Complete action data that was signed
            signature: Signature to verify
        """
        # Framework verifies opponent's action signature
        verification = self.protocol.verify_opponent_action(action_data, signature)
        
        if not verification.valid:
            print(f"❌ {verification.reason}")
            return None
        
        # Track shot
        if (x, y) in self.opponent_shots:
            print(f"❌ Position already shot at!")
            return None
        
        self.opponent_shots.append((x, y))
        
        # Generate proof (using commitment)
        proof = self.grid_commitment.generate_proof((x, y))
        
        # Track hits
        if proof.has_ship:
            self.hits_received += 1
            # Mark hit on ship
            for ship in self.ships:
                ship.mark_hit((x, y))
        
        # Framework generates signed proof
        proof_obj, proof_signature = self.protocol.generate_proof(
            self.grid_commitment,
            (x, y)
        )
        
        print(f"💥 Shot at ({x}, {y}) - Result: {proof.result.upper()} - Framework verified & recorded")
        return proof, proof_signature
    
    def verify_opponent_proof(self, 
                             proof: MerkleProof, 
                             proof_signature: str) -> bool:
        """
        Verify opponent's proof - Framework handles verification.
        DETECTS AND RECORDS CHEATING if proof is invalid.
        """
        if not hasattr(self, 'opponent_commitment_root'):
            print("❌ Opponent commitment not set!")
            return False
        
        # Framework verifies proof
        verification = self.protocol.verify_proof(
            proof,
            proof_signature,
            self.opponent_commitment_root
        )
        
        if not verification.valid:
            print(f"❌ {verification.reason}")
            
            # RECORD CHEATING WITH EVIDENCE
            self.cheat_detector.record_cheat(
                cheat_type=CheatType.INVALID_PROOF,
                cheater_id=self.protocol.opponent_participant_id,
                description=f"Invalid proof for position {proof.position}: {verification.reason}",
                evidence={
                    'proof': {
                        'position': proof.position,
                        'has_ship': proof.has_ship,
                        'result': proof.result,
                        'leaf_data': proof.leaf_data,
                        'merkle_path': proof.merkle_path
                    },
                    'commitment_root': self.opponent_commitment_root,
                    'proof_signature': proof_signature
                }
            )
            
            # INVALIDATE OPPONENT
            self.cheat_invalidator.invalidate_participant(
                self.protocol.opponent_participant_id,
                self.cheat_detector.cheating_proof
            )
            
            print(f"🚫 OPPONENT INVALIDATED - CHEATING DETECTED AND PROVEN")
            return False
        
        # Track result
        self.my_shot_results[proof.position] = proof.result
        if proof.has_ship:
            self.confirmed_hits_on_opponent += 1
        
        print(f"✅ {verification.reason} - Result: {proof.result.upper()}")
        return True
    
    def check_game_over(self) -> Optional[str]:
        """
        Check if game is over.
        Returns winner's participant_id or None.
        """
        # I lost - all my ships hit
        if self.hits_received >= self.total_ship_cells:
            winner = self.protocol.opponent_participant_id
            print(f"🏁 Game Over! All my ships sunk. Winner: {winner}")
            return winner
        
        # Opponent lost - all their ships hit
        if self.confirmed_hits_on_opponent >= self.total_ship_cells:
            winner = self.protocol.my_participant_id
            print(f"🏁 Game Over! All opponent ships sunk. Winner: {winner}")
            return winner
        
        return None
    
    def get_game_state(self) -> Dict[str, Any]:
        """
        Get complete game state.
        Includes framework protocol state + game-specific state.
        """
        protocol_state = self.protocol.get_protocol_state()
        
        return {
            **protocol_state,
            'my_shots_count': len(self.my_shots),
            'opponent_shots_count': len(self.opponent_shots),
            'hits_received': self.hits_received,
            'confirmed_hits_on_opponent': self.confirmed_hits_on_opponent,
            'total_ship_cells': self.total_ship_cells,
            'ships_sunk': sum(1 for ship in self.ships if ship.is_sunk()),
            'total_ships': len(self.ships)
        }
    
    def verify_game_state(self) -> VerificationResult:
        """
        Verify entire game state using framework.
        Framework handles all cryptographic verification.
        """
        # Framework verifies blockchain and signatures
        blockchain_result = self.protocol.verify_blockchain_integrity()
        if not blockchain_result.valid:
            return blockchain_result
        
        signatures_result = self.protocol.verify_all_signatures()
        if not signatures_result.valid:
            return signatures_result
        
        # Verify game-specific state consistency
        if self.hits_received > self.total_ship_cells:
            return VerificationResult(
                valid=False,
                reason="Invalid state: more hits than ship cells"
            )
        
        return VerificationResult(
            valid=True,
            reason="Game state fully verified"
        )
    
    def replay_entire_game(self) -> VerificationResult:
        """
        Replay entire game from blockchain using framework.
        Framework does all the cryptographic verification.
        """
        return self.protocol.replay_from_blockchain()
    
    def reveal_grid(self) -> Dict[str, Any]:
        """
        Reveal grid after game completion for verification.
        Opponent can verify no cheating occurred.
        """
        revelation = self.protocol.reveal_commitment(self.ship_positions)
        revelation['grid_commitment_root'] = self.grid_commitment.get_commitment_root()
        return revelation
    
    def verify_opponent_grid(self, revelation: Dict[str, Any]) -> VerificationResult:
        """
        Verify opponent's revealed grid.
        Checks that their commitment matches their actual ship positions.
        DETECTS POST-GAME CHEATING.
        """
        # First verify the revelation signature
        result = self.protocol.verify_opponent_revelation(
            revelation,
            self.opponent_commitment_root
        )
        
        if not result.valid:
            # Record signature forgery
            self.cheat_detector.record_cheat(
                cheat_type=CheatType.FORGED_SIGNATURE,
                cheater_id=self.protocol.opponent_participant_id,
                description="Invalid signature on grid revelation",
                evidence={'revelation': revelation}
            )
            self.cheat_invalidator.invalidate_participant(
                self.protocol.opponent_participant_id,
                self.cheat_detector.cheating_proof
            )
            return result
        
        # Reconstruct opponent's commitment from revealed data
        try:
            revealed_positions = revelation['commitment_data']
            revealed_seed_hex = revelation['seed']
            revealed_seed = bytes.fromhex(revealed_seed_hex)
            
            # Reconstruct commitment
            from crypto import GridCommitment
            reconstructed_commitment = GridCommitment(
                marked_positions=revealed_positions,
                seed=revealed_seed
            )
            
            # Check if commitment root matches
            if reconstructed_commitment.get_commitment_root() != self.opponent_commitment_root:
                # RECORD COMMITMENT MISMATCH - PROOF OF CHEATING
                self.cheat_detector.record_cheat(
                    cheat_type=CheatType.COMMITMENT_MISMATCH,
                    cheater_id=self.protocol.opponent_participant_id,
                    description=f"Revealed grid doesn't match commitment! Expected {self.opponent_commitment_root[:16]}..., got {reconstructed_commitment.get_commitment_root()[:16]}...",
                    evidence={
                        'revealed_positions': revealed_positions,
                        'revealed_seed': revealed_seed_hex,
                        'claimed_commitment': self.opponent_commitment_root,
                        'actual_commitment': reconstructed_commitment.get_commitment_root()
                    }
                )
                
                self.cheat_invalidator.invalidate_participant(
                    self.protocol.opponent_participant_id,
                    self.cheat_detector.cheating_proof
                )
                
                return VerificationResult(
                    valid=False,
                    reason="🚫 OPPONENT CHEATED! Revealed grid doesn't match commitment - INVALIDATED"
                )
            
            # Verify all our shots against revealed grid
            for shot_pos, result_str in self.my_shot_results.items():
                actual_hit = shot_pos in revealed_positions
                claimed_hit = (result_str == 'hit')
                
                if actual_hit != claimed_hit:
                    # RECORD LYING ABOUT SHOT RESULTS
                    self.cheat_detector.record_cheat(
                        cheat_type=CheatType.INVALID_PROOF,
                        cheater_id=self.protocol.opponent_participant_id,
                        description=f"Lied about shot at {shot_pos}! Claimed {result_str}, actually {'hit' if actual_hit else 'miss'}",
                        evidence={
                            'shot_position': shot_pos,
                            'claimed_result': result_str,
                            'actual_result': 'hit' if actual_hit else 'miss',
                            'revealed_grid': revealed_positions
                        }
                    )
                    
                    self.cheat_invalidator.invalidate_participant(
                        self.protocol.opponent_participant_id,
                        self.cheat_detector.cheating_proof
                    )
                    
                    return VerificationResult(
                        valid=False,
                        reason=f"🚫 OPPONENT CHEATED! Lied about shot at {shot_pos} - INVALIDATED"
                    )
            
            return VerificationResult(
                valid=True,
                reason="Opponent's revealed grid matches commitment - no cheating detected!",
                details={'revealed_positions': revealed_positions}
            )
            
        except Exception as e:
            return VerificationResult(
                valid=False,
                reason=f"Error verifying revelation: {e}"
            )


__all__ = [
    'BattleshipZeroTrust',
    'Ship'
]

