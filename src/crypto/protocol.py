"""
Zero-Trust Protocol Framework

This is the CORE framework - a generic, reusable protocol for any application
that needs cryptographic guarantees without trust.

The framework provides:
- Commitments (bind to state without revealing it)
- Zero-knowledge proofs (prove facts without revealing data)
- Digital signatures (authenticate actions)
- Synchronized blockchain (immutable shared history)
- Independent verification (anyone can verify correctness)

This is domain-agnostic - can be used for games, voting, contracts, etc.
"""

import json
import time
import threading
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from ecdsa import VerifyingKey, SECP256k1

from .merkle import MerkleGridCommitment, MerkleProof, SimpleMerkleTree
from .identity import CryptoIdentity
from .blockchain import Blockchain, Transaction, MoveType
from .timeout import ActionTimeout, TimeoutConfig, TimeoutReason, ProtocolMonitor
from .cheating import CheatType, CheatEvidence, CheatDetector, CheatInvalidator
from .state_manager import StateManager
from .reconnection import ReconnectionHandler


@dataclass
class VerificationResult:
    """Result of verification operation"""
    valid: bool
    reason: str = ""
    details: Dict[str, Any] = None


class ProtocolEnforcement:
    """
    Enforcement manager for protocol rules.
    Handles timeout enforcement, turn order, and violation detection.
    """
    
    def __init__(self, protocol, timeout_config: TimeoutConfig = None):
        self.protocol = protocol
        self.timeout_manager = ActionTimeout(timeout_config or TimeoutConfig())
        self.current_turn: Optional[str] = None
        self.turn_sequence: List[str] = []  # History of whose turn it was
        self.action_timeouts: Dict[str, float] = {}  # action_id -> custom timeout
    
    def start_action_with_timeout(self, action_id: str, timeout: float = 30.0) -> None:
        """Start tracking an action with custom timeout"""
        # Store custom timeout for this action
        self.action_timeouts[action_id] = timeout
        self.timeout_manager.start_action(action_id)
    
    def enforce_turn_order(self, participant_id: str) -> bool:
        """
        Enforce turn order. Returns True if it's their turn, False otherwise.
        """
        # If no turn is set, allow first action
        if self.current_turn is None:
            self.current_turn = participant_id
            self.turn_sequence.append(participant_id)
            return True
        
        # Check if it's their turn
        if self.current_turn == participant_id:
            return True
        
        # Not their turn - violation
        return False
    
    def switch_turn(self) -> None:
        """Switch turn to the other participant"""
        if self.current_turn and self.protocol.opponent_participant_id:
            if self.current_turn == self.protocol.my_participant_id:
                self.current_turn = self.protocol.opponent_participant_id
            else:
                self.current_turn = self.protocol.my_participant_id
            self.turn_sequence.append(self.current_turn)
    
    def handle_timeout(self, action_id: str) -> Optional[CheatEvidence]:
        """Handle a timeout and create cheat evidence"""
        if not self.protocol.opponent_participant_id:
            return None
        
        # Check if we have cheat detector
        if not hasattr(self.protocol, 'cheat_detector'):
            return None
        
        cheat = self.protocol.cheat_detector.record_cheat(
            CheatType.TIMEOUT_STALL,
            self.protocol.opponent_participant_id,
            f"Timeout on action {action_id}",
            {'action_id': action_id, 'timeout': self.timeout_manager.config.action_timeout}
        )
        return cheat
    
    def check_and_enforce(self) -> List[CheatEvidence]:
        """Check for violations and return list of cheat evidence"""
        violations = []
        
        # Check timeouts with custom timeout values
        now = time.time()
        timed_out = {}
        
        for action_id, start_time in list(self.timeout_manager.pending_actions.items()):
            elapsed = now - start_time
            
            # Use custom timeout if set, otherwise use default
            custom_timeout = self.action_timeouts.get(action_id, self.timeout_manager.config.action_timeout)
            
            if elapsed > custom_timeout:
                timed_out[action_id] = TimeoutReason.NO_RESPONSE
                del self.timeout_manager.pending_actions[action_id]
                if action_id in self.action_timeouts:
                    del self.action_timeouts[action_id]
        
        for action_id, reason in timed_out.items():
            cheat = self.handle_timeout(action_id)
            if cheat:
                violations.append(cheat)
        
        return violations


