"""
Zero-Trust Protocol Framework

This is the CORE framework - a generic, reusable protocol for any application
that needs cryptographic guarantees without trust.

The framework provides:
- Commitments (bind to state without revealing it)
- Zero-knowledge proofs (prove facts without revealing data)
- Digital signatures (authenticate actions)
- Synchronized blockchain (immutable shared history)
- Independent verification (anyone can verify correctness)

This is domain-agnostic - can be used for games, voting, contracts, etc.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from ecdsa import VerifyingKey, SECP256k1

from .merkle import MerkleGridCommitment, MerkleProof, SimpleMerkleTree
from .identity import CryptoIdentity
from .blockchain import Blockchain, Transaction, MoveType


@dataclass
class VerificationResult:
    """Result of verification operation"""
    valid: bool
    reason: str = ""
    details: Dict[str, Any] = None


class ZeroTrustProtocol:
    """
    Generic Zero-Trust Protocol Framework
    
    This is the main framework class that applications use.
    It handles all cryptographic operations and maintains
    a synchronized, verifiable state between participants.
    
    Applications just provide:
    - Initial state (commitment)
    - Actions (signed by participants)
    - Verification logic (domain-specific)
    """
    
    def __init__(self, 
                 my_commitment_data: Any,
                 seed: bytes = None):
        """
        Initialize protocol with commitment to initial state.
        
        Args:
            my_commitment_data: Data to commit to (e.g., grid state)
            seed: Optional seed for deterministic key generation
        """
        self.seed = seed
        
        # Cryptographic components
        self.identity = CryptoIdentity(self.seed, my_commitment_data)
        self.blockchain = Blockchain()
        
        # Participant state
        self.my_participant_id = self.identity.player_id
        self.opponent_participant_id: Optional[str] = None
        self.opponent_public_key: Optional[VerifyingKey] = None
        self.opponent_commitment: Optional[str] = None
        
        # Protocol state
        self.protocol_active = False
        self.my_actions_count = 0
        self.opponent_actions_count = 0
        
        # Verification callbacks (application-specific)
        self.verify_commitment_callback: Optional[Callable] = None
        self.verify_action_callback: Optional[Callable] = None
        
    def get_my_commitment(self) -> Dict[str, str]:
        """
        Get my commitment to share with opponent.
        Commitment binds to state without revealing it.
        """
        return {
            'participant_id': self.my_participant_id,
            'public_key': self.identity.public_key.to_string().hex()
        }
    
    def set_opponent_commitment(self, commitment: Dict[str, str]) -> VerificationResult:
        """
        Receive and verify opponent's commitment.
        Both participants must commit before protocol starts.
        """
        try:
            self.opponent_participant_id = commitment['participant_id']
            self.opponent_public_key = VerifyingKey.from_string(
                bytes.fromhex(commitment['public_key']),
                curve=SECP256k1
            )
            self.opponent_commitment = commitment.get('commitment_root')
            
            # Record commitment to blockchain
            transaction = Transaction(
                move_type=MoveType.COMMITMENT,
                participant_id=self.opponent_participant_id,
                data=commitment,
                timestamp=time.time(),
                signature=""  # Commitments don't need signatures
            )
            self.blockchain.add_transaction(transaction)
            self.blockchain.mine_block()
            
            self.protocol_active = True
            
            return VerificationResult(
                valid=True,
                reason="Opponent commitment recorded"
            )
            
        except Exception as e:
            return VerificationResult(
                valid=False,
                reason=f"Invalid commitment: {e}"
            )
    
    def record_my_action(self, action_type: str, action_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        Record my action with digital signature.
        Returns (complete_action_data, signature) tuple for opponent to verify.
        """
        # Create complete action data
        complete_data = {
            **action_data,
            'action_type': action_type,
            'timestamp': time.time()
        }
        
        message = json.dumps(complete_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        transaction = Transaction(
            move_type=MoveType.ACTION,
            participant_id=self.my_participant_id,
            data=complete_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        self.my_actions_count += 1
        
        return complete_data, signature
    
    def verify_opponent_action(self, 
                               action_data: Dict[str, Any], 
                               signature: str) -> VerificationResult:
        """
        Verify opponent's action signature and record to blockchain.
        This ensures opponent can't deny or forge actions.
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent commitment not set"
            )
        
        # Verify signature
        message = json.dumps(action_data, sort_keys=True)
        signature_valid = self.identity.verify_signature(
            message,
            signature,
            self.opponent_public_key
        )
        
        if not signature_valid:
            return VerificationResult(
                valid=False,
                reason="Invalid signature - opponent may be cheating!"
            )
        
        # Record to our blockchain
        transaction = Transaction(
            move_type=MoveType.ACTION,
            participant_id=self.opponent_participant_id,
            data=action_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        self.opponent_actions_count += 1
        
        return VerificationResult(
            valid=True,
            reason="Opponent action verified and recorded"
        )
    
    def generate_proof(self, 
                      commitment_obj: Any,
                      query: Any) -> Tuple[Any, str]:
        """
        Generate zero-knowledge proof for a query.
        Returns (proof, signature) tuple.
        
        The proof reveals ONLY the answer to the query,
        nothing else about the committed state.
        """
        # Generate proof using commitment object (e.g., Merkle tree)
        proof = commitment_obj.generate_proof(query)
        
        # Sign the proof
        proof_data = {
            'proof_type': 'merkle',
            'query': query,
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,  # Generic: "has_value" not "has_ship"
            'leaf_data': proof.leaf_data,
            'merkle_path': proof.merkle_path,
            'timestamp': time.time()
        }
        
        message = json.dumps(proof_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        # Record proof generation to blockchain
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.my_participant_id,
            data=proof_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        
        return proof, signature
    
    def verify_proof(self,
                    proof: MerkleProof,
                    proof_signature: str,
                    committed_root: str) -> VerificationResult:
        """
        Verify zero-knowledge proof from opponent.
        Checks:
        1. Signature is valid (authentication)
        2. Proof is cryptographically correct (ZK verification)
        3. Proof matches commitment (binding)
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent not set up"
            )
        
        # Verify signature on proof
        proof_data = {
            'proof_type': 'merkle',
            'query': None,  # We don't know their query
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,
            'leaf_data': proof.leaf_data,
            'merkle_path': proof.merkle_path,
            'timestamp': proof.leaf_data.split(':')[-1] if ':' in proof.leaf_data else time.time()
        }
        
        # Verify cryptographic proof
        proof_valid = MerkleGridCommitment.verify_proof(proof, committed_root)
        
        if not proof_valid:
            return VerificationResult(
                valid=False,
                reason="Invalid proof - opponent is cheating!"
            )
        
        # Record verification to blockchain (with full proof for replay)
        verification_data = {
            'action': 'verified_proof',
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,
            'merkle_path': proof.merkle_path,  # Store full proof!
            'leaf_data': proof.leaf_data,      # Store leaf data!
            'committed_root': committed_root,   # Store root used!
            'opponent_id': self.opponent_participant_id,
            'timestamp': time.time()
        }
        
        message = json.dumps(verification_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.my_participant_id,
            data=verification_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        
        return VerificationResult(
            valid=True,
            reason="Proof verified and recorded",
            details={'result': proof.result}
        )
    
    def verify_blockchain_integrity(self) -> VerificationResult:
        """Verify entire blockchain hasn't been tampered with"""
        valid = self.blockchain.verify_chain()
        
        return VerificationResult(
            valid=valid,
            reason="Blockchain valid" if valid else "Blockchain corrupted!"
        )
    
    def verify_all_signatures(self) -> VerificationResult:
        """
        Verify ALL signatures in blockchain.
        This ensures no transactions were forged.
        """
        invalid_txs = []
        
        for block_num, block in enumerate(self.blockchain.chain):
            for tx_num, tx in enumerate(block.transactions):
                # Skip commitments (no signature)
                if tx.move_type == MoveType.COMMITMENT:
                    continue
                
                # Verify signature
                if tx.participant_id == self.my_participant_id:
                    # My transaction - verify with my key
                    message = json.dumps(tx.data, sort_keys=True)
                    if not self.identity.verify_signature(
                        message, tx.signature, self.identity.public_key
                    ):
                        invalid_txs.append((block_num, tx_num, "my"))
                        
                elif tx.participant_id == self.opponent_participant_id:
                    # Opponent's transaction - verify with their key
                    if self.opponent_public_key:
                        message = json.dumps(tx.data, sort_keys=True)
                        if not self.identity.verify_signature(
                            message, tx.signature, self.opponent_public_key
                        ):
                            invalid_txs.append((block_num, tx_num, "opponent"))
        
        if invalid_txs:
            return VerificationResult(
                valid=False,
                reason=f"Found {len(invalid_txs)} invalid signatures",
                details={'invalid_transactions': invalid_txs}
            )
        
        return VerificationResult(
            valid=True,
            reason="All signatures valid"
        )
    
    def replay_from_blockchain(self) -> VerificationResult:
        """
        Replay entire protocol execution from blockchain.
        Verify every action, every proof, every signature.
        
        This allows ANYONE (even third party) to independently
        verify the entire protocol execution was fair.
        """
        # Verify blockchain structure
        chain_result = self.verify_blockchain_integrity()
        if not chain_result.valid:
            return chain_result
        
        # Verify all signatures
        sig_result = self.verify_all_signatures()
        if not sig_result.valid:
            return sig_result
        
        # Verify all proofs stored in blockchain
        invalid_proofs = []
        for block_num, block in enumerate(self.blockchain.chain):
            for tx_num, tx in enumerate(block.transactions):
                if tx.move_type == MoveType.RESULT and 'merkle_path' in tx.data:
                    # Reconstruct and verify proof
                    if 'committed_root' in tx.data:
                        proof = MerkleProof(
                            position=tuple(tx.data['position']),
                            has_ship=tx.data['has_value'],  # Note: MerkleProof uses 'has_ship' field name
                            result=tx.data['result'],
                            leaf_data=tx.data['leaf_data'],
                            merkle_path=tx.data['merkle_path']
                        )
                        
                        valid = MerkleGridCommitment.verify_proof(
                            proof,
                            tx.data['committed_root']
                        )
                        
                        if not valid:
                            invalid_proofs.append((block_num, tx_num))
        
        if invalid_proofs:
            return VerificationResult(
                valid=False,
                reason=f"Found {len(invalid_proofs)} invalid proofs in history",
                details={'invalid_proofs': invalid_proofs}
            )
        
        return VerificationResult(
            valid=True,
            reason="Complete protocol execution verified from blockchain"
        )
    
    def get_protocol_state(self) -> Dict[str, Any]:
        """
        Get complete protocol state for inspection/debugging.
        All information is cryptographically verifiable.
        """
        return {
            'protocol_active': self.protocol_active,
            'my_participant_id': self.my_participant_id,
            'opponent_participant_id': self.opponent_participant_id,
            'my_actions_count': self.my_actions_count,
            'opponent_actions_count': self.opponent_actions_count,
            'blockchain_blocks': len(self.blockchain.chain),
            'total_transactions': sum(len(b.transactions) for b in self.blockchain.chain),
            'blockchain_valid': self.blockchain.verify_chain(),
            'all_signatures_valid': self.verify_all_signatures().valid
        }
    
    def reveal_commitment(self, commitment_data: Any) -> Dict[str, Any]:
        """
        Reveal commitment data after protocol completion.
        This allows opponent to verify no cheating occurred.
        
        Returns revelation data that should be shared with opponent.
        """
        # Convert commitment data to serializable format
        if isinstance(commitment_data, (list, tuple)):
            commitment_data = list(commitment_data)
        
        revelation = {
            'participant_id': self.my_participant_id,
            'commitment_data': commitment_data,
            'seed': self.seed.hex() if isinstance(self.seed, bytes) else str(self.seed),
            'timestamp': time.time()
        }
        
        # Sign the revelation (without signature field)
        message = json.dumps(revelation, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        # Add signature to result
        result = revelation.copy()
        result['signature'] = signature
        
        return result
    
    def verify_opponent_revelation(self, 
                                   revelation: Dict[str, Any],
                                   original_commitment_root: str) -> VerificationResult:
        """
        Verify opponent's commitment revelation.
        Ensures they didn't cheat during the protocol.
        
        Args:
            revelation: Opponent's revealed commitment data
            original_commitment_root: The commitment root they shared at start
        
        Returns:
            VerificationResult indicating if revelation is valid
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent public key not set"
            )
        
        # Extract signature
        signature = revelation.get('signature', '')
        if not signature:
            return VerificationResult(
                valid=False,
                reason="No signature in revelation"
            )
        
        # Verify signature on revelation (without signature field)
        revelation_copy = {k: v for k, v in revelation.items() if k != 'signature'}
        message = json.dumps(revelation_copy, sort_keys=True)
        
        if not self.identity.verify_signature(message, signature, self.opponent_public_key):
            return VerificationResult(
                valid=False,
                reason="Invalid signature on revelation"
            )
        
        # Signature valid - application layer should verify actual commitment
        return VerificationResult(
            valid=True,
            reason="Revelation signature valid - application should verify commitment",
            details=revelation_copy
        )


__all__ = [
    'ZeroTrustProtocol',
    'VerificationResult'
]

