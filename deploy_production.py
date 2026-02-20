#!/usr/bin/env python3
"""
Automated deployment script for Farcaster Coordination Monitor
One-command deployment: python deploy_production.py
"""

import os
import sys
import subprocess
import json
import time
import requests
from pathlib import Path

class ProductionDeployer:
    def __init__(self):
        self.base_dir = Path.cwd()
        self.farcaster_mcp_dir = self.base_dir / "farcaster-mcp"
        self.log_file = self.base_dir / "deployment.log"
        
    def log(self, message):
        """Log deployment progress"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(self.log_file, "a") as f:
            f.write(log_entry + "\n")
    
    def run_command(self, command, cwd=None, check=True):
        """Run shell command and log output"""
        self.log(f"Running: {command}")
        try:
            result = subprocess.run(
                command, shell=True, cwd=cwd,
                capture_output=True, text=True, check=check
            )
            if result.stdout:
                self.log(f"STDOUT: {result.stdout.strip()}")
            if result.stderr:
                self.log(f"STDERR: {result.stderr.strip()}")
            return result
        except subprocess.CalledProcessError as e:
            self.log(f"ERROR: Command failed with exit code {e.returncode}")
            self.log(f"STDERR: {e.stderr}")
            return e
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        self.log("Checking dependencies...")
        
        # Check Python
        try:
            python_version = subprocess.check_output([sys.executable, "--version"]).decode().strip()
            self.log(f"Python: {python_version}")
        except Exception as e:
            self.log(f"ERROR: Python not found - {e}")
            return False
        
        # Check Node.js
        try:
            node_version = subprocess.check_output(["node", "--version"]).decode().strip()
            self.log(f"Node.js: {node_version}")
        except Exception as e:
            self.log(f"ERROR: Node.js not found - {e}")
            return False
        
        # Check npm
        try:
            npm_version = subprocess.check_output(["npm", "--version"]).decode().strip()
            self.log(f"npm: {npm_version}")
        except Exception as e:
            self.log(f"ERROR: npm not found - {e}")
            return False
        
        return True
    
    def clone_farcaster_mcp(self):
        """Clone the Farcaster MCP server"""
        if self.farcaster_mcp_dir.exists():
            self.log("Farcaster MCP directory already exists, pulling latest...")
            self.run_command("git pull", cwd=self.farcaster_mcp_dir)
        else:
            self.log("Cloning Farcaster MCP server...")
            self.run_command("git clone https://github.com/manimohans/farcaster-mcp.git farcaster-mcp")
        
        return self.farcaster_mcp_dir.exists()
    
    def install_mcp_dependencies(self):
        """Install MCP server dependencies"""
        self.log("Installing MCP server dependencies...")
        
        # Install npm dependencies
        result = self.run_command("npm install", cwd=self.farcaster_mcp_dir)
        if isinstance(result, subprocess.CalledProcessError):
            return False
        
        # Build the server
        result = self.run_command("npm run build", cwd=self.farcaster_mcp_dir)
        if isinstance(result, subprocess.CalledProcessError):
            return False
        
        return True
    
    def install_python_dependencies(self):
        """Install Python monitoring dependencies"""
        self.log("Installing Python dependencies...")
        
        if not (self.base_dir / "requirements.txt").exists():
            self.log("requirements.txt not found, creating...")
            requirements = """
asyncio
aiohttp
numpy
pandas
scikit-learn
raga-ai-catalyst>=0.1.0
websockets
requests
python-dotenv
matplotlib
seaborn
            """.strip()
            with open("requirements.txt", "w") as f:
                f.write(requirements)
        
        result = self.run_command(f"{sys.executable} -m pip install -r requirements.txt")
        return not isinstance(result, subprocess.CalledProcessError)
    
    def create_environment_file(self):
        """Create environment configuration"""
        env_file = self.base_dir / ".env"
        if env_file.exists():
            self.log(".env file already exists")
            return True
        
        self.log("Creating .env configuration file...")
        env_content = """
# Farcaster Configuration
FARCASTER_API_KEY=your_farcaster_api_key_here

# RagaAI Configuration
RAGA_API_KEY=your_raga_api_key_here
RAGA_PROJECT_ID=coordination-monitor

