#!/usr/bin/env python3
"""
Production MCP Bridge for Farcaster Coordination Monitor
Integrates Mani Mohan's Farcaster MCP server with RagaAI-Catalyst monitoring
for real-time coordination pathology detection.
"""

import json
import subprocess
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import numpy as np
from dataclasses import dataclass

# RagaAI-Catalyst integration (when available)
try:
    from raga_ai_catalyst import trace_agent, log_metric
    RAGA_AVAILABLE = True
except ImportError:
    print("RagaAI-Catalyst not available - using mock decorators")
    RAGA_AVAILABLE = False
    
    # Mock decorators for development
    def trace_agent(func):
        return func
    
    def log_metric(name, value, tags=None):
        print(f"METRIC: {name}={value}, tags={tags}")

@dataclass
class CoordinationSignal:
    """Represents a detected coordination pattern"""
    signal_type: str
    strength: float
    participants: List[str]
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class CSDIndicator:
    """Critical Slowing Down indicators"""
    variance: float
    autocorrelation: float
    response_time_ms: float
    threshold_exceeded: bool
    risk_level: str  # 'low', 'medium', 'high', 'critical'

class FarcasterMCPBridge:
    """Production bridge between Farcaster MCP server and coordination monitoring"""
    
    def __init__(self, mcp_server_path: str = "./farcaster-mcp/build/index.js"):
        self.mcp_server_path = mcp_server_path
        self.logger = logging.getLogger(__name__)
        self.coordination_buffer = []
        self.csd_history = []
        
        # CSD detection thresholds
        self.variance_threshold = 2.5  # standard deviations
        self.autocorr_threshold = 0.7
        self.response_time_threshold = 150  # milliseconds
        
    @trace_agent
    async def start_mcp_server(self) -> bool:
        """Start the Farcaster MCP server"""
        try:
            # Verify MCP server exists
            process = await asyncio.create_subprocess_exec(
                'node', self.mcp_server_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            if process.returncode is None:  # Still running
                self.logger.info("Farcaster MCP server started successfully")
                log_metric("mcp_server_status", 1, {"status": "running"})
                return True
            else:
                self.logger.error(f"MCP server failed to start: {process.returncode}")
                log_metric("mcp_server_status", 0, {"status": "failed"})
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start MCP server: {e}")
            log_metric("mcp_server_status", 0, {"status": "error", "error": str(e)})
            return False
    
    @trace_agent
    async def get_user_casts(self, fid: int, limit: int = 50) -> Dict[str, Any]:
        """Get user casts with coordination monitoring"""
        start_time = datetime.now()
        
        try:
            # Mock MCP call (replace with actual MCP client call)
            result = await self._mock_mcp_call("get-user-casts", {
                "fid": fid,
                "limit": limit
            })
            
            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log metrics
            log_metric("mcp_call_duration", response_time, {
                "tool": "get-user-casts",
                "fid": str(fid),
                "limit": str(limit)
            })
            
            # Analyze for coordination signals
            coordination_signals = self._detect_coordination_patterns(result)
            
            if coordination_signals:
                log_metric("coordination_signals_detected", len(coordination_signals), {
                    "fid": str(fid),
                    "signal_types": [s.signal_type for s in coordination_signals]
                })
            
            # Update CSD indicators
            csd_indicator = self._calculate_csd_indicators(response_time, result)
            self._update_csd_history(csd_indicator)
            
            return {
                "casts": result,
                "coordination_signals": coordination_signals,
                "csd_indicator": csd_indicator,
                "response_time_ms": response_time
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user casts: {e}")
            log_metric("mcp_call_error", 1, {
                "tool": "get-user-casts",
                "error": str(e)
            })
            raise
    
    @trace_agent 
    async def get_channel_casts(self, channel: str, limit: int = 50) -> Dict[str, Any]:
        """Get channel casts with swarm coordination analysis"""
        start_time = datetime.now()
        
        try:
            result = await self._mock_mcp_call("get-channel-casts", {
                "channel": channel,
                "limit": limit
            })
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Channel-specific coordination detection
            swarm_signals = self._detect_swarm_coordination(result, channel)
            
            if swarm_signals:
                log_metric("swarm_coordination_detected", len(swarm_signals), {
                    "channel": channel,
                    "agent_count": len(set([s.participants for s in swarm_signals]))
                })
            
            csd_indicator = self._calculate_csd_indicators(response_time, result)
            
            return {
                "casts": result,
                "swarm_signals": swarm_signals,
                "csd_indicator": csd_indicator,
                "response_time_ms": response_time
            }
            
        except Exception as e:
            self.logger.error(f"Error getting channel casts: {e}")
            log_metric("mcp_call_error", 1, {
                "tool": "get-channel-casts", 
                "error": str(e)
            })
            raise
    
    def _detect_coordination_patterns(self, casts: List[Dict]) -> List[CoordinationSignal]:
        """Detect coordination patterns in cast data"""
        signals = []
        
        if not casts:
            return signals
            
        # Timestamp clustering analysis
        timestamps = [cast.get('timestamp', 0) for cast in casts]
        if len(timestamps) > 1:
            time_diffs = np.diff(sorted(timestamps))
            
            # Detect synchronized posting (small time differences)
            sync_threshold = 30  # seconds
            sync_events = sum(1 for diff in time_diffs if diff < sync_threshold)
            
            if sync_events > len(time_diffs) * 0.3:  # 30% of posts are synchronized
                signals.append(CoordinationSignal(
                    signal_type="synchronous_posting",
                    strength=sync_events / len(time_diffs),
                    participants=[cast.get('author_fid', 'unknown') for cast in casts],
                    timestamp=datetime.now(),
                    metadata={"sync_events": sync_events, "total_posts": len(casts)}
                ))
        
        # Content similarity analysis (simplified)
        if len(casts) > 2:
            content_similarity = self._calculate_content_similarity(casts)
            if content_similarity > 0.8:  # High similarity threshold
                signals.append(CoordinationSignal(
                    signal_type="content_coordination",
                    strength=content_similarity,
                    participants=[cast.get('author_fid', 'unknown') for cast in casts],
                    timestamp=datetime.now(),
                    metadata={"similarity_score": content_similarity}
                ))
        
        return signals
    
    def _detect_swarm_coordination(self, casts: List[Dict], channel: str) -> List[CoordinationSignal]:
        """Detect AI agent swarm coordination patterns"""
        signals = []
        
        if not casts:
            return signals
        
        # Identify potential AI agents (heuristic-based)
        potential_agents = []
        for cast in casts:
            author = cast.get('author', {})
            username = author.get('username', '')
            display_name = author.get('display_name', '')
            
            # Simple AI agent detection heuristics
            agent_indicators = [
                'agent' in username.lower(),
                'ai' in username.lower() or 'ai' in display_name.lower(),
                'bot' in username.lower(),
                cast.get('text', '').count('\n') > 3,  # Structured content
                len(cast.get('text', '')) > 280  # Long-form content
            ]
            
            if sum(agent_indicators) >= 2:
                potential_agents.append(cast)
        
        if len(potential_agents) >= 3:  # Minimum swarm size
            # Analyze swarm coordination
            agent_timestamps = [cast.get('timestamp', 0) for cast in potential_agents]
            time_variance = np.var(agent_timestamps) if agent_timestamps else 0
            
            # Low time variance suggests coordination
            if time_variance < 3600:  # Within 1 hour variance
                signals.append(CoordinationSignal(
                    signal_type="agent_swarm_coordination",
                    strength=1 - (time_variance / 3600),  # Inverse of variance
                    participants=[cast.get('author_fid', 'unknown') for cast in potential_agents],
                    timestamp=datetime.now(),
                    metadata={
                        "channel": channel,
                        "agent_count": len(potential_agents),
                        "time_variance": time_variance
                    }
                ))
        
        return signals
    
    def _calculate_content_similarity(self, casts: List[Dict]) -> float:
        """Simple content similarity calculation"""
        texts = [cast.get('text', '') for cast in casts]
        if len(texts) < 2:
            return 0.0
        
        # Simple word overlap similarity
        word_sets = [set(text.lower().split()) for text in texts]
        
        total_similarity = 0
        comparisons = 0
        
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                if len(word_sets[i]) > 0 and len(word_sets[j]) > 0:
                    intersection = len(word_sets[i].intersection(word_sets[j]))
                    union = len(word_sets[i].union(word_sets[j]))
                    similarity = intersection / union if union > 0 else 0
                    total_similarity += similarity
                    comparisons += 1
        
        return total_similarity / comparisons if comparisons > 0 else 0.0
    
    def _calculate_csd_indicators(self, response_time: float, data: Any) -> CSDIndicator:
        """Calculate Critical Slowing Down indicators"""
        # Add current response time to history
        self.coordination_buffer.append({
            'timestamp': datetime.now(),
            'response_time': response_time,
            'data_size': len(data) if isinstance(data, list) else 1
        })
        
        # Keep only recent history (last 100 data points)
        if len(self.coordination_buffer) > 100:
            self.coordination_buffer = self.coordination_buffer[-100:]
        
        if len(self.coordination_buffer) < 10:
            return CSDIndicator(0, 0, response_time, False, "insufficient_data")
        
        # Calculate variance in response times
        response_times = [item['response_time'] for item in self.coordination_buffer]
        variance = np.var(response_times)
        mean_response = np.mean(response_times)
        variance_zscore = (variance - np.mean(response_times)) / (np.std(response_times) + 1e-8)
        
        # Calculate lag-1 autocorrelation
        if len(response_times) > 1:
            autocorrelation = np.corrcoef(response_times[:-1], response_times[1:])[0, 1]
            autocorrelation = 0 if np.isnan(autocorrelation) else autocorrelation
        else:
            autocorrelation = 0
        
        # Determine if thresholds are exceeded
        variance_exceeded = abs(variance_zscore) > self.variance_threshold
        autocorr_exceeded = abs(autocorrelation) > self.autocorr_threshold
        response_exceeded = response_time > self.response_time_threshold
        
        threshold_exceeded = any([variance_exceeded, autocorr_exceeded, response_exceeded])
        
        # Determine risk level
        if variance_exceeded and autocorr_exceeded and response_exceeded:
            risk_level = "critical"
        elif (variance_exceeded and autocorr_exceeded) or response_exceeded:
            risk_level = "high"
        elif variance_exceeded or autocorr_exceeded:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return CSDIndicator(
            variance=variance,
            autocorrelation=autocorrelation,
            response_time_ms=response_time,
            threshold_exceeded=threshold_exceeded,
            risk_level=risk_level
        )
    
    def _update_csd_history(self, indicator: CSDIndicator):
        """Update CSD history and trigger alerts if needed"""
        self.csd_history.append({
            'timestamp': datetime.now(),
            'indicator': indicator
        })
        
        # Keep only recent history
        if len(self.csd_history) > 1000:
            self.csd_history = self.csd_history[-1000:]
        
        # Log critical indicators
        if indicator.risk_level in ['high', 'critical']:
            log_metric("csd_critical_indicator", 1, {
                "risk_level": indicator.risk_level,
                "variance": str(indicator.variance),
                "autocorrelation": str(indicator.autocorrelation),
                "response_time": str(indicator.response_time_ms)
            })
            
            self.logger.warning(f"CSD Critical Indicator Detected: {indicator.risk_level} "
                               f"(var={indicator.variance:.3f}, "
                               f"autocorr={indicator.autocorrelation:.3f}, "
                               f"response={indicator.response_time_ms:.1f}ms)")
    
    async def _mock_mcp_call(self, tool: str, params: Dict) -> List[Dict]:
        """Mock MCP call for development - replace with actual MCP client"""
        # This would be replaced with actual MCP client call
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # Return mock data structure
        return [
            {
                "hash": f"0x123...{i}",
                "author_fid": params.get('fid', 1000 + i),
                "author": {
                    "username": f"user_{i}",
                    "display_name": f"User {i}"
                },
                "text": f"Mock cast content {i}",
                "timestamp": 1640995200 + i * 60,  # Mock timestamps
                "replies": {"count": i % 5},
                "reactions": {"likes": i % 10, "recasts": i % 3}
            }
            for i in range(params.get('limit', 10))
        ]

# Example usage
async def main():
    """Example production usage"""
    bridge = FarcasterMCPBridge()
    
    # Start MCP server
    if await bridge.start_mcp_server():
        print("MCP server running, monitoring coordination patterns...")
        
        # Monitor a user for coordination patterns
        result = await bridge.get_user_casts(fid=6846, limit=20)
        
        print(f"Response time: {result['response_time_ms']:.1f}ms")
        print(f"Coordination signals detected: {len(result['coordination_signals'])}")
        print(f"CSD risk level: {result['csd_indicator'].risk_level}")
        
        # Monitor a channel for swarm coordination
        channel_result = await bridge.get_channel_casts("aichannel", limit=50)
        
        print(f"Swarm signals detected: {len(channel_result['swarm_signals'])}")
        
        for signal in channel_result['swarm_signals']:
            print(f"  {signal.signal_type}: strength={signal.strength:.3f}, "
                  f"participants={len(signal.participants)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())