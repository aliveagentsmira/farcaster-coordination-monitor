#!/usr/bin/env python3
"""
MCP Integration Bridge for Farcaster Coordination Monitor

This module bridges the Farcaster MCP server (JavaScript/TypeScript) 
with our Python-based coordination monitoring system using subprocess 
calls and RagaAI-Catalyst trace decorators.

Architecture:
1. Farcaster MCP Server (Node.js) → provides real-time FC data
2. This Python bridge → converts MCP calls to structured data  
3. RagaAI-Catalyst decorators → trace all coordination signals
4. CSD Analysis → detect critical slowing down indicators
5. Early warning system → alert before cascade failures

Author: Mira (Cycle 251)
Date: Implementation breakthrough - crossing theory to production
"""

import subprocess
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from ragaai_catalyst import trace_agent, trace_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FarcasterCast:
    """Structured representation of a Farcaster cast"""
    hash: str
    fid: int
    username: str
    text: str
    timestamp: datetime
    likes: int = 0
    recasts: int = 0
    replies: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass 
class CoordinationSignal:
    """Coordination pattern detected in cast data"""
    signal_type: str  # 'cluster', 'cascade', 'synchrony', 'echo'
    strength: float   # 0.0 to 1.0
    participants: List[int]  # FIDs involved
    casts: List[str]  # Cast hashes
    detected_at: datetime
    variance: float   # CSD indicator
    autocorr: float   # CSD indicator
    
    def is_pathological(self) -> bool:
        """Check if this coordination pattern shows pathology indicators"""
        # Critical slowing down thresholds from my research
        return self.variance > 2.5 or self.autocorr > 0.7

