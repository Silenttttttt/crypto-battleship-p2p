"""
Timeout and Error Handling for Zero-Trust Protocol

Provides timeout management, error recovery, and dispute resolution.
"""

import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class TimeoutReason(Enum):
    """Reasons for timeout"""
    NO_RESPONSE = "no_response"
    INVALID_ACTION = "invalid_action"
    NETWORK_ERROR = "network_error"
    PROTOCOL_VIOLATION = "protocol_violation"


@dataclass
class TimeoutConfig:
    """Configuration for timeouts"""
    action_timeout: float = 30.0  # Seconds to wait for action
    response_timeout: float = 15.0  # Seconds to wait for response
    commitment_timeout: float = 60.0  # Seconds to wait for commitment
    max_retries: int = 3  # Maximum retry attempts
    keepalive_interval: float = 10.0  # Seconds between keepalives


class ActionTimeout:
    """Manages timeouts for protocol actions"""
    
    def __init__(self, config: TimeoutConfig = None):
        self.config = config or TimeoutConfig()
        self.pending_actions: Dict[str, float] = {}  # action_id -> start_time
        self.timeout_handlers: Dict[str, Callable] = {}
    
    def start_action(self, action_id: str) -> None:
        """Start tracking an action"""
        self.pending_actions[action_id] = time.time()
    
    def complete_action(self, action_id: str) -> bool:
        """Mark action as complete"""
        if action_id in self.pending_actions:
            del self.pending_actions[action_id]
            return True
        return False
    
    def check_timeouts(self) -> Dict[str, TimeoutReason]:
        """
        Check for timed-out actions.
        Returns dict of action_id -> timeout_reason
        """
        now = time.time()
        timed_out = {}
        
        for action_id, start_time in list(self.pending_actions.items()):
            elapsed = now - start_time
            
            if elapsed > self.config.action_timeout:
                timed_out[action_id] = TimeoutReason.NO_RESPONSE
                del self.pending_actions[action_id]
        
        return timed_out
    
    def get_elapsed(self, action_id: str) -> Optional[float]:
        """Get elapsed time for an action"""
        if action_id in self.pending_actions:
            return time.time() - self.pending_actions[action_id]
        return None


class ErrorRecovery:
    """Handles error recovery and retry logic"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_counts: Dict[str, int] = {}  # action_id -> retry_count
        self.failed_actions: Dict[str, str] = {}  # action_id -> error_reason
    
    def should_retry(self, action_id: str) -> bool:
        """Check if action should be retried"""
        retry_count = self.retry_counts.get(action_id, 0)
        return retry_count < self.max_retries
    
    def record_retry(self, action_id: str) -> int:
        """Record a retry attempt, returns new retry count"""
        self.retry_counts[action_id] = self.retry_counts.get(action_id, 0) + 1
        return self.retry_counts[action_id]
    
    def record_failure(self, action_id: str, reason: str) -> None:
        """Record a failed action"""
        self.failed_actions[action_id] = reason
        if action_id in self.retry_counts:
            del self.retry_counts[action_id]
    
    def record_success(self, action_id: str) -> None:
        """Record a successful action"""
        if action_id in self.retry_counts:
            del self.retry_counts[action_id]
        if action_id in self.failed_actions:
            del self.failed_actions[action_id]
    
    def get_retry_count(self, action_id: str) -> int:
        """Get current retry count for action"""
        return self.retry_counts.get(action_id, 0)


class DisputeResolution:
    """Handles dispute resolution between peers"""
    
    def __init__(self):
        self.disputes: Dict[str, Dict[str, Any]] = {}  # dispute_id -> dispute_data
    
    def create_dispute(self, 
                      dispute_id: str, 
                      reason: str, 
                      evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a dispute record.
        
        Args:
            dispute_id: Unique identifier for dispute
            reason: Human-readable reason
            evidence: Evidence supporting the dispute
        
        Returns:
            Dispute record
        """
        dispute = {
            'dispute_id': dispute_id,
            'reason': reason,
            'evidence': evidence,
            'timestamp': time.time(),
            'status': 'pending'
        }
        self.disputes[dispute_id] = dispute
        return dispute
    
    def resolve_dispute(self, 
                       dispute_id: str, 
                       resolution: str, 
                       winner: Optional[str] = None) -> bool:
        """
        Resolve a dispute.
        
        Args:
            dispute_id: Dispute to resolve
            resolution: Resolution description
            winner: Optional participant who won the dispute
        
        Returns:
            True if dispute was resolved
        """
        if dispute_id not in self.disputes:
            return False
        
        self.disputes[dispute_id]['status'] = 'resolved'
        self.disputes[dispute_id]['resolution'] = resolution
        self.disputes[dispute_id]['winner'] = winner
        self.disputes[dispute_id]['resolved_at'] = time.time()
        return True
    
    def get_dispute(self, dispute_id: str) -> Optional[Dict[str, Any]]:
        """Get dispute record"""
        return self.disputes.get(dispute_id)
    
    def get_pending_disputes(self) -> Dict[str, Dict[str, Any]]:
        """Get all pending disputes"""
        return {
            dispute_id: dispute
            for dispute_id, dispute in self.disputes.items()
            if dispute['status'] == 'pending'
        }


class ProtocolMonitor:
    """Monitors protocol health and detects issues"""
    
    def __init__(self):
        self.last_activity: Optional[float] = None
        self.action_count: int = 0
        self.error_count: int = 0
        self.warning_count: int = 0
    
    def record_activity(self):
        """Record protocol activity"""
        self.last_activity = time.time()
        self.action_count += 1
    
    def record_error(self):
        """Record an error"""
        self.error_count += 1
    
    def record_warning(self):
        """Record a warning"""
        self.warning_count += 1
    
    def get_inactivity_duration(self) -> Optional[float]:
        """Get duration since last activity"""
        if self.last_activity is None:
            return None
        return time.time() - self.last_activity
    
    def is_stalled(self, threshold: float = 60.0) -> bool:
        """Check if protocol appears stalled"""
        inactivity = self.get_inactivity_duration()
        return inactivity is not None and inactivity > threshold
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall protocol health status"""
        inactivity = self.get_inactivity_duration()
        
        return {
            'actions': self.action_count,
            'errors': self.error_count,
            'warnings': self.warning_count,
            'last_activity': self.last_activity,
            'inactivity_seconds': inactivity,
            'is_stalled': self.is_stalled(),
            'error_rate': self.error_count / max(self.action_count, 1)
        }


__all__ = [
    'TimeoutConfig',
    'TimeoutReason',
    'ActionTimeout',
    'ErrorRecovery',
    'DisputeResolution',
    'ProtocolMonitor'
]

