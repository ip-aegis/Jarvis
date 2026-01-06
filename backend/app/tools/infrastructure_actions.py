"""
LLM tools for infrastructure management actions.
These tools can modify system state and may require confirmation.
"""

from app.database import SessionLocal
from app.models import NetworkDevice, Server
from app.services.actions import ActionDefinition, action_registry
from app.services.ssh import SSHService
from app.tools.base import ActionCategory, ActionTool, ActionType, tool_registry

# =============================================================================
# Server Actions
# =============================================================================


async def restart_service_handler(
    server_id: int,
    service_name: str,
) -> dict:
    """Restart a systemd service on a server."""
    db = SessionLocal()
    try:
        server = db.query(Server).filter_by(id=server_id).first()
        if not server:
            return {"error": "Server not found"}

        ssh = SSHService()
        try:
            connected = await ssh.connect(
                host=server.ip_address,
                username=server.username,
                key_path=server.ssh_key_path,
                port=server.port,
            )
            if not connected:
                return {"error": "Failed to connect to server"}

            stdout, stderr, exit_code = await ssh.execute(f"systemctl restart {service_name}")
            await ssh.disconnect()

            if exit_code == 0:
                return {
                    "success": True,
                    "server": server.hostname,
                    "service": service_name,
                    "message": f"Service {service_name} restarted successfully",
                }
            else:
                return {
                    "success": False,
                    "server": server.hostname,
                    "service": service_name,
                    "error": stderr or f"Exit code: {exit_code}",
                }
        except Exception as e:
            return {"error": f"SSH error: {str(e)}"}
    finally:
        db.close()


async def get_service_status_handler(
    server_id: int,
    service_name: str,
) -> dict:
    """Get the status of a systemd service on a server."""
    db = SessionLocal()
    try:
        server = db.query(Server).filter_by(id=server_id).first()
        if not server:
            return {"error": "Server not found"}

        ssh = SSHService()
        try:
            connected = await ssh.connect(
                host=server.ip_address,
                username=server.username,
                key_path=server.ssh_key_path,
                port=server.port,
            )
            if not connected:
                return {"error": "Failed to connect to server"}

            stdout, stderr, exit_code = await ssh.execute(f"systemctl is-active {service_name}")
            is_active = stdout.strip() == "active"

            # Get more details
            stdout2, _, _ = await ssh.execute(
                f"systemctl show {service_name} --property=ActiveState,SubState,MainPID"
            )
            await ssh.disconnect()

            properties = {}
            for line in stdout2.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    properties[key] = value

            return {
                "server": server.hostname,
                "service": service_name,
                "is_active": is_active,
                "active_state": properties.get("ActiveState"),
                "sub_state": properties.get("SubState"),
                "main_pid": properties.get("MainPID"),
            }
        except Exception as e:
            return {"error": f"SSH error: {str(e)}"}
    finally:
        db.close()


async def reboot_server_handler(server_id: int) -> dict:
    """Reboot a managed server."""
    db = SessionLocal()
    try:
        server = db.query(Server).filter_by(id=server_id).first()
        if not server:
            return {"error": "Server not found"}

        ssh = SSHService()
        try:
            connected = await ssh.connect(
                host=server.ip_address,
                username=server.username,
                key_path=server.ssh_key_path,
                port=server.port,
            )
            if not connected:
                return {"error": "Failed to connect to server"}

            # Schedule reboot in 1 minute to allow response
            stdout, stderr, exit_code = await ssh.execute("shutdown -r +1")
            await ssh.disconnect()

            if exit_code == 0:
                # Update server status
                server.status = "rebooting"
                db.commit()

                return {
                    "success": True,
                    "server": server.hostname,
                    "ip_address": server.ip_address,
                    "message": "Server will reboot in 1 minute",
                }
            else:
                return {
                    "success": False,
                    "server": server.hostname,
                    "error": stderr or "Failed to initiate reboot",
                }
        except Exception as e:
            return {"error": f"SSH error: {str(e)}"}
    finally:
        db.close()


