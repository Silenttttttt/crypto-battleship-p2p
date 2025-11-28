"""
Zero-Trust Cryptographic Framework

This package provides a complete zero-trust protocol framework:
- Zero-Trust Protocol (main framework class)
- Merkle tree commitments (zero-knowledge)
- Cryptographic identity and signatures (authentication)
- Synchronized blockchain (immutable shared history)
- Independent verification (anyone can verify)

The framework is domain-agnostic and reusable for any application
needing cryptographic guarantees without trust.
"""

# Main Framework API (recommended)
from .protocol import ZeroTrustProtocol, VerificationResult
from .commitment import CommitmentScheme, GridCommitment
from .framework import CryptoFramework, create_crypto_framework
from .sync import BlockchainSync, SyncState, create_sync_message, handle_sync_message
from .timeout import (
    TimeoutConfig, TimeoutReason, ActionTimeout, ErrorRecovery,
    DisputeResolution, ProtocolMonitor
)
from .cheating import CheatType, CheatEvidence, CheatDetector, CheatInvalidator

# Core components (for advanced usage)
from .merkle import MerkleProof, MerkleGridCommitment, SimpleMerkleTree
from .identity import CryptoIdentity
from .blockchain import Blockchain, Transaction, MoveType, Block

__all__ = [
    # Main Framework API
    'ZeroTrustProtocol',
    'VerificationResult',
    'CommitmentScheme',
    'GridCommitment',
    'CryptoFramework',
    'create_crypto_framework',
    'BlockchainSync',
    'SyncState',
    'create_sync_message',
    'handle_sync_message',
    'TimeoutConfig',
    'TimeoutReason',
    'ActionTimeout',
    'ErrorRecovery',
    'DisputeResolution',
    'ProtocolMonitor',
    'CheatType',
    'CheatEvidence',
    'CheatDetector',
    'CheatInvalidator',
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
