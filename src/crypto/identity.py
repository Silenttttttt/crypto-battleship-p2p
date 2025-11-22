"""
Cryptographic Identity Management
Handles player identity, key derivation, and digital signatures
"""

import hashlib
import json
from typing import List, Tuple
import ecdsa
from ecdsa import SigningKey, VerifyingKey, SECP256k1


class CryptoIdentity:
    """Cryptographic identity derived from seed and grid"""
    
    def __init__(self, seed: bytes, ship_positions: List[Tuple[int, int]]):
        self.seed = seed
        self.ship_positions = ship_positions
        self.private_key, self.public_key = self._derive_keypair()
        self.player_id = self._generate_player_id()
    
    def _derive_keypair(self) -> Tuple[SigningKey, VerifyingKey]:
        """Derive ECDSA keypair from seed and ship positions"""
        # Create deterministic key material
        ship_data = json.dumps(sorted(self.ship_positions), sort_keys=True)
        key_material = hashlib.sha256(self.seed + ship_data.encode()).digest()
        
        # Create ECDSA keypair
        private_key = SigningKey.from_string(key_material, curve=SECP256k1)
        public_key = private_key.get_verifying_key()
        
        return private_key, public_key
    
    def _generate_player_id(self) -> str:
        """Generate unique player ID from public key"""
        public_key_bytes = self.public_key.to_string()
        return hashlib.sha256(public_key_bytes).hexdigest()[:16]
    
    def sign_message(self, message: str) -> str:
        """Sign a message with private key"""
        signature = self.private_key.sign(message.encode())
        return signature.hex()
    
    def verify_signature(self, message: str, signature: str, public_key: VerifyingKey) -> bool:
        """Verify a signature"""
        try:
            signature_bytes = bytes.fromhex(signature)
            public_key.verify(signature_bytes, message.encode())
            return True
        except:
            return False
