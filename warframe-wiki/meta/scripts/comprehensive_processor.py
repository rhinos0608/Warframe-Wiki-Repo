#!/usr/bin/env python3
"""
Comprehensive Warframe Content Processor
Handles ALL 15,805+ items from the WFCD API across every game system
"""

import asyncio
import yaml
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import logging

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

class ComprehensiveWarframeProcessor:
    """
    Processes ALL Warframe content types from WFCD API into structured files
    Covers the complete game ecosystem: weapons, warframes, mods, fish, resources,
    nodes, enemies, skins, relics, gear, arcanes, and everything else
    """

    def __init__(self, output_dir: Path, image_dir: Path = None):
        self.output_dir = Path(output_dir)
        self.image_dir = Path(image_dir) if image_dir else self.output_dir / "images"

        # Create directories
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.image_dir.mkdir(exist_ok=True, parents=True)

        # Comprehensive category mappings for ALL content types
        self.category_mappings = {
            # Weapons
            'Rifle': 'weapons/primary',
            'Shotgun': 'weapons/primary',
            'Bow': 'weapons/primary',
            'Sniper Rifle': 'weapons/primary',
            'Assault Rifle': 'weapons/primary',
            'Pistol': 'weapons/secondary',
            'Thrown Knife': 'weapons/secondary',
            'Shotgun Sidearm': 'weapons/secondary',
            'Dual Pistols': 'weapons/secondary',
            'Melee': 'weapons/melee',
            'Nikana': 'weapons/melee',
            'Heavy Blade': 'weapons/melee',
            'Sword': 'weapons/melee',
            'Dagger': 'weapons/melee',
            'Staff': 'weapons/melee',
            'Polearm': 'weapons/melee',
            'Whip': 'weapons/melee',
            'Scythe': 'weapons/melee',
            'Hammer': 'weapons/melee',
            'Fist Weapon': 'weapons/melee',
            'Claws': 'weapons/melee',
            'Glaive': 'weapons/melee',
            'Nunchaku': 'weapons/melee',

            # Arch weapons
            'Arch-Gun': 'weapons/arch/gun',
            'Arch-Melee': 'weapons/arch/melee',

            # Warframes and variants
            'Warframe': 'warframes',
            'Archwing': 'warframes/archwing',
            'Necramech': 'warframes/necramech',

            # Mods
            'Warframe Mod': 'mods/warframe',
            'Primary Mod': 'mods/primary',
            'Secondary Mod': 'mods/secondary',
            'Melee Mod': 'mods/melee',
            'Shotgun Mod': 'mods/shotgun',
            'Rifle Mod': 'mods/rifle',
            'Pistol Mod': 'mods/pistol',
            'Companion Mod': 'mods/companion',
            'Riven Mod': 'mods/riven',
            'Peculiar Mod': 'mods/peculiar',
            'Stance Mod': 'mods/stance',
            'Mod': 'mods',

            # Resources and crafting
            'Resource': 'resources',
            'Mined Resource': 'resources/mining',
            'Fish Resource': 'resources/fishing',
            'Refined Resource': 'resources/refined',
            'Blueprint': 'resources/blueprints',
            'Component': 'resources/components',

            # Fish by region
            'Fish': 'fishing/all',
            'Cetus Fish': 'fishing/cetus',
            'Vallis Fish': 'fishing/vallis',
            'Deimos Fish': 'fishing/deimos',
            'Duviri Fish': 'fishing/duviri',

            # Locations and missions
            'Node': 'nodes',
            'Hub': 'nodes/hubs',
            'Relay': 'nodes/relays',
            'Dojo Room': 'nodes/dojo',

            # Enemies
            'Grineer': 'enemies/grineer',
            'Corpus': 'enemies/corpus',
            'Infested': 'enemies/infested',
            'Orokin': 'enemies/orokin',
            'Sentient': 'enemies/sentient',
            'Wild': 'enemies/wildlife',
            'Corrupted': 'enemies/corrupted',
            'Enemy': 'enemies',

            # Cosmetics and skins
            'Skin': 'cosmetics/skins',
            'Warframe Skin': 'cosmetics/skins/warframe',
            'Weapon Skin': 'cosmetics/skins/weapon',
            'Syandana': 'cosmetics/syandanas',
            'Armor': 'cosmetics/armor',
            'Helmet': 'cosmetics/helmets',
            'Animation': 'cosmetics/animations',
            'Sigil': 'cosmetics/sigils',
            'Color Picker': 'cosmetics/colors',
            'Fur Color': 'cosmetics/colors/fur',
            'Scene': 'cosmetics/captura',
            'Captura': 'cosmetics/captura',
            'Emotes': 'cosmetics/emotes',
            'Glyph': 'cosmetics/glyphs',

            # Relics and drops
            'Relic': 'relics',
            'Lith': 'relics/lith',
            'Meso': 'relics/meso',
            'Neo': 'relics/neo',
            'Axi': 'relics/axi',
            'Requiem': 'relics/requiem',

            # Gear and consumables
            'Gear': 'gear',
            'Key': 'gear/keys',
            'Consumable': 'gear/consumables',
            'Quest': 'story/quests',
            'Codex': 'lore/codex',

            # Companions
            'Sentinel': 'companions/sentinels',
            'Kubrow': 'companions/kubrow',
            'Kavat': 'companions/kavat',
            'Predasite': 'companions/predasite',
            'Vulpaphyla': 'companions/vulpaphyla',
            'Pet': 'companions',

            # Enhancements
            'Arcane': 'enhancements/arcanes',
            'Focus Lens': 'enhancements/focus',
            'Amp': 'enhancements/amps',
            'Zaw': 'weapons/zaw',
            'Kitgun': 'weapons/kitgun',

            # Railjack
            'Railjack': 'railjack',
            'Railjack Armament': 'railjack/armaments',
            'Railjack Component': 'railjack/components',
            'Avionic': 'railjack/avionics',
            'Plexus Mod': 'railjack/plexus',

            # Decorations and housing
            'Ship Decoration': 'housing/decorations',
            'Decoration': 'housing/decorations',
            'Orbiter': 'housing/orbiter',
            'Dojo Decoration': 'housing/dojo',

            # Special categories
            'Misc': 'misc',
            'Game Mode': 'modes',
            'Conclave': 'pvp/conclave',
            'Lunaro': 'pvp/lunaro',
        }

    def sanitize_filename(self, name: str) -> str:
        """Convert item name to safe filename"""
        # Remove or replace problematic characters
        safe_name = re.sub(r'[^\w\s-]', '', name.lower())
        safe_name = re.sub(r'\s+', '-', safe_name)
        safe_name = re.sub(r'-+', '-', safe_name)
        return safe_name.strip('-')

    def determine_category_path(self, item: Dict[str, Any]) -> str:
        """Determine file path category for any item type"""
        item_type = item.get('type', '').strip()
        category = item.get('category', '').strip()
        name = item.get('name', '').lower()

        # Primary mapping by type
        if item_type in self.category_mappings:
            return self.category_mappings[item_type]

        # Secondary mapping by category
        if category in self.category_mappings:
            return self.category_mappings[category]

        # Special logic for complex types

        # Fish categorization by region
        if item_type == 'Fish':
            if 'cetus' in name or 'plains' in name or 'ostron' in name:
                return 'fishing/cetus'
            elif 'vallis' in name or 'fortuna' in name or 'corpus' in name:
                return 'fishing/vallis'
            elif 'deimos' in name or 'necraloid' in name or 'entrati' in name:
                return 'fishing/deimos'
            elif 'duviri' in name:
                return 'fishing/duviri'
            else:
                return 'fishing/all'

        # Resource categorization
        if item_type == 'Resource':
            if any(word in name for word in ['ore', 'mineral', 'gem', 'mining']):
                return 'resources/mining'
            elif any(word in name for word in ['fish', 'bait', 'fishing']):
                return 'resources/fishing'
            elif any(word in name for word in ['refined', 'alloy', 'polymer']):
                return 'resources/refined'
            else:
                return 'resources'

        # Node categorization by name patterns
        if item_type == 'Node':
            if any(word in name for word in ['relay', 'hub', 'bazaar']):
                return 'nodes/hubs'
            elif 'dojo' in name:
                return 'nodes/dojo'
            else:
                return 'nodes'

        # Enemy categorization
        if 'enemy' in item_type.lower() or category.lower() in ['grineer', 'corpus', 'infested']:
            if 'grineer' in name or 'grineer' in category.lower():
                return 'enemies/grineer'
            elif 'corpus' in name or 'corpus' in category.lower():
                return 'enemies/corpus'
            elif 'infested' in name or 'infested' in category.lower():
                return 'enemies/infested'
            elif 'sentient' in name:
                return 'enemies/sentient'
            elif 'orokin' in name:
                return 'enemies/orokin'
            else:
                return 'enemies'

        # Relic subcategorization
        if item_type == 'Relic':
            relic_name = name.lower()
            if relic_name.startswith('lith'):
                return 'relics/lith'
            elif relic_name.startswith('meso'):
                return 'relics/meso'
            elif relic_name.startswith('neo'):
                return 'relics/neo'
            elif relic_name.startswith('axi'):
                return 'relics/axi'
            elif 'requiem' in relic_name:
                return 'relics/requiem'
            else:
                return 'relics'

        # Skin categorization
        if item_type == 'Skin':
            if any(word in name for word in ['warframe', 'frame']):
                return 'cosmetics/skins/warframe'
            elif any(word in name for word in ['weapon', 'rifle', 'pistol', 'melee']):
                return 'cosmetics/skins/weapon'
            else:
                return 'cosmetics/skins'

        # Fallback based on common patterns
        if 'mod' in item_type.lower():
            return 'mods'
        elif 'weapon' in item_type.lower():
            return 'weapons'
        elif 'companion' in item_type.lower():
            return 'companions'
        elif 'arcane' in item_type.lower():
            return 'enhancements/arcanes'

        # Final fallback
        return 'misc'

    def extract_common_metadata(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata common to all item types"""
        metadata = {
            'name': item.get('name', 'Unknown'),
            'type': item.get('type', ''),
            'category': item.get('category', ''),
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
                if acquisition:
                    metadata['acquisition'] = acquisition

        # Add tags based on type and category
        tags = []
        if item.get('type'):
            tags.append(item['type'])
        if item.get('category') and item.get('category') != item.get('type'):
            tags.append(item['category'])

        if tags:
            metadata['tags'] = tags

        # Add rarity if present
        if 'rarity' in item:
            metadata['rarity'] = item['rarity']

        # Add mastery requirement if present
        if 'masteryReq' in item:
            metadata['mastery_rank'] = int(item['masteryReq'])

        return metadata

    def extract_type_specific_metadata(self, item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
        """Extract metadata specific to item type"""
        metadata = {}

        # Weapon-specific
        if 'weapon' in item_type.lower() or item_type in ['Rifle', 'Pistol', 'Shotgun', 'Bow', 'Melee']:
            if 'fireRate' in item:
                metadata['fire_rate'] = float(item['fireRate'])
            if 'criticalChance' in item:
                metadata['crit_chance'] = float(item['criticalChance'])
            if 'criticalMultiplier' in item:
                metadata['crit_multiplier'] = float(item['criticalMultiplier'])
            if 'statusChance' in item:
                metadata['status_chance'] = float(item['statusChance'])
            if 'disposition' in item:
                metadata['disposition'] = int(item['disposition'])

        # Fish-specific
        elif item_type == 'Fish':
            if 'rare' in item:
                metadata['rare'] = bool(item['rare'])
            if 'small' in item:
                metadata['size_small'] = item['small']
            if 'medium' in item:
                metadata['size_medium'] = item['medium']
            if 'large' in item:
                metadata['size_large'] = item['large']
            if 'bait' in item:
                metadata['bait'] = item['bait']
            if 'time' in item:
                metadata['time_of_day'] = item['time']

        # Node-specific
        elif item_type == 'Node':
            if 'systemName' in item:
                metadata['system'] = item['systemName']
            if 'planet' in item:
                metadata['planet'] = item['planet']
            if 'type' in item:
                metadata['mission_type'] = item['type']
            if 'enemy' in item:
                metadata['faction'] = item['enemy']
            if 'minEnemyLevel' in item:
                metadata['min_level'] = int(item['minEnemyLevel'])
            if 'maxEnemyLevel' in item:
                metadata['max_level'] = int(item['maxEnemyLevel'])

        # Enemy-specific
        elif item_type in ['Grineer', 'Corpus', 'Infested', 'Enemy']:
            if 'health' in item:
                metadata['health'] = item['health']
            if 'armor' in item:
                metadata['armor'] = item['armor']
            if 'shield' in item:
                metadata['shield'] = item['shield']
            if 'cloneFleshHP' in item:
                metadata['clone_flesh_hp'] = item['cloneFleshHP']

        # Relic-specific
        elif item_type == 'Relic':
            if 'tier' in item:
                metadata['tier'] = item['tier']
            if 'rewards' in item:
                metadata['rewards'] = item['rewards']

        # Mod-specific
        elif 'mod' in item_type.lower():
            if 'polarity' in item:
                metadata['polarity'] = item['polarity'].lower()
            if 'rarity' in item:
                metadata['rarity'] = item['rarity']
            if 'baseDrain' in item:
                metadata['drain'] = int(item['baseDrain'])
            if 'maxRank' in item:
                metadata['max_rank'] = int(item['maxRank'])

        return metadata

    def generate_type_specific_content(self, item: Dict[str, Any], item_type: str) -> str:
        """Generate content specific to item type"""
        content = ""

        if item_type == 'Fish':
            content += self.generate_fish_content(item)
        elif item_type == 'Node':
            content += self.generate_node_content(item)
        elif item_type in ['Grineer', 'Corpus', 'Infested', 'Enemy']:
            content += self.generate_enemy_content(item)
        elif item_type == 'Relic':
            content += self.generate_relic_content(item)
        elif item_type == 'Resource':
            content += self.generate_resource_content(item)
        elif item_type == 'Gear':
            content += self.generate_gear_content(item)
        elif item_type == 'Skin':
            content += self.generate_cosmetic_content(item)
        elif 'weapon' in item_type.lower() or item_type in ['Rifle', 'Pistol', 'Shotgun', 'Bow', 'Melee']:
            content += self.generate_weapon_content(item)

        return content

    def generate_fish_content(self, fish: Dict[str, Any]) -> str:
        """Generate fish-specific content"""
        content = "## Overview\n\n"
        name = fish.get('name', 'Unknown Fish')
        content += f"**{name}** is a fish species"

        if 'location' in fish or 'bait' in fish:
            content += " found in Warframe's fishing locations"

        content += ".\n\n"

        # Fishing details
        if 'bait' in fish or 'time' in fish or 'small' in fish:
            content += "## Fishing Details\n\n"

            if 'bait' in fish:
                content += f"**Bait Required:** {fish['bait']}\n\n"

            if 'time' in fish:
                content += f"**Time of Day:** {fish['time']}\n\n"

            if any(k in fish for k in ['small', 'medium', 'large']):
                content += "### Size Variants\n\n"
                for size in ['small', 'medium', 'large']:
                    if size in fish:
                        content += f"- **{size.title()}:** {fish[size]}\n"
                content += "\n"

        return content

    def generate_node_content(self, node: Dict[str, Any]) -> str:
        """Generate node/mission-specific content"""
        content = "## Mission Details\n\n"

        if 'type' in node:
            content += f"**Mission Type:** {node['type']}\n\n"

        if 'systemName' in node:
            content += f"**System:** {node['systemName']}\n\n"

        if 'enemy' in node:
            content += f"**Faction:** {node['enemy']}\n\n"

        if 'minEnemyLevel' in node and 'maxEnemyLevel' in node:
            content += f"**Enemy Level:** {node['minEnemyLevel']}-{node['maxEnemyLevel']}\n\n"

        if 'archwingRequired' in node and node['archwingRequired']:
            content += "**Special Requirements:** Archwing Required\n\n"

        return content

    def generate_enemy_content(self, enemy: Dict[str, Any]) -> str:
        """Generate enemy-specific content"""
        content = "## Enemy Information\n\n"

        # Health/armor stats if available
        if any(k in enemy for k in ['health', 'armor', 'shield']):
            content += "### Combat Stats\n\n"
            if 'health' in enemy:
                content += f"**Health:** {enemy['health']}\n\n"
            if 'armor' in enemy:
                content += f"**Armor:** {enemy['armor']}\n\n"
            if 'shield' in enemy:
                content += f"**Shield:** {enemy['shield']}\n\n"

        return content

    def generate_relic_content(self, relic: Dict[str, Any]) -> str:
        """Generate relic-specific content"""
        content = "## Relic Information\n\n"

        if 'tier' in relic:
            content += f"**Tier:** {relic['tier']}\n\n"

        if 'rewards' in relic and isinstance(relic['rewards'], list):
            content += "## Rewards\n\n"
            content += "| Item | Rarity | Chance |\n|------|---------|--------|\n"
            for reward in relic['rewards']:
                if isinstance(reward, dict):
                    item_name = reward.get('itemName', 'Unknown')
                    rarity = reward.get('rarity', 'Unknown')
                    chance = reward.get('chance', 'Unknown')
                    content += f"| {item_name} | {rarity} | {chance} |\n"
            content += "\n"

        return content

    def generate_resource_content(self, resource: Dict[str, Any]) -> str:
        """Generate resource-specific content"""
        content = "## Resource Information\n\n"

        resource_type = resource.get('type', 'Resource')
        content += f"**{resource['name']}** is a {resource_type.lower()}"

        if 'category' in resource:
            content += f" in the {resource['category']} category"

        content += ".\n\n"

        return content

    def generate_gear_content(self, gear: Dict[str, Any]) -> str:
        """Generate gear-specific content"""
        content = "## Gear Information\n\n"

        content += f"**{gear['name']}** is a gear item"

        if 'consumable' in gear and gear['consumable']:
            content += " that can be consumed during missions"

        content += ".\n\n"

        return content

    def generate_cosmetic_content(self, cosmetic: Dict[str, Any]) -> str:
        """Generate cosmetic-specific content"""
        content = "## Cosmetic Information\n\n"

        cosmetic_type = cosmetic.get('type', 'Cosmetic')
        content += f"**{cosmetic['name']}** is a {cosmetic_type.lower()} cosmetic item"

        if 'category' in cosmetic:
            content += f" for {cosmetic['category']}"

        content += ".\n\n"

        return content

    def generate_weapon_content(self, weapon: Dict[str, Any]) -> str:
        """Generate weapon-specific content"""
        content = "## Overview\n\n"

        weapon_type = weapon.get('type', 'weapon')
        content += f"**{weapon['name']}** is a {weapon_type.lower()}"

        if 'slot' in weapon:
            content += f" that occupies the {weapon['slot'].lower()} slot"

        content += ".\n\n"

        # Stats section if available
        if any(k in weapon for k in ['fireRate', 'criticalChance', 'statusChance']):
            content += "## Characteristics\n\n"

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

        return content

    async def process_item(self, item: Dict[str, Any]) -> ProcessedItem:
        """Process any item type into structured format"""

        # Extract common metadata
        metadata = self.extract_common_metadata(item)

        # Add type-specific metadata
        item_type = item.get('type', '')
        type_specific = self.extract_type_specific_metadata(item, item_type)
        metadata.update(type_specific)

        # Generate base content
        name = item.get('name', 'Unknown')
        description = item.get('description', '')

        content = f"# {name}\n\n"
        if description:
            content += f"{description}\n\n"

        # Add type-specific content
        type_content = self.generate_type_specific_content(item, item_type)
        content += type_content

        # Add acquisition information
        if 'drops' in item or 'acquisition' in metadata:
            content += "## Acquisition\n\n"
            if 'acquisition' in metadata:
                content += "Available from:\n"
                for source in metadata['acquisition']:
                    content += f"- {source}\n"
                content += "\n"

        # Determine file path
        category_path = self.determine_category_path(item)
        safe_filename = self.sanitize_filename(name)
        file_path = self.output_dir / category_path / f"{safe_filename}.md"

        # Extract image URLs
        image_urls = []
        if 'imageName' in item:
            image_urls.append(f"https://cdn.warframestat.us/img/{item['imageName']}")

        return ProcessedItem(
            category=category_path,
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

    async def process_all_items(self, items_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process all items from the WFCD dataset"""
        logger.info(f"Processing {len(items_data)} items comprehensively")

        category_counts = {}
        processed_count = 0

        for item in items_data:
            try:
                processed_item = await self.process_item(item)
                await self.write_item_file(processed_item)

                # Track by category
                category = processed_item.category
                category_counts[category] = category_counts.get(category, 0) + 1

                processed_count += 1

                if processed_count % 1000 == 0:
                    logger.info(f"Processed {processed_count} items...")

            except Exception as e:
                logger.error(f"Failed to process item {item.get('name', 'unknown')}: {e}")

        logger.info(f"Comprehensive processing complete: {processed_count} items")
        return category_counts

# CLI interface
async def main():
    """CLI interface for comprehensive processing"""
    import argparse

    parser = argparse.ArgumentParser(description='Comprehensive Warframe Content Processor')
    parser.add_argument('--input', required=True, help='Input JSON file from WFCD client')
    parser.add_argument('--output', required=True, help='Output directory for processed files')
    parser.add_argument('--images', help='Images directory')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load input data
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Get all items from the comprehensive dataset
    items = data['items_all']['All']['data']
    logger.info(f"Loaded {len(items)} items for comprehensive processing")

    # Process all items
    processor = ComprehensiveWarframeProcessor(args.output, args.images)
    category_counts = await processor.process_all_items(items)

    # Summary
    total_items = sum(category_counts.values())
    print(f"\nComprehensive processing complete: {total_items} items processed")
    print(f"\nItems by category:")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count}")

if __name__ == "__main__":
    asyncio.run(main())