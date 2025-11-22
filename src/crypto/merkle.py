"""
Merkle Tree Implementation for Crypto Battleship
Provides cryptographic commitments and proofs for grid cells
"""

import hashlib
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class MerkleProof:
    """Proof that a specific grid cell has a certain value"""
    position: Tuple[int, int]
    has_ship: bool
    result: str  # 'hit' or 'miss'
    leaf_data: str
    merkle_path: List[Dict[str, Any]]


class SimpleMerkleTree:
    """Simple, robust Merkle tree implementation"""
    
    def __init__(self, data_list: List[str]):
        self.data_list = data_list
        self.leaves = [hashlib.sha256(data.encode()).digest() for data in data_list]
        self.tree = self._build_tree()
        self.root = self.tree[-1][0] if self.tree else b''
    
    def _build_tree(self) -> List[List[bytes]]:
        """Build the complete Merkle tree"""
        if not self.leaves:
            return []
        
        tree = [self.leaves]
        current_level = self.leaves
        
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent = hashlib.sha256(left + right).digest()
                next_level.append(parent)
            
            tree.append(next_level)
            current_level = next_level
        
        return tree
    
    def get_proof(self, index: int) -> List[Tuple[bytes, bool]]:
        """Get Merkle proof for leaf at given index"""
        if index >= len(self.leaves):
            raise ValueError(f"Index {index} out of range")
        
        proof = []
        current_index = index
        
        for level in range(len(self.tree) - 1):
            level_size = len(self.tree[level])
            sibling_index = current_index ^ 1  # XOR with 1 to get sibling
            
            if sibling_index < level_size:
                sibling_hash = self.tree[level][sibling_index]
                is_left = sibling_index < current_index
                proof.append((sibling_hash, is_left))
            else:
                # If sibling doesn't exist, use the node itself (odd number case)
                sibling_hash = self.tree[level][current_index]
                is_left = False
                proof.append((sibling_hash, is_left))
            
            current_index //= 2
        
        return proof
    
    def verify_proof(self, leaf_data: str, proof: List[Tuple[bytes, bool]]) -> bool:
        """Verify a Merkle proof"""
        current_hash = hashlib.sha256(leaf_data.encode()).digest()
        
        for sibling_hash, is_left in proof:
            if is_left:
                current_hash = hashlib.sha256(sibling_hash + current_hash).digest()
            else:
                current_hash = hashlib.sha256(current_hash + sibling_hash).digest()
        
        return current_hash == self.root


class MerkleGridCommitment:
    """Merkle tree commitment for battleship grid"""
    
    def __init__(self, ship_positions: List[Tuple[int, int]], seed: bytes, grid_size: int = 10):
        self.ship_positions = set(ship_positions)
        self.seed = seed
        self.grid_size = grid_size
        
        # Create grid data for each cell
        self.grid_data = []
        for x in range(grid_size):
            for y in range(grid_size):
                has_ship = (x, y) in self.ship_positions
                cell_data = f"{seed.hex()}:{x}:{y}:{has_ship}"
                self.grid_data.append(cell_data)
        
        # Build Merkle tree
        self.merkle_tree = SimpleMerkleTree(self.grid_data)
        self.root = self.merkle_tree.root.hex()
    
    def generate_proof(self, x: int, y: int) -> MerkleProof:
        """Generate Merkle proof for a specific cell"""
        # Validate coordinates
        if x < 0 or x >= self.grid_size or y < 0 or y >= self.grid_size:
            raise ValueError(f"Invalid coordinates ({x}, {y}). Must be in range [0, {self.grid_size-1}]")
        
        index = x * self.grid_size + y
        has_ship = (x, y) in self.ship_positions
        result = 'hit' if has_ship else 'miss'
        leaf_data = self.grid_data[index]
        
        # Get proof from tree
        proof_tuples = self.merkle_tree.get_proof(index)
        merkle_path = [
            {'hash': sibling_hash.hex(), 'is_left': is_left}
            for sibling_hash, is_left in proof_tuples
        ]
        
        return MerkleProof(
            position=(x, y),
            has_ship=has_ship,
            result=result,
            leaf_data=leaf_data,
            merkle_path=merkle_path
        )
    
    @staticmethod
    def verify_proof(proof: MerkleProof, committed_root: str) -> bool:
        """Verify a Merkle proof against committed root"""
        # Verify leaf data consistency
        parts = proof.leaf_data.split(':')
        if len(parts) != 4:
            return False
        
        x, y = int(parts[1]), int(parts[2])
        has_ship = parts[3] == 'True'
        
        if (x, y) != proof.position or has_ship != proof.has_ship:
            return False
        
        # Verify result consistency
        expected_result = 'hit' if has_ship else 'miss'
        if proof.result != expected_result:
            return False
        
        # Reconstruct root from proof
        current_hash = hashlib.sha256(proof.leaf_data.encode()).digest()
        
        for path_element in proof.merkle_path:
            sibling_hash = bytes.fromhex(path_element['hash'])
            is_left = path_element['is_left']
            
            if is_left:
                current_hash = hashlib.sha256(sibling_hash + current_hash).digest()
            else:
                current_hash = hashlib.sha256(current_hash + sibling_hash).digest()
        
        final_root = current_hash.hex()
        return final_root == committed_root
