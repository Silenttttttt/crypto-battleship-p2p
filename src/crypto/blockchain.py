"""
Blockchain Implementation for Immutable History
Maintains immutable record of all transactions/actions
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class MoveType(Enum):
    """Types of transactions that can be recorded"""
    COMMITMENT = "commitment"
    ACTION = "action"
    RESULT = "result"
    TERMINATION = "termination"


@dataclass
class Transaction:
    """Individual transaction in the blockchain"""
    move_type: MoveType
    participant_id: str
    data: Dict[str, Any]
    timestamp: float
    signature: str
    sequence_number: int = 0  # For consensus ordering


class Block:
    """Individual block in the blockchain"""
    
    def __init__(self, prev_hash: str, transactions: List[Transaction], block_number: int):
        self.prev_hash = prev_hash
        self.transactions = transactions
        self.block_number = block_number
        self.timestamp = time.time()
        self.hash = self._calculate_block_hash()
    
    def _calculate_block_hash(self) -> str:
        """Calculate this block's hash"""
        transactions_data = json.dumps([{
            'move_type': tx.move_type.value,
            'participant_id': tx.participant_id,
            'data': tx.data,
            'timestamp': tx.timestamp,
            'signature': tx.signature
        } for tx in self.transactions], sort_keys=True)
        
        block_data = f"{self.prev_hash}:{transactions_data}:{self.block_number}:{self.timestamp}"
        return hashlib.sha256(block_data.encode()).hexdigest()


class Blockchain:
    """Blockchain for immutable history with consensus support"""
    
    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.transaction_sequence: int = 0  # Global sequence
        self.participant_sequences: Dict[str, int] = {}  # Per-participant
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Create the first block"""
        genesis = Block("0" * 64, [], 0)
        self.chain.append(genesis)
    
    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Add a transaction to pending transactions with sequence number.
        Ensures ordering for consensus.
        """
        # Assign sequence number if not set
        if transaction.sequence_number == 0:
            self.transaction_sequence += 1
            transaction.sequence_number = self.transaction_sequence
        
        # Track per-participant sequence
        participant = transaction.participant_id
        if participant not in self.participant_sequences:
            self.participant_sequences[participant] = 0
        self.participant_sequences[participant] += 1
        
        self.pending_transactions.append(transaction)
        return True
    
    def mine_block(self) -> Optional[Block]:
        """Create new block with pending transactions"""
        if not self.pending_transactions:
            return None
        
        prev_hash = self.chain[-1].hash
        block_number = len(self.chain)
        new_block = Block(prev_hash, self.pending_transactions.copy(), block_number)
        
        self.chain.append(new_block)
        self.pending_transactions.clear()
        
        return new_block
    
    def verify_chain(self) -> bool:
        """Verify the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            prev_block = self.chain[i - 1]
            
            # Verify hash links
            if current_block.prev_hash != prev_block.hash:
                return False
            
            # Verify block hash
            if current_block.hash != current_block._calculate_block_hash():
                return False
        
        return True
    
    def get_transactions_by_participant(self, participant_id: str) -> List[Transaction]:
        """Get all transactions by a specific participant"""
        transactions = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.participant_id == participant_id:
                    transactions.append(tx)
        return transactions