# Monitoring Configuration
COORDINATION_THRESHOLD_WARNING=0.7
COORDINATION_THRESHOLD_CRITICAL=0.85
CSD_WINDOW_SIZE=50
CSD_VARIANCE_THRESHOLD=2.0
CSD_AUTOCORR_THRESHOLD=0.8

# Server Configuration
MCP_SERVER_PORT=3001
MONITORING_PORT=8000
        """.strip()
        
        with open(env_file, "w") as f:
            f.write(env_content)
        
        self.log("Created .env file - please add your API keys!")
        return True
    
    def start_mcp_server(self):
        """Start the Farcaster MCP server"""
        self.log("Starting Farcaster MCP server...")
        
        # Check if server is already running
        try:
            response = requests.get("http://localhost:3001/health", timeout=5)
            if response.status_code == 200:
                self.log("MCP server already running")
                return True
        except:
            pass
        
        # Start the server in background
        self.run_command("npm start > mcp_server.log 2>&1 &", cwd=self.farcaster_mcp_dir, check=False)
        
        # Wait for server to be ready
        for i in range(10):
            time.sleep(2)
            try:
                response = requests.get("http://localhost:3001/health", timeout=5)
                if response.status_code == 200:
                    self.log("MCP server started successfully")
                    return True
            except:
                continue
        
        self.log("WARNING: MCP server may not have started properly")
        return False
    
    def start_monitoring_system(self):
        """Start the coordination monitoring system"""
        self.log("Starting coordination monitoring system...")
        
        # Start the main monitoring process
        monitoring_script = "mcp_production_bridge.py"
        if not (self.base_dir / monitoring_script).exists():
            self.log(f"ERROR: {monitoring_script} not found")
            return False
        
        self.run_command(f"{sys.executable} {monitoring_script} > monitoring.log 2>&1 &", check=False)
        self.log("Monitoring system started in background")
        return True
    
    def health_check(self):
        """Perform system health checks"""
        self.log("Performing health checks...")
        
        checks = []
        
        # Check MCP server
        try:
            response = requests.get("http://localhost:3001/health", timeout=5)
            checks.append(("MCP Server", response.status_code == 200))
        except:
            checks.append(("MCP Server", False))
        
        # Check monitoring system (look for process)
        try:
            result = subprocess.check_output(["pgrep", "-f", "mcp_production_bridge.py"])
            checks.append(("Monitoring System", len(result.strip()) > 0))
        except:
            checks.append(("Monitoring System", False))
        
        # Log results
        all_healthy = True
        for name, status in checks:
            status_str = "✅ HEALTHY" if status else "❌ UNHEALTHY"
            self.log(f"{name}: {status_str}")
            if not status:
                all_healthy = False
        
        return all_healthy
    
    def deploy(self):
        """Main deployment process"""
        self.log("=" * 50)
        self.log("STARTING PRODUCTION DEPLOYMENT")
        self.log("=" * 50)
        
        steps = [
            ("Checking dependencies", self.check_dependencies),
            ("Cloning Farcaster MCP server", self.clone_farcaster_mcp),
            ("Installing MCP dependencies", self.install_mcp_dependencies),
            ("Installing Python dependencies", self.install_python_dependencies),
            ("Creating environment configuration", self.create_environment_file),
            ("Starting MCP server", self.start_mcp_server),
            ("Starting monitoring system", self.start_monitoring_system),
            ("Health check", self.health_check)
        ]
        
        for step_name, step_func in steps:
            self.log(f"\n--- {step_name} ---")
            success = step_func()
            if not success:
                self.log(f"❌ DEPLOYMENT FAILED at step: {step_name}")
                return False
            self.log(f"✅ {step_name} completed")
        
        self.log("\n" + "=" * 50)
        self.log("🚀 DEPLOYMENT SUCCESSFUL!")
        self.log("=" * 50)
        self.log("\nNext steps:")
        self.log("1. Add your API keys to .env file")
        self.log("2. Monitor logs: tail -f deployment.log")
        self.log("3. Check MCP server: curl http://localhost:3001/health")
        self.log("4. Monitor coordination data in real-time")
        
        return True

if __name__ == "__main__":
    deployer = ProductionDeployer()
    success = deployer.deploy()
    sys.exit(0 if success else 1)