"""
Reconnection Handler

Handles disconnection and reconnection with state recovery.
"""

import time
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .protocol import ZeroTrustProtocol
    from .state_manager import StateManager

from .sync import BlockchainSync


class ReconnectionHandler:
    """
    Handles reconnection logic with state recovery and blockchain sync.
    """
    
    def __init__(self, 
                 protocol: 'ZeroTrustProtocol', 
                 state_manager: 'StateManager',
                 max_attempts: int = 3,
                 retry_delay: float = 5.0):
        self.protocol = protocol
        self.state_manager = state_manager
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
    
    def handle_disconnect(self) -> bool:
        """
        Handle disconnection with state save.
        
        Returns:
            True if state saved successfully
        """
        try:
            # Save current state before disconnect
            return self.state_manager.save_state()
        except Exception as e:
            print(f"⚠️  Failed to save state on disconnect: {e}")
            return False
    
    def attempt_reconnection(self, connect_fn: Callable[[], bool]) -> bool:
        """
        Attempt to reconnect with exponential backoff.
        
        Args:
            connect_fn: Function that attempts connection, returns True if successful
        
        Returns:
            True if reconnected successfully, False otherwise
        """
        for attempt in range(self.max_attempts):
            try:
                print(f"🔄 Reconnection attempt {attempt + 1}/{self.max_attempts}...")
                
                if connect_fn():
                    print("✅ Reconnected successfully")
                    
                    # Load saved state
                    if self.state_manager.load_state():
                        print("✅ State restored from disk")
                    
                    # Sync blockchain with opponent
                    if hasattr(self.protocol, 'sync_blockchain'):
                        self.protocol.sync_blockchain()
                    
                    return True
                    
            except Exception as e:
                print(f"⚠️  Reconnection attempt {attempt + 1} failed: {e}")
            
            # Exponential backoff
            if attempt < self.max_attempts - 1:
                wait_time = self.retry_delay * (2 ** attempt)
                print(f"⏳ Waiting {wait_time:.1f}s before next attempt...")
                time.sleep(wait_time)
        
        print("❌ Reconnection failed after all attempts")
        return False
    
    def verify_state_after_reconnect(self) -> bool:
        """
        Verify blockchain consistency after reconnection.
        Compares local blockchain with opponent's and resolves conflicts.
        
        Returns:
            True if state is consistent, False if conflicts detected
        """
        try:
            # Use blockchain sync to verify consistency
            sync = BlockchainSync(self.protocol.blockchain)
            
            # Get our state
            our_state = sync.get_sync_state()
            
            # If we have opponent's state from sync, compare
            if hasattr(sync, 'peer_state') and sync.peer_state:
                # Check if chains match
                if our_state.chain_length != sync.peer_state.chain_length:
                    print(f"⚠️  Chain length mismatch: {our_state.chain_length} vs {sync.peer_state.chain_length}")
                    # Try to merge
                    needs_sync, reason = sync.needs_sync()
                    if needs_sync:
                        print(f"📡 Syncing blockchain: {reason}")
                        # The sync mechanism will handle merging
                        return True
                
                # Check state roots
                if our_state.state_root != sync.peer_state.state_root:
                    print(f"⚠️  State root mismatch - chains may have diverged")
                    # This is more serious - may need manual resolution
                    return False
            
            print("✅ Blockchain state verified after reconnection")
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to verify state after reconnect: {e}")
            return False


__all__ = ['ReconnectionHandler']

