"""
Cheat Detection and Proof System

Provides mechanisms to detect, prove, and invalidate cheaters.
"""

import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class CheatType(Enum):
    """Types of cheating that can be detected"""
    INVALID_PROOF = "invalid_proof"  # Proof doesn't verify
    FORGED_SIGNATURE = "forged_signature"  # Signature doesn't match
    COMMITMENT_MISMATCH = "commitment_mismatch"  # Revealed grid doesn't match commitment
    BLOCKCHAIN_TAMPERING = "blockchain_tampering"  # Blockchain hash chain invalid
    INVALID_MOVE = "invalid_move"  # Move violates rules
    TIMEOUT_STALL = "timeout_stall"  # Deliberately stalling
    DOUBLE_MOVE = "double_move"  # Multiple moves in one turn


@dataclass
class CheatEvidence:
    """Evidence of cheating"""
    cheat_type: CheatType
    cheater_id: str
    description: str
    evidence: Dict[str, Any]
    timestamp: float
    witness_id: str  # Who detected the cheating


class CheatDetector:
    """
    Detects and records cheating attempts.
    
    Maintains cryptographic proof of cheating for dispute resolution.
    """
    
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.detected_cheats: List[CheatEvidence] = []
        self.opponent_is_cheater = False
        self.cheating_proof: Optional[CheatEvidence] = None
    
    def record_cheat(self, 
                    cheat_type: CheatType,
                    cheater_id: str,
                    description: str,
                    evidence: Dict[str, Any]) -> CheatEvidence:
        """
        Record detected cheating attempt with evidence.
        
        Args:
            cheat_type: Type of cheating detected
            cheater_id: ID of the cheater
            description: Human-readable description
            evidence: Cryptographic evidence (proofs, signatures, etc.)
        
        Returns:
            CheatEvidence object
        """
        cheat = CheatEvidence(
            cheat_type=cheat_type,
            cheater_id=cheater_id,
            description=description,
            evidence=evidence,
            timestamp=time.time(),
            witness_id=self.participant_id
        )
        
        self.detected_cheats.append(cheat)
        
        # Flag opponent as cheater
        self.opponent_is_cheater = True
        self.cheating_proof = cheat
        
        return cheat
    
    def has_detected_cheating(self) -> bool:
        """Check if any cheating was detected"""
        return len(self.detected_cheats) > 0
    
    def get_cheating_proof(self) -> Optional[CheatEvidence]:
        """Get proof of cheating for dispute resolution"""
        return self.cheating_proof
    
    def create_cheat_report(self) -> Dict[str, Any]:
        """
        Create a comprehensive cheat report.
        This can be shared with third parties for verification.
        """
        return {
            'detector_id': self.participant_id,
            'opponent_is_cheater': self.opponent_is_cheater,
            'total_cheats_detected': len(self.detected_cheats),
            'cheats': [
                {
                    'type': cheat.cheat_type.value,
                    'cheater_id': cheat.cheater_id,
                    'description': cheat.description,
                    'timestamp': cheat.timestamp,
                    'evidence': cheat.evidence
                }
                for cheat in self.detected_cheats
            ]
        }
    
    def verify_cheat_claim(self, 
                          cheat_evidence: CheatEvidence,
                          blockchain: Any,
                          opponent_public_key: Any) -> bool:
        """
        Verify a cheat claim is legitimate.
        Third party can use this to verify cheating accusations.
        
        Args:
            cheat_evidence: The cheating evidence to verify
            blockchain: The blockchain to check against
            opponent_public_key: Alleged cheater's public key
        
        Returns:
            True if cheat claim is valid
        """
        if cheat_evidence.cheat_type == CheatType.INVALID_PROOF:
            # Verify that the proof in evidence is indeed invalid
            proof_data = cheat_evidence.evidence.get('proof')
            commitment_root = cheat_evidence.evidence.get('commitment_root')
            
            if proof_data and commitment_root:
                from .merkle import MerkleGridCommitment, MerkleProof
                proof = MerkleProof(**proof_data)
                is_valid = MerkleGridCommitment.verify_proof(proof, commitment_root)
                # If proof is invalid, cheat claim is valid
                return not is_valid
        
        elif cheat_evidence.cheat_type == CheatType.FORGED_SIGNATURE:
            # Verify that signature in evidence is indeed forged
            message = cheat_evidence.evidence.get('message')
            signature = cheat_evidence.evidence.get('signature')
            
            if message and signature and opponent_public_key:
                from .identity import CryptoIdentity
                identity = CryptoIdentity(b"dummy", [])
                is_valid = identity.verify_signature(message, signature, opponent_public_key)
                # If signature is invalid, cheat claim is valid
                return not is_valid
        
        elif cheat_evidence.cheat_type == CheatType.BLOCKCHAIN_TAMPERING:
            # Verify blockchain is invalid
            if blockchain:
                is_valid = blockchain.verify_chain()
                # If blockchain is invalid, cheat claim is valid
                return not is_valid
        
        # Can't verify this type of cheat
        return False


class CheatInvalidator:
    """
    Handles invalidation of cheaters.
    
    When cheating is proven, invalidates all their actions.
    """
    
    def __init__(self):
        self.invalidated_participants: Dict[str, CheatEvidence] = {}
    
    def invalidate_participant(self, 
                              participant_id: str, 
                              evidence: CheatEvidence) -> None:
        """
        Invalidate a participant due to proven cheating.
        
        Args:
            participant_id: ID of cheater to invalidate
            evidence: Cryptographic proof of cheating
        """
        self.invalidated_participants[participant_id] = evidence
        print(f"🚫 PARTICIPANT INVALIDATED: {participant_id}")
        print(f"   Reason: {evidence.cheat_type.value}")
        print(f"   Proof: {evidence.description}")
    
    def is_invalidated(self, participant_id: str) -> bool:
        """Check if a participant has been invalidated"""
        return participant_id in self.invalidated_participants
    
    def get_invalidation_proof(self, participant_id: str) -> Optional[CheatEvidence]:
        """Get proof of why participant was invalidated"""
        return self.invalidated_participants.get(participant_id)
    
    def forfeit_game(self, cheater_id: str, winner_id: str) -> Dict[str, Any]:
        """
        Forfeit game due to cheating.
        Returns game over data with cheating evidence.
        """
        evidence = self.invalidated_participants.get(cheater_id)
        
        return {
            'game_over': True,
            'winner': winner_id,
            'reason': 'opponent_caught_cheating',
            'cheater': cheater_id,
            'cheat_type': evidence.cheat_type.value if evidence else 'unknown',
            'evidence': asdict(evidence) if evidence else {},
            'timestamp': time.time()
        }


__all__ = [
    'CheatType',
    'CheatEvidence',
    'CheatDetector',
    'CheatInvalidator'
]

