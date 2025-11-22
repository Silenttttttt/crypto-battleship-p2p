# 🛡️ Crypto Battleship P2P

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Crypto](https://img.shields.io/badge/Crypto-Secure-red.svg)](#cryptographic-features)

> **Cryptographically secure peer-to-peer Battleship with cheat-proof gameplay**

Experience Battleship like never before! This implementation uses advanced cryptographic techniques including Merkle trees, blockchain technology, and digital signatures to create a mathematically cheat-proof multiplayer experience. No central server required - just pure P2P gaming with cryptographic guarantees.

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/Silenttttttt/crypto-battleship-p2p.git
cd crypto-battleship-p2p
pip install -r requirements.txt

# Terminal 1 (Player 1)
python main.py listen

# Terminal 2 (Player 2) 
python main.py connect localhost
```

## ✨ Key Features

### 🔐 **Cryptographic Security**
- **Merkle Tree Commitments**: Cryptographically bind players to their ship placement
- **Real-time Proof Verification**: Every shot result includes unforgeable cryptographic proof
- **Seed-derived Identity**: Deterministic ECDSA keypairs for player authentication
- **Blockchain History**: Immutable game log with cryptographic integrity

### 🌐 **True Peer-to-Peer**
- **No Central Server**: Direct player-to-player communication
- **ExProtocol Integration**: Military-grade encryption with ECDH and AES-GCM
- **Secure Handshake**: Proof-of-Work anti-spam protection
- **Error Correction**: Hamming codes ensure reliable data transmission

### 🎮 **Advanced Gameplay**
- **Cheat-Proof**: Mathematically impossible to lie about ship positions or shot results
- **Real-time Verification**: Instant cryptographic validation of all moves
- **Tamper Detection**: Any cheating attempt is immediately detected and rejected
- **Cryptographic Guarantees**: Both players have equal mathematical protection

## 🔬 How It Works

### 1. **Cryptographic Commitment**
```python
# Players commit to ship placement using Merkle trees
commitment = MerkleGridCommitment(ship_positions, secret_seed)
shared_root = commitment.root  # Publicly shared, cryptographically binding
```

### 2. **Cheat-Proof Shot Results**
```python
# When hit, player must provide mathematical proof
proof = generate_merkle_proof(x, y, actual_result)
# Opponent verifies proof against committed grid
verified = verify_proof(proof, opponent_committed_root)
```

### 3. **Blockchain Integrity**
```python
# All moves are cryptographically signed and chained
signed_move = sign_move(shot_data, private_key)
blockchain.add_verified_move(signed_move)
```

## 📁 Architecture

```
src/
├── 🎮 game/
│   └── core.py              # Main game logic with crypto integration
├── 🔐 crypto/  
│   ├── merkle.py            # Merkle tree commitments & proofs
│   ├── identity.py          # Player identity & digital signatures
│   └── blockchain.py        # Immutable game history
├── 🌐 network/
│   ├── transport.py         # Secure transport abstraction
│   ├── p2p.py              # P2P networking with ExProtocol
│   └── integration.py      # Crypto + networking integration
└── 📱 cli/
    └── interface.py        # Interactive command-line interface
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- C compiler (for ExProtocol's error correction)

### Setup
```bash
# 1. Clone repository
git clone https://github.com/Silenttttttt/crypto-battleship-p2p.git
cd crypto-battleship-p2p

# 2. Install dependencies
pip install -r requirements.txt

# 3. Compile ExProtocol (if needed)
cd ExProtocol/c_hamming && make && cd ../..

# 4. Run comprehensive test
python tests/test_integration.py
```

## 🎯 Usage

### **Basic Gameplay**
```bash
# Player 1: Start listening
python main.py listen

# Player 2: Connect to Player 1
python main.py connect <player1_ip>
```

### **Advanced Options**
```bash
# Custom port
python main.py listen --port 8080
python main.py connect <ip> --port 8080
```

### **Game Flow**
1. **Secure Connection**: Players establish encrypted P2P channel
2. **Cryptographic Setup**: Exchange Merkle tree commitments for ship grids
3. **Verified Gameplay**: Take turns with cryptographically proven shot results
4. **Guaranteed Victory**: Winner determined by mathematical proof, not trust

## 🔒 Cryptographic Features

### **Cheat Prevention**
- ✅ **Ship Placement**: Cryptographically locked after commitment
- ✅ **Shot Results**: Mathematically proven with Merkle proofs
- ✅ **Move Ordering**: Blockchain prevents replay attacks
- ✅ **Player Identity**: ECDSA signatures prevent impersonation

### **Cryptographic Primitives**
- **Hashing**: SHA-256 for all commitments and proofs
- **Signatures**: ECDSA with secp256k1 curve (Bitcoin-grade)
- **Encryption**: AES-GCM authenticated encryption
- **Key Exchange**: Elliptic Curve Diffie-Hellman (ECDH)

### **Security Guarantees**
- **Commitment Binding**: Computationally infeasible to change ships after commitment
- **Proof Integrity**: Merkle proofs provide mathematical certainty of shot results
- **Replay Protection**: Blockchain ordering prevents move manipulation
- **Identity Verification**: Cryptographic signatures ensure authentic players

## 🧪 Testing

### **Comprehensive Verification**
```bash
# Run full system test
python tests/test_integration.py
```

**This test verifies:**
- ✅ P2P connection with ExProtocol handshake
- ✅ Cryptographic commitment exchange
- ✅ Merkle proof generation and verification
- ✅ Blockchain integrity and validation
- ✅ End-to-end encrypted gameplay

### **Manual Testing**
```bash
# Terminal 1
python main.py listen

# Terminal 2  
python main.py connect localhost
```

## 🔧 Technical Implementation

### **Merkle Tree Cryptography**
- **Leaf Nodes**: `SHA256(seed || x || y || has_ship)`
- **Internal Nodes**: `SHA256(left_child || right_child)`
- **Proof Size**: `O(log n)` for n grid cells
- **Verification**: `O(log n)` time complexity

### **Blockchain Structure**
```python
GameBlock {
    prev_hash: str,           # Links to previous block
    moves: List[GameMove],    # Cryptographically signed moves
    merkle_root: str,         # Merkle root of all moves
    timestamp: float,         # Block creation time
    block_hash: str          # SHA256 hash of entire block
}
```

### **Network Security**
- **Transport**: TCP with ExProtocol encryption layer
- **Handshake**: ECDH key exchange + Proof-of-Work anti-spam
- **Messages**: JSON over authenticated encrypted channel
- **Error Correction**: Hamming codes for transmission reliability

## 🤝 Contributing

**Areas for Enhancement:**
- **UI/UX**: Web interface, mobile app, or desktop GUI
- **Networking**: NAT traversal, relay servers, peer discovery
- **Cryptography**: Zero-knowledge proofs, advanced commitment schemes
- **Performance**: Optimization, caching, parallel processing
- **Features**: Tournament mode, spectator support, replay system

### **Development Setup**
```bash
# Fork and clone
git clone https://github.com/yourusername/crypto-battleship-p2p.git
cd crypto-battleship-p2p

# Create feature branch
git checkout -b feature/your-enhancement

# Test your changes
python tests/test_integration.py

# Submit pull request
```

## 📚 Learn More

### **Cryptographic Concepts**
- [Merkle Trees](https://en.wikipedia.org/wiki/Merkle_tree) - Efficient cryptographic verification
- [Commitment Schemes](https://en.wikipedia.org/wiki/Commitment_scheme) - Cryptographic binding
- [Digital Signatures](https://en.wikipedia.org/wiki/Digital_signature) - Authentication & non-repudiation
- [Blockchain Technology](https://en.wikipedia.org/wiki/Blockchain) - Distributed ledger systems

### **Implementation References**
- [ExProtocol](ExProtocol/README.md) - Secure transport protocol
- [ECDSA](https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm) - Elliptic curve signatures
- [AES-GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode) - Authenticated encryption

## 🎖️ Why This Matters

Traditional online games rely on trusted servers to prevent cheating. This project demonstrates that **peer-to-peer games can achieve mathematical cheat-proofing** using cryptographic techniques.

**Potential Applications:**
- 🎮 **Decentralized Gaming**: Tournaments without trusted referees
- 🏛️ **Governance Systems**: Transparent voting with cryptographic verification  
- 💰 **Financial Applications**: Trustless gambling and prediction markets
- 🔬 **Distributed Computing**: Verifiable computation without trust

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ExProtocol**: Foundation for secure transport
- **Python Cryptography**: Robust cryptographic primitives
- **ECDSA Library**: Elliptic curve digital signatures
- **Open Source Community**: Inspiration and feedback

---

**🔬 Ready to experiment with cryptographic P2P gaming? Clone and explore! 🔬**

*Remember: This is experimental software for learning purposes.*