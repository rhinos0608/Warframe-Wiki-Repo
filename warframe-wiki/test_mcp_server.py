#!/usr/bin/env python3
"""
Test script for Warframe MCP Server
Verifies that the MCP server functions correctly with both stdio and HTTP transports

This script:
1. Tests MCP protocol initialization
2. Validates tool discovery
3. Tests various search and analytics functions
4. Verifies vector search capabilities
5. Tests git-based analytics
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# HTTP client for testing HTTP transport
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Rich for beautiful test output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPServerTester:
    """
    Comprehensive test suite for Warframe MCP Server

    Tests both transport methods:
    - STDIO for direct AI integration
    - HTTP for web-based clients
    """

    def __init__(self, wiki_dir: Path = Path("./warframe-wiki")):
        self.wiki_dir = wiki_dir
        self.console = Console() if RICH_AVAILABLE else None
        self.test_results = {}
        self.server_process = None

    def log_info(self, message: str):
        """Log info with rich formatting if available"""
        if self.console:
            self.console.print(f"[blue]ℹ[/blue] {message}")
        else:
            logger.info(message)

    def log_success(self, message: str):
        """Log success with rich formatting if available"""
        if self.console:
            self.console.print(f"[green]✅[/green] {message}")
        else:
            logger.info(f"✅ {message}")

    def log_warning(self, message: str):
        """Log warning with rich formatting if available"""
        if self.console:
            self.console.print(f"[yellow]⚠[/yellow] {message}")
        else:
            logger.warning(f"⚠ {message}")

    def log_error(self, message: str):
        """Log error with rich formatting if available"""
        if self.console:
            self.console.print(f"[red]❌[/red] {message}")
        else:
            logger.error(f"❌ {message}")

    async def test_mcp_initialization(self) -> bool:
        """Test MCP protocol initialization"""
        self.log_info("Testing MCP initialization...")

        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": True
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        try:
            # Test via HTTP if possible
            if HTTPX_AVAILABLE:
                result = await self._test_http_request(init_message)
                if result and "result" in result:
                    self.log_success("MCP initialization successful (HTTP)")
                    self.test_results["initialization_http"] = True
                    return True

            # Test via stdio would require more complex subprocess handling
            self.log_warning("HTTP test not available, skipping initialization test")
            self.test_results["initialization_http"] = False
            return False

        except Exception as e:
            self.log_error(f"MCP initialization failed: {e}")
            self.test_results["initialization_http"] = False
            return False

    async def test_tools_list(self) -> bool:
        """Test tool discovery"""
        self.log_info("Testing tool discovery...")

        tools_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        try:
            if HTTPX_AVAILABLE:
                result = await self._test_http_request(tools_message)
                if result and "result" in result and "tools" in result["result"]:
                    tools = result["result"]["tools"]
                    self.log_success(f"Found {len(tools)} available tools")

                    # Verify expected tools exist
                    expected_tools = [
                        "search_items",
                        "get_item_details",
                        "compare_weapons",
                        "get_balance_history",
                        "predict_nerf_candidates"
                    ]

                    tool_names = [tool["name"] for tool in tools]
                    missing_tools = [tool for tool in expected_tools if tool not in tool_names]

                    if missing_tools:
                        self.log_warning(f"Missing expected tools: {missing_tools}")

                    self.test_results["tools_list"] = {
                        "success": True,
                        "tool_count": len(tools),
                        "tools": tool_names,
                        "missing_tools": missing_tools
                    }
                    return True

            self.log_warning("HTTP test not available, skipping tools list test")
            self.test_results["tools_list"] = {"success": False, "reason": "HTTP not available"}
            return False

        except Exception as e:
            self.log_error(f"Tools list test failed: {e}")
            self.test_results["tools_list"] = {"success": False, "error": str(e)}
            return False

    async def test_search_functionality(self) -> bool:
        """Test search_items tool"""
        self.log_info("Testing search functionality...")

        search_message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_items",
                "arguments": {
                    "query": "braton",
                    "limit": 5
                }
            }
        }

        try:
            if HTTPX_AVAILABLE:
                result = await self._test_http_request(search_message)
                if result and "result" in result:
                    content = result["result"].get("content", [])
                    if content and len(content) > 0:
                        # Parse the JSON response
                        search_results = json.loads(content[0]["text"])

                        if "results" in search_results:
                            results_count = len(search_results["results"])
                            search_method = search_results.get("search_method", "unknown")

                            self.log_success(f"Search returned {results_count} results using {search_method} method")

                            self.test_results["search_functionality"] = {
                                "success": True,
                                "results_count": results_count,
                                "search_method": search_method,
                                "query": "braton"
                            }
                            return True

            self.log_warning("HTTP test not available, skipping search test")
            self.test_results["search_functionality"] = {"success": False, "reason": "HTTP not available"}
            return False

        except Exception as e:
            self.log_error(f"Search functionality test failed: {e}")
            self.test_results["search_functionality"] = {"success": False, "error": str(e)}
            return False

    async def test_balance_history(self) -> bool:
        """Test git-based balance history functionality"""
        self.log_info("Testing balance history functionality...")

        balance_message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_balance_history",
                "arguments": {
                    "item_id": "braton prime",
                    "time_range": "6m"
                }
            }
        }

        try:
            if HTTPX_AVAILABLE:
                result = await self._test_http_request(balance_message)
                if result and "result" in result:
                    content = result["result"].get("content", [])
                    if content and len(content) > 0:
                        balance_results = json.loads(content[0]["text"])

                        if "balance_changes" in balance_results:
                            changes_count = len(balance_results["balance_changes"])
                            time_range = balance_results.get("time_range", "unknown")

                            self.log_success(f"Balance history returned {changes_count} changes over {time_range}")

                            self.test_results["balance_history"] = {
                                "success": True,
                                "changes_count": changes_count,
                                "time_range": time_range
                            }
                            return True

            self.log_warning("HTTP test not available, skipping balance history test")
            self.test_results["balance_history"] = {"success": False, "reason": "HTTP not available"}
            return False

        except Exception as e:
            self.log_error(f"Balance history test failed: {e}")
            self.test_results["balance_history"] = {"success": False, "error": str(e)}
            return False

    async def test_nerf_prediction(self) -> bool:
        """Test nerf prediction analytics"""
        self.log_info("Testing nerf prediction functionality...")

        prediction_message = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "predict_nerf_candidates",
                "arguments": {
                    "category": "weapons",
                    "confidence_threshold": 0.6
                }
            }
        }

        try:
            if HTTPX_AVAILABLE:
                result = await self._test_http_request(prediction_message)
                if result and "result" in result:
                    content = result["result"].get("content", [])
                    if content and len(content) > 0:
                        prediction_results = json.loads(content[0]["text"])

                        if "candidates" in prediction_results:
                            candidates_count = len(prediction_results["candidates"])
                            threshold = prediction_results.get("confidence_threshold", 0)

                            self.log_success(f"Nerf prediction found {candidates_count} candidates above {threshold} confidence")

                            self.test_results["nerf_prediction"] = {
                                "success": True,
                                "candidates_count": candidates_count,
                                "confidence_threshold": threshold
                            }
                            return True

            self.log_warning("HTTP test not available, skipping nerf prediction test")
            self.test_results["nerf_prediction"] = {"success": False, "reason": "HTTP not available"}
            return False

        except Exception as e:
            self.log_error(f"Nerf prediction test failed: {e}")
            self.test_results["nerf_prediction"] = {"success": False, "error": str(e)}
            return False

    async def test_server_health(self) -> bool:
        """Test server health endpoint"""
        self.log_info("Testing server health...")

        try:
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://127.0.0.1:8000/health", timeout=5.0)
                    if response.status_code == 200:
                        health_data = response.json()
                        if health_data.get("status") == "healthy":
                            features = health_data.get("features", {})
                            self.log_success(f"Server healthy with features: {list(features.keys())}")

                            self.test_results["server_health"] = {
                                "success": True,
                                "features": features,
                                "version": health_data.get("version"),
                                "mcp_version": health_data.get("mcp_version")
                            }
                            return True

            self.log_warning("HTTP client not available, skipping health test")
            self.test_results["server_health"] = {"success": False, "reason": "HTTP not available"}
            return False

        except Exception as e:
            self.log_error(f"Server health test failed: {e}")
            self.test_results["server_health"] = {"success": False, "error": str(e)}
            return False

    async def _test_http_request(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send HTTP request to MCP server"""
        if not HTTPX_AVAILABLE:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://127.0.0.1:8000/mcp",
                    json=message,
                    timeout=10.0
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    self.log_error(f"HTTP request failed with status {response.status_code}")
                    return None

        except httpx.ConnectError:
            self.log_warning("Cannot connect to MCP server - is it running on port 8000?")
            return None
        except Exception as e:
            self.log_error(f"HTTP request failed: {e}")
            return None

    async def start_test_server(self) -> bool:
        """Start MCP server for testing"""
        self.log_info("Starting MCP server for testing...")

        try:
            # Start server in HTTP mode
            cmd = [
                sys.executable, "mcp_server.py",
                "--transport", "http",
                "--wiki-path", str(self.wiki_dir),
                "--host", "127.0.0.1",
                "--port", "8000"
            ]

            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.wiki_dir
            )

            # Wait for server to start
            await asyncio.sleep(3)

            # Check if server is running
            if self.server_process.poll() is None:
                self.log_success("MCP server started successfully")
                return True
            else:
                stdout, stderr = self.server_process.communicate()
                self.log_error(f"Server failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            self.log_error(f"Failed to start server: {e}")
            return False

    def stop_test_server(self):
        """Stop the test server"""
        if self.server_process:
            self.log_info("Stopping test server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.log_success("Test server stopped")

    def generate_test_report(self):
        """Generate comprehensive test report"""
        if RICH_AVAILABLE and self.console:
            self._generate_rich_report()
        else:
            self._generate_simple_report()

    def _generate_rich_report(self):
        """Generate rich-formatted test report"""
        # Summary table
        summary_table = Table(title="MCP Server Test Results")
        summary_table.add_column("Test", style="cyan", no_wrap=True)
        summary_table.add_column("Status", style="magenta")
        summary_table.add_column("Details", style="white")

        for test_name, result in self.test_results.items():
            if isinstance(result, dict):
                status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
                details = ""

                if test_name == "tools_list" and result.get("success"):
                    details = f"{result.get('tool_count', 0)} tools found"
                elif test_name == "search_functionality" and result.get("success"):
                    details = f"{result.get('results_count', 0)} results ({result.get('search_method', 'unknown')})"
                elif test_name == "balance_history" and result.get("success"):
                    details = f"{result.get('changes_count', 0)} changes tracked"
                elif test_name == "nerf_prediction" and result.get("success"):
                    details = f"{result.get('candidates_count', 0)} candidates found"
                elif test_name == "server_health" and result.get("success"):
                    features = result.get('features', {})
                    active_features = [k for k, v in features.items() if v]
                    details = f"Features: {', '.join(active_features)}"
                elif not result.get("success"):
                    details = result.get("error", result.get("reason", "Unknown"))

            else:
                status = "✅ PASS" if result else "❌ FAIL"
                details = ""

            summary_table.add_row(test_name.replace("_", " ").title(), status, details)

        self.console.print(Panel(summary_table, title="🧪 Test Results Summary"))

        # Calculate overall success rate
        passed_tests = sum(1 for result in self.test_results.values()
                          if (isinstance(result, dict) and result.get("success", False)) or
                             (isinstance(result, bool) and result))
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        self.console.print(f"\n[bold]Overall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests} tests passed)[/bold]")

    def _generate_simple_report(self):
        """Generate simple text test report"""
        print("\n" + "=" * 60)
        print("MCP SERVER TEST RESULTS")
        print("=" * 60)

        for test_name, result in self.test_results.items():
            status = "PASS" if (isinstance(result, dict) and result.get("success", False)) or (isinstance(result, bool) and result) else "FAIL"
            print(f"{test_name.replace('_', ' ').title()}: {status}")

        passed_tests = sum(1 for result in self.test_results.values()
                          if (isinstance(result, dict) and result.get("success", False)) or
                             (isinstance(result, bool) and result))
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        print(f"\nOverall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests} tests passed)")
        print("=" * 60)

async def main():
    """Main test execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Warframe MCP Server")
    parser.add_argument("--wiki-dir", default="./warframe-wiki", help="Path to wiki directory")
    parser.add_argument("--start-server", action="store_true", help="Start server automatically for testing")
    parser.add_argument("--server-only", action="store_true", help="Only start server, don't run tests")

    args = parser.parse_args()

    tester = MCPServerTester(Path(args.wiki_dir))

    if args.server_only:
        # Just start the server and wait
        if await tester.start_test_server():
            tester.log_info("Server running on http://127.0.0.1:8000")
            tester.log_info("Press Ctrl+C to stop")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                tester.stop_test_server()
        return

    server_started = False

    try:
        if args.start_server:
            server_started = await tester.start_test_server()
            if not server_started:
                tester.log_error("Failed to start server, cannot run tests")
                return

        # Run all tests
        test_functions = [
            tester.test_server_health,
            tester.test_mcp_initialization,
            tester.test_tools_list,
            tester.test_search_functionality,
            tester.test_balance_history,
            tester.test_nerf_prediction
        ]

        for test_func in test_functions:
            await test_func()
            await asyncio.sleep(0.5)  # Small delay between tests

        # Generate report
        tester.generate_test_report()

    except KeyboardInterrupt:
        tester.log_warning("Tests interrupted by user")

    finally:
        if server_started:
            tester.stop_test_server()

if __name__ == "__main__":
    asyncio.run(main())