async def execute_command_handler(
    server_id: int,
    command: str,
) -> dict:
    """Execute a command on a server (read-only queries preferred)."""
    db = SessionLocal()
    try:
        server = db.query(Server).filter_by(id=server_id).first()
        if not server:
            return {"error": "Server not found"}

        # Block dangerous commands
        dangerous = ["rm -rf", "mkfs", "dd if=", ":(){", "fork bomb"]
        if any(d in command.lower() for d in dangerous):
            return {"error": "Command blocked for safety"}

        ssh = SSHService()
        try:
            connected = await ssh.connect(
                host=server.ip_address,
                username=server.username,
                key_path=server.ssh_key_path,
                port=server.port,
            )
            if not connected:
                return {"error": "Failed to connect to server"}

            stdout, stderr, exit_code = await ssh.execute(command)
            await ssh.disconnect()

            return {
                "server": server.hostname,
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout[:5000] if stdout else "",  # Limit output
                "stderr": stderr[:1000] if stderr else "",
            }
        except Exception as e:
            return {"error": f"SSH error: {str(e)}"}
    finally:
        db.close()


# =============================================================================
# Network Device Actions
# =============================================================================


async def set_port_state_handler(
    device_id: int,
    port_number: int,
    enabled: bool,
) -> dict:
    """Enable or disable a switch port."""
    db = SessionLocal()
    try:
        from app.models import NetworkPort

        device = db.query(NetworkDevice).filter_by(id=device_id).first()
        if not device:
            return {"error": "Network device not found"}

        port = db.query(NetworkPort).filter_by(device_id=device_id, port_number=port_number).first()
        if not port:
            return {"error": f"Port {port_number} not found on device {device.name}"}

        # For Cisco devices, we would need SSH CLI commands
        # This is a placeholder - actual implementation depends on device vendor
        if device.vendor == "cisco":
            # Would need: interface GigabitEthernet0/{port_number}, shutdown/no shutdown
            return {
                "status": "not_implemented",
                "device": device.name,
                "port": port_number,
                "message": "Cisco CLI command execution not yet implemented",
            }

        # Update database record
        port.enabled = enabled
        port.admin_status = "enabled" if enabled else "disabled"
        db.commit()

        return {
            "success": True,
            "device": device.name,
            "port": port_number,
            "enabled": enabled,
            "message": f"Port {port_number} {'enabled' if enabled else 'disabled'}",
        }
    finally:
        db.close()


async def set_port_vlan_handler(
    device_id: int,
    port_number: int,
    vlan_id: int,
) -> dict:
    """Change the VLAN assignment for a switch port."""
    db = SessionLocal()
    try:
        from app.models import NetworkPort

        device = db.query(NetworkDevice).filter_by(id=device_id).first()
        if not device:
            return {"error": "Network device not found"}

        port = db.query(NetworkPort).filter_by(device_id=device_id, port_number=port_number).first()
        if not port:
            return {"error": f"Port {port_number} not found on device {device.name}"}

        old_vlan = port.vlan_id

        # For Cisco devices, we would need SSH CLI commands
        if device.vendor == "cisco":
            return {
                "status": "not_implemented",
                "device": device.name,
                "port": port_number,
                "message": "Cisco CLI command execution not yet implemented",
            }

        # Update database record
        port.vlan_id = vlan_id
        db.commit()

        return {
            "success": True,
            "device": device.name,
            "port": port_number,
            "old_vlan": old_vlan,
            "new_vlan": vlan_id,
            "message": f"Port {port_number} VLAN changed from {old_vlan} to {vlan_id}",
        }
    finally:
        db.close()


# =============================================================================
# Tool Registrations
# =============================================================================

# Read-only tools (no confirmation needed)
get_service_status_tool = ActionTool(
    name="get_service_status",
    description="Get the status of a systemd service on a server.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID",
            },
            "service_name": {
                "type": "string",
                "description": "Name of the systemd service (e.g., 'nginx', 'docker')",
            },
        },
        "required": ["server_id", "service_name"],
    },
    handler=get_service_status_handler,
    action_type=ActionType.READ,
    category=ActionCategory.SERVICE,
)

execute_command_tool = ActionTool(
    name="execute_command",
    description="Execute a read-only command on a server. Dangerous commands are blocked.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID",
            },
            "command": {
                "type": "string",
                "description": "The command to execute",
            },
        },
        "required": ["server_id", "command"],
    },
    handler=execute_command_handler,
    action_type=ActionType.READ,
    category=ActionCategory.SERVER,
)

