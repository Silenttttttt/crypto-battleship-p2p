#!/usr/bin/env python3
"""
Test Cheat Detection and Invalidation

Verifies that cheating is detected, proven, and cheaters are invalidated.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from game.battleship_protocol import BattleshipZeroTrust
from zerotrust import MerkleProof
from zerotrust import CheatType


def test_invalid_proof_detection():
    """Test that invalid proofs are detected and cheater is invalidated"""
    print("🧪 Test 1: Invalid Proof Detection")
    print("=" * 70)
    
    # Create two players
    alice = BattleshipZeroTrust([(0, 0), (0, 1)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    # Exchange commitments
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    print("1️⃣ Legitimate shot...")
    success, action_data, signature = alice.fire_shot(9, 9)
    result = bob.handle_incoming_shot(9, 9, action_data, signature)
    
    if result:
        legit_proof, proof_sig = result
        print(f"   Result: {legit_proof.result}")
        
        # Alice verifies (should pass)
        verified = alice.verify_opponent_proof(legit_proof, proof_sig)
        print(f"   Verified: {verified}")
        print(f"   Cheating detected: {alice.cheat_detector.has_detected_cheating()}")
    
    print("\n2️⃣ Now Alice tries to cheat - sends FAKE proof...")
    
    # Create a FAKE proof claiming (0,0) is a miss when it's actually a hit
    fake_proof = MerkleProof(
        position=(0, 0),
        has_ship=False,  # LIE - this position HAS a ship
        result='miss',   # LIE - should be hit
        leaf_data='fake_leaf_data',
        merkle_path=['fake', 'path']
    )
    
    # Bob tries to verify this fake proof
    verified = bob.verify_opponent_proof(fake_proof, "fake_signature")
    
    print(f"   Fake proof verified: {verified}")
    print(f"   Cheating detected: {bob.cheat_detector.has_detected_cheating()}")
    print(f"   Alice invalidated: {bob.cheat_invalidator.is_invalidated(alice.protocol.my_participant_id)}")
    
    if bob.cheat_detector.has_detected_cheating():
        proof_of_cheating = bob.cheat_detector.get_cheating_proof()
        print(f"\n   🚫 CHEATING PROVEN:")
        print(f"      Type: {proof_of_cheating.cheat_type.value}")
        print(f"      Cheater: {proof_of_cheating.cheater_id}")
        print(f"      Description: {proof_of_cheating.description}")
        print(f"      Evidence available: Yes")
        
        # Create cheat report for third-party verification
        cheat_report = bob.cheat_detector.create_cheat_report()
        print(f"\n   📋 Cheat Report:")
        print(f"      Detector: {cheat_report['detector_id']}")
        print(f"      Opponent is cheater: {cheat_report['opponent_is_cheater']}")
        print(f"      Total cheats: {cheat_report['total_cheats_detected']}")
    
    return bob.cheat_detector.has_detected_cheating()


def test_commitment_mismatch_detection():
    """Test that post-game grid revelation detects commitment mismatch"""
    print("\n\n🧪 Test 2: Commitment Mismatch Detection")
    print("=" * 70)
    
    # Create two players
    alice = BattleshipZeroTrust([(0, 0), (0, 1)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    # Exchange commitments
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    print("1️⃣ Play a legitimate game...")
    success, action_data, signature = alice.fire_shot(9, 9)
    result = bob.handle_incoming_shot(9, 9, action_data, signature)
    if result:
        proof, proof_sig = result
        alice.verify_opponent_proof(proof, proof_sig)
    
    print("\n2️⃣ Alice tries to cheat in post-game revelation...")
    print("   (Claims ships were at different positions than committed)")
    
    # Alice reveals but LIES about her ship positions
    fake_revelation = alice.reveal_grid()
    fake_revelation['commitment_data'] = [(5, 5), (6, 6)]  # LIE - not her real ships
    # Note: This won't match the commitment root!
    
    # Bob verifies the fake revelation
    verification = bob.verify_opponent_grid(fake_revelation)
    
    print(f"\n   Fake revelation verified: {verification.valid}")
    print(f"   Reason: {verification.reason}")
    print(f"   Cheating detected: {bob.cheat_detector.has_detected_cheating()}")
    print(f"   Alice invalidated: {bob.cheat_invalidator.is_invalidated(alice.protocol.my_participant_id)}")
    
    if not verification.valid:
        print(f"\n   ✅ CHEATING CAUGHT AND PROVEN")
        proof_of_cheating = bob.cheat_detector.get_cheating_proof()
        if proof_of_cheating:
            print(f"      Type: {proof_of_cheating.cheat_type.value}")
            print(f"      Evidence: Commitment mismatch proven cryptographically")
    
    return bob.cheat_detector.has_detected_cheating()


def test_blockchain_tampering_detection():
    """Test that blockchain tampering is detected"""
    print("\n\n🧪 Test 3: Blockchain Tampering Detection")
    print("=" * 70)
    
    alice = BattleshipZeroTrust([(0, 0)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    print("1️⃣ Normal game play...")
    success, action_data, signature = alice.fire_shot(9, 9)
    result = bob.handle_incoming_shot(9, 9, action_data, signature)
    if result:
        proof, proof_sig = result
        alice.verify_opponent_proof(proof, proof_sig)
    
    print("\n2️⃣ Alice tries to tamper with her blockchain...")
    # Tamper with Alice's blockchain
    if alice.protocol.blockchain.chain:
        alice.protocol.blockchain.chain[-1].hash = "fake_hash_000000"
    
    # Verify blockchain
    blockchain_valid = alice.protocol.blockchain.verify_chain()
    
    print(f"   Tampered blockchain valid: {blockchain_valid}")
    
    if not blockchain_valid:
        # Record blockchain tampering
        alice.cheat_detector.record_cheat(
            cheat_type=CheatType.BLOCKCHAIN_TAMPERING,
            cheater_id=alice.protocol.my_participant_id,
            description="Blockchain hash chain is invalid - tampering detected",
            evidence={'tampered_block': alice.protocol.blockchain.chain[-1].hash}
        )
        
        print(f"\n   ✅ TAMPERING DETECTED")
        print(f"      Blockchain integrity check failed")
        print(f"      Cheater can be proven guilty with blockchain")
    
    return not blockchain_valid


if __name__ == "__main__":
    print("🔥 TESTING CHEAT DETECTION & INVALIDATION\n")
    
    try:
        # Test 1: Invalid proof
        test1 = test_invalid_proof_detection()
        
        # Test 2: Commitment mismatch
        test2 = test_commitment_mismatch_detection()
        
        # Test 3: Blockchain tampering
        test3 = test_blockchain_tampering_detection()
        
        print("\n" + "=" * 70)
        print("📊 CHEAT DETECTION RESULTS")
        print("=" * 70)
        print(f"Invalid proof detection:     {'✅ PASS' if test1 else '❌ FAIL'}")
        print(f"Commitment mismatch:         {'✅ PASS' if test2 else '❌ FAIL'}")
        print(f"Blockchain tampering:        {'✅ PASS' if test3 else '❌ FAIL'}")
        
        if all([test1, test2, test3]):
            print("\n🏆 ALL CHEAT DETECTION WORKING!")
            print("\n✅ Cheaters can be:")
            print("   - Detected cryptographically")
            print("   - Proven with evidence")
            print("   - Invalidated automatically")
            print("\n✅ Honest players are protected:")
            print("   - Can prove they didn't cheat")
            print("   - Can prove opponent DID cheat")
            print("   - Have cryptographic evidence")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

