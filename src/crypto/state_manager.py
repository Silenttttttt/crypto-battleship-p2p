"""
State Persistence Manager

Handles saving and loading protocol state for recovery and reconnection.
"""

import json
import time
import threading
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from .protocol import ZeroTrustProtocol


class StateManager:
    """
    Manages protocol state persistence.
    Saves complete state to disk for recovery.
    """
    
    def __init__(self, protocol: 'ZeroTrustProtocol', save_path: str = "game_state.json"):
        self.protocol = protocol
        self.save_path = Path(save_path)
        self._auto_save_thread = None
        self._auto_save_interval = 30.0
        self._auto_save_running = False
    
    def save_state(self) -> bool:
        """
        Save complete protocol state to disk.
        
        Returns:
            True if save successful, False otherwise
        """
        try:
            state = {
                'blockchain': self.protocol.blockchain.serialize(),
                'my_participant_id': self.protocol.my_participant_id,
                'opponent_participant_id': self.protocol.opponent_participant_id,
                'my_commitment_root': getattr(self.protocol, 'my_commitment_root', None),
                'opponent_commitment': self.protocol.opponent_commitment,
                'my_actions_count': self.protocol.my_actions_count,
                'opponent_actions_count': self.protocol.opponent_actions_count,
                'protocol_active': self.protocol.protocol_active,
                'timestamp': time.time(),
                'version': '1.0'
            }
            
            # Save enforcement state if enabled
            if self.protocol.enable_enforcement and self.protocol.enforcement:
                state['enforcement'] = {
                    'current_turn': self.protocol.enforcement.current_turn,
                    'turn_sequence': self.protocol.enforcement.turn_sequence,
                    'pending_actions': list(self.protocol.enforcement.timeout_manager.pending_actions.keys())
                }
            
            # Save cheat detection state
            if self.protocol.cheat_detector:
                state['cheat_detection'] = {
                    'opponent_is_cheater': self.protocol.cheat_detector.opponent_is_cheater,
                    'total_cheats': len(self.protocol.cheat_detector.detected_cheats)
                }
            
            # Write to file atomically
            temp_path = self.save_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(state, f, indent=2)
            
            # Atomic rename
            temp_path.replace(self.save_path)
            
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to save state: {e}")
            return False
    
    def load_state(self) -> bool:
        """
        Load protocol state from disk.
        
        Returns:
            True if load successful, False otherwise
        """
        try:
            if not self.save_path.exists():
                return False
            
            with open(self.save_path, 'r') as f:
                state = json.load(f)
            
            # Restore blockchain
            self.protocol.blockchain = self.protocol.blockchain.deserialize(state['blockchain'])
            
            # Restore participant state
            self.protocol.opponent_participant_id = state.get('opponent_participant_id')
            self.protocol.opponent_commitment = state.get('opponent_commitment')
            self.protocol.my_actions_count = state.get('my_actions_count', 0)
            self.protocol.opponent_actions_count = state.get('opponent_actions_count', 0)
            self.protocol.protocol_active = state.get('protocol_active', False)
            
            # Restore enforcement state
            if self.protocol.enable_enforcement and self.protocol.enforcement:
                enforcement_state = state.get('enforcement', {})
                self.protocol.enforcement.current_turn = enforcement_state.get('current_turn')
                self.protocol.enforcement.turn_sequence = enforcement_state.get('turn_sequence', [])
            
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to load state: {e}")
            return False
    
    def start_auto_save(self, interval: float = 30.0) -> None:
        """
        Start automatic periodic state saving.
        
        Args:
            interval: Seconds between auto-saves
        """
        if self._auto_save_running:
            return
        
        self._auto_save_interval = interval
        self._auto_save_running = True
        
        def auto_save_loop():
            while self._auto_save_running:
                time.sleep(self._auto_save_interval)
                if self._auto_save_running:
                    self.save_state()
        
        self._auto_save_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self._auto_save_thread.start()
    
    def stop_auto_save(self) -> None:
        """Stop automatic state saving"""
        self._auto_save_running = False
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=1.0)
            self._auto_save_thread = None


__all__ = ['StateManager']

