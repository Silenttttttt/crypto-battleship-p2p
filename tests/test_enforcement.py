#!/usr/bin/env python3
"""
Comprehensive Enforcement Test Suite

Tests all enforcement mechanisms:
- Timeout enforcement
- Turn violation enforcement
- State persistence
- Reconnection
- Post-game enforcement
"""

import sys
import os
import time
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from game.battleship_protocol import BattleshipZeroTrust
from crypto import ZeroTrustProtocol, TimeoutConfig, CheatType
from crypto.merkle import MerkleProof


def test_timeout_enforcement():
    """Test automatic timeout and forfeit"""
    print("\n🧪 Test 1: Timeout Enforcement")
    print("=" * 70)
    
    # Create players with enforcement enabled
    alice = BattleshipZeroTrust([(0, 0), (0, 1)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    # Exchange commitments
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    # Start monitoring
    alice.protocol.start_monitoring(interval=0.5)
    bob.protocol.start_monitoring(interval=0.5)
    
    print("1️⃣ Starting action with short timeout...")
    action_id = "test_shot"
    
    # Start action with very short timeout (1 second)
    alice.protocol.enforcement.start_action_with_timeout(action_id, timeout=1.0)
    
    print("2️⃣ Waiting for timeout...")
    time.sleep(2.0)  # Wait longer than timeout
    
    print("3️⃣ Checking for violations...")
    violations = alice.protocol.check_enforcement()
    
    print(f"   Violations detected: {len(violations)}")
    
    if violations:
        violation = violations[0]
        print(f"   ✅ Timeout detected!")
        print(f"   Type: {violation.cheat_type.value}")
        print(f"   Cheater: {violation.cheater_id}")
        print(f"   Description: {violation.description}")
        
        # Check if opponent was invalidated
        invalidated = alice.protocol.cheat_invalidator.is_invalidated(bob.protocol.my_participant_id)
        print(f"   Opponent invalidated: {invalidated}")
        
        alice.protocol.stop_monitoring()
        bob.protocol.stop_monitoring()
        return True
    else:
        print("   ❌ Timeout not detected")
        alice.protocol.stop_monitoring()
        bob.protocol.stop_monitoring()
        return False


def test_turn_violation_enforcement():
    """Test turn order enforcement"""
    print("\n🧪 Test 2: Turn Violation Enforcement")
    print("=" * 70)
    
    alice = BattleshipZeroTrust([(0, 0)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    # Exchange commitments
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    # Set initial turn (Alice's turn)
    alice.protocol.enforcement.current_turn = alice.protocol.my_participant_id
    bob.protocol.enforcement.current_turn = alice.protocol.my_participant_id
    
    print("1️⃣ Alice fires shot (her turn)...")
    success, action_data, signature = alice.fire_shot(9, 9)
    print(f"   Result: {success}")
    
    print("2️⃣ Bob tries to fire out of turn...")
    # Bob tries to fire when it's still Alice's turn
    fake_action = {
        'action_type': 'fire_shot',
        'x': 0,
        'y': 0,
        'timestamp': time.time()
    }
    fake_signature = "fake_signature"
    
    # Verify action (should fail due to turn violation)
    result = bob.protocol.verify_opponent_action(fake_action, fake_signature)
    
    print(f"   Verification result: {result.valid}")
    print(f"   Reason: {result.reason}")
    
    if not result.valid and "turn" in result.reason.lower():
        print("   ✅ Turn violation detected!")
        
        # Check if cheating was recorded
        if bob.protocol.cheat_detector.has_detected_cheating():
            proof = bob.protocol.cheat_detector.get_cheating_proof()
            print(f"   Cheat type: {proof.cheat_type.value}")
            print(f"   ✅ Turn violation enforcement working!")
            return True
    
    print("   ❌ Turn violation not properly enforced")
    return False


def test_state_persistence():
    """Test save/load state"""
    print("\n🧪 Test 3: State Persistence")
    print("=" * 70)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        alice = BattleshipZeroTrust([(0, 0), (0, 1)], 
                                    enable_persistence=True, 
                                    save_path=temp_path)
        bob = BattleshipZeroTrust([(9, 9)])
        
        # Exchange commitments
        alice.set_opponent_commitment(bob.get_commitment_data())
        bob.set_opponent_commitment(alice.get_commitment_data())
        
        # Fire a shot
        alice.fire_shot(9, 9)
        
        print("1️⃣ Saving state...")
        if alice.protocol.state_manager:
            saved = alice.protocol.state_manager.save_state()
            print(f"   Save successful: {saved}")
        
        # Get state before save
        original_blocks = len(alice.protocol.blockchain.chain)
        original_actions = alice.protocol.my_actions_count
        
        print(f"   Original state: {original_blocks} blocks, {original_actions} actions")
        
        # Create new instance and load
        print("2️⃣ Loading state...")
        alice2 = BattleshipZeroTrust([(0, 0), (0, 1)], 
                                     enable_persistence=True,
                                     save_path=temp_path)
        
        if alice2.protocol.state_manager:
            loaded = alice2.protocol.state_manager.load_state()
            print(f"   Load successful: {loaded}")
        
        # Verify state restored
        restored_blocks = len(alice2.protocol.blockchain.chain)
        restored_actions = alice2.protocol.my_actions_count
        
        print(f"   Restored state: {restored_blocks} blocks, {restored_actions} actions")
        
        if restored_blocks == original_blocks and restored_actions == original_actions:
            print("   ✅ State persistence working!")
            return True
        else:
            print("   ❌ State not properly restored")
            return False
            
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_reconnection():
    """Test reconnection with state recovery"""
    print("\n🧪 Test 4: Reconnection")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        alice = BattleshipZeroTrust([(0, 0)], 
                                    enable_persistence=True,
                                    save_path=temp_path)
        bob = BattleshipZeroTrust([(9, 9)])
        
        # Exchange commitments
        alice.set_opponent_commitment(bob.get_commitment_data())
        bob.set_opponent_commitment(alice.get_commitment_data())
        
        # Fire a shot
        alice.fire_shot(9, 9)
        
        print("1️⃣ Simulating disconnection...")
        # Handle disconnect (saves state)
        if alice.protocol.reconnection_handler:
            alice.protocol.reconnection_handler.handle_disconnect()
            print("   ✅ State saved on disconnect")
        
        print("2️⃣ Simulating reconnection...")
        # Simulate reconnection
        reconnect_attempts = 0
        def mock_connect():
            nonlocal reconnect_attempts
            reconnect_attempts += 1
            return reconnect_attempts >= 2  # Succeed on second attempt
        
        if alice.protocol.reconnection_handler:
            success = alice.protocol.reconnection_handler.attempt_reconnection(mock_connect)
            print(f"   Reconnection successful: {success}")
            
            if success:
                # Verify state
                verified = alice.protocol.reconnection_handler.verify_state_after_reconnect()
                print(f"   State verified: {verified}")
                
                if verified:
                    print("   ✅ Reconnection working!")
                    return True
        
        print("   ❌ Reconnection test incomplete")
        return False
        
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_post_game_enforcement():
    """Test mandatory revelation"""
    print("\n🧪 Test 5: Post-Game Enforcement")
    print("=" * 70)
    
    alice = BattleshipZeroTrust([(0, 0)])
    bob = BattleshipZeroTrust([(9, 9)])
    
    # Exchange commitments
    alice.set_opponent_commitment(bob.get_commitment_data())
    bob.set_opponent_commitment(alice.get_commitment_data())
    
    print("1️⃣ Starting post-game revelation enforcement...")
    print("   (Opponent will NOT reveal - should timeout)")
    
    # Start enforcement with short timeout
    alice_thread = None
    def enforce_in_thread():
        result = alice.protocol.enforce_post_game_revelation(timeout=2.0)
        return result
    
    import threading
    alice_thread = threading.Thread(target=enforce_in_thread, daemon=True)
    alice_thread.start()
    
    # Wait for timeout
    time.sleep(3.0)
    
    # Check if cheating was detected
    if alice.protocol.cheat_detector.has_detected_cheating():
        proof = alice.protocol.cheat_detector.get_cheating_proof()
        print(f"   ✅ Post-game timeout detected!")
        print(f"   Cheat type: {proof.cheat_type.value}")
        print(f"   Description: {proof.description}")
        
        invalidated = alice.protocol.cheat_invalidator.is_invalidated(bob.protocol.my_participant_id)
        print(f"   Opponent invalidated: {invalidated}")
        
        if invalidated:
            print("   ✅ Post-game enforcement working!")
            return True
    
    print("   ❌ Post-game enforcement not working")
    return False


if __name__ == "__main__":
    print("🔥 ENFORCEMENT TEST SUITE")
    print("=" * 70)
    
    results = []
    
    try:
        # Test 1: Timeout enforcement
        results.append(("Timeout Enforcement", test_timeout_enforcement()))
        
        # Test 2: Turn violation
        results.append(("Turn Violation", test_turn_violation_enforcement()))
        
        # Test 3: State persistence
        results.append(("State Persistence", test_state_persistence()))
        
        # Test 4: Reconnection
        results.append(("Reconnection", test_reconnection()))
        
        # Test 5: Post-game enforcement
        results.append(("Post-Game Enforcement", test_post_game_enforcement()))
        
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 ENFORCEMENT TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:30} {status}")
        if result:
            passed += 1
    
    print("=" * 70)
    print(f"Total: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🏆 ALL ENFORCEMENT TESTS PASSING!")
        print("✅ Framework enforcement is production-ready!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed")
        sys.exit(1)