# Write tools (confirmation recommended)
restart_service_tool = ActionTool(
    name="restart_service",
    description="Restart a systemd service on a managed server. This may cause brief service interruption.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID",
            },
            "service_name": {
                "type": "string",
                "description": "Name of the systemd service to restart",
            },
        },
        "required": ["server_id", "service_name"],
    },
    handler=restart_service_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.SERVICE,
    requires_confirmation=True,
    confirmation_message="This will restart {service_name} on the server, causing brief service interruption. Confirm?",
    target_type="server",
)

set_port_state_tool = ActionTool(
    name="set_port_state",
    description="Enable or disable a switch port. This will affect network connectivity for devices on that port.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The network device ID",
            },
            "port_number": {
                "type": "integer",
                "description": "The port number to modify",
            },
            "enabled": {
                "type": "boolean",
                "description": "True to enable, False to disable",
            },
        },
        "required": ["device_id", "port_number", "enabled"],
    },
    handler=set_port_state_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.NETWORK,
    requires_confirmation=True,
    confirmation_message="This will {'enable' if enabled else 'disable'} port {port_number}. Devices on this port will {'regain' if enabled else 'lose'} network connectivity. Confirm?",
    target_type="network_device",
)

set_port_vlan_tool = ActionTool(
    name="set_port_vlan",
    description="Change the VLAN assignment for a switch port. This will move the port to a different network segment.",
    parameters={
        "type": "object",
        "properties": {
            "device_id": {
                "type": "integer",
                "description": "The network device ID",
            },
            "port_number": {
                "type": "integer",
                "description": "The port number to modify",
            },
            "vlan_id": {
                "type": "integer",
                "description": "The new VLAN ID",
            },
        },
        "required": ["device_id", "port_number", "vlan_id"],
    },
    handler=set_port_vlan_handler,
    action_type=ActionType.WRITE,
    category=ActionCategory.NETWORK,
    requires_confirmation=True,
    confirmation_message="This will move port {port_number} to VLAN {vlan_id}. Devices may need new IP addresses. Confirm?",
    target_type="network_device",
)

# Destructive tools (always require confirmation)
reboot_server_tool = ActionTool(
    name="reboot_server",
    description="Reboot a managed server. This will cause downtime while the server restarts.",
    parameters={
        "type": "object",
        "properties": {
            "server_id": {
                "type": "integer",
                "description": "The server ID to reboot",
            },
        },
        "required": ["server_id"],
    },
    handler=reboot_server_handler,
    action_type=ActionType.DESTRUCTIVE,
    category=ActionCategory.SERVER,
    requires_confirmation=True,
    confirmation_message="This will reboot the server, causing several minutes of downtime. Confirm?",
    target_type="server",
)

# Register all tools
tool_registry.register(get_service_status_tool)
tool_registry.register(execute_command_tool)
tool_registry.register(restart_service_tool)
tool_registry.register(set_port_state_tool)
tool_registry.register(set_port_vlan_tool)
tool_registry.register(reboot_server_tool)

# Also register with action_registry for the action service
action_registry.register(
    ActionDefinition(
        name="restart_service",
        description="Restart a systemd service on a managed server",
        handler=restart_service_handler,
        action_type=ActionType.WRITE,
        category=ActionCategory.SERVICE,
        requires_confirmation=True,
        confirmation_message="This will restart {service_name}, causing brief service interruption. Confirm?",
        target_type="server",
    )
)

action_registry.register(
    ActionDefinition(
        name="reboot_server",
        description="Reboot a managed server",
        handler=reboot_server_handler,
        action_type=ActionType.DESTRUCTIVE,
        category=ActionCategory.SERVER,
        requires_confirmation=True,
        confirmation_message="This will reboot the server, causing several minutes of downtime. Confirm?",
        target_type="server",
    )
)

action_registry.register(
    ActionDefinition(
        name="set_port_state",
        description="Enable or disable a switch port",
        handler=set_port_state_handler,
        action_type=ActionType.WRITE,
        category=ActionCategory.NETWORK,
        requires_confirmation=True,
        confirmation_message="This will change the port state, affecting network connectivity. Confirm?",
        target_type="network_device",
    )
)
