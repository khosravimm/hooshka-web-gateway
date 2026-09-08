#!/usr/bin/env python3
"""
Web LLM Bridge - CLI Management Tool

Usage:
    python manage.py <command> [options]

Commands:
    service     - Manage Windows service (install, start, stop, restart, status, logs)
    providers   - List/manage providers
    sessions    - List/manage conversation sessions
    logs        - View logs
    config      - View/edit configuration
    test        - Test provider health
    stats       - Show statistics
"""

import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.provider_registry import provider_registry
from core.mcp import mcp_session_manager
from core.config import load_config
import psutil


class ServiceManager:
    def __init__(self, service_name="WebLLMBridge"):
        self.service_name = service_name
    
    def _run_ps(self, script):
        result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", script], 
                                capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    
    def install(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" install
        """
        return self._run_ps(script)
    
    def uninstall(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" uninstall
        """
        return self._run_ps(script)
    
    def start(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" start
        """
        return self._run_ps(script)
    
    def stop(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" stop
        """
        return self._run_ps(script)
    
    def restart(self):
        self.stop()
        time.sleep(2)
        return self.start()
    
    def status(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" status
        """
        return self._run_ps(script)
    
    def logs(self):
        script = f"""
        . "{Path(__file__).parent}/service_manager.ps1" logs
        """
        return self._run_ps(script)


class ProviderManager:
    def __init__(self):
        self.config = load_config()
    
    def list_providers(self):
        providers = provider_registry.list_providers(enabled_only=False)
        for p in providers:
            caps = []
            if p.capabilities.chat_completion: caps.append("chat")
            if p.capabilities.streaming: caps.append("stream")
            if p.capabilities.tools: caps.append("tools")
            if p.capabilities.vision: caps.append("vision")
            
            status = "●" if p.config.enabled else "○"
            color = "\033[92m" if p.config.enabled else "\033[91m"
            reset = "\033[0m"
            
            print(f"  {color}{status} {p.provider_id:<20} {p.provider_type.value:<15} Prio:{p.config.priority:<3} [{','.join(caps)}] {reset}")
            if p.capabilities.supported_models:
                print(f"      Models: {', '.join(p.capabilities.supported_models)}")
    
    def test_provider(self, provider_id):
        provider = provider_registry.get(provider_id)
        if not provider:
            print(f"Provider '{provider_id}' not found")
            return False
        
        import asyncio
        try:
            health = asyncio.run(provider.health_check())
            status = "HEALTHY" if health else "UNHEALTHY"
            print(f"Provider {provider_id}: {status}")
            return health
        except Exception as e:
            print(f"Provider {provider_id}: ERROR - {e}")
            return False


class SessionManager:
    def list_sessions(self):
        sessions = mcp_session_manager.list_sessions()
        if not sessions:
            print("  No active sessions")
            return
        
        print(f"  {'Conversation ID':<32} {'Provider':<20} {'Msgs':<5} {'Created':<20} {'Updated':<20}")
        print("  " + "-" * 100)
        for s in sessions:
            created = datetime.fromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M:%S')
            updated = datetime.fromtimestamp(s['updated_at']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  {s['conversation_id']:<32} {s['provider_id']:<20} {s['message_count']:<5} {created:<20} {updated:<20}")
    
    def delete_session(self, conversation_id):
        mcp_session_manager.delete_session(conversation_id)
        print(f"Deleted session: {conversation_id}")


class LogManager:
    def __init__(self):
        self.log_dir = Path(__file__).parent / "logs"
    
    def show(self, log_type="bridge", lines=50):
        log_files = {
            "bridge": "bridge.log",
            "audit": "audit.log",
            "service_stdout": "service_stdout.log",
            "service_stderr": "service_stderr.log"
        }
        
        path = self.log_dir / log_files.get(log_type, "bridge.log")
        if not path.exists():
            print(f"Log file not found: {path}")
            return
        
        with open(path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                if log_type == "audit":
                    try:
                        entry = json.loads(line)
                        print(json.dumps(entry, ensure_ascii=False, indent=2))
                    except:
                        print(line.rstrip())
                else:
                    print(line.rstrip())


class ConfigManager:
    def __init__(self):
        self.config_path = Path(__file__).parent / "config.yaml"
    
    def show(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                print(f.read())
        else:
            print("config.yaml not found")
    
    def edit(self):
        import subprocess
        subprocess.run(["notepad", str(self.config_path)])


class StatsManager:
    def show(self):
        audit_log = Path(__file__).parent / "logs" / "audit.log"
        if not audit_log.exists():
            print("No audit log found")
            return
        
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400
        
        total_requests = 0
        requests_1h = 0
        requests_24h = 0
        by_provider = {}
        by_endpoint = {}
        errors = 0
        
        with open(audit_log, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "request_complete":
                        total_requests += 1
                        ts = entry.get("timestamp", 0)
                        if ts >= hour_ago:
                            requests_1h += 1
                        if ts >= day_ago:
                            requests_24h += 1
                        
                        provider = entry.get("provider", "unknown")
                        endpoint = entry.get("endpoint", "unknown")
                        status = entry.get("status_code", 0)
                        
                        by_provider[provider] = by_provider.get(provider, 0) + 1
                        by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
                        
                        if status >= 400:
                            errors += 1
                except:
                    pass
        
        print(f"\n  Total Requests:     {total_requests}")
        print(f"  Last Hour:          {requests_1h}")
        print(f"  Last 24 Hours:      {requests_24h}")
        print(f"  Errors:             {errors}")
        print(f"\n  By Provider:")
        for k, v in sorted(by_provider.items(), key=lambda x: -x[1]):
            print(f"    {k:<20} {v}")
        print(f"\n  By Endpoint:")
        for k, v in sorted(by_endpoint.items(), key=lambda x: -x[1]):
            print(f"    {k:<30} {v}")


def cmd_service(args):
    sm = ServiceManager()
    if args.action == "install":
        code, out, err = sm.install()
        print(out or err)
    elif args.action == "uninstall":
        code, out, err = sm.uninstall()
        print(out or err)
    elif args.action == "start":
        code, out, err = sm.start()
        print(out or err)
    elif args.action == "stop":
        code, out, err = sm.stop()
        print(out or err)
    elif args.action == "restart":
        code, out, err = sm.restart()
        print(out or err)
    elif args.action == "status":
        code, out, err = sm.status()
        print(out or err)
    elif args.action == "logs":
        code, out, err = sm.logs()
        print(out or err)


def cmd_providers(args):
    pm = ProviderManager()
    if args.action == "list":
        print("\nRegistered Providers:")
        pm.list_providers()
    elif args.action == "test":
        pm.test_provider(args.provider_id)


def cmd_sessions(args):
    sm = SessionManager()
    if args.action == "list":
        print("\nActive Sessions:")
        sm.list_sessions()
    elif args.action == "delete":
        sm.delete_session(args.conversation_id)


def cmd_logs(args):
    lm = LogManager()
    lm.show(args.type, args.lines)


def cmd_config(args):
    cm = ConfigManager()
    if args.action == "show":
        cm.show()
    elif args.action == "edit":
        cm.edit()


def cmd_test(args):
    pm = ProviderManager()
    if args.provider_id:
        pm.test_provider(args.provider_id)
    else:
        print("Testing all providers...")
        providers = provider_registry.list_providers(enabled_only=True)
        for p in providers:
            pm.test_provider(p.provider_id)


def cmd_stats(args):
    sm = StatsManager()
    sm.show()


def main():
    parser = argparse.ArgumentParser(
        description="Web LLM Bridge Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Service
    svc = subparsers.add_parser("service", help="Manage Windows service")
    svc.add_argument("action", choices=["install", "uninstall", "start", "stop", "restart", "status", "logs"])
    svc.set_defaults(func=cmd_service)
    
    # Providers
    prov = subparsers.add_parser("providers", help="Manage providers")
    prov.add_argument("action", choices=["list", "test"])
    prov.add_argument("provider_id", nargs="?", help="Provider ID for test")
    prov.set_defaults(func=cmd_providers)
    
    # Sessions
    sess = subparsers.add_parser("sessions", help="Manage conversation sessions")
    sess.add_argument("action", choices=["list", "delete"])
    sess.add_argument("conversation_id", nargs="?", help="Conversation ID for delete")
    sess.set_defaults(func=cmd_sessions)
    
    # Logs
    log = subparsers.add_parser("logs", help="View logs")
    log.add_argument("type", choices=["bridge", "audit", "service_stdout", "service_stderr"], default="bridge", nargs="?")
    log.add_argument("-n", "--lines", type=int, default=50, help="Number of lines")
    log.set_defaults(func=cmd_logs)
    
    # Config
    cfg = subparsers.add_parser("config", help="View/edit configuration")
    cfg.add_argument("action", choices=["show", "edit"])
    cfg.set_defaults(func=cmd_config)
    
    # Test
    test = subparsers.add_parser("test", help="Test provider health")
    test.add_argument("provider_id", nargs="?", help="Provider ID (default: all)")
    test.set_defaults(func=cmd_test)
    
    # Stats
    stats = subparsers.add_parser("stats", help="Show statistics")
    stats.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()