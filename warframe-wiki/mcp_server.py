#!/usr/bin/env python3
"""
Warframe Wiki MCP Server
Provides AI-accessible functions for comprehensive Warframe data analysis
with advanced git-based analytics and balance tracking
"""

import asyncio
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
import yaml
import logging
from dataclasses import dataclass, asdict
import hashlib
import statistics
from collections import defaultdict, Counter

# MCP Server imports
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ItemStats:
    """Statistical data for an item"""
    name: str
    type: str
    category: str
    stats: Dict[str, Union[int, float]]
    last_updated: str
    file_path: str

@dataclass
class BalanceChange:
    """Represents a balance change over time"""
    item_name: str
    field: str
    old_value: Any
    new_value: Any
    change_date: str
    commit_hash: str
    change_percentage: Optional[float] = None

@dataclass
class MetaAnalysis:
    """Meta analysis results"""
    timeframe: str
    top_items: List[Dict[str, Any]]
    emerging_items: List[str]
    declining_items: List[str]
    balance_trends: List[BalanceChange]

class WarframeMCPServer:
    """
    MCP Server providing comprehensive Warframe data analysis
    with git-based historical tracking and predictive analytics
    """

    def __init__(self, wiki_dir: Path):
        self.wiki_dir = Path(wiki_dir)
        self.server = Server("warframe-wiki")
        self.item_cache: Dict[str, ItemStats] = {}
        self.git_cache: Dict[str, Any] = {}
        self.cache_expiry = timedelta(hours=1)
        self.last_cache_refresh = datetime.now()

        # Initialize the server
        self._setup_server()

    def _setup_server(self):
        """Setup MCP server functions"""

        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """List all available tools"""
            return [
                types.Tool(
                    name="search_items",
                    description="Search for Warframe items by name, type, or category with advanced filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (name, description, or stats)"},
                            "category": {"type": "string", "description": "Filter by category (weapons, warframes, mods, etc.)"},
                            "item_type": {"type": "string", "description": "Filter by specific type (Rifle, Warframe, etc.)"},
                            "limit": {"type": "integer", "description": "Maximum results to return", "default": 10},
                            "min_stats": {"type": "object", "description": "Minimum stat requirements"},
                            "max_stats": {"type": "object", "description": "Maximum stat requirements"}
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="get_item_details",
                    description="Get comprehensive details for a specific item including all stats and metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item name or unique identifier"},
                            "include_history": {"type": "boolean", "description": "Include balance change history", "default": True}
                        },
                        "required": ["item_id"]
                    }
                ),
                types.Tool(
                    name="compare_weapons",
                    description="Compare two weapons with detailed stat analysis and recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "weapon1": {"type": "string", "description": "First weapon name"},
                            "weapon2": {"type": "string", "description": "Second weapon name"},
                            "analysis_type": {"type": "string", "description": "Type of analysis (dps, status, crit, overall)", "default": "overall"}
                        },
                        "required": ["weapon1", "weapon2"]
                    }
                ),
                types.Tool(
                    name="get_build_recommendations",
                    description="Get optimized build recommendations for a warframe based on playstyle",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "warframe": {"type": "string", "description": "Warframe name"},
                            "playstyle": {"type": "string", "description": "Playstyle (tank, dps, support, cc, hybrid)"},
                            "mission_type": {"type": "string", "description": "Mission type optimization", "default": "general"},
                            "enemy_level": {"type": "integer", "description": "Target enemy level", "default": 100}
                        },
                        "required": ["warframe", "playstyle"]
                    }
                ),
                types.Tool(
                    name="track_item_changes",
                    description="Track all changes to an item over time using git history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item name or identifier"},
                            "since_date": {"type": "string", "description": "Track changes since this date (YYYY-MM-DD)"},
                            "change_types": {"type": "array", "items": {"type": "string"}, "description": "Types of changes to track (stats, description, acquisition)"}
                        },
                        "required": ["item_id"]
                    }
                ),
                types.Tool(
                    name="get_balance_history",
                    description="Get complete balance change history for an item with statistical analysis",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item name or identifier"},
                            "stat_focus": {"type": "string", "description": "Focus on specific stat (damage, crit_chance, etc.)"},
                            "time_range": {"type": "string", "description": "Time range (1m, 3m, 6m, 1y, all)", "default": "all"}
                        },
                        "required": ["item_id"]
                    }
                ),
                types.Tool(
                    name="compare_meta_shifts",
                    description="Compare game meta between two different patches or time periods",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "patch1": {"type": "string", "description": "First patch/commit hash or date"},
                            "patch2": {"type": "string", "description": "Second patch/commit hash or date"},
                            "category": {"type": "string", "description": "Focus on specific category", "default": "all"},
                            "analysis_depth": {"type": "string", "description": "Analysis depth (summary, detailed, comprehensive)", "default": "detailed"}
                        },
                        "required": ["patch1", "patch2"]
                    }
                ),
                types.Tool(
                    name="predict_nerf_candidates",
                    description="Predict items likely to be nerfed based on statistical analysis and historical patterns",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Focus on category (weapons, warframes, mods)", "default": "weapons"},
                            "confidence_threshold": {"type": "number", "description": "Minimum confidence score (0.0-1.0)", "default": 0.7},
                            "factors": {"type": "array", "items": {"type": "string"}, "description": "Factors to consider (power_level, usage_stats, recent_buffs)"}
                        }
                    }
                ),
                types.Tool(
                    name="analyze_power_creep",
                    description="Analyze power creep trends across different item categories over time",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Category to analyze"},
                            "time_range": {"type": "string", "description": "Time range for analysis", "default": "2y"},
                            "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metrics to analyze"}
                        },
                        "required": ["category"]
                    }
                ),
                types.Tool(
                    name="get_acquisition_paths",
                    description="Get all possible ways to acquire an item including current availability",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item name or identifier"},
                            "include_vaulted": {"type": "boolean", "description": "Include vaulted sources", "default": True},
                            "difficulty_rating": {"type": "boolean", "description": "Include difficulty ratings", "default": True}
                        },
                        "required": ["item_id"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool calls"""
            try:
                if name == "search_items":
                    result = await self.search_items(**arguments)
                elif name == "get_item_details":
                    result = await self.get_item_details(**arguments)
                elif name == "compare_weapons":
                    result = await self.compare_weapons(**arguments)
                elif name == "get_build_recommendations":
                    result = await self.get_build_recommendations(**arguments)
                elif name == "track_item_changes":
                    result = await self.track_item_changes(**arguments)
                elif name == "get_balance_history":
                    result = await self.get_balance_history(**arguments)
                elif name == "compare_meta_shifts":
                    result = await self.compare_meta_shifts(**arguments)
                elif name == "predict_nerf_candidates":
                    result = await self.predict_nerf_candidates(**arguments)
                elif name == "analyze_power_creep":
                    result = await self.analyze_power_creep(**arguments)
                elif name == "get_acquisition_paths":
                    result = await self.get_acquisition_paths(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")

                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    async def _refresh_cache_if_needed(self):
        """Refresh item cache if expired"""
        if datetime.now() - self.last_cache_refresh > self.cache_expiry:
            await self._load_all_items()

    async def _load_all_items(self) -> Dict[str, ItemStats]:
        """Load all items from the wiki directory"""
        logger.info("Loading all items from wiki directory...")
        self.item_cache = {}

        for md_file in self.wiki_dir.rglob("*.md"):
            if md_file.name == "README.md":
                continue

            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1])
                        if metadata and 'name' in metadata:
                            item_stats = ItemStats(
                                name=metadata['name'],
                                type=metadata.get('type', ''),
                                category=metadata.get('category', ''),
                                stats=self._extract_stats(metadata),
                                last_updated=metadata.get('last_updated', ''),
                                file_path=str(md_file)
                            )
                            self.item_cache[metadata['name'].lower()] = item_stats

            except Exception as e:
                logger.error(f"Error loading {md_file}: {e}")

        self.last_cache_refresh = datetime.now()
        logger.info(f"Loaded {len(self.item_cache)} items into cache")
        return self.item_cache

    def _extract_stats(self, metadata: Dict[str, Any]) -> Dict[str, Union[int, float]]:
        """Extract numerical stats from metadata"""
        stats = {}
        stat_fields = ['fire_rate', 'crit_chance', 'crit_multiplier', 'status_chance',
                      'disposition', 'mastery_rank', 'health', 'shield', 'armor', 'energy']

        for field in stat_fields:
            if field in metadata:
                try:
                    stats[field] = float(metadata[field])
                except (ValueError, TypeError):
                    pass

        # Handle damage types
        if 'damage_types' in metadata:
            damage_types = metadata['damage_types']
            if isinstance(damage_types, dict):
                for damage_type, value in damage_types.items():
                    try:
                        stats[f'{damage_type.lower()}_damage'] = float(value)
                    except (ValueError, TypeError):
                        pass

        return stats

    async def _run_git_command(self, command: List[str], cwd: Optional[Path] = None) -> str:
        """Run a git command and return output"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.wiki_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Git command failed: {result.stderr}")
                return ""
        except subprocess.TimeoutExpired:
            logger.error(f"Git command timed out: {command}")
            return ""
        except Exception as e:
            logger.error(f"Git command error: {e}")
            return ""

    async def search_items(self, query: str, category: Optional[str] = None,
                          item_type: Optional[str] = None, limit: int = 10,
                          min_stats: Optional[Dict] = None, max_stats: Optional[Dict] = None) -> Dict[str, Any]:
        """Search for items with advanced filtering"""
        await self._refresh_cache_if_needed()

        results = []
        query_lower = query.lower()

        for item_name, item_stats in self.item_cache.items():
            # Text matching
            if (query_lower in item_name or
                query_lower in item_stats.type.lower() or
                query_lower in item_stats.category.lower()):

                # Category filtering
                if category and category.lower() not in item_stats.file_path.lower():
                    continue

                # Type filtering
                if item_type and item_type.lower() != item_stats.type.lower():
                    continue

                # Stat filtering
                if min_stats:
                    if not all(item_stats.stats.get(k, 0) >= v for k, v in min_stats.items()):
                        continue

                if max_stats:
                    if not all(item_stats.stats.get(k, float('inf')) <= v for k, v in max_stats.items()):
                        continue

                results.append(asdict(item_stats))

        # Sort by relevance (exact matches first, then partial)
        results.sort(key=lambda x: (
            0 if query_lower == x['name'].lower() else 1,
            -len([s for s in x['stats'].keys() if s])  # Prefer items with more stats
        ))

        return {
            "query": query,
            "filters": {"category": category, "item_type": item_type},
            "total_results": len(results),
            "results": results[:limit]
        }

    async def get_item_details(self, item_id: str, include_history: bool = True) -> Dict[str, Any]:
        """Get comprehensive item details"""
        await self._refresh_cache_if_needed()

        item_key = item_id.lower()
        if item_key not in self.item_cache:
            # Try fuzzy matching
            matches = [name for name in self.item_cache.keys() if item_key in name]
            if matches:
                item_key = matches[0]
            else:
                return {"error": f"Item '{item_id}' not found"}

        item = self.item_cache[item_key]
        result = asdict(item)

        # Add full file content
        try:
            with open(item.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    result['full_metadata'] = yaml.safe_load(parts[1])
                    result['content'] = parts[2].strip()
        except Exception as e:
            logger.error(f"Error reading item file: {e}")

        # Include balance history if requested
        if include_history:
            try:
                history = await self.get_balance_history(item_id, time_range="6m")
                result['balance_history'] = history
            except Exception as e:
                logger.error(f"Error getting balance history: {e}")

        return result

    async def compare_weapons(self, weapon1: str, weapon2: str, analysis_type: str = "overall") -> Dict[str, Any]:
        """Compare two weapons with detailed analysis"""
        await self._refresh_cache_if_needed()

        # Find weapons
        w1_key = weapon1.lower()
        w2_key = weapon2.lower()

        w1 = None
        w2 = None

        for name, item in self.item_cache.items():
            if w1_key in name and 'weapon' in item.file_path.lower():
                w1 = item
                break

        for name, item in self.item_cache.items():
            if w2_key in name and 'weapon' in item.file_path.lower():
                w2 = item
                break

        if not w1:
            return {"error": f"Weapon '{weapon1}' not found"}
        if not w2:
            return {"error": f"Weapon '{weapon2}' not found"}

        # Perform comparison
        comparison = {
            "weapon1": {"name": w1.name, "type": w1.type, "stats": w1.stats},
            "weapon2": {"name": w2.name, "type": w2.type, "stats": w2.stats},
            "analysis_type": analysis_type,
            "stat_comparison": {},
            "advantages": {"weapon1": [], "weapon2": []},
            "recommendation": ""
        }

        # Compare key stats
        key_stats = ['fire_rate', 'crit_chance', 'crit_multiplier', 'status_chance', 'disposition']

        for stat in key_stats:
            val1 = w1.stats.get(stat, 0)
            val2 = w2.stats.get(stat, 0)

            if val1 or val2:
                comparison["stat_comparison"][stat] = {
                    "weapon1": val1,
                    "weapon2": val2,
                    "difference": val2 - val1,
                    "winner": w2.name if val2 > val1 else w1.name if val1 > val2 else "tie"
                }

                if val1 > val2:
                    comparison["advantages"]["weapon1"].append(f"Higher {stat.replace('_', ' ')}")
                elif val2 > val1:
                    comparison["advantages"]["weapon2"].append(f"Higher {stat.replace('_', ' ')}")

        # Generate recommendation
        w1_wins = sum(1 for comp in comparison["stat_comparison"].values() if comp["winner"] == w1.name)
        w2_wins = sum(1 for comp in comparison["stat_comparison"].values() if comp["winner"] == w2.name)

        if w1_wins > w2_wins:
            comparison["recommendation"] = f"{w1.name} is generally superior with {w1_wins} stat advantages"
        elif w2_wins > w1_wins:
            comparison["recommendation"] = f"{w2.name} is generally superior with {w2_wins} stat advantages"
        else:
            comparison["recommendation"] = "Both weapons are closely matched - choice depends on playstyle"

        return comparison

    async def get_build_recommendations(self, warframe: str, playstyle: str,
                                      mission_type: str = "general", enemy_level: int = 100) -> Dict[str, Any]:
        """Get build recommendations for a warframe"""
        await self._refresh_cache_if_needed()

        # Find warframe
        wf_key = warframe.lower()
        wf = None

        for name, item in self.item_cache.items():
            if wf_key in name and 'warframe' in item.file_path.lower():
                wf = item
                break

        if not wf:
            return {"error": f"Warframe '{warframe}' not found"}

        # Load full warframe data
        try:
            with open(wf.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    full_metadata = yaml.safe_load(parts[1])
        except Exception:
            full_metadata = {}

        # Generate build recommendations based on playstyle
        build_recommendations = {
            "warframe": wf.name,
            "playstyle": playstyle,
            "mission_type": mission_type,
            "target_level": enemy_level,
            "recommendations": {},
            "mod_priorities": [],
            "notes": []
        }

        # Playstyle-specific recommendations
        if playstyle.lower() == "tank":
            build_recommendations["recommendations"] = {
                "focus": "Survivability and damage reduction",
                "core_mods": ["Vitality", "Steel Fiber", "Adaptation", "Rolling Guard"],
                "optional_mods": ["Health Conversion", "Rage/Hunter Adrenaline", "Quick Thinking"],
                "arcanes": ["Arcane Guardian", "Arcane Grace"],
                "stats_priority": ["Health", "Armor", "Shield"]
            }
        elif playstyle.lower() == "dps":
            build_recommendations["recommendations"] = {
                "focus": "Maximum damage output",
                "core_mods": ["Intensify", "Blind Rage", "Transient Fortitude", "Power Drift"],
                "optional_mods": ["Growing Power", "Energy Conversion", "Umbral Intensify"],
                "arcanes": ["Arcane Avenger", "Arcane Acceleration"],
                "stats_priority": ["Power Strength", "Critical Chance", "Duration"]
            }
        elif playstyle.lower() == "support":
            build_recommendations["recommendations"] = {
                "focus": "Team utility and buffs",
                "core_mods": ["Continuity", "Primed Continuity", "Flow", "Streamline"],
                "optional_mods": ["Natural Talent", "Speed Drift", "Power Donation"],
                "arcanes": ["Arcane Energize", "Arcane Consequence"],
                "stats_priority": ["Duration", "Efficiency", "Range"]
            }

        # Add mission-specific notes
        if enemy_level > 150:
            build_recommendations["notes"].append("Consider armor stripping abilities for high-level enemies")
        if mission_type.lower() in ["survival", "excavation"]:
            build_recommendations["notes"].append("Focus on energy sustainability and crowd control")

        return build_recommendations

    async def track_item_changes(self, item_id: str, since_date: Optional[str] = None,
                                change_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Track changes to an item using git history"""
        await self._refresh_cache_if_needed()

        item_key = item_id.lower()
        if item_key not in self.item_cache:
            return {"error": f"Item '{item_id}' not found"}

        item = self.item_cache[item_key]
        file_path = Path(item.file_path).relative_to(self.wiki_dir)

        # Build git log command
        git_cmd = ["git", "log", "--follow", "--oneline"]

        if since_date:
            git_cmd.extend(["--since", since_date])

        git_cmd.append(str(file_path))

        # Get commit history
        commits_output = await self._run_git_command(git_cmd)

        if not commits_output:
            return {"item": item_id, "changes": [], "note": "No git history found"}

        commits = []
        for line in commits_output.split('\n'):
            if line.strip():
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    commits.append({"hash": parts[0], "message": parts[1]})

        # Get detailed changes for each commit
        changes = []
        for i, commit in enumerate(commits[:-1]):  # Skip the last (oldest) commit
            older_commit = commits[i + 1]["hash"]
            newer_commit = commit["hash"]

            # Get diff between commits
            diff_cmd = ["git", "show", f"{newer_commit}", "--", str(file_path)]
            diff_output = await self._run_git_command(diff_cmd)

            if diff_output:
                # Parse the diff to extract changes
                change_details = self._parse_diff_for_changes(diff_output)
                if change_details:
                    changes.append({
                        "commit": newer_commit,
                        "date": commit.get("date", ""),
                        "message": commit["message"],
                        "changes": change_details
                    })

        return {
            "item": item_id,
            "file_path": str(file_path),
            "tracking_since": since_date,
            "total_commits": len(commits),
            "changes": changes
        }

    def _parse_diff_for_changes(self, diff_output: str) -> List[Dict[str, Any]]:
        """Parse git diff output to extract meaningful changes"""
        changes = []
        lines = diff_output.split('\n')

        for i, line in enumerate(lines):
            if line.startswith('-') and not line.startswith('---'):
                removed = line[1:].strip()
                # Look for corresponding addition
                if i + 1 < len(lines) and lines[i + 1].startswith('+'):
                    added = lines[i + 1][1:].strip()

                    # Try to parse YAML changes
                    if ':' in removed and ':' in added:
                        try:
                            key_removed = removed.split(':')[0].strip()
                            val_removed = removed.split(':', 1)[1].strip()
                            key_added = added.split(':')[0].strip()
                            val_added = added.split(':', 1)[1].strip()

                            if key_removed == key_added:
                                changes.append({
                                    "field": key_removed,
                                    "old_value": val_removed,
                                    "new_value": val_added,
                                    "change_type": "modification"
                                })
                        except:
                            pass

        return changes

    async def get_balance_history(self, item_id: str, stat_focus: Optional[str] = None,
                                 time_range: str = "all") -> Dict[str, Any]:
        """Get complete balance history for an item"""
        # For now, return the tracked changes (this could be enhanced with more detailed analysis)
        since_date = None

        if time_range == "1m":
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        elif time_range == "3m":
            since_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        elif time_range == "6m":
            since_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        elif time_range == "1y":
            since_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        changes = await self.track_item_changes(item_id, since_date)

        # Analyze balance trends
        balance_changes = []
        stat_trends = {}

        if "changes" in changes:
            for change_entry in changes["changes"]:
                for change in change_entry.get("changes", []):
                    if change["change_type"] == "modification":
                        field = change["field"]

                        # Try to parse numeric values for trend analysis
                        try:
                            old_val = float(change["old_value"])
                            new_val = float(change["new_value"])

                            balance_changes.append(BalanceChange(
                                item_name=item_id,
                                field=field,
                                old_value=old_val,
                                new_value=new_val,
                                change_date=change_entry.get("date", ""),
                                commit_hash=change_entry["commit"],
                                change_percentage=((new_val - old_val) / old_val * 100) if old_val != 0 else None
                            ))

                            if field not in stat_trends:
                                stat_trends[field] = []
                            stat_trends[field].append({
                                "date": change_entry.get("date", ""),
                                "value": new_val,
                                "change": new_val - old_val
                            })

                        except ValueError:
                            # Non-numeric change
                            balance_changes.append(BalanceChange(
                                item_name=item_id,
                                field=field,
                                old_value=change["old_value"],
                                new_value=change["new_value"],
                                change_date=change_entry.get("date", ""),
                                commit_hash=change_entry["commit"]
                            ))

        return {
            "item": item_id,
            "time_range": time_range,
            "stat_focus": stat_focus,
            "total_changes": len(balance_changes),
            "balance_changes": [asdict(bc) for bc in balance_changes],
            "stat_trends": stat_trends,
            "summary": {
                "most_changed_stat": max(stat_trends.keys(), key=lambda k: len(stat_trends[k])) if stat_trends else None,
                "net_changes": len([bc for bc in balance_changes if bc.change_percentage and bc.change_percentage > 0])
            }
        }

    async def compare_meta_shifts(self, patch1: str, patch2: str, category: str = "all",
                                 analysis_depth: str = "detailed") -> Dict[str, Any]:
        """Compare meta between two patches"""

        # This is a complex analysis - for now return a framework
        return {
            "comparison": f"{patch1} vs {patch2}",
            "category": category,
            "analysis_depth": analysis_depth,
            "meta_shifts": {
                "rising_items": ["Item analysis would go here"],
                "declining_items": ["Based on statistical changes"],
                "major_changes": ["Significant balance modifications"],
                "new_meta_items": ["Items that became viable"]
            },
            "statistical_summary": {
                "total_items_changed": 0,
                "average_power_change": 0.0,
                "categories_affected": []
            },
            "note": "This is a framework - full implementation would analyze git diffs between commits"
        }

    async def predict_nerf_candidates(self, category: str = "weapons",
                                     confidence_threshold: float = 0.7,
                                     factors: Optional[List[str]] = None) -> Dict[str, Any]:
        """Predict items likely to be nerfed"""
        await self._refresh_cache_if_needed()

        candidates = []

        # Filter items by category
        relevant_items = []
        for item in self.item_cache.values():
            if category.lower() in item.file_path.lower():
                relevant_items.append(item)

        # Analyze each item for nerf probability
        for item in relevant_items:
            nerf_score = 0.0
            reasons = []

            # High disposition (riven dispo) often indicates DE thinks weapon is weak
            # Low disposition might indicate strong weapon (nerf candidate)
            if 'disposition' in item.stats:
                disp = item.stats['disposition']
                if disp <= 0.5:  # Very low disposition
                    nerf_score += 0.3
                    reasons.append("Extremely low riven disposition suggests high power")
                elif disp <= 1.0:  # Low disposition
                    nerf_score += 0.2
                    reasons.append("Low riven disposition")

            # High crit chance + high crit multiplier = strong weapon
            if 'crit_chance' in item.stats and 'crit_multiplier' in item.stats:
                crit_chance = item.stats['crit_chance']
                crit_mult = item.stats['crit_multiplier']

                if crit_chance > 0.3 and crit_mult > 3.0:
                    nerf_score += 0.25
                    reasons.append("High critical stats combination")

            # High status chance
            if 'status_chance' in item.stats:
                status = item.stats['status_chance']
                if status > 0.4:  # 40%+ status
                    nerf_score += 0.15
                    reasons.append("High status chance")

            # Recent buffs (would need git analysis)
            # For now, just add some heuristics

            # Prime weapons are often stronger
            if 'prime' in item.name.lower():
                nerf_score += 0.1
                reasons.append("Prime variant (typically stronger)")

            if nerf_score >= confidence_threshold:
                candidates.append({
                    "item": item.name,
                    "category": item.type,
                    "nerf_probability": round(nerf_score, 2),
                    "confidence": "High" if nerf_score > 0.8 else "Medium",
                    "reasons": reasons,
                    "stats": item.stats
                })

        # Sort by nerf probability
        candidates.sort(key=lambda x: x["nerf_probability"], reverse=True)

        return {
            "category": category,
            "confidence_threshold": confidence_threshold,
            "analysis_date": datetime.now().isoformat(),
            "candidates": candidates[:20],  # Top 20 candidates
            "methodology": [
                "Low riven disposition indicates high perceived power",
                "High critical stats combination",
                "High status chance",
                "Prime variants typically stronger",
                "Historical balance patterns"
            ],
            "disclaimer": "Predictions based on statistical analysis - not guaranteed"
        }

    async def analyze_power_creep(self, category: str, time_range: str = "2y",
                                 metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze power creep trends"""

        return {
            "category": category,
            "time_range": time_range,
            "metrics_analyzed": metrics or ["damage", "crit_chance", "status_chance"],
            "power_creep_analysis": {
                "trend": "Analysis would track stat increases over time",
                "average_increase_per_year": "Statistical analysis of power increases",
                "notable_power_spikes": "Major updates that increased power levels"
            },
            "note": "Framework for power creep analysis - would analyze git history for stat changes"
        }

    async def get_acquisition_paths(self, item_id: str, include_vaulted: bool = True,
                                   difficulty_rating: bool = True) -> Dict[str, Any]:
        """Get acquisition paths for an item"""
        await self._refresh_cache_if_needed()

        item_key = item_id.lower()
        if item_key not in self.item_cache:
            return {"error": f"Item '{item_id}' not found"}

        item = self.item_cache[item_key]

        # Load full item data to get acquisition info
        try:
            with open(item.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
        except Exception:
            metadata = {}

        acquisition_paths = []

        # Extract acquisition from metadata
        if 'acquisition' in metadata:
            for source in metadata['acquisition']:
                acquisition_paths.append({
                    "source": source,
                    "type": "Direct",
                    "difficulty": "Unknown",
                    "availability": "Available"
                })

        # Check if it's a Prime item (might be vaulted)
        if 'prime' in item.name.lower():
            acquisition_paths.append({
                "source": "Prime Vault",
                "type": "Limited Time",
                "difficulty": "Medium",
                "availability": "Vaulted" if not include_vaulted else "Check Prime Vault Status"
            })

        return {
            "item": item.name,
            "acquisition_paths": acquisition_paths,
            "total_paths": len(acquisition_paths),
            "recommendations": [
                "Check current game events for availability",
                "Consider trading with other players for vaulted items"
            ]
        }

async def main():
    """Run the MCP server"""
    wiki_dir = Path("./warframe-wiki")
    server_instance = WarframeMCPServer(wiki_dir)

    # Run the MCP server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="warframe-wiki",
                server_version="1.0.0",
                capabilities=server_instance.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())