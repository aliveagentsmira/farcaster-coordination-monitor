"""
Farcaster Data Collector
Collects real-time agent interaction data from Farcaster via MCP servers.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AgentInteraction:
    """Represents a single agent interaction on Farcaster"""
    agent_id: str
    interaction_type: str  # 'cast', 'like', 'recast', 'reply'
    timestamp: int
    target_agent: Optional[str]
    response_time: float  # milliseconds
    content_length: int
    channel: Optional[str]
    engagement_score: float

class FarcasterDataCollector:
    """
    Collects real-time agent interaction data from Farcaster MCP servers.
    Focuses on agent-to-agent coordination patterns.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8080/sse"):
        self.mcp_server_url = mcp_server_url
        self.known_agents = set()
        self.interaction_buffer = []
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def identify_ai_agents(self) -> List[str]:
        """
        Identify AI agents on Farcaster by looking for common patterns.
        This is a heuristic approach - could be improved with a registry.
        """
        # For now, maintain a hardcoded list of known agents
        # In production, this would query a registry or use ML classification
        known_ai_agents = [
            "agentic_mira",
            "based-agent", 
            "clanker",
            "askgina.eth",
            "bountybot",
            # Add more as discovered
        ]
        
        self.known_agents.update(known_ai_agents)
        return list(self.known_agents)
        
    async def collect_interactions(self, duration_minutes: int = 10) -> List[AgentInteraction]:
        """
        Collect agent interactions for specified duration.
        
        Args:
            duration_minutes: How long to collect data
            
        Returns:
            List of agent interactions
        """
        await self.identify_ai_agents()
        interactions = []
        
        try:
            # In a real implementation, this would connect to the Farcaster MCP server
            # For now, simulate data collection
            interactions = await self._simulate_interaction_collection(duration_minutes)
            
        except Exception as e:
            logger.error(f"Error collecting interactions: {e}")
            
        return interactions
        
    async def _simulate_interaction_collection(self, duration_minutes: int) -> List[AgentInteraction]:
        """
        Simulate interaction collection for testing.
        In production, this would be replaced with real MCP server integration.
        """
        import random
        
        interactions = []
        agents = list(self.known_agents)
        
        if not agents:
            return interactions
            
        # Simulate interactions over time
        start_time = int(datetime.now().timestamp() * 1000)
        
        for i in range(duration_minutes * 5):  # ~5 interactions per minute
            timestamp = start_time + (i * 12000)  # 12 second intervals
            
            agent = random.choice(agents)
            target = random.choice(agents) if random.random() > 0.3 else None
            
            interaction = AgentInteraction(
                agent_id=agent,
                interaction_type=random.choice(['cast', 'like', 'recast', 'reply']),
                timestamp=timestamp,
                target_agent=target,
                response_time=random.gauss(1500, 500),  # 1.5s ± 0.5s
                content_length=random.randint(50, 280),
                channel=random.choice([None, 'ai-agents', 'dev', 'based']),
                engagement_score=random.random()
            )
            
            interactions.append(interaction)
            
        return interactions
        
    async def stream_interactions(self) -> AsyncGenerator[AgentInteraction, None]:
        """
        Stream interactions in real-time.
        This would connect to the MCP server's SSE endpoint in production.
        """
        await self.identify_ai_agents()
        
        # Simulate real-time streaming
        while True:
            interaction = await self._get_next_interaction()
            if interaction:
                yield interaction
            await asyncio.sleep(2)  # 2 second intervals
            
    async def _get_next_interaction(self) -> Optional[AgentInteraction]:
        """Get the next interaction from the stream"""
        import random
        
        agents = list(self.known_agents)
        if not agents:
            return None
            
        # Simulate receiving an interaction
        if random.random() > 0.3:  # 70% chance of interaction
            return AgentInteraction(
                agent_id=random.choice(agents),
                interaction_type=random.choice(['cast', 'like', 'recast', 'reply']),
                timestamp=int(datetime.now().timestamp() * 1000),
                target_agent=random.choice(agents) if random.random() > 0.4 else None,
                response_time=random.gauss(1500, 500),
                content_length=random.randint(50, 280),
                channel=random.choice([None, 'ai-agents', 'dev', 'based']),
                engagement_score=random.random()
            )
            
        return None
        
    def convert_to_monitor_format(self, interactions: List[AgentInteraction]) -> List[Dict]:
        """Convert AgentInteraction objects to format expected by CoordinationMonitor"""
        return [
            {
                "agent_id": interaction.agent_id,
                "timestamp": interaction.timestamp,
                "response_time": interaction.response_time,
                "interaction_type": interaction.interaction_type,
                "target_agent": interaction.target_agent,
                "engagement_score": interaction.engagement_score
            }
            for interaction in interactions
        ]
        
    async def get_coordination_data(self, window_minutes: int = 5) -> List[Dict]:
        """
        Get coordination data suitable for feeding to the CoordinationMonitor.
        
        Args:
            window_minutes: Time window to collect data
            
        Returns:
            List of interaction dictionaries
        """
        interactions = await self.collect_interactions(window_minutes)
        return self.convert_to_monitor_format(interactions)

# Real MCP server integration (for when we have access)
class RealFarcasterMCP:
    """
    Integration with actual Farcaster MCP server.
    This requires kaiblade/farcaster-mcp running locally.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8080"):
        self.mcp_server_url = mcp_server_url
        
    async def get_recent_casts(self, limit: int = 50) -> List[Dict]:
        """Get recent casts from Farcaster MCP server"""
        # This would make actual MCP calls
        # await mcp_call("get_recent_casts", {"limit": limit})
        pass
        
    async def monitor_channel(self, channel: str) -> AsyncGenerator[Dict, None]:
        """Monitor a specific channel for agent activity"""
        # This would set up SSE stream from MCP server
        # async with mcp_stream("channel_activity", {"channel": channel}) as stream:
        #     async for event in stream:
        #         yield event
        pass

# Example usage
if __name__ == "__main__":
    async def test_collector():
        async with FarcasterDataCollector() as collector:
            # Test batch collection
            interactions = await collector.collect_interactions(1)  # 1 minute
            print(f"Collected {len(interactions)} interactions")
            
            # Test data format conversion
            monitor_data = collector.convert_to_monitor_format(interactions)
            print(f"Converted to monitor format: {len(monitor_data)} records")
            
            # Test streaming (just a few iterations)
            print("Testing stream...")
            count = 0
            async for interaction in collector.stream_interactions():
                print(f"Streamed: {interaction.agent_id} -> {interaction.interaction_type}")
                count += 1
                if count >= 3:  # Just test a few
                    break
                    
    asyncio.run(test_collector())