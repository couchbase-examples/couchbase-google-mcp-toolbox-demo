#!/usr/bin/env python3
"""
Script to list machine information with alerts from the last 24 hours.
Displays:
- Machine ID
- Current Status  
- Recent Alerts (last 24 hours) with resolution status
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any, Optional
from .couchbase_client import CouchbaseClient
from src.config.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MachineAlertsReporter:
    """Reporter for machine status and recent alerts."""
    
    def __init__(self):
        self.cb_client = CouchbaseClient()
        
    def fetch_machines_with_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Fetch all machines with their recent alerts using JOIN."""
        try:
            bucket = settings.couchbase_bucket_name
            scope = settings.couchbase_scope_name
            machines_collection = settings.couchbase_collections['machines']
            alerts_collection = settings.couchbase_collections['alerts']
            
            # Calculate cutoff time (N hours ago)
            cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
            cutoff_iso = cutoff_time.isoformat()
            
            query = (
                f"SELECT m.machine_id, m.name, m.current_status, m.production_line_id, m.machine_type, "
                f"ARRAY_AGG({{ "
                f"  'alert_id': a.alert_id, "
                f"  'severity': a.severity, "
                f"  'status': a.status, "
                f"  'error_code': a.error_code, "
                f"  'solution_comment': a.solution_comment, "
                f"  'timestamp': a.timestamp, "
                f"  'acknowledged_by': a.acknowledged_by, "
                f"  'resolved_by': a.resolved_by, "
                f"  'resolution_time': a.resolution_time "
                f"}}) AS alerts "
                f"FROM `{bucket}`.`{scope}`.`{machines_collection}` m "
                f"LEFT JOIN `{bucket}`.`{scope}`.`{alerts_collection}` a "
                f"ON m.machine_id = a.machine_id "
                f"AND a.type = 'alert' "
                f"AND a.timestamp >= '{cutoff_iso}' "
                f"WHERE m.type = 'machine' "
                f"GROUP BY m.machine_id, m.name, m.current_status, m.production_line_id, m.machine_type "
                f"ORDER BY m.machine_id"
            )
            
            result = list(self.cb_client.cluster.query(query))
            logger.info(f"Fetched {len(result)} machines with their alerts using JOIN")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch machines with alerts: {e}")
            return []
    
    def fetch_alert_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Fetch alert statistics using aggregation queries."""
        try:
            bucket = settings.couchbase_bucket_name
            scope = settings.couchbase_scope_name
            alerts_collection = settings.couchbase_collections['alerts']
            
            # Calculate cutoff time (N hours ago)
            cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
            cutoff_iso = cutoff_time.isoformat()
            
            # Query for basic alert statistics
            basic_stats_query = (
                f"SELECT COUNT(*) as total_alerts "
                f"FROM `{bucket}`.`{scope}`.`{alerts_collection}` "
                f"WHERE type = 'alert' AND timestamp >= '{cutoff_iso}'"
            )
            
            # Query for status counts
            status_stats_query = (
                f"SELECT status, COUNT(*) as count "
                f"FROM `{bucket}`.`{scope}`.`{alerts_collection}` "
                f"WHERE type = 'alert' AND timestamp >= '{cutoff_iso}' "
                f"GROUP BY status"
            )
            
            # Query for severity counts  
            severity_stats_query = (
                f"SELECT severity, COUNT(*) as count "
                f"FROM `{bucket}`.`{scope}`.`{alerts_collection}` "
                f"WHERE type = 'alert' AND timestamp >= '{cutoff_iso}' "
                f"GROUP BY severity"
            )
            
            # Execute queries
            basic_result = list(self.cb_client.cluster.query(basic_stats_query))
            status_result = list(self.cb_client.cluster.query(status_stats_query))
            severity_result = list(self.cb_client.cluster.query(severity_stats_query))
            
            # Combine results
            stats = {
                'total_alerts': basic_result[0]['total_alerts'] if basic_result else 0,
                'status_counts': {row['status']: row['count'] for row in status_result},
                'severity_counts': {row['severity']: row['count'] for row in severity_result}
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to fetch alert statistics: {e}")
            return {}
    
    def format_alert_info(self, alert: Dict[str, Any]) -> str:
        """Format alert information for display."""
        alert_id = alert.get('alert_id', 'N/A')[:8]  # Show first 8 chars
        severity = alert.get('severity', 'N/A').upper()
        status = alert.get('status', 'N/A').upper()
        error_code = alert.get('error_code', 'N/A')
        timestamp = alert.get('timestamp', 'N/A')
        
        # Format timestamp
        if timestamp != 'N/A':
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = timestamp
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                timestamp_str = str(timestamp)
        else:
            timestamp_str = 'N/A'
        
        # Resolution info
        resolution_info = ""
        if status == 'RESOLVED':
            resolved_by = alert.get('resolved_by', 'Unknown')
            resolution_time = alert.get('resolution_time')
            if resolution_time:
                try:
                    if isinstance(resolution_time, str):
                        res_dt = datetime.fromisoformat(resolution_time.replace('Z', '+00:00'))
                    else:
                        res_dt = resolution_time
                    res_time_str = res_dt.strftime('%Y-%m-%d %H:%M')
                    resolution_info = f" | Resolved by: {resolved_by} at {res_time_str}"
                except:
                    resolution_info = f" | Resolved by: {resolved_by}"
        elif status == 'ACKNOWLEDGED':
            ack_by = alert.get('acknowledged_by', 'Unknown')
            resolution_info = f" | Acknowledged by: {ack_by}"
        
        return f"    • {alert_id} | {error_code} | {severity} | {status} | {timestamp_str}{resolution_info}"
    
    def generate_report(self, hours: int = 24):
        """Generate and display the machine alerts report."""
        print("\n" + "="*80)
        print(f"MACHINE STATUS & ALERTS REPORT (Last {hours} hours)")
        print("="*80)
        print(f"Report generated at: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print()
        
        # Fetch data using JOIN
        machines_with_alerts = self.fetch_machines_with_alerts(hours)
        alert_stats = self.fetch_alert_statistics(hours)
        
        if not machines_with_alerts:
            print("❌ No machines found in the database.")
            return
        
        # Count total alerts from the result set
        total_alerts = 0
        for machine in machines_with_alerts:
            alerts = machine.get('alerts', [])
            # Filter out None values from alerts array (from LEFT JOIN)
            valid_alerts = [alert for alert in alerts if alert and alert.get('alert_id')]
            total_alerts += len(valid_alerts)
        
        print(f"📊 Found {len(machines_with_alerts)} machines and {total_alerts} alerts from last {hours} hours")
        print("-" * 80)
        
        # Display report for each machine
        for i, machine in enumerate(machines_with_alerts, 1):
            machine_id = machine.get('machine_id', 'N/A')
            name = machine.get('name', 'N/A')
            status = machine.get('current_status', 'N/A').upper()
            line_id = machine.get('production_line_id', 'N/A')
            machine_type = machine.get('machine_type', 'N/A')
            
            # Status emoji
            status_emoji = {
                'OPERATIONAL': '✅',
                'MAINTENANCE': '🔧',
                'WARNING': '⚠️',
                'ERROR': '❌'
            }.get(status, '❓')
            
            print(f"{i:2d}. {status_emoji} {machine_id} | {name}")
            print(f"     Status: {status} | Line: {line_id} | Type: {machine_type}")
            
            # Show alerts for this machine (from JOIN result)
            alerts = machine.get('alerts', [])
            # Filter out None values from alerts array (from LEFT JOIN)
            valid_alerts = [alert for alert in alerts if alert and alert.get('alert_id')]
            
            if valid_alerts:
                print(f"     Recent Alerts ({len(valid_alerts)}):")
                # Sort alerts by timestamp (newest first)
                sorted_alerts = sorted(valid_alerts, key=lambda x: x.get('timestamp', ''), reverse=True)
                for alert in sorted_alerts:
                    print(self.format_alert_info(alert))
            else:
                print("     Recent Alerts: None")
            
            print()
        
        # Summary statistics
        print("-" * 80)
        print("SUMMARY:")
        
        # Count machines by status
        status_counts = {}
        for machine in machines_with_alerts:
            status = machine.get('current_status', 'unknown').upper()
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print("Machine Status Distribution:")
        for status, count in sorted(status_counts.items()):
            emoji = {
                'OPERATIONAL': '✅',
                'MAINTENANCE': '🔧', 
                'WARNING': '⚠️',
                'ERROR': '❌'
            }.get(status, '❓')
            print(f"  {emoji} {status}: {count}")
        
        # Alert statistics from aggregation query
        if alert_stats.get('total_alerts', 0) > 0:
            total_alerts_from_stats = alert_stats.get('total_alerts', 0)
            status_counts = alert_stats.get('status_counts', {})
            severity_counts = alert_stats.get('severity_counts', {})
            
            print(f"\nAlert Status Distribution (Last {hours}h):")
            for status, count in sorted(status_counts.items()):
                status_upper = status.upper()
                emoji = {
                    'ACTIVE': '🔴',
                    'ACKNOWLEDGED': '🟡',
                    'RESOLVED': '✅'
                }.get(status_upper, '❓')
                print(f"  {emoji} {status_upper}: {count}")
            
            print(f"\nAlert Severity Distribution (Last {hours}h):")
            for severity, count in sorted(severity_counts.items()):
                severity_upper = severity.upper()
                emoji = {
                    'LOW': '🟢',
                    'MEDIUM': '🟡',
                    'HIGH': '🟠',
                    'CRITICAL': '🔴'
                }.get(severity_upper, '❓')
                print(f"  {emoji} {severity_upper}: {count}")
        else:
            print(f"\nNo alerts found in the last {hours} hours.")
        
        print("\n" + "="*80)
    
    def close(self):
        """Close database connection."""
        if self.cb_client:
            self.cb_client.close()


def main():
    """Main function to run the report."""
    reporter = None
    try:
        reporter = MachineAlertsReporter()
        
        # Allow user to specify different time ranges
        import sys
        hours = 24
        if len(sys.argv) > 1:
            try:
                hours = int(sys.argv[1])
                if hours <= 0:
                    print("Hours must be a positive integer. Using default 24 hours.")
                    hours = 24
            except ValueError:
                print("Invalid hours argument. Using default 24 hours.")
                hours = 24
        
        reporter.generate_report(hours)
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        print(f"\n❌ Error generating report: {e}")
    finally:
        if reporter:
            reporter.close()


if __name__ == "__main__":
    main() 