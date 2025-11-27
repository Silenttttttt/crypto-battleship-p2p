"""
Cryptographic Framework for Commitments and Proofs

This framework provides:
- Merkle tree commitments for state
- Cryptographic identity and signatures
- Immutable blockchain for history
- Proof generation and verification

The framework is domain-agnostic and can be used for any application
that needs cryptographic guarantees and verifiable commitments.
"""

from typing import List, Tuple, Optional, Dict, Any
from .merkle import MerkleGridCommitment, MerkleProof, SimpleMerkleTree
from .identity import CryptoIdentity
from .blockchain import Blockchain, Transaction, MoveType, Block


class CryptoFramework:
    """
    Main framework class that provides cryptographic primitives.
    
    This is the entry point for applications to use cryptographic features:
    - Commitments (Merkle trees)
    - Identity and signatures
    - Blockchain for immutable history
    """
    
    def __init__(self, seed: bytes = None):
        """
        Initialize the cryptographic framework.
        
        Args:
            seed: Optional seed for deterministic key generation
        """
        self.seed = seed
        self._identity: Optional[CryptoIdentity] = None
        self._blockchain: Optional[Blockchain] = None
    
    def create_identity(self, data: Any) -> CryptoIdentity:
        """
        Create a cryptographic identity from data.
        
        Args:
            data: Application-specific data used for identity generation
        
        Returns:
            CryptoIdentity instance
        """
        if not self.seed:
            import os
            self.seed = os.urandom(32)
        
        self._identity = CryptoIdentity(self.seed, data)
        return self._identity
    
    def get_identity(self) -> Optional[CryptoIdentity]:
        """Get the current identity, or None if not created."""
        return self._identity
    
    def create_blockchain(self) -> Blockchain:
        """
        Create a new blockchain for immutable history.
        
        Returns:
            Blockchain instance
        """
        self._blockchain = Blockchain()
        return self._blockchain
    
    def get_blockchain(self) -> Optional[Blockchain]:
        """Get the current blockchain, or None if not created."""
        return self._blockchain
    
    @staticmethod
    def create_grid_commitment(
        positions: List[Tuple[int, int]], 
        seed: bytes, 
        grid_size: int = 10
    ) -> MerkleGridCommitment:
        """
        Create a Merkle tree commitment for a grid-based structure.
        
        Args:
            positions: List of (x, y) positions that are "marked"
            seed: Secret seed for the commitment
            grid_size: Size of the grid (default 10x10)
        
        Returns:
            MerkleGridCommitment instance
        """
        return MerkleGridCommitment(positions, seed, grid_size)
    
    @staticmethod
    def verify_proof(proof: MerkleProof, committed_root: str) -> bool:
        """
        Verify a Merkle proof against a committed root.
        
        Args:
            proof: The Merkle proof to verify
            committed_root: The root hash that was committed to
        
        Returns:
            True if proof is valid, False otherwise
        """
        return MerkleGridCommitment.verify_proof(proof, committed_root)
    
    @staticmethod
    def create_merkle_tree(data_list: List[str]) -> SimpleMerkleTree:
        """
        Create a generic Merkle tree from a list of data strings.
        
        Args:
            data_list: List of data strings to commit to
        
        Returns:
            SimpleMerkleTree instance
        """
        return SimpleMerkleTree(data_list)


# Convenience functions for direct framework usage
def create_crypto_framework(seed: bytes = None) -> CryptoFramework:
    """
    Create a new cryptographic framework instance.
    
    Args:
        seed: Optional seed for deterministic operations
    
    Returns:
        CryptoFramework instance
    """
    return CryptoFramework(seed)


__all__ = [
    'CryptoFramework',
    'create_crypto_framework',
    # Re-export core types for convenience
    'MerkleGridCommitment',
    'MerkleProof',
    'SimpleMerkleTree',
    'CryptoIdentity',
    'Blockchain',
    'Transaction',
    'MoveType',
    'Block',
]

