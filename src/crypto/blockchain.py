"""
Blockchain Implementation for Game History
Maintains immutable record of all game moves
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class MoveType(Enum):
    """Types of moves that can be recorded"""
    GRID_COMMITMENT = "grid_commitment"
    SHOT_FIRED = "shot_fired"
    SHOT_RESULT = "shot_result"
    GAME_OVER = "game_over"


@dataclass
class GameMove:
    """Individual move in the game"""
    move_type: MoveType
    player_id: str
    data: Dict[str, Any]
    timestamp: float
    signature: str


class GameBlock:
    """Individual block in the battleship blockchain"""
    
    def __init__(self, prev_hash: str, moves: List[GameMove], block_number: int):
        self.prev_hash = prev_hash
        self.moves = moves
        self.block_number = block_number
        self.timestamp = time.time()
        self.hash = self._calculate_block_hash()
    
    def _calculate_block_hash(self) -> str:
        """Calculate this block's hash"""
        moves_data = json.dumps([{
            'move_type': move.move_type.value,
            'player_id': move.player_id,
            'data': move.data,
            'timestamp': move.timestamp,
            'signature': move.signature
        } for move in self.moves], sort_keys=True)
        
        block_data = f"{self.prev_hash}:{moves_data}:{self.block_number}:{self.timestamp}"
        return hashlib.sha256(block_data.encode()).hexdigest()


class BattleshipBlockchain:
    """Blockchain for immutable game history"""
    
    def __init__(self):
        self.chain: List[GameBlock] = []
        self.pending_moves: List[GameMove] = []
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Create the first block"""
        genesis = GameBlock("0" * 64, [], 0)
        self.chain.append(genesis)
    
    def add_move(self, move: GameMove) -> bool:
        """Add a move to pending moves"""
        self.pending_moves.append(move)
        return True
    
    def mine_block(self) -> Optional[GameBlock]:
        """Create new block with pending moves"""
        if not self.pending_moves:
            return None
        
        prev_hash = self.chain[-1].hash
        block_number = len(self.chain)
        new_block = GameBlock(prev_hash, self.pending_moves.copy(), block_number)
        
        self.chain.append(new_block)
        self.pending_moves.clear()
        
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
    
    def get_moves_by_player(self, player_id: str) -> List[GameMove]:
        """Get all moves by a specific player"""
        moves = []
        for block in self.chain:
            for move in block.moves:
                if move.player_id == player_id:
                    moves.append(move)
        return moves
