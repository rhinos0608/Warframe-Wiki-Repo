#!/usr/bin/env python3
"""
Warframe Vector Database Population Script
Loads all processed Warframe wiki items into Qdrant vector database for enhanced search capabilities

This script:
1. Reads all markdown files from the processed wiki
2. Generates embeddings using SentenceTransformer
3. Stores vectors in Qdrant with comprehensive metadata
4. Creates optimized collections for different search types
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import hashlib
from datetime import datetime

# Vector and ML imports
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, CollectionParams
    from sentence_transformers import SentenceTransformer
    QDRANT_AVAILABLE = True
except ImportError:
    print("❌ Qdrant client or sentence-transformers not available")
    print("Install with: pip install qdrant-client sentence-transformers")
    sys.exit(1)

# Rich for beautiful progress displays
try:
    from rich.console import Console
    from rich.progress import Progress, TaskID, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WarframeVectorPopulator:
    """
    Populates Qdrant vector database with Warframe wiki content

    Features:
    - Multi-collection architecture for different search types
    - Optimized embeddings for semantic search
    - Comprehensive metadata storage
    - Incremental updates support
    - Performance metrics and reporting
    """

    def __init__(self, wiki_dir: Path, vector_db_path: str, model_name: str = "all-MiniLM-L6-v2"):
        self.wiki_dir = Path(wiki_dir)
        self.vector_db_path = vector_db_path
        self.model_name = model_name

        # Initialize clients
        if vector_db_path.startswith('http'):
            # Remote Qdrant instance
            self.client = QdrantClient(url=vector_db_path)
        else:
            # Local Qdrant instance or file-based
            self.client = QdrantClient(path=vector_db_path)

        self.embeddings_model = SentenceTransformer(model_name)

        # Collections to create
        self.collections = {
            "warframe_items": {
                "description": "All Warframe items with semantic search",
                "vector_size": 384,  # all-MiniLM-L6-v2 output size
                "distance": Distance.COSINE
            },
            "warframe_weapons": {
                "description": "Weapons with combat-focused metadata",
                "vector_size": 384,
                "distance": Distance.COSINE
            },
            "warframe_characters": {
                "description": "Warframes and companions with ability focus",
                "vector_size": 384,
                "distance": Distance.COSINE
            },
            "warframe_content": {
                "description": "General content including lore and descriptions",
                "vector_size": 384,
                "distance": Distance.DOT
            }
        }

        # Performance tracking
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_vectors": 0,
            "processing_time": 0,
            "categories": {}
        }

        # Rich console if available
        self.console = Console() if RICH_AVAILABLE else None

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

    async def initialize_collections(self):
        """Initialize Qdrant collections with optimized configurations"""
        self.log_info("Initializing Qdrant collections...")

        for collection_name, config in self.collections.items():
            try:
                # Check if collection exists
                try:
                    collection_info = self.client.get_collection(collection_name)
                    self.log_info(f"Collection '{collection_name}' already exists with {collection_info.points_count} points")
                    continue
                except Exception:
                    pass  # Collection doesn't exist, create it

                # Create collection with optimized parameters
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=config["vector_size"],
                        distance=config["distance"]
                    ),
                    optimizers_config=CollectionParams(
                        default_segment_number=2,
                        memmap_threshold=20000,
                    )
                )

                self.log_success(f"Created collection '{collection_name}': {config['description']}")

            except Exception as e:
                self.log_error(f"Failed to create collection '{collection_name}': {e}")
                raise

    def extract_yaml_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter from markdown content"""
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    markdown_content = parts[2].strip()
                    return metadata, markdown_content
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse YAML frontmatter: {e}")
                    return {}, content
        return {}, content

    def create_embedding_text(self, metadata: Dict[str, Any], markdown_content: str) -> str:
        """Create optimized text for embedding generation"""
        # Start with core item information
        embed_parts = []

        # Item name and type (high importance)
        if 'name' in metadata:
            embed_parts.append(f"Name: {metadata['name']}")

        if 'type' in metadata:
            embed_parts.append(f"Type: {metadata['type']}")

        if 'category' in metadata:
            embed_parts.append(f"Category: {metadata['category']}")

        # Description (if available)
        if 'description' in metadata:
            embed_parts.append(f"Description: {metadata['description']}")

        # Key stats for searchability
        if 'damage_types' in metadata:
            damage_info = metadata['damage_types']
            if isinstance(damage_info, dict):
                damage_list = [f"{k}: {v}" for k, v in damage_info.items()]
                embed_parts.append(f"Damage: {', '.join(damage_list)}")

        # Abilities for warframes
        if 'abilities' in metadata:
            abilities = metadata['abilities']
            if isinstance(abilities, list):
                ability_names = [ability.get('name', '') for ability in abilities if isinstance(ability, dict)]
                embed_parts.append(f"Abilities: {', '.join(ability_names)}")

        # Add markdown content (truncated for performance)
        if markdown_content:
            # Clean and truncate markdown content
            clean_content = markdown_content.replace('#', '').replace('*', '').replace('`', '')
            # Take first 300 characters to avoid embedding size issues
            if len(clean_content) > 300:
                clean_content = clean_content[:300] + "..."
            embed_parts.append(clean_content)

        return " | ".join(embed_parts)

    def determine_collections(self, metadata: Dict[str, Any], file_path: Path) -> List[str]:
        """Determine which collections this item should be added to"""
        collections = ["warframe_items"]  # All items go to main collection

        # Categorize by type and path
        file_path_str = str(file_path).lower()
        item_type = metadata.get('type', '').lower()
        category = metadata.get('category', '').lower()

        # Weapons collection
        if ('weapon' in file_path_str or
            'weapon' in item_type or
            any(weapon_type in item_type for weapon_type in ['rifle', 'pistol', 'shotgun', 'bow', 'launcher', 'melee'])):
            collections.append("warframe_weapons")

        # Characters collection (warframes, companions)
        if ('warframe' in file_path_str or
            'warframe' in item_type or
            'companion' in category or
            'pet' in category):
            collections.append("warframe_characters")

        # Content collection for items with substantial descriptions
        if metadata.get('description') or len(metadata.get('lore', '')) > 100:
            collections.append("warframe_content")

        return collections

    def create_comprehensive_payload(self, metadata: Dict[str, Any], markdown_content: str, file_path: Path) -> Dict[str, Any]:
        """Create comprehensive payload with all relevant metadata"""
        payload = {
            # Core identification
            "name": metadata.get('name', file_path.stem),
            "type": metadata.get('type', ''),
            "category": metadata.get('category', ''),
            "file_path": str(file_path.relative_to(self.wiki_dir)),

            # Content
            "description": metadata.get('description', ''),
            "content_preview": markdown_content[:200] + "..." if len(markdown_content) > 200 else markdown_content,

            # Timestamps
            "last_updated": metadata.get('last_updated', ''),
            "indexed_at": datetime.now().isoformat(),

            # Content hash for change detection
            "content_hash": hashlib.md5((str(metadata) + markdown_content).encode()).hexdigest(),

            # Stats (if applicable)
            "mastery_rank": metadata.get('mastery_rank'),
            "disposition": metadata.get('disposition'),
        }

        # Add damage information for weapons
        if 'damage_types' in metadata:
            payload["damage_types"] = metadata['damage_types']
            # Calculate total damage if possible
            if isinstance(metadata['damage_types'], dict):
                try:
                    total_damage = sum(float(v) for v in metadata['damage_types'].values() if isinstance(v, (int, float)))
                    payload["total_damage"] = total_damage
                except:
                    pass

        # Add weapon-specific stats
        weapon_stats = ['fire_rate', 'reload_time', 'crit_chance', 'crit_multiplier', 'status_chance', 'magazine_size']
        for stat in weapon_stats:
            if stat in metadata:
                payload[stat] = metadata[stat]

        # Add warframe-specific stats
        warframe_stats = ['health', 'shield', 'armor', 'energy', 'sprint_speed']
        for stat in warframe_stats:
            if stat in metadata:
                payload[stat] = metadata[stat]

        # Add abilities information
        if 'abilities' in metadata:
            abilities = metadata['abilities']
            if isinstance(abilities, list):
                payload["abilities"] = [
                    {
                        "name": ability.get('name', ''),
                        "description": ability.get('description', '')[:100] + "..." if len(ability.get('description', '')) > 100 else ability.get('description', '')
                    }
                    for ability in abilities if isinstance(ability, dict)
                ]
                payload["ability_count"] = len(abilities)

        # Add acquisition information
        if 'acquisition' in metadata:
            payload["acquisition"] = metadata['acquisition']

        # Add tags for better filtering
        tags = []
        if 'prime' in payload["name"].lower():
            tags.append("prime")
        if metadata.get('mastery_rank', 0) > 10:
            tags.append("high_mastery")
        if metadata.get('disposition', 3) <= 1:
            tags.append("low_disposition")

        payload["tags"] = tags

        return payload

    async def process_files(self) -> Dict[str, Any]:
        """Process all markdown files and create embeddings"""
        # Find all markdown files
        md_files = list(self.wiki_dir.rglob("*.md"))
        md_files = [f for f in md_files if f.name != "README.md"]

        self.stats["total_files"] = len(md_files)
        self.log_info(f"Found {len(md_files)} markdown files to process")

        # Progress tracking
        if RICH_AVAILABLE:
            with Progress(
                TextColumn("[bold blue]Processing", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                TimeElapsedColumn(),
                "•",
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Processing files...", total=len(md_files))
                return await self._process_files_with_progress(md_files, progress, task)
        else:
            return await self._process_files_simple(md_files)

    async def _process_files_with_progress(self, md_files: List[Path], progress: Progress, task: TaskID) -> Dict[str, Any]:
        """Process files with rich progress display"""
        processed_items = {}

        for i, md_file in enumerate(md_files):
            try:
                result = await self._process_single_file(md_file)
                if result:
                    processed_items[str(md_file)] = result
                    self.stats["processed_files"] += 1
                else:
                    self.stats["failed_files"] += 1

                progress.update(task, advance=1)

            except Exception as e:
                self.log_error(f"Error processing {md_file}: {e}")
                self.stats["failed_files"] += 1
                progress.update(task, advance=1)

        return processed_items

    async def _process_files_simple(self, md_files: List[Path]) -> Dict[str, Any]:
        """Process files with simple logging"""
        processed_items = {}

        for i, md_file in enumerate(md_files):
            if i % 100 == 0:
                self.log_info(f"Processing file {i+1}/{len(md_files)}: {md_file.name}")

            try:
                result = await self._process_single_file(md_file)
                if result:
                    processed_items[str(md_file)] = result
                    self.stats["processed_files"] += 1
                else:
                    self.stats["failed_files"] += 1

            except Exception as e:
                self.log_error(f"Error processing {md_file}: {e}")
                self.stats["failed_files"] += 1

        return processed_items

    async def _process_single_file(self, md_file: Path) -> Optional[Dict[str, Any]]:
        """Process a single markdown file"""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract frontmatter and content
            metadata, markdown_content = self.extract_yaml_frontmatter(content)

            if not metadata or 'name' not in metadata:
                return None

            # Track category statistics
            category = metadata.get('category', 'unknown')
            self.stats["categories"][category] = self.stats["categories"].get(category, 0) + 1

            # Create embedding text
            embed_text = self.create_embedding_text(metadata, markdown_content)

            # Generate embedding
            embedding = self.embeddings_model.encode([embed_text])[0]

            # Determine target collections
            target_collections = self.determine_collections(metadata, md_file)

            # Create comprehensive payload
            payload = self.create_comprehensive_payload(metadata, markdown_content, md_file)

            return {
                "metadata": metadata,
                "embedding": embedding.tolist(),
                "payload": payload,
                "collections": target_collections,
                "embed_text": embed_text[:200] + "..." if len(embed_text) > 200 else embed_text
            }

        except Exception as e:
            logger.error(f"Error processing {md_file}: {e}")
            return None

    async def upload_to_collections(self, processed_items: Dict[str, Any]):
        """Upload processed items to appropriate Qdrant collections"""
        self.log_info("Uploading vectors to Qdrant collections...")

        # Group items by collection
        collection_uploads = {name: [] for name in self.collections.keys()}

        for file_path, item_data in processed_items.items():
            item_id = item_data["payload"]["name"].lower().replace(' ', '_').replace('-', '_')

            # Create point for each target collection
            for collection_name in item_data["collections"]:
                if collection_name in collection_uploads:
                    point = PointStruct(
                        id=f"{collection_name}_{item_id}",
                        vector=item_data["embedding"],
                        payload=item_data["payload"]
                    )
                    collection_uploads[collection_name].append(point)

        # Upload to each collection
        for collection_name, points in collection_uploads.items():
            if points:
                try:
                    self.client.upsert(
                        collection_name=collection_name,
                        points=points
                    )
                    self.stats["total_vectors"] += len(points)
                    self.log_success(f"Uploaded {len(points)} vectors to '{collection_name}'")
                except Exception as e:
                    self.log_error(f"Failed to upload to '{collection_name}': {e}")

    def generate_report(self) -> str:
        """Generate a comprehensive processing report"""
        if RICH_AVAILABLE and self.console:
            return self._generate_rich_report()
        else:
            return self._generate_simple_report()

    def _generate_rich_report(self) -> str:
        """Generate rich-formatted report"""
        # Summary table
        summary_table = Table(title="Vector Database Population Summary")
        summary_table.add_column("Metric", style="cyan", no_wrap=True)
        summary_table.add_column("Value", style="magenta")

        summary_table.add_row("Total Files Found", str(self.stats["total_files"]))
        summary_table.add_row("Successfully Processed", str(self.stats["processed_files"]))
        summary_table.add_row("Failed Files", str(self.stats["failed_files"]))
        summary_table.add_row("Total Vectors Created", str(self.stats["total_vectors"]))
        summary_table.add_row("Success Rate", f"{(self.stats['processed_files'] / max(self.stats['total_files'], 1)) * 100:.1f}%")

        # Category breakdown
        category_table = Table(title="Items by Category")
        category_table.add_column("Category", style="cyan")
        category_table.add_column("Count", style="magenta")

        for category, count in sorted(self.stats["categories"].items()):
            category_table.add_row(category, str(count))

        self.console.print(Panel(summary_table, title="📊 Processing Results"))
        self.console.print(Panel(category_table, title="📂 Category Breakdown"))

        return "Report displayed above"

    def _generate_simple_report(self) -> str:
        """Generate simple text report"""
        report = []
        report.append("=" * 60)
        report.append("VECTOR DATABASE POPULATION REPORT")
        report.append("=" * 60)
        report.append(f"Total Files Found: {self.stats['total_files']}")
        report.append(f"Successfully Processed: {self.stats['processed_files']}")
        report.append(f"Failed Files: {self.stats['failed_files']}")
        report.append(f"Total Vectors Created: {self.stats['total_vectors']}")
        report.append(f"Success Rate: {(self.stats['processed_files'] / max(self.stats['total_files'], 1)) * 100:.1f}%")
        report.append("")
        report.append("Items by Category:")
        for category, count in sorted(self.stats["categories"].items()):
            report.append(f"  {category}: {count}")
        report.append("=" * 60)

        return "\n".join(report)

async def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Populate Qdrant vector database with Warframe wiki content")
    parser.add_argument("--wiki-dir", default="../../", help="Path to processed wiki directory")
    parser.add_argument("--vector-db", default="./vector_db", help="Path to Qdrant database")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model name")
    parser.add_argument("--force-recreate", action="store_true", help="Recreate collections even if they exist")

    args = parser.parse_args()

    # Initialize populator
    populator = WarframeVectorPopulator(
        wiki_dir=Path(args.wiki_dir),
        vector_db_path=args.vector_db,
        model_name=args.model
    )

    try:
        # Initialize collections
        await populator.initialize_collections()

        # Process all files
        start_time = datetime.now()
        processed_items = await populator.process_files()

        if not processed_items:
            populator.log_error("No items were successfully processed!")
            return

        # Upload to collections
        await populator.upload_to_collections(processed_items)

        # Calculate processing time
        end_time = datetime.now()
        populator.stats["processing_time"] = (end_time - start_time).total_seconds()

        # Generate and display report
        populator.generate_report()

        populator.log_success(f"✅ Vector database population completed in {populator.stats['processing_time']:.1f} seconds")
        populator.log_info(f"Database location: {args.vector_db}")

    except KeyboardInterrupt:
        populator.log_warning("⚠️ Process interrupted by user")
    except Exception as e:
        populator.log_error(f"❌ Population failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())