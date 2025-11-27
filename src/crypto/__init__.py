"""
Cryptographic Framework for Commitments and Proofs

This package provides cryptographic primitives for verifiable commitments:
- Merkle tree commitments
- Cryptographic identity and signatures  
- Immutable blockchain for history
- Proof generation and verification

The framework is domain-agnostic and reusable.
"""

# Framework API (recommended way to use)
from .framework import CryptoFramework, create_crypto_framework

# Core components (for direct access if needed)
from .merkle import MerkleProof, MerkleGridCommitment, SimpleMerkleTree
from .identity import CryptoIdentity
from .blockchain import Blockchain, Transaction, MoveType, Block

__all__ = [
    # Framework API
    'CryptoFramework',
    'create_crypto_framework',
    # Core components
    'MerkleProof',
    'MerkleGridCommitment',
    'SimpleMerkleTree',
    'CryptoIdentity',
    'Blockchain',
    'Transaction',
    'MoveType',
    'Block'
]
