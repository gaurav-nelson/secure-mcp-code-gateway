"""
Log Store API - Approved Tool for Log Analysis MCP Server

This module provides safe, efficient log searching capabilities that run
LOCALLY in the sandbox. Large log files are processed in the container,
and only the filtered results are returned to the LLM.

This solves the "context rot" problem by avoiding sending 500MB+ log files
as intermediate results to the LLM.

Security: This file is managed via GitOps. Changes require security approval
via pull request.
"""

import os
import re
from typing import List, Optional


def search_logs(
    service_name: str,
    keyword: str,
    limit: int = 100,
    log_level: Optional[str] = None
) -> List[str]:
    """
    Searches log files for a specific service and keyword.
    
    Runs LOCALLY in the sandbox. Does NOT send 500MB to the LLM.
    Only the final, filtered results are returned.
    
    Args:
        service_name: Name of the service to search logs for (e.g., "payment-service")
        keyword: Keyword or regex pattern to search for
        limit: Maximum number of results to return (default: 100)
        log_level: Optional filter for log level (ERROR, WARN, INFO, DEBUG)
    
    Returns:
        List of matching log lines
    
    Example:
        >>> errors = search_logs("payment-service", "HTTP 500", limit=10)
        >>> print(f"Found {len(errors)} errors")
    """
    # In a real pattern, this would mount a PVC with actual logs
    # For this example, we use mock data to demonstrate the concept
    
    mock_logs = f"""
[2024-01-15 10:23:45] [INFO] Service '{service_name}' started successfully
[2024-01-15 10:24:12] [INFO] User 'alex@company.com' authenticated
[2024-01-15 10:25:33] [ERROR] Transaction tx-123 failed: Connection timed out
[2024-01-15 10:26:01] [INFO] User 'bob@company.com' authenticated
[2024-01-15 10:27:15] [ERROR] Transaction tx-124 failed: Insufficient funds
[2024-01-15 10:28:42] [WARN] High memory usage detected: 85%
[2024-01-15 10:29:03] [ERROR] Transaction tx-125 failed: NullPointerException
[2024-01-15 10:30:21] [INFO] Database connection pool refreshed
[2024-01-15 10:31:45] [ERROR] API request failed: HTTP 500 Internal Server Error
[2024-01-15 10:32:10] [INFO] Cache cleared successfully
[2024-01-15 10:33:28] [ERROR] Failed to process message: Timeout after 30s
[2024-01-15 10:34:52] [WARN] Retry attempt 3/3 for operation op-456
[2024-01-15 10:35:16] [ERROR] Database query failed: Connection refused
[2024-01-15 10:36:39] [INFO] Health check passed
[2024-01-15 10:37:55] [ERROR] Payment processing failed: Gateway unreachable
"""
    
    results = []
    
    # In a real implementation, you would read from a file:
    # log_path = f"/data/logs/{service_name}.log"
    # if not os.path.exists(log_path):
    #     return [f"No log file found for service '{service_name}'"]
    # 
    # with open(log_path, 'r') as f:
    #     for line in f:
    
    for line in mock_logs.splitlines():
        if not line.strip():
            continue
        
        # Filter by log level if specified
        if log_level:
            if f"[{log_level.upper()}]" not in line:
                continue
        
        # Search for keyword (case-insensitive)
        if keyword.lower() in line.lower():
            results.append(line.strip())
            
            if len(results) >= limit:
                break
    
    if not results:
        return [f"No logs found for service '{service_name}' matching '{keyword}'"]
    
    return results


def get_error_summary(service_name: str, hours: int = 24) -> dict:
    """
    Returns a summary of errors for a service over the last N hours.
    
    This demonstrates efficient aggregation: the sandbox processes all logs
    and returns only the summary statistics, not the raw data.
    
    Args:
        service_name: Name of the service
        hours: Number of hours to look back (default: 24)
    
    Returns:
        Dictionary with error counts by type
    
    Example:
        >>> summary = get_error_summary("payment-service")
        >>> print(f"Total errors: {summary['total_errors']}")
    """
    # In a real implementation, this would analyze actual log files
    # For now, return mock statistics
    
    return {
        "service": service_name,
        "time_range_hours": hours,
        "total_errors": 42,
        "errors_by_type": {
            "Connection timeout": 15,
            "HTTP 500": 12,
            "NullPointerException": 8,
            "Database connection refused": 7
        },
        "most_frequent_error": "Connection timeout",
        "error_rate_per_hour": 1.75
    }


def tail_logs(service_name: str, lines: int = 50) -> List[str]:
    """
    Returns the last N lines from a service's log file.
    
    Args:
        service_name: Name of the service
        lines: Number of lines to return (default: 50)
    
    Returns:
        List of the most recent log lines
    """
    # Mock implementation - in production, use actual log tailing
    mock_recent_logs = [
        f"[2024-01-15 10:4{i}:00] [INFO] Service '{service_name}' heartbeat"
        for i in range(min(lines, 10))
    ]
    
    return mock_recent_logs


# Example usage (for testing)
if __name__ == "__main__":
    print("=== Log Store API Demo ===")
    print()
    
    print("1. Search for errors:")
    errors = search_logs("payment-service", "ERROR", limit=5)
    for log in errors:
        print(f"  {log}")
    print()
    
    print("2. Get error summary:")
    summary = get_error_summary("payment-service")
    print(f"  Total errors: {summary['total_errors']}")
    print(f"  Most frequent: {summary['most_frequent_error']}")
    print()
    
    print("3. Filter by log level:")
    warnings = search_logs("payment-service", "", limit=5, log_level="WARN")
    for log in warnings:
        print(f"  {log}")