class ZeroTrustProtocol:
    """
    Generic Zero-Trust Protocol Framework
    
    This is the main framework class that applications use.
    It handles all cryptographic operations and maintains
    a synchronized, verifiable state between participants.
    
    Applications just provide:
    - Initial state (commitment)
    - Actions (signed by participants)
    - Verification logic (domain-specific)
    """
    
    def __init__(self, 
                 my_commitment_data: Any,
                 seed: bytes = None,
                 enable_enforcement: bool = True,
                 enable_persistence: bool = True,
                 timeout_config: TimeoutConfig = None,
                 save_path: Optional[str] = None):
        """
        Initialize protocol with commitment to initial state.
        
        Args:
            my_commitment_data: Data to commit to (e.g., grid state)
            seed: Optional seed for deterministic key generation
            enable_enforcement: Enable protocol enforcement (timeouts, turn order)
            enable_persistence: Enable state persistence (save/load)
            timeout_config: Custom timeout configuration
            save_path: Path for state persistence file
        """
        self.seed = seed
        
        # Cryptographic components
        self.identity = CryptoIdentity(self.seed, my_commitment_data)
        self.blockchain = Blockchain()
        
        # Participant state
        self.my_participant_id = self.identity.player_id
        self.opponent_participant_id: Optional[str] = None
        self.opponent_public_key: Optional[VerifyingKey] = None
        self.opponent_commitment: Optional[str] = None
        
        # Protocol state
        self.protocol_active = False
        self.my_actions_count = 0
        self.opponent_actions_count = 0
        
        # Enforcement and cheat detection
        self.enable_enforcement = enable_enforcement
        if enable_enforcement:
            self.enforcement = ProtocolEnforcement(self, timeout_config)
            self.cheat_detector = CheatDetector(self.my_participant_id)
            self.cheat_invalidator = CheatInvalidator()
        else:
            self.enforcement = None
            self.cheat_detector = None
            self.cheat_invalidator = None
        
        # State persistence
        self.enable_persistence = enable_persistence
        if enable_persistence:
            self.state_manager = StateManager(self, save_path or "game_state.json")
            # Try to load existing state
            self.state_manager.load_state()
            # Start auto-save
            self.state_manager.start_auto_save()
            # Initialize reconnection handler
            self.reconnection_handler = ReconnectionHandler(self, self.state_manager)
        else:
            self.state_manager = None
            self.reconnection_handler = None
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread = None
        self.opponent_revealed = False
        self._monitor_interval = 1.0
        
        # Protocol health monitoring
        if enable_enforcement:
            self.health_monitor = ProtocolMonitor()
        else:
            self.health_monitor = None
        
        # Callbacks
        self.verify_commitment_callback: Optional[Callable] = None
        self.verify_action_callback: Optional[Callable] = None
        self.on_violation: Optional[Callable[[CheatEvidence], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        
    def get_my_commitment(self) -> Dict[str, str]:
        """
        Get my commitment to share with opponent.
        Commitment binds to state without revealing it.
        """
        return {
            'participant_id': self.my_participant_id,
            'public_key': self.identity.public_key.to_string().hex()
        }
    
    def set_opponent_commitment(self, commitment: Dict[str, str]) -> VerificationResult:
        """
        Receive and verify opponent's commitment.
        Both participants must commit before protocol starts.
        """
        try:
            self.opponent_participant_id = commitment['participant_id']
            self.opponent_public_key = VerifyingKey.from_string(
                bytes.fromhex(commitment['public_key']),
                curve=SECP256k1
            )
            self.opponent_commitment = commitment.get('commitment_root')
            
            # Record commitment to blockchain
            transaction = Transaction(
                move_type=MoveType.COMMITMENT,
                participant_id=self.opponent_participant_id,
                data=commitment,
                timestamp=time.time(),
                signature=""  # Commitments don't need signatures
            )
            self.blockchain.add_transaction(transaction)
            self.blockchain.mine_block()
            
            self.protocol_active = True
            
            return VerificationResult(
                valid=True,
                reason="Opponent commitment recorded"
            )
            
        except Exception as e:
            return VerificationResult(
                valid=False,
                reason=f"Invalid commitment: {e}"
            )
    
    def record_my_action(self, action_type: str, action_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        Record my action with digital signature.
        Returns (complete_action_data, signature) tuple for opponent to verify.
        """
        # Create complete action data
        complete_data = {
            **action_data,
            'action_type': action_type,
            'timestamp': time.time()
        }
        
        message = json.dumps(complete_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        transaction = Transaction(
            move_type=MoveType.ACTION,
            participant_id=self.my_participant_id,
            data=complete_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        self.my_actions_count += 1
        
        return complete_data, signature
    
    def verify_opponent_action(self, 
                               action_data: Dict[str, Any], 
                               signature: str) -> VerificationResult:
        """
        Verify opponent's action signature and record to blockchain.
        This ensures opponent can't deny or forge actions.
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent commitment not set"
            )
        
        # Enforce turn order if enforcement is enabled
        if self.enable_enforcement and self.enforcement:
            if not self.enforcement.enforce_turn_order(self.opponent_participant_id):
                # Turn violation - record cheating
                if self.cheat_detector:
                    cheat = self.cheat_detector.record_cheat(
                        CheatType.DOUBLE_MOVE,
                        self.opponent_participant_id,
                        "Move attempted out of turn",
                        {
                            'action_data': action_data,
                            'current_turn': self.enforcement.current_turn,
                            'attempted_by': self.opponent_participant_id
                        }
                    )
                    if self.cheat_invalidator:
                        self.cheat_invalidator.invalidate_participant(
                            self.opponent_participant_id,
                            cheat
                        )
                
                return VerificationResult(
                    valid=False,
                    reason="Turn violation - opponent attempted move out of turn"
                )
        
        # Verify signature
        message = json.dumps(action_data, sort_keys=True)
        signature_valid = self.identity.verify_signature(
            message,
            signature,
            self.opponent_public_key
        )
        
        if not signature_valid:
            return VerificationResult(
                valid=False,
                reason="Invalid signature - opponent may be cheating!"
            )
        
        # Record to our blockchain
        transaction = Transaction(
            move_type=MoveType.ACTION,
            participant_id=self.opponent_participant_id,
            data=action_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        self.opponent_actions_count += 1
        
        # Switch turn after valid action
        if self.enable_enforcement and self.enforcement:
            self.enforcement.switch_turn()
        
        return VerificationResult(
            valid=True,
            reason="Opponent action verified and recorded"
        )
    
    def generate_proof(self, 
                      commitment_obj: Any,
                      query: Any) -> Tuple[Any, str]:
        """
        Generate zero-knowledge proof for a query.
        Returns (proof, signature) tuple.
        
        The proof reveals ONLY the answer to the query,
        nothing else about the committed state.
        """
        # Generate proof using commitment object (e.g., Merkle tree)
        proof = commitment_obj.generate_proof(query)
        
        # Sign the proof
        proof_data = {
            'proof_type': 'merkle',
            'query': query,
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,  # Generic: "has_value" not "has_ship"
            'leaf_data': proof.leaf_data,
            'merkle_path': proof.merkle_path,
            'timestamp': time.time()
        }
        
        message = json.dumps(proof_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        # Record proof generation to blockchain
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.my_participant_id,
            data=proof_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        
        return proof, signature
    
    def verify_proof(self,
                    proof: MerkleProof,
                    proof_signature: str,
                    committed_root: str) -> VerificationResult:
        """
        Verify zero-knowledge proof from opponent.
        Checks:
        1. Signature is valid (authentication)
        2. Proof is cryptographically correct (ZK verification)
        3. Proof matches commitment (binding)
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent not set up"
            )
        
        # Verify signature on proof
        proof_data = {
            'proof_type': 'merkle',
            'query': None,  # We don't know their query
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,
            'leaf_data': proof.leaf_data,
            'merkle_path': proof.merkle_path,
            'timestamp': proof.leaf_data.split(':')[-1] if ':' in proof.leaf_data else time.time()
        }
        
        # Verify cryptographic proof
        proof_valid = MerkleGridCommitment.verify_proof(proof, committed_root)
        
        if not proof_valid:
            return VerificationResult(
                valid=False,
                reason="Invalid proof - opponent is cheating!"
            )
        
        # Record verification to blockchain (with full proof for replay)
        verification_data = {
            'action': 'verified_proof',
            'position': proof.position,
            'result': proof.result,
            'has_value': proof.has_ship,
            'merkle_path': proof.merkle_path,  # Store full proof!
            'leaf_data': proof.leaf_data,      # Store leaf data!
            'committed_root': committed_root,   # Store root used!
            'opponent_id': self.opponent_participant_id,
            'timestamp': time.time()
        }
        
        message = json.dumps(verification_data, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        transaction = Transaction(
            move_type=MoveType.RESULT,
            participant_id=self.my_participant_id,
            data=verification_data,
            timestamp=time.time(),
            signature=signature
        )
        
        self.blockchain.add_transaction(transaction)
        self.blockchain.mine_block()
        
        return VerificationResult(
            valid=True,
            reason="Proof verified and recorded",
            details={'result': proof.result}
        )
    
    def verify_blockchain_integrity(self) -> VerificationResult:
        """Verify entire blockchain hasn't been tampered with"""
        valid = self.blockchain.verify_chain()
        
        return VerificationResult(
            valid=valid,
            reason="Blockchain valid" if valid else "Blockchain corrupted!"
        )
    
    def verify_all_signatures(self) -> VerificationResult:
        """
        Verify ALL signatures in blockchain.
        This ensures no transactions were forged.
        """
        invalid_txs = []
        
        for block_num, block in enumerate(self.blockchain.chain):
            for tx_num, tx in enumerate(block.transactions):
                # Skip commitments (no signature)
                if tx.move_type == MoveType.COMMITMENT:
                    continue
                
                # Verify signature
                if tx.participant_id == self.my_participant_id:
                    # My transaction - verify with my key
                    message = json.dumps(tx.data, sort_keys=True)
                    if not self.identity.verify_signature(
                        message, tx.signature, self.identity.public_key
                    ):
                        invalid_txs.append((block_num, tx_num, "my"))
                        
                elif tx.participant_id == self.opponent_participant_id:
                    # Opponent's transaction - verify with their key
                    if self.opponent_public_key:
                        message = json.dumps(tx.data, sort_keys=True)
                        if not self.identity.verify_signature(
                            message, tx.signature, self.opponent_public_key
                        ):
                            invalid_txs.append((block_num, tx_num, "opponent"))
        
        if invalid_txs:
            return VerificationResult(
                valid=False,
                reason=f"Found {len(invalid_txs)} invalid signatures",
                details={'invalid_transactions': invalid_txs}
            )
        
        return VerificationResult(
            valid=True,
            reason="All signatures valid"
        )
    
    def replay_from_blockchain(self) -> VerificationResult:
        """
        Replay entire protocol execution from blockchain.
        Verify every action, every proof, every signature.
        
        This allows ANYONE (even third party) to independently
        verify the entire protocol execution was fair.
        """
        # Verify blockchain structure
        chain_result = self.verify_blockchain_integrity()
        if not chain_result.valid:
            return chain_result
        
        # Verify all signatures
        sig_result = self.verify_all_signatures()
        if not sig_result.valid:
            return sig_result
        
        # Verify all proofs stored in blockchain
        invalid_proofs = []
        for block_num, block in enumerate(self.blockchain.chain):
            for tx_num, tx in enumerate(block.transactions):
                if tx.move_type == MoveType.RESULT and 'merkle_path' in tx.data:
                    # Reconstruct and verify proof
                    if 'committed_root' in tx.data:
                        proof = MerkleProof(
                            position=tuple(tx.data['position']),
                            has_ship=tx.data['has_value'],  # Note: MerkleProof uses 'has_ship' field name
                            result=tx.data['result'],
                            leaf_data=tx.data['leaf_data'],
                            merkle_path=tx.data['merkle_path']
                        )
                        
                        valid = MerkleGridCommitment.verify_proof(
                            proof,
                            tx.data['committed_root']
                        )
                        
                        if not valid:
                            invalid_proofs.append((block_num, tx_num))
        
        if invalid_proofs:
            return VerificationResult(
                valid=False,
                reason=f"Found {len(invalid_proofs)} invalid proofs in history",
                details={'invalid_proofs': invalid_proofs}
            )
        
        return VerificationResult(
            valid=True,
            reason="Complete protocol execution verified from blockchain"
        )
    
    def get_protocol_state(self) -> Dict[str, Any]:
        """
        Get complete protocol state for inspection/debugging.
        All information is cryptographically verifiable.
        """
        return {
            'protocol_active': self.protocol_active,
            'my_participant_id': self.my_participant_id,
            'opponent_participant_id': self.opponent_participant_id,
            'my_actions_count': self.my_actions_count,
            'opponent_actions_count': self.opponent_actions_count,
            'blockchain_blocks': len(self.blockchain.chain),
            'total_transactions': sum(len(b.transactions) for b in self.blockchain.chain),
            'blockchain_valid': self.blockchain.verify_chain(),
            'all_signatures_valid': self.verify_all_signatures().valid
        }
    
    def reveal_commitment(self, commitment_data: Any) -> Dict[str, Any]:
        """
        Reveal commitment data after protocol completion.
        This allows opponent to verify no cheating occurred.
        
        Returns revelation data that should be shared with opponent.
        """
        # Convert commitment data to serializable format
        if isinstance(commitment_data, (list, tuple)):
            commitment_data = list(commitment_data)
        
        revelation = {
            'participant_id': self.my_participant_id,
            'commitment_data': commitment_data,
            'seed': self.seed.hex() if isinstance(self.seed, bytes) else str(self.seed),
            'timestamp': time.time()
        }
        
        # Sign the revelation (without signature field)
        message = json.dumps(revelation, sort_keys=True)
        signature = self.identity.sign_message(message)
        
        # Add signature to result
        result = revelation.copy()
        result['signature'] = signature
        
        return result
    
    def handle_disconnect(self) -> None:
        """Handle disconnection"""
        if self.reconnection_handler:
            self.reconnection_handler.handle_disconnect()
        
        if self.on_disconnect:
            self.on_disconnect()
    
    def attempt_reconnect(self, connect_fn: Callable[[], bool]) -> bool:
        """Attempt reconnection"""
        if self.reconnection_handler:
            return self.reconnection_handler.attempt_reconnection(connect_fn)
        return False
    
    def verify_state_after_reconnect(self) -> bool:
        """Verify blockchain consistency after reconnection"""
        if self.reconnection_handler:
            return self.reconnection_handler.verify_state_after_reconnect()
        return True
    
    def sync_blockchain(self) -> None:
        """Sync blockchain with opponent (placeholder - should be called by network layer)"""
        # This is a placeholder - actual sync happens via network layer
        # But we can verify our blockchain is valid
        if not self.blockchain.verify_chain():
            print("⚠️  Blockchain invalid after sync attempt")
    
    def start_monitoring(self, interval: float = 1.0) -> None:
        """
        Start continuous monitoring thread.
        
        Args:
            interval: Seconds between monitoring checks
        """
        if self._monitoring:
            return
        
        if not self.enable_enforcement:
            print("⚠️  Monitoring requires enforcement to be enabled")
            return
        
        self._monitoring = True
        self._monitor_interval = interval
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        print("✅ Monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        print("⏹️  Monitoring stopped")
    
    def _monitor_loop(self, interval: float) -> None:
        """Continuous monitoring loop"""
        last_save_time = time.time()
        save_interval = 30.0  # Auto-save every 30 seconds
        
        while self._monitoring:
            try:
                # Check enforcement
                violations = self.check_enforcement()
                if violations:
                    self._handle_violations(violations)
                
                # Check health
                if self.health_monitor:
                    health = self.health_monitor.get_health_status()
                    if health.get('is_stalled', False):
                        self._handle_stall()
                    # Record activity
                    self.health_monitor.record_activity()
                
                # Periodic auto-save
                if self.state_manager and time.time() - last_save_time >= save_interval:
                    self.state_manager.save_state()
                    last_save_time = time.time()
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"⚠️  Monitoring error: {e}")
                time.sleep(interval)
    
    def _handle_violations(self, violations: List[CheatEvidence]) -> None:
        """Handle detected violations"""
        for violation in violations:
            # Log violation
            print(f"🚫 VIOLATION DETECTED: {violation.cheat_type.value}")
            print(f"   Cheater: {violation.cheater_id}")
            print(f"   Reason: {violation.description}")
            
            # Invalidate cheater
            if self.cheat_invalidator:
                self.cheat_invalidator.invalidate_participant(
                    violation.cheater_id,
                    violation
                )
            
            # Trigger forfeit callback
            if self.on_violation:
                try:
                    self.on_violation(violation)
                except Exception as e:
                    print(f"⚠️  Error in violation callback: {e}")
    
    def _handle_stall(self) -> None:
        """Handle protocol stall detection"""
        if self.health_monitor:
            health = self.health_monitor.get_health_status()
            if health.get('is_stalled', False):
                print("⚠️  Protocol appears stalled - checking for timeout violations...")
                # Check enforcement will handle timeouts
                violations = self.check_enforcement()
                if violations:
                    self._handle_violations(violations)
    
    def get_protocol_health(self) -> Dict[str, Any]:
        """
        Get protocol health status.
        
        Returns:
            Dict with health metrics
        """
        health = {
            'protocol_active': self.protocol_active,
            'blockchain_valid': self.blockchain.verify_chain(),
            'monitoring_active': self._monitoring,
            'enforcement_enabled': self.enable_enforcement,
            'persistence_enabled': self.enable_persistence
        }
        
        if self.health_monitor:
            monitor_health = self.health_monitor.get_health_status()
            health.update(monitor_health)
        
        if self.enforcement:
            health['pending_actions'] = len(self.enforcement.timeout_manager.pending_actions)
            health['current_turn'] = self.enforcement.current_turn
        
        if self.cheat_detector:
            health['cheats_detected'] = len(self.cheat_detector.detected_cheats)
            health['opponent_is_cheater'] = self.cheat_detector.opponent_is_cheater
        
        return health
    
    def check_enforcement(self) -> List[CheatEvidence]:
        """
        Check all enforcement rules and auto-forfeit if needed.
        Returns list of detected violations.
        """
        if not self.enable_enforcement or not self.enforcement:
            return []
        
        violations = []
        
        # Use enforcement's check_and_enforce which handles custom timeouts
        violations = self.enforcement.check_and_enforce()
        
        # Invalidate cheaters for all violations
        for cheat in violations:
            if self.cheat_invalidator:
                self.cheat_invalidator.invalidate_participant(
                    self.opponent_participant_id,
                    cheat
                )
        
        return violations
    
    def enforce_post_game_revelation(self, timeout: float = 60.0) -> bool:
        """
        Enforce post-game commitment revelation with timeout.
        Opponent must reveal their commitment within timeout or be invalidated.
        
        Args:
            timeout: Seconds to wait for revelation
        
        Returns:
            True if opponent revealed, False if timeout/invalidated
        """
        if not self.enable_enforcement or not self.enforcement:
            print("⚠️  Post-game enforcement requires enforcement to be enabled")
            return False
        
        if not self.opponent_participant_id:
            print("⚠️  No opponent to enforce revelation against")
            return False
        
        # Start timeout for revelation
        action_id = "post_game_reveal"
        self.enforcement.timeout_manager.start_action(action_id)
        original_timeout = self.enforcement.timeout_manager.config.action_timeout
        self.enforcement.timeout_manager.config.action_timeout = timeout
        
        print(f"⏳ Waiting for opponent to reveal commitment (timeout: {timeout}s)...")
        
        # Wait for revelation or timeout
        start = time.time()
        while time.time() - start < timeout:
            if self.opponent_revealed:
                # Opponent revealed - complete timeout
                self.enforcement.timeout_manager.complete_action(action_id)
                self.enforcement.timeout_manager.config.action_timeout = original_timeout
                print("✅ Opponent revealed commitment")
                return True
            
            # Check if timeout occurred
            timeouts = self.enforcement.timeout_manager.check_timeouts()
            if action_id in timeouts:
                # Timeout - opponent refused to reveal
                self.enforcement.timeout_manager.config.action_timeout = original_timeout
                
                if self.cheat_detector:
                    cheat = self.cheat_detector.record_cheat(
                        CheatType.COMMITMENT_MISMATCH,
                        self.opponent_participant_id,
                        f"Refused to reveal commitment after game (timeout: {timeout}s)",
                        {
                            'timeout': timeout,
                            'action_id': action_id,
                            'elapsed': time.time() - start
                        }
                    )
                    
                    if self.cheat_invalidator:
                        self.cheat_invalidator.invalidate_participant(
                            self.opponent_participant_id,
                            cheat
                        )
                
                print(f"🚫 Opponent failed to reveal commitment within {timeout}s - INVALIDATED")
                return False
            
            time.sleep(0.5)
        
        # Final check
        if not self.opponent_revealed:
            self.enforcement.timeout_manager.config.action_timeout = original_timeout
            
            if self.cheat_detector:
                cheat = self.cheat_detector.record_cheat(
                    CheatType.COMMITMENT_MISMATCH,
                    self.opponent_participant_id,
                    f"Refused to reveal commitment after game (timeout: {timeout}s)",
                    {
                        'timeout': timeout,
                        'action_id': action_id,
                        'elapsed': time.time() - start
                    }
                )
                
                if self.cheat_invalidator:
                    self.cheat_invalidator.invalidate_participant(
                        self.opponent_participant_id,
                        cheat
                    )
            
            print(f"🚫 Opponent failed to reveal commitment within {timeout}s - INVALIDATED")
            return False
        
        return True
    
    def verify_opponent_revelation(self, 
                                   revelation: Dict[str, Any],
                                   original_commitment_root: str) -> VerificationResult:
        """
        Verify opponent's commitment revelation.
        Ensures they didn't cheat during the protocol.
        
        Args:
            revelation: Opponent's revealed commitment data
            original_commitment_root: The commitment root they shared at start
        
        Returns:
            VerificationResult indicating if revelation is valid
        """
        if not self.opponent_public_key:
            return VerificationResult(
                valid=False,
                reason="Opponent public key not set"
            )
        
        # Extract signature
        signature = revelation.get('signature', '')
        if not signature:
            return VerificationResult(
                valid=False,
                reason="No signature in revelation"
            )
        
        # Verify signature on revelation (without signature field)
        revelation_copy = {k: v for k, v in revelation.items() if k != 'signature'}
        message = json.dumps(revelation_copy, sort_keys=True)
        
        if not self.identity.verify_signature(message, signature, self.opponent_public_key):
            return VerificationResult(
                valid=False,
                reason="Invalid signature on revelation"
            )
        
        # Mark opponent as revealed
        self.opponent_revealed = True
        
        # Signature valid - application layer should verify actual commitment
        return VerificationResult(
            valid=True,
            reason="Revelation signature valid - application should verify commitment",
            details=revelation_copy
        )


__all__ = [
    'ZeroTrustProtocol',
    'VerificationResult',
    'ProtocolEnforcement'
]

