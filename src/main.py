"""
Farcaster Coordination Monitor - Main Application
Real-time early warning system for AI agent coordination failures.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from coordination_monitor import CoordinationMonitor, EarlyWarningSignal
from farcaster_data_collector import FarcasterDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CoordinationMonitoringSystem:
    """
    Main coordination monitoring system that orchestrates data collection,
    analysis, and early warning detection.
    """
    
    def __init__(self):
        self.monitor = CoordinationMonitor(
            window_size=100,
            warning_threshold=0.7
        )
        self.data_collector = None
        self.is_running = False
        self.warning_callbacks = []
        
    async def start(self):
        """Start the monitoring system"""
        logger.info("Starting Farcaster Coordination Monitor...")
        
        self.data_collector = FarcasterDataCollector()
        await self.data_collector.__aenter__()
        
        self.is_running = True
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._monitoring_loop()),
            asyncio.create_task(self._status_reporter())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        finally:
            await self.stop()
            
    async def stop(self):
        """Stop the monitoring system"""
        logger.info("Stopping coordination monitor...")
        self.is_running = False
        
        if self.data_collector:
            await self.data_collector.__aexit__(None, None, None)
            
    async def _monitoring_loop(self):
        """Main monitoring loop - collects data and analyzes coordination"""
        logger.info("Starting monitoring loop...")
        
        while self.is_running:
            try:
                # Collect interaction data from the last 5 minutes
                coordination_data = await self.data_collector.get_coordination_data(
                    window_minutes=5
                )
                
                if coordination_data:
                    # Analyze coordination patterns
                    metrics = await self.monitor.analyze_coordination_patterns(
                        coordination_data
                    )
                    
                    logger.info(f"Health: {metrics.coordination_health:.2f}, "
                              f"Variance: {metrics.variance:.1f}, "
                              f"Autocorr: {metrics.autocorrelation:.3f}")
                    
                    # Check for early warning signals
                    warning = self.monitor.detect_early_warnings(metrics)
                    if warning:
                        await self._handle_warning(warning)
                        
                else:
                    logger.debug("No coordination data collected this cycle")
                    
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                
            # Wait before next monitoring cycle (30 seconds)
            await asyncio.sleep(30)
            
    async def _status_reporter(self):
        """Periodically report system status"""
        while self.is_running:
            try:
                status = self.monitor.get_coordination_status()
                
                if status["status"] != "healthy":
                    logger.warning(f"Coordination Status: {status}")
                else:
                    logger.info(f"System healthy - Health: {status['health']:.2f}")
                    
            except Exception as e:
                logger.error(f"Error in status reporter: {e}")
                
            # Report every 5 minutes
            await asyncio.sleep(300)
            
    async def _handle_warning(self, warning: EarlyWarningSignal):
        """Handle detected early warning signals"""
        logger.warning(f"⚠️  COORDINATION WARNING: {warning.signal_type} "
                      f"(severity: {warning.severity:.2f})")
        
        # Log detailed warning information
        logger.warning(f"   Health: {warning.metrics.coordination_health:.2f}")
        logger.warning(f"   Variance: {warning.metrics.variance:.1f}")
        logger.warning(f"   Autocorrelation: {warning.metrics.autocorrelation:.3f}")
        logger.warning(f"   Response Time: {warning.metrics.response_time:.1f}ms")
        logger.warning(f"   Agents: {warning.metrics.agent_count}")
        
        # Execute warning callbacks
        for callback in self.warning_callbacks:
            try:
                await callback(warning)
            except Exception as e:
                logger.error(f"Error in warning callback: {e}")
                
    def add_warning_callback(self, callback):
        """Add a callback function to be called when warnings are detected"""
        self.warning_callbacks.append(callback)
        
    def get_current_status(self) -> Dict:
        """Get current system status"""
        return self.monitor.get_coordination_status()
        
    def get_recent_warnings(self, hours: int = 1) -> List[EarlyWarningSignal]:
        """Get warnings from the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [w for w in self.monitor.warnings if w.timestamp > cutoff]

# Example warning handler
async def post_warning_to_farcaster(warning: EarlyWarningSignal):
    """
    Example warning handler that posts alerts to Farcaster.
    In a real implementation, this would use the Farcaster MCP to post.
    """
    severity_emoji = "🟡" if warning.severity < 0.8 else "🔴"
    
    message = (f"{severity_emoji} Coordination Warning Detected\n"
               f"Type: {warning.signal_type}\n"
               f"Health: {warning.metrics.coordination_health:.1%}\n"
               f"Time: {warning.timestamp.strftime('%H:%M:%S')}")
    
    logger.info(f"Would post to Farcaster: {message}")
    # await farcaster_mcp.post_cast(message)

# CLI interface for testing
async def run_monitoring_system():
    """Run the monitoring system with basic configuration"""
    system = CoordinationMonitoringSystem()
    
    # Add warning handler
    system.add_warning_callback(post_warning_to_farcaster)
    
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")

# Simple test mode
async def test_mode():
    """Run a quick test of the monitoring system"""
    logger.info("Running in test mode...")
    
    system = CoordinationMonitoringSystem()
    system.data_collector = FarcasterDataCollector()
    await system.data_collector.__aenter__()
    
    try:
        # Collect some test data
        coordination_data = await system.data_collector.get_coordination_data(1)
        logger.info(f"Collected {len(coordination_data)} test interactions")
        
        # Analyze it
        metrics = await system.monitor.analyze_coordination_patterns(coordination_data)
        logger.info(f"Analysis complete - Health: {metrics.coordination_health:.2f}")
        
        # Check for warnings
        warning = system.monitor.detect_early_warnings(metrics)
        if warning:
            logger.warning(f"Warning detected: {warning.signal_type}")
        else:
            logger.info("No warnings detected")
            
        # Show status
        status = system.monitor.get_coordination_status()
        logger.info(f"Final status: {status}")
        
    finally:
        await system.data_collector.__aexit__(None, None, None)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_mode())
    else:
        asyncio.run(run_monitoring_system())