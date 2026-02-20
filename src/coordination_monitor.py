"""
Farcaster Coordination Monitor
Real-time detection of coordination failures using critical slowing down theory.
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

# RagaAI-Catalyst integration for monitoring
from raga_catalyst.trace import trace_agent, trace_tool
from raga_catalyst.traceable import traceable

logger = logging.getLogger(__name__)

@dataclass
class CoordinationMetrics:
    """Metrics for coordination health analysis"""
    timestamp: datetime
    variance: float
    autocorrelation: float
    response_time: float
    interaction_count: int
    agent_count: int
    coordination_health: float  # 0-1 scale

@dataclass
class EarlyWarningSignal:
    """Early warning signal for coordination failure"""
    timestamp: datetime
    signal_type: str  # 'variance_spike', 'autocorr_increase', 'response_lag'
    severity: float  # 0-1 scale
    metrics: CoordinationMetrics
    threshold_exceeded: bool

class CoordinationMonitor:
    """
    Main coordination monitoring system.
    Detects early warning signs of coordination failure using CSD theory.
    """
    
    def __init__(self, window_size: int = 100, warning_threshold: float = 0.7):
        self.window_size = window_size
        self.warning_threshold = warning_threshold
        self.interaction_history = []
        self.metrics_history = []
        self.warnings = []
        
    @trace_agent('coordination_monitor')
    async def analyze_coordination_patterns(self, interactions: List[Dict]) -> CoordinationMetrics:
        """
        Analyze coordination patterns from Farcaster interaction data.
        
        Args:
            interactions: List of agent interaction events from Farcaster MCP
            
        Returns:
            CoordinationMetrics with health assessment
        """
        if len(interactions) < 2:
            return CoordinationMetrics(
                timestamp=datetime.now(),
                variance=0.0,
                autocorrelation=0.0,
                response_time=0.0,
                interaction_count=0,
                agent_count=0,
                coordination_health=1.0
            )
            
        # Store interaction history
        self.interaction_history.extend(interactions)
        if len(self.interaction_history) > self.window_size:
            self.interaction_history = self.interaction_history[-self.window_size:]
            
        # Calculate core CSD metrics
        variance = self._calculate_variance()
        autocorr = self._calculate_autocorrelation()
        response_time = self._calculate_response_time()
        
        # Calculate coordination health (inverse of warning signals)
        health = self._calculate_coordination_health(variance, autocorr, response_time)
        
        metrics = CoordinationMetrics(
            timestamp=datetime.now(),
            variance=variance,
            autocorrelation=autocorr,
            response_time=response_time,
            interaction_count=len(interactions),
            agent_count=len(set(i.get('agent_id') for i in interactions)),
            coordination_health=health
        )
        
        self.metrics_history.append(metrics)
        return metrics
        
    @trace_tool('variance_calculator')
    def _calculate_variance(self) -> float:
        """Calculate variance in interaction timing (CSD indicator)"""
        if len(self.interaction_history) < 2:
            return 0.0
            
        timestamps = [i.get('timestamp', 0) for i in self.interaction_history]
        intervals = np.diff(timestamps)
        return float(np.var(intervals)) if len(intervals) > 0 else 0.0
        
    @trace_tool('autocorrelation_calculator') 
    def _calculate_autocorrelation(self, lag: int = 1) -> float:
        """Calculate lag-1 autocorrelation in interaction patterns (CSD indicator)"""
        if len(self.interaction_history) < lag + 2:
            return 0.0
            
        # Use response times as the time series
        response_times = [i.get('response_time', 0) for i in self.interaction_history]
        
        if len(response_times) < lag + 1:
            return 0.0
            
        series = np.array(response_times)
        n = len(series)
        
        # Calculate autocorrelation at specified lag
        mean = np.mean(series)
        c0 = np.mean((series - mean) ** 2)
        
        if c0 == 0:
            return 0.0
            
        c_lag = np.mean((series[:-lag] - mean) * (series[lag:] - mean))
        return float(c_lag / c0)
        
    def _calculate_response_time(self) -> float:
        """Calculate average response time between interactions"""
        if len(self.interaction_history) < 2:
            return 0.0
            
        response_times = [i.get('response_time', 0) for i in self.interaction_history]
        return float(np.mean(response_times))
        
    def _calculate_coordination_health(self, variance: float, autocorr: float, response_time: float) -> float:
        """
        Calculate overall coordination health score (0-1).
        Lower variance, lower autocorrelation, faster response = better health.
        """
        # Normalize metrics (these thresholds would be calibrated from data)
        variance_norm = min(variance / 1000.0, 1.0)  # Normalize to 0-1
        autocorr_norm = min(abs(autocorr), 1.0)  # High autocorr is warning sign
        response_norm = min(response_time / 5000.0, 1.0)  # Normalize to 0-1
        
        # Health decreases as warning indicators increase
        health = 1.0 - (0.4 * variance_norm + 0.4 * autocorr_norm + 0.2 * response_norm)
        return max(0.0, min(1.0, health))
        
    @traceable
    def detect_early_warnings(self, metrics: CoordinationMetrics) -> Optional[EarlyWarningSignal]:
        """Detect if current metrics indicate coordination failure risk"""
        warnings = []
        
        # Check for variance spike (system becoming unstable)
        if len(self.metrics_history) >= 2:
            prev_variance = self.metrics_history[-2].variance
            if metrics.variance > prev_variance * 2 and metrics.variance > 500:
                warnings.append(('variance_spike', metrics.variance / 1000.0))
                
        # Check for increasing autocorrelation (slower recovery from perturbations)
        if abs(metrics.autocorrelation) > 0.5:
            warnings.append(('autocorr_increase', abs(metrics.autocorrelation)))
            
        # Check for response time degradation
        if metrics.response_time > 3000:  # 3 seconds
            warnings.append(('response_lag', metrics.response_time / 5000.0))
            
        if warnings:
            # Take the most severe warning
            warning_type, severity = max(warnings, key=lambda x: x[1])
            
            warning = EarlyWarningSignal(
                timestamp=metrics.timestamp,
                signal_type=warning_type,
                severity=min(1.0, severity),
                metrics=metrics,
                threshold_exceeded=severity > self.warning_threshold
            )
            
            self.warnings.append(warning)
            return warning
            
        return None
        
    def get_coordination_status(self) -> Dict:
        """Get current coordination system status"""
        if not self.metrics_history:
            return {"status": "no_data", "health": 1.0}
            
        latest = self.metrics_history[-1]
        recent_warnings = [w for w in self.warnings 
                          if w.timestamp > datetime.now() - timedelta(minutes=10)]
        
        status = "healthy"
        if latest.coordination_health < 0.3:
            status = "critical"
        elif latest.coordination_health < 0.6:
            status = "warning"
        elif recent_warnings:
            status = "monitoring"
            
        return {
            "status": status,
            "health": latest.coordination_health,
            "variance": latest.variance,
            "autocorrelation": latest.autocorrelation,
            "response_time": latest.response_time,
            "recent_warnings": len(recent_warnings),
            "agent_count": latest.agent_count,
            "interaction_count": latest.interaction_count
        }

# Example usage and testing
if __name__ == "__main__":
    async def test_monitor():
        monitor = CoordinationMonitor()
        
        # Simulate some interaction data
        test_interactions = [
            {"agent_id": "agent1", "timestamp": 1000, "response_time": 200},
            {"agent_id": "agent2", "timestamp": 1200, "response_time": 300},
            {"agent_id": "agent1", "timestamp": 1400, "response_time": 250},
            {"agent_id": "agent3", "timestamp": 1600, "response_time": 400},
        ]
        
        metrics = await monitor.analyze_coordination_patterns(test_interactions)
        warning = monitor.detect_early_warnings(metrics)
        status = monitor.get_coordination_status()
        
        print(f"Coordination Health: {metrics.coordination_health:.2f}")
        print(f"Status: {status}")
        if warning:
            print(f"Warning: {warning.signal_type} (severity: {warning.severity:.2f})")
            
    asyncio.run(test_monitor())