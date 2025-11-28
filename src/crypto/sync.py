"""
Blockchain Synchronization and Consensus

Provides mechanisms for synchronizing blockchain state between peers:
- Ordered transaction processing
- Conflict resolution
- State reconciliation
- Merkle state roots
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from .blockchain import Blockchain, Transaction, Block


@dataclass
class SyncState:
    """State for blockchain synchronization"""
    chain_length: int
    chain_hash: str  # Hash of latest block
    state_root: str  # Merkle root of current state
    transaction_count: int
    participant_sequences: Dict[str, int]


class BlockchainSync:
    """
    Blockchain synchronization manager.
    
    Handles consensus and synchronization between two peers.
    """
    
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
        self.peer_state: Optional[SyncState] = None
    
    def get_sync_state(self) -> SyncState:
        """Get current synchronization state"""
        latest_block = self.blockchain.chain[-1] if self.blockchain.chain else None
        total_transactions = sum(len(block.transactions) for block in self.blockchain.chain)
        
        return SyncState(
            chain_length=len(self.blockchain.chain),
            chain_hash=latest_block.hash if latest_block else "0",
            state_root=self._calculate_state_root(),
            transaction_count=total_transactions,
            participant_sequences=self.blockchain.participant_sequences.copy()
        )
    
    def _calculate_state_root(self) -> str:
        """Calculate Merkle root of all transactions"""
        all_tx_hashes = []
        for block in self.blockchain.chain:
            for tx in block.transactions:
                # Convert transaction to dict, handling enums
                tx_dict = {
                    'move_type': tx.move_type.value if hasattr(tx.move_type, 'value') else str(tx.move_type),
                    'participant_id': tx.participant_id,
                    'data': tx.data,
                    'timestamp': tx.timestamp,
                    'signature': tx.signature,
                    'sequence_number': getattr(tx, 'sequence_number', 0)
                }
                tx_data = json.dumps(tx_dict, sort_keys=True)
                tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()
                all_tx_hashes.append(tx_hash)
        
        if not all_tx_hashes:
            return hashlib.sha256(b"empty").hexdigest()
        
        # Build Merkle tree
        while len(all_tx_hashes) > 1:
            if len(all_tx_hashes) % 2 == 1:
                all_tx_hashes.append(all_tx_hashes[-1])  # Duplicate last if odd
            
            next_level = []
            for i in range(0, len(all_tx_hashes), 2):
                combined = all_tx_hashes[i] + all_tx_hashes[i + 1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            all_tx_hashes = next_level
        
        return all_tx_hashes[0]
    
    def update_peer_state(self, peer_state: SyncState):
        """Update known peer state"""
        self.peer_state = peer_state
    
    def needs_sync(self) -> Tuple[bool, str]:
        """
        Check if synchronization is needed.
        Returns (needs_sync, reason)
        """
        if not self.peer_state:
            return False, "No peer state"
        
        my_state = self.get_sync_state()
        
        # Check if chains match
        if my_state.chain_length != self.peer_state.chain_length:
            return True, f"Chain length mismatch: {my_state.chain_length} vs {self.peer_state.chain_length}"
        
        if my_state.chain_hash != self.peer_state.chain_hash:
            return True, "Chain hash mismatch"
        
        if my_state.state_root != self.peer_state.state_root:
            return True, "State root mismatch"
        
        return False, "Synchronized"
    
    def get_missing_transactions(self, peer_sequences: Dict[str, int]) -> List[Transaction]:
        """
        Get transactions that peer is missing based on sequence numbers.
        """
        missing = []
        
        for block in self.blockchain.chain:
            for tx in block.transactions:
                participant = tx.participant_id
                peer_seq = peer_sequences.get(participant, 0)
                
                # Find transactions peer hasn't seen
                if participant in self.blockchain.participant_sequences:
                    my_seq = self.blockchain.participant_sequences[participant]
                    if peer_seq < my_seq:
                        # Check if this specific transaction is after peer's sequence
                        # This is simplified - in production would track per-tx sequences
                        missing.append(tx)
        
        return missing
    
    def merge_transactions(self, transactions: List[Transaction]) -> Tuple[bool, str]:
        """
        Merge transactions from peer into our blockchain.
        Resolves conflicts using sequence numbers.
        
        Returns (success, message)
        """
        if not transactions:
            return True, "No transactions to merge"
        
        # Sort by sequence number
        sorted_txs = sorted(transactions, key=lambda tx: tx.sequence_number)
        
        added = 0
        for tx in sorted_txs:
            # Check if we already have this transaction
            exists = False
            for block in self.blockchain.chain:
                for existing_tx in block.transactions:
                    if (existing_tx.participant_id == tx.participant_id and
                        existing_tx.sequence_number == tx.sequence_number):
                        exists = True
                        break
                if exists:
                    break
            
            if not exists:
                self.blockchain.add_transaction(tx)
                added += 1
        
        if added > 0:
            # Mine a block with merged transactions
            self.blockchain.mine_block()
            return True, f"Merged {added} transactions"
        
        return True, "All transactions already present"
    
    def resolve_conflict(self) -> Tuple[bool, str]:
        """
        Resolve blockchain conflicts.
        Uses longest chain rule and transaction ordering.
        
        Returns (resolved, message)
        """
        if not self.peer_state:
            return False, "No peer state to resolve against"
        
        my_state = self.get_sync_state()
        
        # Longest chain wins
        if self.peer_state.chain_length > my_state.chain_length:
            return False, "Peer has longer chain - need to request peer's chain"
        elif my_state.chain_length > self.peer_state.chain_length:
            return True, "My chain is longer - peer should sync to me"
        else:
            # Same length - use state root as tiebreaker
            if my_state.state_root == self.peer_state.state_root:
                return True, "Chains are synchronized"
            else:
                # Need manual resolution or accept peer's chain
                return False, "Chain conflict - same length different state"


def create_sync_message(blockchain: Blockchain) -> Dict[str, Any]:
    """Create a synchronization message to send to peer"""
    sync = BlockchainSync(blockchain)
    state = sync.get_sync_state()
    
    return {
        'type': 'blockchain_sync',
        'state': asdict(state)
    }


def handle_sync_message(blockchain: Blockchain, message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle incoming synchronization message.
    Returns response message.
    """
    sync = BlockchainSync(blockchain)
    peer_state = SyncState(**message['state'])
    sync.update_peer_state(peer_state)
    
    needs_sync, reason = sync.needs_sync()
    
    if needs_sync:
        # Get transactions peer might need
        my_state = sync.get_sync_state()
        missing_txs = sync.get_missing_transactions(peer_state.participant_sequences)
        
        return {
            'type': 'blockchain_sync_response',
            'needs_sync': True,
            'reason': reason,
            'my_state': asdict(my_state),
            'transactions': [asdict(tx) for tx in missing_txs]
        }
    
    return {
        'type': 'blockchain_sync_response',
        'needs_sync': False,
        'reason': reason
    }


__all__ = [
    'BlockchainSync',
    'SyncState',
    'create_sync_message',
    'handle_sync_message'
]