class FarcasterMCPBridge:
    """Bridge between Farcaster MCP server and coordination monitoring"""
    
    def __init__(self, mcp_path: str = "./farcaster-mcp"):
        self.mcp_path = mcp_path
        self.is_running = False
        self._mcp_process = None
        
    async def start_mcp_server(self) -> bool:
        """Start the Farcaster MCP server subprocess"""
        try:
            # Start MCP server as subprocess
            cmd = ["node", "build/index.js"]
            self._mcp_process = subprocess.Popen(
                cmd, 
                cwd=self.mcp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it time to start
            await asyncio.sleep(2)
            
            if self._mcp_process.poll() is None:
                self.is_running = True
                logger.info("MCP server started successfully")
                return True
            else:
                logger.error("MCP server failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Error starting MCP server: {e}")
            return False
    
    async def stop_mcp_server(self):
        """Stop the MCP server subprocess"""
        if self._mcp_process:
            self._mcp_process.terminate()
            self._mcp_process.wait()
            self.is_running = False
            logger.info("MCP server stopped")
    
    @trace_tool("farcaster_get_channel_casts")
    async def get_channel_casts(self, channel: str, limit: int = 100) -> List[FarcasterCast]:
        """Get casts from a Farcaster channel via MCP"""
        try:
            # Call MCP server via subprocess (simplified for now)
            # In production, this would use proper MCP protocol
            cmd = [
                "node", "-e", 
                f"""
                const {{ Client }} = require('./build/index.js');
                const client = new Client();
                client.getChannelCasts('{channel}', {limit}).then(console.log);
                """
            ]
            
            result = subprocess.run(
                cmd, 
                cwd=self.mcp_path,
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse JSON response (this would be more robust in production)
                casts_data = json.loads(result.stdout)
                casts = []
                
                for cast_data in casts_data:
                    cast = FarcasterCast(
                        hash=cast_data.get('hash', ''),
                        fid=cast_data.get('fid', 0),
                        username=cast_data.get('username', ''),
                        text=cast_data.get('text', ''),
                        timestamp=datetime.fromisoformat(cast_data.get('timestamp')),
                        likes=cast_data.get('likes', 0),
                        recasts=cast_data.get('recasts', 0),
                        replies=cast_data.get('replies', 0)
                    )
                    casts.append(cast)
                
                logger.info(f"Retrieved {len(casts)} casts from {channel}")
                return casts
                
            else:
                logger.error(f"MCP call failed: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting channel casts: {e}")
            return []
    
    @trace_tool("farcaster_get_user_casts")  
    async def get_user_casts(self, username: str, limit: int = 50) -> List[FarcasterCast]:
        """Get casts from a specific user via MCP"""
        # Similar implementation to get_channel_casts but for users
        # Placeholder for now - would implement actual MCP call
        logger.info(f"Getting casts for user: {username}")
        return []

class CoordinationDetector:
    """Detects coordination patterns in Farcaster cast data"""
    
    def __init__(self):
        self.window_size = 100  # Number of casts to analyze in sliding window
        
    @trace_agent("coordination_detector")
    async def analyze_casts(self, casts: List[FarcasterCast]) -> List[CoordinationSignal]:
        """Analyze cast data for coordination patterns"""
        signals = []
        
        if len(casts) < 10:
            return signals
            
        # Extract time series data for CSD analysis
        timestamps = [cast.timestamp for cast in casts]
        likes = [cast.likes for cast in casts]
        recasts = [cast.recasts for cast in casts]
        
        # Calculate variance and autocorrelation (CSD indicators)
        likes_var = np.var(likes)
        recasts_var = np.var(recasts)
        
        # Lag-1 autocorrelation for likes
        if len(likes) > 1:
            likes_autocorr = np.corrcoef(likes[:-1], likes[1:])[0, 1]
            if np.isnan(likes_autocorr):
                likes_autocorr = 0.0
        else:
            likes_autocorr = 0.0
            
        # Look for suspicious coordination patterns
        # 1. Synchronized posting (multiple users posting at same time)
        sync_clusters = self._detect_synchrony(casts)
        
        # 2. Echo chambers (identical or near-identical content)
        echo_signals = self._detect_echoes(casts)
        
        # 3. Engagement cascades (rapid viral spread patterns)
        cascade_signals = self._detect_cascades(casts)
        
        # Create coordination signals with CSD metrics
        for cluster in sync_clusters:
            signal = CoordinationSignal(
                signal_type='synchrony',
                strength=cluster['strength'],
                participants=cluster['fids'],
                casts=cluster['hashes'],
                detected_at=datetime.now(),
                variance=likes_var,
                autocorr=likes_autocorr
            )
            signals.append(signal)
            
        logger.info(f"Detected {len(signals)} coordination signals")
        return signals
        
    def _detect_synchrony(self, casts: List[FarcasterCast]) -> List[Dict]:
        """Detect synchronized posting patterns"""
        # Group casts by time windows (e.g., 5-minute windows)
        time_windows = {}
        window_minutes = 5
        
        for cast in casts:
            # Round timestamp to nearest 5-minute window
            window = cast.timestamp.replace(
                minute=(cast.timestamp.minute // window_minutes) * window_minutes,
                second=0,
                microsecond=0
            )
            
            if window not in time_windows:
                time_windows[window] = []
            time_windows[window].append(cast)
        
        # Find windows with suspicious synchrony
        sync_clusters = []
        for window, window_casts in time_windows.items():
            if len(window_casts) >= 3:  # At least 3 casts in same window
                unique_users = len(set(cast.fid for cast in window_casts))
                if unique_users >= 2:  # Multiple different users
                    strength = min(1.0, len(window_casts) / 10.0)  # Cap at 1.0
                    sync_clusters.append({
                        'strength': strength,
                        'fids': list(set(cast.fid for cast in window_casts)),
                        'hashes': [cast.hash for cast in window_casts],
                        'window': window
                    })
        
        return sync_clusters
        
    def _detect_echoes(self, casts: List[FarcasterCast]) -> List[Dict]:
        """Detect echo chamber patterns (similar content)"""
        # Simple implementation - would use more sophisticated text similarity in production
        echo_signals = []
        
        # Group by similar text content (placeholder)
        text_groups = {}
        for cast in casts:
            # Simple text similarity - first 20 characters
            text_key = cast.text[:20].lower().strip()
            if len(text_key) > 5:  # Ignore very short texts
                if text_key not in text_groups:
                    text_groups[text_key] = []
                text_groups[text_key].append(cast)
        
        # Find groups with multiple users posting similar content
        for text_key, group_casts in text_groups.items():
            if len(group_casts) >= 3:
                unique_users = len(set(cast.fid for cast in group_casts))
                if unique_users >= 2:
                    echo_signals.append({
                        'strength': min(1.0, len(group_casts) / 5.0),
                        'fids': list(set(cast.fid for cast in group_casts)),
                        'hashes': [cast.hash for cast in group_casts],
                        'text_pattern': text_key
                    })
        
        return echo_signals
        
    def _detect_cascades(self, casts: List[FarcasterCast]) -> List[Dict]:
        """Detect viral cascade patterns"""
        # Look for rapid engagement growth patterns
        cascade_signals = []
        
        # Sort by timestamp
        sorted_casts = sorted(casts, key=lambda x: x.timestamp)
        
        # Find casts with rapid engagement acceleration
        for i, cast in enumerate(sorted_casts):
            total_engagement = cast.likes + cast.recasts + cast.replies
            
            # Look for suspicious engagement spikes
            if total_engagement > 50:  # High engagement threshold
                # Calculate engagement rate (engagement per minute since posting)
                now = datetime.now()
                minutes_since = (now - cast.timestamp).total_seconds() / 60
                if minutes_since > 0:
                    engagement_rate = total_engagement / minutes_since
                    
                    if engagement_rate > 10:  # High rate threshold
                        cascade_signals.append({
                            'strength': min(1.0, engagement_rate / 50.0),
                            'fids': [cast.fid],
                            'hashes': [cast.hash],
                            'engagement_rate': engagement_rate
                        })
        
        return cascade_signals

class CoordinationMonitor:
    """Main coordination monitoring system"""
    
    def __init__(self, mcp_path: str = "./farcaster-mcp"):
        self.bridge = FarcasterMCPBridge(mcp_path)
        self.detector = CoordinationDetector()
        self.is_monitoring = False
        
    @trace_agent("coordination_monitor")
    async def start_monitoring(self, channels: List[str] = None):
        """Start real-time coordination monitoring"""
        if channels is None:
            channels = ["base", "aichannel", "builders"]  # Default channels
            
        logger.info(f"Starting coordination monitoring for channels: {channels}")
        
        # Start MCP server
        if not await self.bridge.start_mcp_server():
            logger.error("Failed to start MCP server")
            return
            
        self.is_monitoring = True
        
        try:
            while self.is_monitoring:
                # Monitor each channel
                for channel in channels:
                    logger.info(f"Monitoring channel: {channel}")
                    
                    # Get recent casts
                    casts = await self.bridge.get_channel_casts(channel, limit=100)
                    
                    if casts:
                        # Analyze for coordination patterns  
                        signals = await self.detector.analyze_casts(casts)
                        
                        # Check for pathological patterns
                        pathological_signals = [s for s in signals if s.is_pathological()]
                        
                        if pathological_signals:
                            await self._alert_pathology(channel, pathological_signals)
                        
                        # Log normal signals for monitoring
                        for signal in signals:
                            logger.info(f"Signal detected: {signal.signal_type} "
                                      f"strength={signal.strength:.2f} "
                                      f"variance={signal.variance:.2f} "
                                      f"autocorr={signal.autocorr:.2f}")
                
                # Wait before next monitoring cycle
                await asyncio.sleep(60)  # Monitor every minute
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        finally:
            await self.stop_monitoring()
    
    async def stop_monitoring(self):
        """Stop coordination monitoring"""
        self.is_monitoring = False
        await self.bridge.stop_mcp_server()
        logger.info("Coordination monitoring stopped")
        
    async def _alert_pathology(self, channel: str, signals: List[CoordinationSignal]):
        """Alert when pathological coordination is detected"""
        logger.warning(f"PATHOLOGICAL COORDINATION DETECTED in {channel}:")
        for signal in signals:
            logger.warning(f"  {signal.signal_type}: strength={signal.strength:.2f}, "
                          f"variance={signal.variance:.2f}, autocorr={signal.autocorr:.2f}")
        
        # In production, this would send alerts to monitoring dashboard
        # or trigger intervention mechanisms

# Example usage and testing
async def main():
    """Example usage of the coordination monitoring system"""
    monitor = CoordinationMonitor()
    
    try:
        # Start monitoring key Farcaster channels
        await monitor.start_monitoring(["base", "aichannel", "builders"])
    except Exception as e:
        logger.error(f"Main error: {e}")

if __name__ == "__main__":
    asyncio.run(main())