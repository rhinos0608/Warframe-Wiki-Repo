#!/usr/bin/env python3
"""
Warframe Data Processor
Converts WFCD API data to structured YAML frontmatter + Markdown files
"""

import asyncio
import yaml
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
import logging
from urllib.parse import quote

from wfcd_client import WFCDClient, APIResponse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ProcessedItem:
    """Container for processed item data"""
    category: str
    file_path: Path
    metadata: Dict[str, Any]
    content: str
    image_urls: List[str] = None

class WFDataProcessor:
    """
    Converts WFCD API data to structured YAML frontmatter + Markdown files
    """

    def __init__(self, output_dir: Path, image_dir: Path = None):
        self.output_dir = Path(output_dir)
        self.image_dir = Path(image_dir) if image_dir else self.output_dir / "images"

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.image_dir.mkdir(exist_ok=True, parents=True)

        # Category mappings
        self.category_mappings = {
            'Primary': 'weapons/primary',
            'Secondary': 'weapons/secondary',
            'Melee': 'weapons/melee',
            'Warframes': 'warframes',
            'Mods': 'mods',
            'Relics': 'relics',
            'Resources': 'resources',
            'Companions': 'companions',
            'Arcanes': 'mods/arcanes',
            'Fish': 'resources/fish',
            'Sentinels': 'companions/sentinels',
            'Pets': 'companions/pets'
        }

    def sanitize_filename(self, name: str) -> str:
        """Convert item name to safe filename"""
        # Remove or replace problematic characters
        safe_name = re.sub(r'[^\w\s-]', '', name.lower())
        safe_name = re.sub(r'\s+', '-', safe_name)
        safe_name = re.sub(r'-+', '-', safe_name)
        return safe_name.strip('-')

    def determine_category_path(self, item: Dict[str, Any]) -> str:
        """Determine the file path category for an item"""
        item_type = item.get('type', '').strip()
        category = item.get('category', '').strip()

        # Primary categorization by type
        if item_type in self.category_mappings:
            return self.category_mappings[item_type]

        # Secondary categorization by category
        if category in self.category_mappings:
            return self.category_mappings[category]

        # Weapon-specific logic
        if 'weapon' in item_type.lower():
            if 'primary' in item_type.lower():
                return 'weapons/primary'
            elif 'secondary' in item_type.lower():
                return 'weapons/secondary'
            elif 'melee' in item_type.lower():
                return 'weapons/melee'
            else:
                return 'weapons'

        # Default categorization
        if 'mod' in item_type.lower():
            return 'mods'
        elif 'relic' in item_type.lower():
            return 'relics'
        elif 'resource' in item_type.lower():
            return 'resources'
        elif 'warframe' in item_type.lower():
            return 'warframes'

        # Fallback
        return 'misc'

    def extract_damage_data(self, item: Dict[str, Any]) -> Optional[Dict[str, Union[int, float]]]:
        """Extract and normalize damage data from weapon"""
        damage_data = {}

        # Look for damage in various possible fields
        damage_fields = ['damage', 'totalDamage', 'attacks']

        for field in damage_fields:
            if field in item:
                damage_info = item[field]

                if isinstance(damage_info, dict):
                    # Extract physical damage types
                    for damage_type in ['impact', 'puncture', 'slash']:
                        if damage_type in damage_info:
                            damage_data[damage_type.title()] = float(damage_info[damage_type])

                    # Extract elemental damage types
                    for damage_type in ['heat', 'cold', 'electricity', 'toxin', 'blast', 'corrosive', 'gas', 'magnetic', 'radiation', 'viral']:
                        if damage_type in damage_info:
                            damage_data[damage_type.title()] = float(damage_info[damage_type])

                elif isinstance(damage_info, (int, float)):
                    damage_data['Total'] = float(damage_info)

        return damage_data if damage_data else None

    def extract_weapon_stats(self, weapon: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize weapon statistics"""
        stats = {}

        # Basic stats mapping
        stat_mappings = {
            'fireRate': 'fire_rate',
            'accuracy': 'accuracy',
            'criticalChance': 'crit_chance',
            'criticalMultiplier': 'crit_multiplier',
            'statusChance': 'status_chance',
            'magazineSize': 'magazine_size',
            'reloadTime': 'reload_time',
            'disposition': 'disposition',
            'masteryReq': 'mastery_rank',
            'projectile': 'projectile_type',
            'trigger': 'trigger_type'
        }

        for api_key, our_key in stat_mappings.items():
            if api_key in weapon:
                value = weapon[api_key]
                if isinstance(value, (int, float)):
                    stats[our_key] = float(value)
                else:
                    stats[our_key] = value

        # Extract damage data
        damage_data = self.extract_damage_data(weapon)
        if damage_data:
            stats['damage_types'] = damage_data

        # Extract polarities
        if 'polarities' in weapon:
            polarities = weapon['polarities']
            if isinstance(polarities, list):
                stats['polarities'] = [pol.lower() for pol in polarities if pol]

        # Extract build recommendations (if available)
        if 'buildPresets' in weapon or 'recommendedMods' in weapon:
            builds = self.extract_build_recommendations(weapon)
            if builds:
                stats['recommended_builds'] = builds

        return stats

    def extract_build_recommendations(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract build recommendations from item data"""
        builds = []

        # Check for build presets
        if 'buildPresets' in item:
            for preset in item['buildPresets']:
                build = {
                    'name': preset.get('name', 'Build'),
                    'description': preset.get('description', ''),
                    'mods': []
                }

                if 'mods' in preset:
                    build['mods'] = [mod.get('name', mod) for mod in preset['mods']]

                builds.append(build)

        # Check for recommended mods
        elif 'recommendedMods' in item:
            build = {
                'name': 'Recommended Build',
                'mods': item['recommendedMods']
            }
            builds.append(build)

        return builds

    def extract_warframe_stats(self, warframe: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize Warframe statistics"""
        stats = {}

        # Basic stats
        if 'health' in warframe:
            stats['health'] = float(warframe['health'])
        if 'shield' in warframe:
            stats['shield'] = float(warframe['shield'])
        if 'armor' in warframe:
            stats['armor'] = float(warframe['armor'])
        if 'energy' in warframe:
            stats['energy'] = float(warframe['energy'])
        if 'sprint' in warframe:
            stats['sprint_speed'] = float(warframe['sprint'])

        # Abilities
        if 'abilities' in warframe:
            abilities = []
            for ability in warframe['abilities']:
                ability_data = {
                    'name': ability.get('name', ''),
                    'description': ability.get('description', ''),
                    'energy_cost': ability.get('cost', 0)
                }
                abilities.append(ability_data)
            stats['abilities'] = abilities

        # Mastery requirement
        if 'masteryReq' in warframe:
            stats['mastery_rank'] = int(warframe['masteryReq'])

        return stats

    def extract_mod_stats(self, mod: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize mod statistics"""
        stats = {}

        if 'polarity' in mod:
            stats['polarity'] = mod['polarity'].lower()

        if 'rarity' in mod:
            stats['rarity'] = mod['rarity']

        if 'baseDrain' in mod:
            stats['drain'] = int(mod['baseDrain'])

        if 'maxRank' in mod:
            stats['max_rank'] = int(mod['maxRank'])

        # Mod effects
        if 'levelStats' in mod:
            stats['effects'] = mod['levelStats']

        return stats

    def extract_common_metadata(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract common metadata fields from any item"""
        metadata = {
            'name': item.get('name', 'Unknown'),
            'type': item.get('type', ''),
            'description': item.get('description', ''),
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'source': 'WFCD'
        }

        # Add image information
        if 'imageName' in item:
            metadata['image'] = f"../images/{item['imageName']}"

        # Add tradable status
        if 'tradable' in item:
            metadata['tradable'] = bool(item['tradable'])

        # Add introduction info
        if 'introduced' in item:
            intro = item['introduced']
            if isinstance(intro, dict):
                if 'date' in intro:
                    metadata['release_date'] = intro['date']
                if 'version' in intro:
                    metadata['release_version'] = intro['version']

        # Add drop information
        if 'drops' in item:
            drops = item['drops']
            if isinstance(drops, list) and drops:
                acquisition = []
                for drop in drops:
                    if isinstance(drop, dict) and 'location' in drop:
                        acquisition.append(drop['location'])
                    elif isinstance(drop, str):
                        acquisition.append(drop)
                metadata['acquisition'] = acquisition

        # Add category tags
        if 'category' in item:
            metadata['tags'] = [item['category']]

        return metadata

    def generate_content_description(self, item: Dict[str, Any], item_type: str) -> str:
        """Generate markdown content description for item"""
        name = item.get('name', 'Unknown')
        description = item.get('description', '')

        content = f"# {name}\n\n"

        if description:
            content += f"{description}\n\n"

        # Add type-specific content
        if item_type in ['Primary', 'Secondary', 'Melee']:
            content += self.generate_weapon_content(item)
        elif item_type == 'Warframes':
            content += self.generate_warframe_content(item)
        elif item_type == 'Mods':
            content += self.generate_mod_content(item)
        elif item_type == 'Relics':
            content += self.generate_relic_content(item)

        # Add acquisition information
        if 'drops' in item or 'acquisition' in item:
            content += "## Acquisition\n\n"
            if 'drops' in item:
                content += "Available from:\n"
                for drop in item['drops']:
                    if isinstance(drop, dict):
                        location = drop.get('location', 'Unknown')
                        chance = drop.get('chance', '')
                        if chance:
                            content += f"- {location} ({chance}% chance)\n"
                        else:
                            content += f"- {location}\n"
                    else:
                        content += f"- {drop}\n"
                content += "\n"

        return content

    def generate_weapon_content(self, weapon: Dict[str, Any]) -> str:
        """Generate weapon-specific content"""
        content = "## Overview\n\n"

        weapon_type = weapon.get('type', 'weapon')
        content += f"The **{weapon['name']}** is a {weapon_type.lower()} weapon"

        if 'slot' in weapon:
            content += f" that occupies the {weapon['slot'].lower()} slot"

        content += ".\n\n"

        # Add characteristics section
        content += "## Characteristics\n\n"

        # Advantages
        advantages = []
        if weapon.get('criticalChance', 0) > 0.25:
            advantages.append("High critical chance")
        if weapon.get('statusChance', 0) > 0.25:
            advantages.append("High status chance")
        if weapon.get('fireRate', 0) > 10:
            advantages.append("High fire rate")

        if advantages:
            content += "### Advantages\n"
            for advantage in advantages:
                content += f"- {advantage}\n"
            content += "\n"

        # Add notes section
        if 'patchlogs' in weapon or 'notes' in weapon:
            content += "## Notes\n\n"
            if 'notes' in weapon:
                for note in weapon['notes']:
                    content += f"- {note}\n"
                content += "\n"

        return content

    def generate_warframe_content(self, warframe: Dict[str, Any]) -> str:
        """Generate Warframe-specific content"""
        content = "## Overview\n\n"

        content += f"**{warframe['name']}** is a Warframe"

        if 'description' in warframe:
            content += f" {warframe['description']}\n\n"

        # Abilities section
        if 'abilities' in warframe:
            content += "## Abilities\n\n"
            for i, ability in enumerate(warframe['abilities'], 1):
                name = ability.get('name', f'Ability {i}')
                description = ability.get('description', 'No description available')
                content += f"### {name}\n{description}\n\n"

        return content

    def generate_mod_content(self, mod: Dict[str, Any]) -> str:
        """Generate mod-specific content"""
        content = "## Overview\n\n"

        mod_type = mod.get('type', 'mod')
        content += f"**{mod['name']}** is a {mod_type.lower()}"

        if 'polarity' in mod:
            content += f" with {mod['polarity']} polarity"

        content += ".\n\n"

        # Effects section
        if 'levelStats' in mod:
            content += "## Effects\n\n"
            content += "| Rank | Effects |\n|------|----------|\n"
            for rank, stats in enumerate(mod['levelStats']):
                effects = ', '.join([f"{k}: {v}" for k, v in stats.items()])
                content += f"| {rank} | {effects} |\n"
            content += "\n"

        return content

    def generate_relic_content(self, relic: Dict[str, Any]) -> str:
        """Generate relic-specific content"""
        content = "## Overview\n\n"

        content += f"**{relic['name']}** is a Void Relic"

        if 'tier' in relic:
            content += f" of {relic['tier']} tier"

        content += ".\n\n"

        # Rewards section
        if 'rewards' in relic:
            content += "## Rewards\n\n"
            content += "| Item | Rarity | Chance |\n|------|---------|--------|\n"
            for reward in relic['rewards']:
                item_name = reward.get('itemName', 'Unknown')
                rarity = reward.get('rarity', 'Unknown')
                chance = reward.get('chance', 'Unknown')
                content += f"| {item_name} | {rarity} | {chance} |\n"
            content += "\n"

        return content

    async def process_item(self, item: Dict[str, Any], category: str) -> ProcessedItem:
        """Process a single item into structured format"""
        # Extract common metadata
        metadata = self.extract_common_metadata(item)

        # Add category-specific stats
        if category in ['Primary', 'Secondary', 'Melee']:
            weapon_stats = self.extract_weapon_stats(item)
            metadata.update(weapon_stats)
        elif category == 'Warframes':
            warframe_stats = self.extract_warframe_stats(item)
            metadata.update(warframe_stats)
        elif category == 'Mods':
            mod_stats = self.extract_mod_stats(item)
            metadata.update(mod_stats)

        # Generate content
        content = self.generate_content_description(item, category)

        # Determine file path
        category_path = self.determine_category_path(item)
        safe_filename = self.sanitize_filename(item.get('name', 'unknown'))
        file_path = self.output_dir / category_path / f"{safe_filename}.md"

        # Extract image URLs
        image_urls = []
        if 'imageName' in item:
            image_urls.append(f"https://cdn.warframestat.us/img/{item['imageName']}")

        return ProcessedItem(
            category=category,
            file_path=file_path,
            metadata=metadata,
            content=content,
            image_urls=image_urls
        )

    async def write_item_file(self, processed_item: ProcessedItem):
        """Write processed item to file"""
        # Ensure directory exists
        processed_item.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create YAML frontmatter + Markdown content
        frontmatter = "---\n"
        frontmatter += yaml.dump(processed_item.metadata, default_flow_style=False, allow_unicode=True)
        frontmatter += "---\n\n"

        full_content = frontmatter + processed_item.content

        # Write to file
        with open(processed_item.file_path, 'w', encoding='utf-8') as f:
            f.write(full_content)

        logger.debug(f"Wrote file: {processed_item.file_path}")

    async def process_api_response(self, response: APIResponse, category: str) -> List[ProcessedItem]:
        """Process an entire API response"""
        if not response or not response.data:
            logger.warning(f"No data in response for category: {category}")
            return []

        processed_items = []
        items = response.data

        # Handle different response formats
        if isinstance(items, dict):
            if 'items' in items:
                items = items['items']
            elif category in items:
                items = items[category]
            else:
                # Single item response
                items = [items]

        if not isinstance(items, list):
            logger.warning(f"Unexpected response format for category: {category}")
            return []

        logger.info(f"Processing {len(items)} items for category: {category}")

        # Process each item
        for item in items:
            try:
                processed_item = await self.process_item(item, category)
                processed_items.append(processed_item)
            except Exception as e:
                logger.error(f"Failed to process item {item.get('name', 'unknown')}: {e}")

        return processed_items

    async def batch_process_all_data(self, api_data: Dict[str, APIResponse]) -> Dict[str, List[ProcessedItem]]:
        """Process all API data into structured files"""
        logger.info("Starting batch processing of all API data")

        all_processed = {}

        # Define processing tasks
        processing_tasks = [
            ('warframes', 'Warframes'),
            ('weapons', 'Weapons'),
            ('mods', 'Mods'),
            ('relics', 'Relics')
        ]

        for api_key, category in processing_tasks:
            if api_key in api_data and api_data[api_key]:
                logger.info(f"Processing {category} data")
                processed_items = await self.process_api_response(api_data[api_key], category)
                all_processed[category] = processed_items

                # Write all files for this category
                for item in processed_items:
                    await self.write_item_file(item)

                logger.info(f"Completed processing {len(processed_items)} {category} items")

        # Process items_all if available (contains everything)
        if 'items_all' in api_data and api_data['items_all']:
            logger.info("Processing comprehensive items data")
            # This might contain items not in other categories
            # Could be processed separately or used to fill gaps

        logger.info(f"Batch processing complete. Processed {sum(len(items) for items in all_processed.values())} items total")
        return all_processed

# CLI interface
async def main():
    """CLI interface for data processing"""
    import argparse

    parser = argparse.ArgumentParser(description='Warframe Data Processor')
    parser.add_argument('--input', required=True, help='Input JSON file from WFCD client')
    parser.add_argument('--output', required=True, help='Output directory for processed files')
    parser.add_argument('--images', help='Images directory')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load input data
    with open(args.input, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)

    # Convert to APIResponse objects
    api_data = {}
    for key, value in raw_data.items():
        if value:
            api_data[key] = APIResponse(
                data=value.get('data') if isinstance(value, dict) and 'data' in value else value,
                timestamp=datetime.now()
            )

    # Process data
    processor = WFDataProcessor(args.output, args.images)
    processed_data = await processor.batch_process_all_data(api_data)

    # Summary
    total_items = sum(len(items) for items in processed_data.values())
    print(f"Processing complete: {total_items} items processed")
    for category, items in processed_data.items():
        print(f"  {category}: {len(items)} items")

if __name__ == "__main__":
    asyncio.run(main())