from app.core.logging import get_logger
from app.services.ssh import SSHService

logger = get_logger(__name__)


class AgentService:
    """Service for installing and managing remote monitoring agents."""

    AGENT_SCRIPT = '''#!/usr/bin/env python3
"""Jarvis Monitoring Agent - Lightweight metrics collector."""

import json
import time
import socket
import subprocess
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone

# SSL context for self-signed certificates
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Configuration
JARVIS_URL = "{jarvis_url}"
REPORT_INTERVAL = {report_interval}  # seconds
SERVER_ID = "{server_id}"


def get_cpu_usage():
    """Get overall CPU usage percentage."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        idle = int(parts[4])
        total = sum(int(p) for p in parts[1:])
        return round((1 - idle / total) * 100, 2)
    except:
        return 0


def get_cpu_per_core():
    """Get per-core CPU usage percentages."""
    try:
        cores = {{}}
        with open("/proc/stat") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("cpu") and not line.startswith("cpu "):
                parts = line.split()
                core_name = parts[0]
                values = [int(p) for p in parts[1:]]
                idle = values[3] if len(values) > 3 else 0
                total = sum(values)
                usage = round((1 - idle / total) * 100, 2) if total else 0
                cores[core_name] = usage
        return cores
    except:
        return {{}}


def get_memory_info():
    """Get memory usage information with extended details."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {{}}
        for line in lines:
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        buffers = mem.get("Buffers", 0)
        cached = mem.get("Cached", 0)
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        used = total - available
        return {{
            "total": total * 1024,
            "used": used * 1024,
            "available": available * 1024,
            "buffers": buffers * 1024,
            "cached": cached * 1024,
            "percent": round(used / total * 100, 2) if total else 0,
            "swap_total": swap_total * 1024,
            "swap_used": (swap_total - swap_free) * 1024,
        }}
    except:
        return {{"total": 0, "used": 0, "available": 0, "buffers": 0, "cached": 0, "percent": 0, "swap_total": 0, "swap_used": 0}}


def get_load_avg():
    """Get system load averages."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.readline().split()
        return {{
            "1m": float(parts[0]),
            "5m": float(parts[1]),
            "15m": float(parts[2]),
        }}
    except:
        return {{"1m": 0, "5m": 0, "15m": 0}}


def get_disk_info():
    """Get disk usage for root partition."""
    try:
        result = subprocess.run(
            ["df", "-B1", "/"],
            capture_output=True,
            text=True,
        )
        lines = result.stdout.strip().split("\\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            total = int(parts[1])
            used = int(parts[2])
            return {{
                "total": total,
                "used": used,
                "percent": round(used / total * 100, 2) if total else 0,
            }}
    except:
        pass
    return {{"total": 0, "used": 0, "percent": 0}}


def get_gpu_info():
    """Get NVIDIA GPU information if available."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            mem_used = int(parts[1])
            mem_total = int(parts[2])
            return {{
                "utilization": float(parts[0]),
                "memory_used": mem_used * 1024 * 1024,
                "memory_total": mem_total * 1024 * 1024,
                "memory_percent": round(mem_used / mem_total * 100, 2) if mem_total else 0,
                "temperature": float(parts[3]),
                "power": float(parts[4]) if len(parts) > 4 and parts[4].strip() != "[N/A]" else None,
            }}
    except:
        pass
    return None


def get_temperatures():
    """Get system temperatures."""
    temps = {{}}
    try:
        # Try hwmon
        import glob
        for path in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
            try:
                with open(path) as f:
                    temp = int(f.read().strip()) / 1000
                name_path = path.replace("_input", "_label")
                if os.path.exists(name_path):
                    with open(name_path) as f:
                        name = f.read().strip()
                else:
                    name = os.path.basename(os.path.dirname(path))
                temps[name] = temp
            except:
                pass
    except:
        pass
    return temps


def collect_metrics():
    """Collect all system metrics."""
    return {{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_id": SERVER_ID,
        "hostname": socket.gethostname(),
        "cpu": {{"usage": get_cpu_usage(), "per_core": get_cpu_per_core()}},
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "gpu": get_gpu_info(),
        "load_avg": get_load_avg(),
        "temperatures": get_temperatures(),
    }}


def send_report(metrics):
    """Send metrics to Jarvis server."""
    try:
        data = json.dumps(metrics).encode()
        req = urllib.request.Request(
            f"{{JARVIS_URL}}/api/monitoring/agent/report",
            data=data,
            headers={{"Content-Type": "application/json"}},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5, context=SSL_CONTEXT)
        return True
    except urllib.error.URLError as e:
        print(f"Failed to send report: {{e}}")
        return False


def main():
    """Main loop."""
    print(f"Jarvis Agent started. Reporting to {{JARVIS_URL}}")
    while True:
        try:
            metrics = collect_metrics()
            send_report(metrics)
        except Exception as e:
            print(f"Error: {{e}}")
        time.sleep(REPORT_INTERVAL)


if __name__ == "__main__":
    import os
    main()
'''

    SYSTEMD_SERVICE = """[Unit]
Description=Jarvis Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/jarvis/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    async def install(
        self,
        ssh_service: SSHService,
        server_id: int,
        jarvis_url: str = "https://10.10.20.235",
        report_interval: int = 5,
    ) -> bool:
        """Install the monitoring agent on a remote server."""

        # Create agent directory (requires sudo)
        stdout, stderr, exit_code = await ssh_service.execute("sudo mkdir -p /opt/jarvis")
        if exit_code != 0:
            logger.error("agent_directory_creation_failed", stderr=stderr)
            return False

        # Generate agent script with configuration
        agent_script = self.AGENT_SCRIPT.format(
            jarvis_url=jarvis_url,
            server_id=str(server_id),
            report_interval=report_interval,
        )

        # Write agent script using echo with base64 to avoid heredoc issues
        import base64

        encoded_script = base64.b64encode(agent_script.encode()).decode()

        write_cmd = (
            f"echo '{encoded_script}' | base64 -d | sudo tee /opt/jarvis/agent.py > /dev/null"
        )
        stdout, stderr, exit_code = await ssh_service.execute(write_cmd)
        if exit_code != 0:
            logger.error("agent_script_write_failed", stderr=stderr)
            return False

        # Make executable
        await ssh_service.execute("sudo chmod +x /opt/jarvis/agent.py")

        # Write systemd service using base64
        encoded_service = base64.b64encode(self.SYSTEMD_SERVICE.encode()).decode()
        service_cmd = f"echo '{encoded_service}' | base64 -d | sudo tee /etc/systemd/system/jarvis-agent.service > /dev/null"
        await ssh_service.execute(service_cmd)

        # Enable and start service
        await ssh_service.execute("sudo systemctl daemon-reload")
        await ssh_service.execute("sudo systemctl enable jarvis-agent")
        stdout, stderr, exit_code = await ssh_service.execute("sudo systemctl restart jarvis-agent")

        # Give it a moment to start
        import asyncio

        await asyncio.sleep(2)

        # Verify it's running
        stdout, _, exit_code = await ssh_service.execute("sudo systemctl is-active jarvis-agent")
        is_active = stdout.strip() == "active"

        if not is_active:
            # Get error details
            stdout, _, _ = await ssh_service.execute(
                "sudo journalctl -u jarvis-agent -n 10 --no-pager"
            )
            logger.warning("agent_not_active", journal_output=stdout)

        return is_active

    async def uninstall(self, ssh_service: SSHService) -> bool:
        """Remove the monitoring agent from a remote server."""
        commands = [
            "sudo systemctl stop jarvis-agent",
            "sudo systemctl disable jarvis-agent",
            "sudo rm -f /etc/systemd/system/jarvis-agent.service",
            "sudo systemctl daemon-reload",
            "sudo rm -rf /opt/jarvis",
        ]

        for cmd in commands:
            await ssh_service.execute(cmd)

        return True

    async def check_status(self, ssh_service: SSHService) -> dict:
        """Check the status of the monitoring agent."""
        stdout, _, exit_code = await ssh_service.execute("sudo systemctl is-active jarvis-agent")
        is_active = stdout.strip() == "active"

        stdout, _, _ = await ssh_service.execute("sudo systemctl status jarvis-agent --no-pager")
        status_output = stdout

        return {
            "installed": exit_code == 0 or "could not be found" not in stdout,
            "active": is_active,
            "status": status_output,
        }
