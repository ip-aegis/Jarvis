#!/usr/bin/env python3
"""
Jarvis Monitoring Agent - Lightweight metrics collector.

This agent is automatically installed on monitored servers and reports
metrics back to the Jarvis server.
"""

import json
import time
import socket
import subprocess
import urllib.request
import urllib.error
import os
import glob
from datetime import datetime

# Configuration - these are replaced during installation
JARVIS_URL = os.environ.get("JARVIS_URL", "http://10.10.20.235:8000")
REPORT_INTERVAL = int(os.environ.get("REPORT_INTERVAL", "5"))
SERVER_ID = os.environ.get("SERVER_ID", socket.gethostname())


def get_cpu_usage():
    """Get CPU usage percentage."""
    try:
        # Read /proc/stat twice with a small delay
        def read_stat():
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            return [int(p) for p in parts[1:8]]

        stat1 = read_stat()
        time.sleep(0.1)
        stat2 = read_stat()

        delta = [s2 - s1 for s1, s2 in zip(stat1, stat2)]
        idle = delta[3]
        total = sum(delta)

        if total == 0:
            return 0

        return round((1 - idle / total) * 100, 2)
    except Exception as e:
        print(f"CPU error: {e}")
        return 0


def get_memory_info():
    """Get memory usage information."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()

        mem = {}
        for line in lines:
            parts = line.split()
            mem[parts[0].rstrip(":")] = int(parts[1])

        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        used = total - available

        return {
            "total": total * 1024,
            "used": used * 1024,
            "percent": round(used / total * 100, 2) if total else 0,
        }
    except Exception as e:
        print(f"Memory error: {e}")
        return {"total": 0, "used": 0, "percent": 0}


def get_disk_info():
    """Get disk usage for root partition."""
    try:
        result = subprocess.run(
            ["df", "-B1", "/"],
            capture_output=True,
            text=True,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            total = int(parts[1])
            used = int(parts[2])
            return {
                "total": total,
                "used": used,
                "percent": round(used / total * 100, 2) if total else 0,
            }
    except Exception as e:
        print(f"Disk error: {e}")
    return {"total": 0, "used": 0, "percent": 0}


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
            return {
                "utilization": float(parts[0]),
                "memory_used": int(parts[1]) * 1024 * 1024,
                "memory_total": int(parts[2]) * 1024 * 1024,
                "temperature": float(parts[3]),
                "power": float(parts[4]) if len(parts) > 4 and parts[4] != "[N/A]" else None,
            }
    except FileNotFoundError:
        pass  # nvidia-smi not available
    except Exception as e:
        print(f"GPU error: {e}")
    return None


def get_temperatures():
    """Get system temperatures from hwmon."""
    temps = {}
    try:
        for path in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
            try:
                with open(path) as f:
                    temp = int(f.read().strip()) / 1000

                # Try to get label
                name_path = path.replace("_input", "_label")
                if os.path.exists(name_path):
                    with open(name_path) as f:
                        name = f.read().strip()
                else:
                    name = os.path.basename(os.path.dirname(path))

                temps[name] = temp
            except Exception:
                pass
    except Exception as e:
        print(f"Temperature error: {e}")
    return temps


def get_network_info():
    """Get network interface statistics."""
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]  # Skip headers

        interfaces = {}
        for line in lines:
            parts = line.split()
            iface = parts[0].rstrip(":")
            if iface != "lo":
                interfaces[iface] = {
                    "rx_bytes": int(parts[1]),
                    "tx_bytes": int(parts[9]),
                }
        return interfaces
    except Exception as e:
        print(f"Network error: {e}")
    return {}


def collect_metrics():
    """Collect all system metrics."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "server_id": SERVER_ID,
        "hostname": socket.gethostname(),
        "cpu": {"usage": get_cpu_usage()},
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "gpu": get_gpu_info(),
        "temperatures": get_temperatures(),
        "network": get_network_info(),
    }


def send_report(metrics):
    """Send metrics to Jarvis server."""
    try:
        data = json.dumps(metrics).encode()
        req = urllib.request.Request(
            f"{JARVIS_URL}/api/monitoring/agent/report",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except urllib.error.URLError as e:
        print(f"Failed to send report: {e}")
        return False
    except Exception as e:
        print(f"Error sending report: {e}")
        return False


def main():
    """Main loop."""
    print(f"Jarvis Agent started")
    print(f"  Server ID: {SERVER_ID}")
    print(f"  Reporting to: {JARVIS_URL}")
    print(f"  Interval: {REPORT_INTERVAL}s")
    print()

    while True:
        try:
            metrics = collect_metrics()
            success = send_report(metrics)
            if success:
                print(f"[{datetime.now().isoformat()}] Report sent - CPU: {metrics['cpu']['usage']}%")
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(REPORT_INTERVAL)


if __name__ == "__main__":
    main()
