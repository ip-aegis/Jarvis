# Tool registry and tool definitions
from app.tools.base import ActionCategory, ActionTool, ActionType, Tool, ToolRegistry, tool_registry
from app.tools.dns_analytics_tools import (
    acknowledge_dns_alert_tool,
    analyze_dns_threat_tool,
    block_domain_with_alert_tool,
    compare_to_baseline_tool,
    get_client_dns_behavior_tool,
    get_dns_security_alerts_tool,
    get_domain_reputation_tool,
    investigate_client_tool,
    investigate_domain_tool,
    mark_dns_false_positive_tool,
)
from app.tools.dns_tools import (
    allow_domain_tool,
    block_domain_tool,
    detect_dns_anomalies_tool,
    get_dns_client_stats_tool,
    get_dns_stats_tool,
    get_dns_top_blocked_tool,
    get_dns_top_queries_tool,
    get_threat_summary_tool,
    list_blocklists_tool,
    list_custom_rules_tool,
    lookup_domain_tool,
    search_query_log_tool,
)
from app.tools.home_tools import (
    control_media_tool,
    get_appliance_status_tool,
    get_home_device_status_tool,
    get_home_events_tool,
    get_now_playing_tool,
    get_thermostat_status_tool,
    list_home_devices_tool,
    ring_snapshot_tool,
    set_thermostat_tool,
    start_appliance_tool,
    stop_appliance_tool,
)
from app.tools.infrastructure_actions import (
    execute_command_tool,
    get_service_status_tool,
    reboot_server_tool,
    restart_service_tool,
    set_port_state_tool,
    set_port_vlan_tool,
)
from app.tools.journal_tools import (
    get_entries_by_mood_tool,
    get_journal_stats_tool,
    get_recent_entries_tool,
    register_journal_tools,
    search_journal_tool,
)
from app.tools.network_tools import (
    get_network_device_history_tool,
    get_network_device_metrics_tool,
    get_network_topology_tool,
    get_port_status_tool,
    list_network_devices_tool,
)
from app.tools.project_tools import (
    get_project_details_tool,
    list_projects_tool,
    search_projects_tool,
)
from app.tools.server_tools import (
    get_metric_history_tool,
    get_server_metrics_tool,
    list_servers_tool,
)

# Import tools to trigger registration
from app.tools.web_search import web_search_tool
from app.tools.work_tools import (
    add_work_note_tool,
    create_account_tool,
    get_account_context_tool,
    get_recent_activity_tool,
    get_user_profile_tool,
    list_accounts_tool,
    register_work_tools,
    search_accounts_tool,
    search_work_notes_tool,
    update_account_tool,
    update_user_profile_tool,
)

# Register journal tools
register_journal_tools()

# Register work tools
register_work_tools()

# Note: register_infrastructure_actions() is called from main.py startup
# to avoid circular import issues

# Export for easy access
__all__ = [
    "Tool",
    "ActionTool",
    "ActionType",
    "ActionCategory",
    "ToolRegistry",
    "tool_registry",
    "web_search_tool",
    "list_servers_tool",
    "get_server_metrics_tool",
    "get_metric_history_tool",
    "list_projects_tool",
    "get_project_details_tool",
    "search_projects_tool",
    "list_network_devices_tool",
    "get_network_device_metrics_tool",
    "get_port_status_tool",
    "get_network_topology_tool",
    "get_network_device_history_tool",
    "get_service_status_tool",
    "execute_command_tool",
    "restart_service_tool",
    "set_port_state_tool",
    "set_port_vlan_tool",
    "reboot_server_tool",
    # Home automation tools
    "list_home_devices_tool",
    "get_home_device_status_tool",
    "get_home_events_tool",
    "get_thermostat_status_tool",
    "get_now_playing_tool",
    "get_appliance_status_tool",
    "set_thermostat_tool",
    "control_media_tool",
    "start_appliance_tool",
    "stop_appliance_tool",
    "ring_snapshot_tool",
    # Journal tools
    "search_journal_tool",
    "get_recent_entries_tool",
    "get_journal_stats_tool",
    "get_entries_by_mood_tool",
    # Work tools
    "search_accounts_tool",
    "get_account_context_tool",
    "add_work_note_tool",
    "create_account_tool",
    "search_work_notes_tool",
    "list_accounts_tool",
    "update_account_tool",
    "get_recent_activity_tool",
    "update_user_profile_tool",
    "get_user_profile_tool",
    # DNS tools
    "get_dns_stats_tool",
    "get_dns_top_blocked_tool",
    "get_dns_top_queries_tool",
    "lookup_domain_tool",
    "search_query_log_tool",
    "get_dns_client_stats_tool",
    "get_threat_summary_tool",
    "list_blocklists_tool",
    "list_custom_rules_tool",
    "block_domain_tool",
    "allow_domain_tool",
    "detect_dns_anomalies_tool",
    # DNS analytics tools
    "get_client_dns_behavior_tool",
    "get_domain_reputation_tool",
    "get_dns_security_alerts_tool",
    "analyze_dns_threat_tool",
    "investigate_domain_tool",
    "investigate_client_tool",
    "compare_to_baseline_tool",
    "acknowledge_dns_alert_tool",
    "mark_dns_false_positive_tool",
    "block_domain_with_alert_tool",
]
