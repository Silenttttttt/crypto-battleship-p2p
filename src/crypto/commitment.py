"""
Generic Commitment Interface

Provides a generic interface for creating commitments
that applications can implement.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Tuple


class CommitmentScheme(ABC):
    """
    Abstract base class for commitment schemes.
    
    Applications implement this to define how they commit to state.
    The framework uses this interface generically.
    """
    
    @abstractmethod
    def get_commitment_root(self) -> str:
        """
        Get the commitment root hash.
        This is what gets shared publicly.
        """
        pass
    
    @abstractmethod
    def generate_proof(self, query: Any) -> Any:
        """
        Generate zero-knowledge proof for a query.
        
        Args:
            query: Application-specific query (e.g., grid coordinates)
        
        Returns:
            Proof object (application-specific)
        """
        pass
    
    @abstractmethod
    def verify_proof(self, proof: Any, committed_root: str) -> bool:
        """
        Verify a proof against a commitment root.
        
        Args:
            proof: The proof to verify
            committed_root: The commitment root to verify against
        
        Returns:
            True if proof is valid, False otherwise
        """
        pass


class GridCommitment(CommitmentScheme):
    """
    Grid-based commitment using Merkle trees.
    
    This is a concrete implementation for grid-based applications
    (like battleship, chess, checkers, etc.)
    """
    
    def __init__(self, marked_positions: List[Tuple[int, int]], 
                 seed: bytes, 
                 grid_size: int = 10):
        """
        Create commitment to a grid with marked positions.
        
        Args:
            marked_positions: List of (x, y) positions that are marked
            seed: Secret seed for the commitment
            grid_size: Size of the grid
        """
        from .merkle import MerkleGridCommitment
        
        self._commitment = MerkleGridCommitment(marked_positions, seed, grid_size)
        self.grid_size = grid_size
    
    def get_commitment_root(self) -> str:
        return self._commitment.root
    
    def generate_proof(self, query: Tuple[int, int]) -> Any:
        """Query is (x, y) coordinates"""
        return self._commitment.generate_proof(*query)
    
    def verify_proof(self, proof: Any, committed_root: str) -> bool:
        from .merkle import MerkleGridCommitment
        return MerkleGridCommitment.verify_proof(proof, committed_root)


__all__ = [
    'CommitmentScheme',
    'GridCommitment'
]

