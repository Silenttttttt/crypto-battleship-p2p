# 🛡️ Crypto Battleship P2P

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Development-orange.svg)](#development-status)

> **Experimental cryptographically secure peer-to-peer Battleship game**

A proof-of-concept implementation of Battleship that explores using cryptographic techniques to prevent cheating in P2P games. This project demonstrates Merkle tree commitments and blockchain-based game history for tamper-resistant gameplay.

## ⚠️ Development Status

**This is experimental software in active development:**
- ✅ Core cryptographic concepts implemented and tested
- ✅ Basic P2P gameplay works between two terminals
- ⚠️ **Not production ready** - expect bugs and rough edges
- ⚠️ Limited error handling and edge case coverage
- ⚠️ No security audit performed
- ⚠️ Performance not optimized
- ⚠️ UI/UX is basic CLI only

**Use for learning and experimentation only!**

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/yourusername/crypto-battleship-p2p.git
cd crypto-battleship-p2p
pip install -r requirements.txt

# Terminal 1 (Player 1)
python crypto_battleship_cli.py listen

# Terminal 2 (Player 2) 
python crypto_battleship_cli.py connect localhost
```

## ✨ Implemented Features

### 🔐 **Cryptographic Concepts**
- **Merkle Tree Commitments**: Players commit to ship grids using cryptographic hashes
- **Proof Verification**: Shot results include Merkle proofs for validation
- **Seed-derived Keypairs**: ECDSA keys derived from player's secret seed
- **Blockchain History**: Basic blockchain for game move recording

### 🌐 **Networking**
- **P2P Communication**: Direct player-to-player connection (localhost)
- **ExProtocol Integration**: Secure transport with encryption
- **Basic Error Handling**: Connection management and recovery

### 🎮 **Game Mechanics**
- **Ship Placement**: Random ship placement with cryptographic commitment
- **Turn-based Shots**: Players take turns firing at opponent's grid
- **Hit/Miss Verification**: Cryptographic proofs validate shot results
- **Basic CLI Interface**: Terminal-based gameplay

## 🔬 How It Works

### 1. **Grid Commitment Phase**
```python
# Player commits to ship placement using Merkle tree
commitment = MerkleGridCommitment(ship_positions, secret_seed)
root_hash = commitment.root  # Shared with opponent
```

### 2. **Shot Verification**
```python
# When shot at (x,y), player must provide cryptographic proof
proof = generate_merkle_proof(x, y, has_ship)
# Opponent verifies proof against committed root
verified = verify_proof(proof, opponent_root_hash)
```

### 3. **Blockchain Integrity**
```python
# All moves are signed and recorded in blockchain
move = sign_move(shot_data, private_key)
blockchain.add_move(move)
# Chain integrity prevents tampering with game history
```

## 📁 Project Structure

```
crypto-battleship-p2p/
├── 🎮 crypto_battleship_cli.py      # Main game interface
├── 🔗 crypto_battleship_p2p.py     # P2P networking integration
├── 🔐 crypto_battleship_clean.py   # Core cryptographic game logic
├── 🌐 battleship_p2p.py            # Base P2P communication
├── 🚀 transport_adapter.py         # Network transport abstraction
├── ✅ test_final_verification.py   # Comprehensive system test
├── 📋 requirements.txt             # Python dependencies
└── 📁 ExProtocol/                  # Secure transport protocol
    ├── protocol.py                 # Main ExProtocol implementation
    ├── protocol_wrapper.py         # High-level interface
    ├── c_hamming.py               # Error correction
    └── c_hamming/hamming          # Compiled error correction
```

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- C compiler (for ExProtocol's Hamming codes)
- Network connectivity between players

### Setup
```bash
# 1. Clone repository
git clone https://github.com/yourusername/crypto-battleship-p2p.git
cd crypto-battleship-p2p

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Compile ExProtocol components (if needed)
cd ExProtocol/c_hamming
make
cd ../..

# 4. Verify installation
python test_final_verification.py
```

## 🎯 Usage

### Basic Gameplay
```bash
# Player 1: Start listening for connections
python crypto_battleship_cli.py listen

# Player 2: Connect to Player 1
python crypto_battleship_cli.py connect <player1_ip>
```

### Advanced Options
```bash
# Custom port
python crypto_battleship_cli.py listen --port 8080
python crypto_battleship_cli.py connect <ip> --port 8080

# Help
python crypto_battleship_cli.py --help
```

### Game Flow
1. **Connection**: Players establish secure P2P connection
2. **Setup**: Exchange cryptographic commitments for ship grids
3. **Gameplay**: Take turns firing shots with real-time verification
4. **Victory**: First to sink all opponent ships wins (cryptographically verified)

## 🔒 Security Features

### **Cheat Prevention**
- ✅ **Ship Placement**: Cannot change ships after commitment
- ✅ **Shot Results**: Cannot lie about hits/misses (Merkle proofs)
- ✅ **Move Ordering**: Blockchain prevents replay attacks
- ✅ **Identity Binding**: Cryptographic signatures prevent impersonation

### **Cryptographic Primitives**
- **Hashing**: SHA-256 for all commitments and proofs
- **Signatures**: ECDSA with secp256k1 curve
- **Encryption**: AES-GCM via ExProtocol
- **Key Exchange**: ECDH for secure channel establishment

### **Security Notes**
- **Experimental Implementation**: No formal security analysis performed
- **Basic Protections**: Uses standard cryptographic primitives (SHA-256, ECDSA)
- **Known Limitations**: Not hardened against sophisticated attacks
- **Learning Purpose**: Demonstrates concepts, not production security

## 🧪 Testing

### Comprehensive Verification
```bash
# Run full system test (CRITICAL)
python test_final_verification.py
```

This test verifies:
- ✅ P2P connection establishment
- ✅ Cryptographic commitment exchange
- ✅ Merkle proof generation and verification
- ✅ Blockchain integrity maintenance
- ✅ End-to-end game flow

### Manual Testing
```bash
# Terminal 1
python crypto_battleship_cli.py listen

# Terminal 2  
python crypto_battleship_cli.py connect localhost

# Play a few moves to verify everything works
```

## 🔧 Technical Details

### **Merkle Tree Implementation**
- **Leaf Nodes**: `SHA256(seed || x || y || has_ship)`
- **Internal Nodes**: `SHA256(left_child || right_child)`
- **Proof Size**: `O(log n)` for n grid cells
- **Verification**: `O(log n)` time complexity

### **Blockchain Structure**
```python
Block {
    prev_hash: str,
    moves: List[GameMove],
    timestamp: float,
    block_hash: str
}

GameMove {
    player_id: str,
    move_type: MoveType,
    data: Dict,
    signature: str,
    timestamp: float
}
```

### **Network Protocol**
- **Transport**: TCP with ExProtocol encryption
- **Handshake**: ECDH + Proof-of-Work anti-spam
- **Messages**: JSON over encrypted channel
- **Error Correction**: Hamming codes for reliability

## 🤝 Contributing

We welcome contributions! Areas for improvement:

1. **UI/UX**: Web interface, mobile app, or GUI
2. **Network**: NAT traversal, relay servers, DHT discovery
3. **Cryptography**: Zero-knowledge proofs, advanced protocols
4. **Performance**: Optimization, caching, parallelization
5. **Testing**: Unit tests, fuzzing, formal verification

### Development Setup
```bash
# Fork and clone your fork
git clone https://github.com/yourusername/crypto-battleship-p2p.git
cd crypto-battleship-p2p

# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
python test_final_verification.py

# Submit pull request
```

## 📚 Learn More

### **Cryptographic Concepts**
- [Merkle Trees](https://en.wikipedia.org/wiki/Merkle_tree) - Tree structures for efficient verification
- [Commitment Schemes](https://en.wikipedia.org/wiki/Commitment_scheme) - Cryptographic commitments
- [Digital Signatures](https://en.wikipedia.org/wiki/Digital_signature) - Authentication and non-repudiation
- [Blockchain](https://en.wikipedia.org/wiki/Blockchain) - Distributed ledger technology

### **Implementation Details**
- [ExProtocol](ExProtocol/README.md) - Secure transport protocol
- [ECDSA](https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm) - Elliptic curve signatures
- [AES-GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode) - Authenticated encryption

## 🎖️ Why This Project

This is an **experimental exploration** of applying cryptographic techniques to P2P gaming. The goal is to learn and demonstrate concepts like:

- How Merkle trees can create tamper-proof commitments
- Using blockchain for distributed game state
- Cryptographic proofs in real-time applications
- P2P networking challenges and solutions

**This is a learning project** - not a production game system. The concepts could potentially be applied to:
- Educational cryptography demonstrations
- Research into decentralized gaming
- Prototyping cheat-resistant game mechanics

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **ExProtocol**: Secure transport foundation
- **Python Cryptography**: Robust cryptographic primitives
- **ECDSA Library**: Elliptic curve digital signatures
- **Community**: Feedback and testing

---

**🔬 Ready to experiment with cryptographic P2P gaming? Clone and explore! 🔬**

*Remember: This is experimental software for learning purposes.*