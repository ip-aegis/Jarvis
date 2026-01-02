import paramiko
import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.config import get_settings

settings = get_settings()


class SSHService:
    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None
        self.host: Optional[str] = None
        self.username: Optional[str] = None
        self.key_path: Optional[str] = None  # Path to the private key after exchange
        self.keys_path = Path(settings.ssh_keys_path)
        self.keys_path.mkdir(parents=True, exist_ok=True)

    async def connect(
        self,
        host: str,
        username: str,
        password: Optional[str] = None,
        key_path: Optional[str] = None,
        port: int = 22,
    ) -> bool:
        """Connect to a remote server via SSH."""
        self.host = host
        self.username = username

        def _connect():
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            if key_path and os.path.exists(key_path):
                key = paramiko.RSAKey.from_private_key_file(key_path)
                self.client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    pkey=key,
                )
            elif password:
                self.client.connect(
                    hostname=host,
                    port=port,
                    username=username,
                    password=password,
                )
            else:
                # Try default key
                default_key = self.keys_path / f"{host}_{username}_id_rsa"
                if default_key.exists():
                    key = paramiko.RSAKey.from_private_key_file(str(default_key))
                    self.client.connect(
                        hostname=host,
                        port=port,
                        username=username,
                        pkey=key,
                    )
                else:
                    raise ValueError("No password or key provided")

            return True

        return await asyncio.get_event_loop().run_in_executor(None, _connect)

    async def disconnect(self):
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            self.client = None

    async def execute(self, command: str) -> tuple[str, str, int]:
        """Execute a command on the remote server."""
        if not self.client:
            raise RuntimeError("Not connected")

        def _execute():
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            return stdout.read().decode(), stderr.read().decode(), exit_code

        return await asyncio.get_event_loop().run_in_executor(None, _execute)

    async def exchange_keys(self, host: str, username: str) -> bool:
        """
        Generate SSH key pair and install public key on remote server.
        Returns True if successful.
        """
        if not self.client:
            raise RuntimeError("Not connected")

        # Generate key pair
        private_key_path = self.keys_path / f"{host}_{username}_id_rsa"
        public_key_path = self.keys_path / f"{host}_{username}_id_rsa.pub"

        def _generate_keys():
            # Generate RSA key
            key = rsa.generate_private_key(
                backend=default_backend(),
                public_exponent=65537,
                key_size=4096,
            )

            # Save private key
            private_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(private_key_path, "wb") as f:
                f.write(private_pem)
            os.chmod(private_key_path, 0o600)

            # Generate public key in OpenSSH format
            public_key = key.public_key()
            public_ssh = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH,
            )
            with open(public_key_path, "wb") as f:
                f.write(public_ssh)

            return public_ssh.decode()

        public_key = await asyncio.get_event_loop().run_in_executor(None, _generate_keys)

        # Install public key on remote server
        commands = [
            "mkdir -p ~/.ssh",
            "chmod 700 ~/.ssh",
            f'echo "{public_key} jarvis@jarvis-server" >> ~/.ssh/authorized_keys',
            "chmod 600 ~/.ssh/authorized_keys",
        ]

        for cmd in commands:
            stdout, stderr, exit_code = await self.execute(cmd)
            if exit_code != 0:
                return False

        # Store the key path for later use
        self.key_path = str(private_key_path)
        return True

    async def get_system_info(self) -> Dict[str, Any]:
        """Gather system information from the remote server."""
        if not self.client:
            raise RuntimeError("Not connected")

        info = {}

        # OS Info
        stdout, _, _ = await self.execute("cat /etc/os-release 2>/dev/null || uname -a")
        info["os"] = stdout.strip()

        # CPU Info
        stdout, _, _ = await self.execute("lscpu | grep 'Model name' | head -1")
        info["cpu"] = stdout.strip().replace("Model name:", "").strip() if stdout else "Unknown"

        stdout, _, _ = await self.execute("nproc")
        info["cpu_cores"] = int(stdout.strip()) if stdout.strip().isdigit() else 0

        # Memory
        stdout, _, _ = await self.execute("free -h | grep Mem")
        if stdout:
            parts = stdout.split()
            info["memory_total"] = parts[1] if len(parts) > 1 else "Unknown"

        # Disk
        stdout, _, _ = await self.execute("df -h / | tail -1")
        if stdout:
            parts = stdout.split()
            info["disk_total"] = parts[1] if len(parts) > 1 else "Unknown"
            info["disk_used"] = parts[2] if len(parts) > 2 else "Unknown"

        # GPU (NVIDIA)
        stdout, stderr, exit_code = await self.execute(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null"
        )
        if exit_code == 0 and stdout.strip():
            info["gpu"] = stdout.strip()
        else:
            info["gpu"] = None

        # Hostname
        stdout, _, _ = await self.execute("hostname")
        info["hostname"] = stdout.strip()

        return info

    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to the remote server."""
        if not self.client:
            raise RuntimeError("Not connected")

        def _upload():
            sftp = self.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True

        return await asyncio.get_event_loop().run_in_executor(None, _upload)

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote server."""
        if not self.client:
            raise RuntimeError("Not connected")

        def _download():
            sftp = self.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return True

        return await asyncio.get_event_loop().run_in_executor(None, _download)
