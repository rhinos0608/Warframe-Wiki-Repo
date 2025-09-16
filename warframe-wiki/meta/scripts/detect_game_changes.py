#!/usr/bin/env python3
"""
Warframe Game Change Detection
Monitors WFCD APIs for game data changes and triggers updates
"""

import asyncio
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import os
import sys

from wfcd_client import WFCDClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ChangeDetectionResult:
    """Container for change detection results"""
    has_changes: bool
    changed_categories: Set[str]
    unchanged_categories: Set[str]
    new_items: Dict[str, List[str]]
    modified_items: Dict[str, List[str]]
    removed_items: Dict[str, List[str]]
    summary: str
    timestamp: datetime

class GameChangeDetector:
    """
    Detects changes in Warframe game data by comparing API responses
    """

    def __init__(self, state_file: str = ".game-state.json", cache_dir: str = "./cache"):
        self.state_file = Path(state_file)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Categories to monitor
        self.monitored_categories = ['warframes', 'weapons', 'mods', 'relics']

        # Change detection thresholds
        self.significant_change_threshold = 0.05  # 5% of items changed
        self.major_update_threshold = 0.15  # 15% of items changed

    def _calculate_content_hash(self, data: any) -> str:
        """Calculate hash of data for change detection"""
        if data is None:
            return ""

        # Convert to JSON string with sorted keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _extract_item_identifiers(self, items: List[Dict]) -> Dict[str, str]:
        """Extract item identifiers and their hashes"""
        identifiers = {}

        for item in items:
            # Use name as primary identifier
            item_id = item.get('name', item.get('uniqueName', 'unknown'))

            # Create hash of relevant item data (excluding timestamps)
            item_data = {k: v for k, v in item.items() if k not in ['lastUpdate', 'timestamp']}
            item_hash = self._calculate_content_hash(item_data)

            identifiers[item_id] = item_hash

        return identifiers

    def load_previous_state(self) -> Optional[Dict]:
        """Load previous game state from file"""
        if not self.state_file.exists():
            logger.info("No previous game state found")
            return None

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            # Validate state structure
            if 'categories' not in state or 'timestamp' not in state:
                logger.warning("Invalid state file format, starting fresh")
                return None

            # Check if state is too old (older than 7 days)
            state_time = datetime.fromisoformat(state['timestamp'])
            if datetime.now() - state_time > timedelta(days=7):
                logger.info("State file is too old, starting fresh")
                return None

            logger.info(f"Loaded previous state from {state_time}")
            return state

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to load previous state: {e}")
            return None

    def save_current_state(self, current_data: Dict[str, any]):
        """Save current game state to file"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'categories': {},
            'metadata': {
                'detector_version': '1.0',
                'total_items': 0
            }
        }

        total_items = 0

        for category, response in current_data.items():
            if response and response.data:
                items = response.data
                if isinstance(items, dict) and 'items' in items:
                    items = items['items']
                elif not isinstance(items, list):
                    items = [items] if items else []

                identifiers = self._extract_item_identifiers(items)
                state['categories'][category] = {
                    'hash': self._calculate_content_hash(items),
                    'item_count': len(items),
                    'item_identifiers': identifiers,
                    'last_updated': datetime.now().isoformat()
                }
                total_items += len(items)

        state['metadata']['total_items'] = total_items

        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, default=str)
            logger.info(f"Saved current state with {total_items} total items")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def detect_category_changes(self, category: str, current_items: List[Dict],
                             previous_state: Optional[Dict]) -> Dict[str, any]:
        """Detect changes in a specific category"""
        changes = {
            'has_changes': False,
            'new_items': [],
            'modified_items': [],
            'removed_items': [],
            'total_changes': 0
        }

        if not previous_state or category not in previous_state.get('categories', {}):
            # No previous data, treat all as new
            changes['has_changes'] = True
            changes['new_items'] = [item.get('name', 'unknown') for item in current_items]
            changes['total_changes'] = len(current_items)
            return changes

        previous_category = previous_state['categories'][category]
        previous_identifiers = previous_category.get('item_identifiers', {})
        current_identifiers = self._extract_item_identifiers(current_items)

        # Find new items
        new_items = set(current_identifiers.keys()) - set(previous_identifiers.keys())
        if new_items:
            changes['new_items'] = list(new_items)
            changes['has_changes'] = True

        # Find removed items
        removed_items = set(previous_identifiers.keys()) - set(current_identifiers.keys())
        if removed_items:
            changes['removed_items'] = list(removed_items)
            changes['has_changes'] = True

        # Find modified items
        common_items = set(current_identifiers.keys()) & set(previous_identifiers.keys())
        for item_id in common_items:
            if current_identifiers[item_id] != previous_identifiers[item_id]:
                changes['modified_items'].append(item_id)
                changes['has_changes'] = True

        changes['total_changes'] = len(changes['new_items']) + len(changes['modified_items']) + len(changes['removed_items'])

        return changes

    async def detect_all_changes(self) -> ChangeDetectionResult:
        """Detect changes across all monitored categories"""
        logger.info("Starting comprehensive change detection")

        # Load previous state
        previous_state = self.load_previous_state()

        # Fetch current data
        async with WFCDClient(cache_dir=str(self.cache_dir)) as client:
            current_data = {}

            for category in self.monitored_categories:
                try:
                    if category == 'weapons':
                        response = await client.get_weapons()
                    elif category == 'warframes':
                        response = await client.get_warframes()
                    elif category == 'mods':
                        response = await client.get_mods()
                    elif category == 'relics':
                        response = await client.get_relics()
                    else:
                        continue

                    current_data[category] = response
                    logger.info(f"Fetched current {category} data")

                except Exception as e:
                    logger.error(f"Failed to fetch {category} data: {e}")
                    current_data[category] = None

        # Detect changes for each category
        category_changes = {}
        total_changes = 0
        changed_categories = set()
        unchanged_categories = set()

        for category in self.monitored_categories:
            if category not in current_data or not current_data[category]:
                logger.warning(f"No current data for {category}, skipping")
                unchanged_categories.add(category)
                continue

            current_items = current_data[category].data
            if isinstance(current_items, dict) and 'items' in current_items:
                current_items = current_items['items']
            elif not isinstance(current_items, list):
                current_items = [current_items] if current_items else []

            changes = self.detect_category_changes(category, current_items, previous_state)
            category_changes[category] = changes

            if changes['has_changes']:
                changed_categories.add(category)
                total_changes += changes['total_changes']
                logger.info(f"Changes detected in {category}: {changes['total_changes']} items affected")
            else:
                unchanged_categories.add(category)
                logger.info(f"No changes detected in {category}")

        # Save current state
        self.save_current_state(current_data)

        # Aggregate results
        new_items = {cat: changes['new_items'] for cat, changes in category_changes.items() if changes['new_items']}
        modified_items = {cat: changes['modified_items'] for cat, changes in category_changes.items() if changes['modified_items']}
        removed_items = {cat: changes['removed_items'] for cat, changes in category_changes.items() if changes['removed_items']}

        has_changes = len(changed_categories) > 0

        # Generate summary
        summary_parts = []
        if has_changes:
            summary_parts.append(f"Changes detected in {len(changed_categories)} categories")
            summary_parts.append(f"Total items affected: {total_changes}")

            if new_items:
                total_new = sum(len(items) for items in new_items.values())
                summary_parts.append(f"New items: {total_new}")

            if modified_items:
                total_modified = sum(len(items) for items in modified_items.values())
                summary_parts.append(f"Modified items: {total_modified}")

            if removed_items:
                total_removed = sum(len(items) for items in removed_items.values())
                summary_parts.append(f"Removed items: {total_removed}")

            # Determine change magnitude
            total_items = sum(len(current_data[cat].data) if current_data[cat] else 0
                             for cat in self.monitored_categories)

            if total_items > 0:
                change_percentage = total_changes / total_items
                if change_percentage >= self.major_update_threshold:
                    summary_parts.append("MAJOR UPDATE detected")
                elif change_percentage >= self.significant_change_threshold:
                    summary_parts.append("Significant update detected")
        else:
            summary_parts.append("No changes detected in any category")

        summary = "; ".join(summary_parts)

        result = ChangeDetectionResult(
            has_changes=has_changes,
            changed_categories=changed_categories,
            unchanged_categories=unchanged_categories,
            new_items=new_items,
            modified_items=modified_items,
            removed_items=removed_items,
            summary=summary,
            timestamp=datetime.now()
        )

        logger.info(f"Change detection complete: {summary}")
        return result

    def set_github_output(self, result: ChangeDetectionResult):
        """Set GitHub Actions outputs"""
        # For GitHub Actions integration
        github_output_file = os.environ.get('GITHUB_OUTPUT')

        outputs = {
            'changed': 'true' if result.has_changes else 'false',
            'categories': ','.join(sorted(result.changed_categories)),
            'summary': result.summary,
            'new_items_count': str(sum(len(items) for items in result.new_items.values())),
            'modified_items_count': str(sum(len(items) for items in result.modified_items.values())),
            'removed_items_count': str(sum(len(items) for items in result.removed_items.values()))
        }

        if github_output_file:
            try:
                with open(github_output_file, 'a', encoding='utf-8') as f:
                    for key, value in outputs.items():
                        f.write(f"{key}={value}\n")
                logger.info("GitHub Actions outputs set")
            except Exception as e:
                logger.error(f"Failed to set GitHub outputs: {e}")

        # Also output for shell scripts
        for key, value in outputs.items():
            print(f"::set-output name={key}::{value}")

# CLI interface
async def main():
    """CLI interface for change detection"""
    import argparse

    parser = argparse.ArgumentParser(description='Warframe Game Change Detector')
    parser.add_argument('--state-file', default='.game-state.json', help='State file path')
    parser.add_argument('--cache-dir', default='./cache', help='Cache directory')
    parser.add_argument('--output-format', choices=['json', 'text', 'github'], default='text',
                       help='Output format')
    parser.add_argument('--force-update', action='store_true', help='Force update detection')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize detector
    detector = GameChangeDetector(args.state_file, args.cache_dir)

    # Force update if requested
    if args.force_update:
        logger.info("Force update requested, removing previous state")
        if detector.state_file.exists():
            detector.state_file.unlink()

    # Detect changes
    result = await detector.detect_all_changes()

    # Output results
    if args.output_format == 'json':
        print(json.dumps(asdict(result), indent=2, default=str))
    elif args.output_format == 'github':
        detector.set_github_output(result)
    else:
        print(f"Change Detection Summary:")
        print(f"Has Changes: {result.has_changes}")
        print(f"Summary: {result.summary}")
        print(f"Changed Categories: {', '.join(sorted(result.changed_categories))}")

        if result.new_items:
            print(f"\nNew Items:")
            for category, items in result.new_items.items():
                print(f"  {category}: {len(items)} items")

        if result.modified_items:
            print(f"\nModified Items:")
            for category, items in result.modified_items.items():
                print(f"  {category}: {len(items)} items")

        if result.removed_items:
            print(f"\nRemoved Items:")
            for category, items in result.removed_items.items():
                print(f"  {category}: {len(items)} items")

    # Exit with appropriate code
    sys.exit(0 if result.has_changes else 1)

if __name__ == "__main__":
    asyncio.run(main())