#!/usr/bin/env python3
"""
WFCD API Client for Warframe Data Ingestion
Handles data fetching from WFCD warframe-items and WarframeStatus APIs
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class APIResponse:
    """Structured API response container"""
    data: Any
    timestamp: datetime
    etag: Optional[str] = None
    cached: bool = False

class WFCDClient:
    """
    Comprehensive WFCD API client for Warframe data ingestion
    Supports both warframe-items and WarframeStatus APIs
    """

    def __init__(self, cache_dir="./cache", rate_limit_delay=1.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.rate_limit_delay = rate_limit_delay
        self.session = None

        # API Endpoints
        self.base_urls = {
            'items': 'https://api.warframestat.us',
            'worldstate': 'https://api.warframestat.us',
            'cdn_images': 'https://cdn.warframestat.us/img'
        }

        # Supported platforms
        self.platforms = ['pc', 'ps4', 'xb1', 'swi']

        # Item categories from WFCD
        self.item_categories = [
            'All', 'Arcanes', 'Archwing', 'Companions', 'Fish', 'Gear',
            'Glyphs', 'Melee', 'Mods', 'Node', 'Pets', 'Primary',
            'Quests', 'Relics', 'Resources', 'Secondary', 'Sentinels',
            'Skins', 'Warframes'
        ]

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Warframe-Wiki-Bot/1.0 (Python/aiohttp)',
                'Accept': 'application/json'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def _get_cache_path(self, endpoint: str) -> Path:
        """Generate cache file path for endpoint"""
        cache_key = hashlib.md5(endpoint.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.json"

    def _load_cache(self, endpoint: str) -> Optional[APIResponse]:
        """Load cached response if available and not expired"""
        cache_path = self._get_cache_path(endpoint)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)

            # Check if cache is expired (1 hour for most data, 5 minutes for worldstate)
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            expire_time = timedelta(minutes=5 if 'worldstate' in endpoint else 60)

            if datetime.now() - cached_time < expire_time:
                return APIResponse(
                    data=cached_data['data'],
                    timestamp=cached_time,
                    etag=cached_data.get('etag'),
                    cached=True
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file {cache_path}: {e}")
            cache_path.unlink(missing_ok=True)

        return None

    def _save_cache(self, endpoint: str, response: APIResponse):
        """Save response to cache"""
        cache_path = self._get_cache_path(endpoint)

        cache_data = {
            'data': response.data,
            'timestamp': response.timestamp.isoformat(),
            'etag': response.etag,
            'endpoint': endpoint
        }

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache {cache_path}: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _make_request(self, url: str, headers: Optional[Dict] = None) -> APIResponse:
        """Make HTTP request with retry logic and rate limiting"""

        # Check cache first
        cached_response = self._load_cache(url)
        if cached_response:
            logger.debug(f"Using cached response for {url}")
            return cached_response

        # Rate limiting
        await asyncio.sleep(self.rate_limit_delay)

        request_headers = headers or {}

        try:
            async with self.session.get(url, headers=request_headers) as response:
                if response.status == 200:
                    data = await response.json()
                    api_response = APIResponse(
                        data=data,
                        timestamp=datetime.now(),
                        etag=response.headers.get('ETag'),
                        cached=False
                    )

                    # Save to cache
                    self._save_cache(url, api_response)

                    logger.debug(f"Successful request to {url}")
                    return api_response

                elif response.status == 304:  # Not Modified
                    logger.debug(f"Data not modified for {url}")
                    return cached_response or APIResponse(data=None, timestamp=datetime.now())

                elif response.status == 429:  # Rate Limited
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"Rate limited: {response.status}"
                    )

                else:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"HTTP {response.status}: {await response.text()}"
                    )

        except aiohttp.ClientError as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    async def get_all_items(self, categories: Optional[List[str]] = None) -> Dict[str, APIResponse]:
        """
        Fetch all items from WFCD warframe-items API

        Args:
            categories: List of item categories to fetch (default: All)

        Returns:
            Dictionary mapping category names to API responses
        """
        if categories is None:
            categories = ['All']

        results = {}

        for category in categories:
            if category not in self.item_categories:
                logger.warning(f"Unknown category: {category}")
                continue

            url = f"{self.base_urls['items']}/items"
            if category != 'All':
                url += f"?category={category}"

            try:
                response = await self._make_request(url)
                results[category] = response
                logger.info(f"Fetched {len(response.data)} items for category: {category}")
            except Exception as e:
                logger.error(f"Failed to fetch items for category {category}: {e}")

        return results

    async def get_warframes(self) -> APIResponse:
        """Fetch all Warframes with detailed stats"""
        url = f"{self.base_urls['items']}/warframes"
        return await self._make_request(url)

    async def get_weapons(self, weapon_type: Optional[str] = None) -> APIResponse:
        """
        Fetch weapons by type

        Args:
            weapon_type: 'Primary', 'Secondary', 'Melee', or None for all
        """
        url = f"{self.base_urls['items']}/weapons"
        if weapon_type:
            url += f"?type={weapon_type}"

        return await self._make_request(url)

    async def get_mods(self) -> APIResponse:
        """Fetch all mods with stats and polarity"""
        url = f"{self.base_urls['items']}/mods"
        return await self._make_request(url)

    async def get_relics(self) -> APIResponse:
        """Fetch all relics with drop tables"""
        url = f"{self.base_urls['items']}/relics"
        return await self._make_request(url)

    async def search_items(self, query: str) -> APIResponse:
        """Search for items by name or description"""
        url = f"{self.base_urls['items']}/items/search/{query}"
        return await self._make_request(url)

    async def get_worldstate(self, platform: str = 'pc') -> APIResponse:
        """
        Fetch current world state data for platform

        Args:
            platform: 'pc', 'ps4', 'xb1', or 'swi'
        """
        if platform not in self.platforms:
            raise ValueError(f"Invalid platform: {platform}. Must be one of {self.platforms}")

        url = f"{self.base_urls['worldstate']}/{platform}"
        return await self._make_request(url)

    async def get_alerts(self, platform: str = 'pc') -> APIResponse:
        """Fetch current alerts for platform"""
        url = f"{self.base_urls['worldstate']}/{platform}/alerts"
        return await self._make_request(url)

    async def get_invasions(self, platform: str = 'pc') -> APIResponse:
        """Fetch current invasions for platform"""
        url = f"{self.base_urls['worldstate']}/{platform}/invasions"
        return await self._make_request(url)

    async def get_sorties(self, platform: str = 'pc') -> APIResponse:
        """Fetch current sortie for platform"""
        url = f"{self.base_urls['worldstate']}/{platform}/sorties"
        return await self._make_request(url)

    async def get_fissures(self, platform: str = 'pc') -> APIResponse:
        """Fetch current void fissures for platform"""
        url = f"{self.base_urls['worldstate']}/{platform}/fissures"
        return await self._make_request(url)

    async def get_nightwave(self, platform: str = 'pc') -> APIResponse:
        """Fetch current Nightwave status for platform"""
        url = f"{self.base_urls['worldstate']}/{platform}/nightwave"
        return await self._make_request(url)

    async def get_item_image_url(self, image_name: str) -> str:
        """Generate CDN URL for item image"""
        return f"{self.base_urls['cdn_images']}/{image_name}"

    async def detect_changes(self, reference_data: Optional[Dict] = None) -> Dict[str, bool]:
        """
        Detect if data has changed since last fetch

        Args:
            reference_data: Previous data to compare against

        Returns:
            Dictionary indicating which categories have changes
        """
        changes = {}

        try:
            # Check major categories for changes
            categories_to_check = ['warframes', 'weapons', 'mods', 'relics']

            for category in categories_to_check:
                method = getattr(self, f'get_{category}')
                current_response = await method()

                if reference_data and category in reference_data:
                    # Compare ETags or data hashes
                    current_hash = hashlib.md5(
                        json.dumps(current_response.data, sort_keys=True).encode()
                    ).hexdigest()

                    reference_hash = reference_data[category].get('hash')
                    changes[category] = current_hash != reference_hash
                else:
                    changes[category] = True  # Treat as changed if no reference

                logger.info(f"Change detection for {category}: {changes[category]}")

        except Exception as e:
            logger.error(f"Error during change detection: {e}")
            # Default to assuming changes exist if detection fails
            changes = {cat: True for cat in ['warframes', 'weapons', 'mods', 'relics']}

        return changes

    async def batch_fetch_all_data(self) -> Dict[str, APIResponse]:
        """
        Fetch comprehensive dataset from all WFCD APIs

        Returns:
            Dictionary with all fetched data categorized
        """
        logger.info("Starting comprehensive data fetch from WFCD APIs")

        # Gather all tasks for concurrent execution
        tasks = {
            'warframes': self.get_warframes(),
            'weapons': self.get_weapons(),
            'mods': self.get_mods(),
            'relics': self.get_relics(),
            'items_all': self.get_all_items(['All']),
            'worldstate_pc': self.get_worldstate('pc'),
            'alerts_pc': self.get_alerts('pc'),
            'invasions_pc': self.get_invasions('pc'),
            'sorties_pc': self.get_sorties('pc'),
            'fissures_pc': self.get_fissures('pc'),
            'nightwave_pc': self.get_nightwave('pc')
        }

        # Execute all requests concurrently
        logger.info(f"Executing {len(tasks)} concurrent API requests")
        results = {}

        for name, task in tasks.items():
            try:
                results[name] = await task
                logger.info(f"Successfully fetched: {name}")
            except Exception as e:
                logger.error(f"Failed to fetch {name}: {e}")
                results[name] = None

        # Log summary
        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Batch fetch complete: {successful}/{len(tasks)} successful")

        return results

# CLI interface for testing
async def main():
    """CLI interface for testing WFCD client"""
    import argparse

    parser = argparse.ArgumentParser(description='WFCD API Client')
    parser.add_argument('--action', choices=['items', 'warframes', 'weapons', 'changes', 'all'],
                       default='all', help='Action to perform')
    parser.add_argument('--platform', choices=['pc', 'ps4', 'xb1', 'swi'],
                       default='pc', help='Platform for worldstate data')
    parser.add_argument('--category', help='Item category to fetch')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    async with WFCDClient() as client:
        result = None

        if args.action == 'items':
            categories = [args.category] if args.category else ['All']
            result = await client.get_all_items(categories)
        elif args.action == 'warframes':
            result = await client.get_warframes()
        elif args.action == 'weapons':
            result = await client.get_weapons()
        elif args.action == 'changes':
            result = await client.detect_changes()
        elif args.action == 'all':
            result = await client.batch_fetch_all_data()

        # Output results
        if args.output:
            output_path = Path(args.output)
            # Serialize APIResponse objects properly
            def serialize_api_response(obj):
                if hasattr(obj, 'data'):
                    return {
                        'data': obj.data,
                        'timestamp': obj.timestamp.isoformat(),
                        'cached': obj.cached
                    }
                elif isinstance(obj, dict):
                    return {k: serialize_api_response(v) for k, v in obj.items()}
                else:
                    return obj

            serializable_result = serialize_api_response(result)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_result, f, indent=2, ensure_ascii=False)
            print(f"Results saved to: {output_path}")
        else:
            # For console output, show summary
            for key, value in result.items():
                if hasattr(value, 'data') and value.data:
                    print(f"{key}: {len(value.data)} items")
                else:
                    print(f"{key}: {type(value)}")

if __name__ == "__main__":
    asyncio.run(main())