#!/usr/bin/env python3
"""
Warframe Content Update Pipeline
Orchestrates the complete content update process from API to repository
"""

import asyncio
import logging
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
import tempfile
import shutil

from wfcd_client import WFCDClient
from data_processor import WFDataProcessor
from detect_game_changes import GameChangeDetector
from pdf_generator import WarframePDFGenerator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ContentUpdateOrchestrator:
    """
    Orchestrates the complete Warframe content update pipeline
    """

    def __init__(self,
                 wiki_dir: Path,
                 force_update: bool = False,
                 categories: Optional[List[str]] = None,
                 generate_pdfs: bool = True):
        self.wiki_dir = Path(wiki_dir)
        self.force_update = force_update
        self.categories = categories or ['warframes', 'weapons', 'mods', 'relics']
        self.generate_pdfs = generate_pdfs

        # Directory paths
        self.content_dir = self.wiki_dir / "content"
        self.images_dir = self.wiki_dir / "images"
        self.pdfs_dir = self.wiki_dir / "pdfs"
        self.cache_dir = self.wiki_dir / "cache"
        self.meta_dir = self.wiki_dir / "meta"

        # Create directories
        for directory in [self.content_dir, self.images_dir, self.pdfs_dir, self.cache_dir]:
            directory.mkdir(exist_ok=True, parents=True)

        # Initialize components
        self.change_detector = GameChangeDetector(
            state_file=str(self.wiki_dir / ".game-state.json"),
            cache_dir=str(self.cache_dir)
        )

        self.data_processor = WFDataProcessor(
            output_dir=self.content_dir,
            image_dir=self.images_dir
        )

        if self.generate_pdfs:
            self.pdf_generator = WarframePDFGenerator(
                wiki_dir=str(self.wiki_dir),
                output_dir=str(self.pdfs_dir)
            )

        # Statistics tracking
        self.stats = {
            'start_time': datetime.now(),
            'categories_processed': 0,
            'items_processed': 0,
            'files_created': 0,
            'files_updated': 0,
            'pdfs_generated': 0,
            'errors': 0
        }

    def log_stats(self):
        """Log current statistics"""
        duration = datetime.now() - self.stats['start_time']
        logger.info(f"Pipeline Statistics:")
        logger.info(f"  Duration: {duration}")
        logger.info(f"  Categories: {self.stats['categories_processed']}")
        logger.info(f"  Items: {self.stats['items_processed']}")
        logger.info(f"  Files Created: {self.stats['files_created']}")
        logger.info(f"  Files Updated: {self.stats['files_updated']}")
        logger.info(f"  PDFs Generated: {self.stats['pdfs_generated']}")
        logger.info(f"  Errors: {self.stats['errors']}")

    async def check_for_changes(self) -> bool:
        """Check if any changes detected in game data"""
        if self.force_update:
            logger.info("Force update requested, skipping change detection")
            return True

        logger.info("Checking for game data changes...")
        change_result = await self.change_detector.detect_all_changes()

        if change_result.has_changes:
            logger.info(f"Changes detected: {change_result.summary}")
            return True
        else:
            logger.info("No changes detected in game data")
            return False

    async def fetch_api_data(self) -> Dict[str, any]:
        """Fetch data from all WFCD APIs"""
        logger.info("Fetching data from WFCD APIs...")

        async with WFCDClient(cache_dir=str(self.cache_dir)) as client:
            api_data = {}

            # Fetch category-specific data
            for category in self.categories:
                try:
                    if category == 'warframes':
                        response = await client.get_warframes()
                    elif category == 'weapons':
                        response = await client.get_weapons()
                    elif category == 'mods':
                        response = await client.get_mods()
                    elif category == 'relics':
                        response = await client.get_relics()
                    else:
                        logger.warning(f"Unknown category: {category}")
                        continue

                    api_data[category] = response
                    item_count = len(response.data) if response and response.data else 0
                    logger.info(f"Fetched {item_count} {category} items")

                except Exception as e:
                    logger.error(f"Failed to fetch {category} data: {e}")
                    self.stats['errors'] += 1
                    api_data[category] = None

            # Fetch comprehensive items data
            try:
                items_response = await client.get_all_items(['All'])
                if 'All' in items_response:
                    api_data['items_all'] = items_response['All']
                    logger.info("Fetched comprehensive items data")
            except Exception as e:
                logger.error(f"Failed to fetch comprehensive items: {e}")
                self.stats['errors'] += 1

        return api_data

    async def process_content(self, api_data: Dict[str, any]) -> Dict[str, List]:
        """Process API data into structured content files"""
        logger.info("Processing API data into structured content...")

        processed_data = await self.data_processor.batch_process_all_data(api_data)

        # Update statistics
        for category, items in processed_data.items():
            self.stats['categories_processed'] += 1
            self.stats['items_processed'] += len(items)
            self.stats['files_created'] += len(items)  # Assume all are new for now

        logger.info(f"Processed {self.stats['items_processed']} items across {self.stats['categories_processed']} categories")
        return processed_data

    async def generate_pdfs(self, processed_data: Dict[str, List]) -> int:
        """Generate PDFs for all processed content"""
        if not self.generate_pdfs:
            logger.info("PDF generation disabled")
            return 0

        logger.info("Generating PDFs...")
        pdfs_generated = 0

        try:
            # Generate PDFs for all markdown files
            for category_path in self.content_dir.rglob("*.md"):
                try:
                    success = self.pdf_generator.generate_pdf(category_path)
                    if success:
                        pdfs_generated += 1
                except Exception as e:
                    logger.error(f"Failed to generate PDF for {category_path}: {e}")
                    self.stats['errors'] += 1

            self.stats['pdfs_generated'] = pdfs_generated
            logger.info(f"Generated {pdfs_generated} PDFs")

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            self.stats['errors'] += 1

        return pdfs_generated

    async def download_images(self, processed_data: Dict[str, List]):
        """Download images for items that have them"""
        logger.info("Downloading item images...")

        import aiohttp
        import aiofiles

        images_downloaded = 0

        async with aiohttp.ClientSession() as session:
            for category, items in processed_data.items():
                for item in items:
                    if not item.image_urls:
                        continue

                    for image_url in item.image_urls:
                        try:
                            # Extract filename from URL
                            filename = Path(image_url).name
                            local_path = self.images_dir / filename

                            # Skip if already exists
                            if local_path.exists():
                                continue

                            # Download image
                            async with session.get(image_url) as response:
                                if response.status == 200:
                                    async with aiofiles.open(local_path, 'wb') as f:
                                        async for chunk in response.content.iter_chunked(8192):
                                            await f.write(chunk)
                                    images_downloaded += 1
                                    logger.debug(f"Downloaded image: {filename}")

                        except Exception as e:
                            logger.error(f"Failed to download image {image_url}: {e}")
                            self.stats['errors'] += 1

        logger.info(f"Downloaded {images_downloaded} images")

    async def create_index_files(self, processed_data: Dict[str, List]):
        """Create index files for categories"""
        logger.info("Creating category index files...")

        for category, items in processed_data.items():
            if not items:
                continue

            # Create category directory if it doesn't exist
            category_dir = self.content_dir / self.determine_category_path(category)
            category_dir.mkdir(parents=True, exist_ok=True)

            # Create index file
            index_path = category_dir / "README.md"
            index_content = self.generate_index_content(category, items)

            try:
                with open(index_path, 'w', encoding='utf-8') as f:
                    f.write(index_content)
                logger.debug(f"Created index file: {index_path}")
            except Exception as e:
                logger.error(f"Failed to create index file {index_path}: {e}")
                self.stats['errors'] += 1

    def determine_category_path(self, category: str) -> str:
        """Determine directory path for category"""
        category_mappings = {
            'Warframes': 'warframes',
            'Weapons': 'weapons',
            'Mods': 'mods',
            'Relics': 'relics'
        }
        return category_mappings.get(category, category.lower())

    def generate_index_content(self, category: str, items: List) -> str:
        """Generate index file content for category"""
        content = f"# {category}\n\n"
        content += f"This directory contains {len(items)} {category.lower()} items.\n\n"
        content += f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "## Items\n\n"

        # Sort items by name
        sorted_items = sorted(items, key=lambda x: x.metadata.get('name', ''))

        for item in sorted_items:
            name = item.metadata.get('name', 'Unknown')
            file_name = item.file_path.name
            content += f"- [{name}](./{file_name})\n"

        content += f"\n---\n*Generated automatically from WFCD API data*\n"
        return content

    async def cleanup_old_files(self, processed_data: Dict[str, List]):
        """Remove files for items that no longer exist"""
        logger.info("Cleaning up obsolete files...")

        current_files = set()

        # Collect all current file paths
        for category, items in processed_data.items():
            for item in items:
                current_files.add(item.file_path)

        # Find existing markdown files
        existing_files = set(self.content_dir.rglob("*.md"))

        # Remove files that are no longer current
        files_removed = 0
        for file_path in existing_files:
            if file_path not in current_files and file_path.name != "README.md":
                try:
                    file_path.unlink()
                    files_removed += 1
                    logger.debug(f"Removed obsolete file: {file_path}")

                    # Also remove corresponding PDF if it exists
                    pdf_path = self.pdfs_dir / file_path.with_suffix('.pdf').name
                    if pdf_path.exists():
                        pdf_path.unlink()
                        logger.debug(f"Removed obsolete PDF: {pdf_path}")

                except Exception as e:
                    logger.error(f"Failed to remove file {file_path}: {e}")
                    self.stats['errors'] += 1

        if files_removed > 0:
            logger.info(f"Removed {files_removed} obsolete files")

    async def update_game_version_file(self):
        """Update the .game-version file with current timestamp"""
        version_file = self.wiki_dir / ".game-version"
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            logger.debug("Updated game version file")
        except Exception as e:
            logger.error(f"Failed to update version file: {e}")

    async def run_complete_pipeline(self) -> bool:
        """Run the complete content update pipeline"""
        logger.info("Starting Warframe content update pipeline")
        self.log_stats()

        try:
            # Step 1: Check for changes
            if not await self.check_for_changes():
                logger.info("No changes detected, pipeline complete")
                return False

            # Step 2: Fetch API data
            api_data = await self.fetch_api_data()
            if not api_data or all(v is None for v in api_data.values()):
                logger.error("Failed to fetch any API data")
                return False

            # Step 3: Process content
            processed_data = await self.process_content(api_data)
            if not processed_data:
                logger.error("Failed to process any content")
                return False

            # Step 4: Download images
            await self.download_images(processed_data)

            # Step 5: Generate PDFs
            await self.generate_pdfs(processed_data)

            # Step 6: Create index files
            await self.create_index_files(processed_data)

            # Step 7: Cleanup old files
            await self.cleanup_old_files(processed_data)

            # Step 8: Update version file
            await self.update_game_version_file()

            logger.info("Content update pipeline completed successfully")
            self.log_stats()
            return True

        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}")
            self.stats['errors'] += 1
            self.log_stats()
            return False

# CLI interface
async def main():
    """CLI interface for content update pipeline"""
    import argparse

    parser = argparse.ArgumentParser(description='Warframe Content Update Pipeline')
    parser.add_argument('--wiki-dir', default='../warframe-wiki', help='Wiki directory')
    parser.add_argument('--categories', nargs='+', help='Categories to update')
    parser.add_argument('--force-update', action='store_true', help='Force update regardless of changes')
    parser.add_argument('--no-pdfs', action='store_true', help='Skip PDF generation')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize orchestrator
    orchestrator = ContentUpdateOrchestrator(
        wiki_dir=Path(args.wiki_dir),
        force_update=args.force_update,
        categories=args.categories,
        generate_pdfs=not args.no_pdfs
    )

    # Run pipeline
    success = await orchestrator.run_complete_pipeline()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())