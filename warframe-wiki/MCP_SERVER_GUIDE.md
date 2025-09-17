# Warframe Wiki MCP Server - Complete Usage Guide

**Model Context Protocol Server for Comprehensive Warframe Data Analysis**

This guide covers everything you need to know about deploying, configuring, and using the Warframe Wiki MCP Server with its advanced git-based analytics and vector search capabilities.

## 🚀 Quick Start

### Prerequisites

```bash
# Required Python packages
pip install qdrant-client sentence-transformers
pip install fastapi uvicorn websockets
pip install mcp pydantic httpx
pip install rich aiofiles python-frontmatter

# Optional for enhanced features
pip install PyYAML GitPython
```

### Basic Setup

1. **Clone and prepare the repository:**
```bash
git clone <warframe-wiki-repo>
cd warframe-wiki
```

2. **Populate the vector database (first time only):**
```bash
cd meta/scripts
python populate_vector_db.py --wiki-dir ../../ --vector-db ./vector_db
```

3. **Start the MCP server:**
```bash
# STDIO transport (for AI integration)
python mcp_server.py --transport stdio --wiki-path ./warframe-wiki

# HTTP transport (for web clients)
python mcp_server.py --transport http --wiki-path ./warframe-wiki --port 8000
```

## 🔧 Configuration Options

### Command Line Arguments

```bash
python mcp_server.py [OPTIONS]

Options:
  --wiki-path TEXT          Path to Warframe wiki repository [default: ./warframe-wiki]
  --vector-db-path TEXT     Path to Qdrant vector database [optional]
  --transport [stdio|http]  Transport protocol [default: stdio]
  --host TEXT              Host for HTTP transport [default: 127.0.0.1]
  --port INTEGER           Port for HTTP transport [default: 8000]
```

### Environment Variables

```bash
# Optional environment configuration
export WIKI_PATH="/path/to/warframe-wiki"
export VECTOR_DB_PATH="/path/to/vector_db"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
```

## 🎯 Available MCP Tools

The MCP server provides these tools for AI integration:

### Core Search Tools

#### `search_items`
Search for Warframe items with semantic similarity and advanced filtering.

**Parameters:**
- `query` (required): Search query text
- `category` (optional): Filter by category (weapons, warframes, mods, etc.)
- `item_type` (optional): Filter by specific type
- `limit` (optional): Maximum results [default: 10]
- `min_stats` (optional): Minimum stat requirements
- `max_stats` (optional): Maximum stat requirements

**Example:**
```json
{
  "name": "search_items",
  "arguments": {
    "query": "high damage rifle",
    "category": "weapons",
    "limit": 5
  }
}
```

#### `get_item_details`
Get comprehensive details for a specific item.

**Parameters:**
- `item_id` (required): Item name or identifier
- `include_history` (optional): Include balance change history [default: true]

**Example:**
```json
{
  "name": "get_item_details",
  "arguments": {
    "item_id": "Braton Prime",
    "include_history": true
  }
}
```

### Comparison Tools

#### `compare_weapons`
Compare two weapons with detailed statistical analysis.

**Parameters:**
- `weapon1` (required): First weapon name
- `weapon2` (required): Second weapon name
- `analysis_type` (optional): Type of analysis [default: "overall"]

**Example:**
```json
{
  "name": "compare_weapons",
  "arguments": {
    "weapon1": "Braton Prime",
    "weapon2": "Soma Prime",
    "analysis_type": "dps"
  }
}
```

### Build Recommendation Tools

#### `get_build_recommendations`
Get optimized build recommendations for warframes.

**Parameters:**
- `warframe` (required): Warframe name
- `playstyle` (required): Desired playstyle (tank, dps, support, cc, hybrid)
- `mission_type` (optional): Mission type optimization [default: "general"]
- `enemy_level` (optional): Target enemy level [default: 100]

**Example:**
```json
{
  "name": "get_build_recommendations",
  "arguments": {
    "warframe": "Excalibur",
    "playstyle": "dps",
    "mission_type": "survival",
    "enemy_level": 150
  }
}
```

### Git-Based Analytics Tools

#### `track_item_changes`
Track all changes to an item using git history.

**Parameters:**
- `item_id` (required): Item name or identifier
- `since_date` (optional): Track changes since this date (YYYY-MM-DD)
- `change_types` (optional): Types of changes to track

**Example:**
```json
{
  "name": "track_item_changes",
  "arguments": {
    "item_id": "Braton Prime",
    "since_date": "2024-01-01"
  }
}
```

#### `get_balance_history`
Get complete balance change history with statistical analysis.

**Parameters:**
- `item_id` (required): Item name or identifier
- `stat_focus` (optional): Focus on specific stat
- `time_range` (optional): Time range (1m, 3m, 6m, 1y, all) [default: "all"]

**Example:**
```json
{
  "name": "get_balance_history",
  "arguments": {
    "item_id": "Braton Prime",
    "stat_focus": "damage",
    "time_range": "6m"
  }
}
```

#### `compare_meta_shifts`
Compare game meta between different patches or time periods.

**Parameters:**
- `patch1` (required): First patch/commit hash or date
- `patch2` (required): Second patch/commit hash or date
- `category` (optional): Focus on specific category [default: "all"]
- `analysis_depth` (optional): Analysis depth [default: "detailed"]

**Example:**
```json
{
  "name": "compare_meta_shifts",
  "arguments": {
    "patch1": "2024-01-01",
    "patch2": "2024-06-01",
    "category": "weapons"
  }
}
```

#### `predict_nerf_candidates`
Predict items likely to be nerfed based on statistical analysis.

**Parameters:**
- `category` (optional): Focus category [default: "weapons"]
- `confidence_threshold` (optional): Minimum confidence score [default: 0.7]
- `factors` (optional): Factors to consider

**Example:**
```json
{
  "name": "predict_nerf_candidates",
  "arguments": {
    "category": "weapons",
    "confidence_threshold": 0.8
  }
}
```

### Utility Tools

#### `analyze_power_creep`
Analyze power creep trends across categories.

#### `get_acquisition_paths`
Get all possible ways to acquire an item.

## 🌐 HTTP Transport API

When running with `--transport http`, the server provides additional endpoints:

### Health Check
```bash
GET http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "server": "warframe-wiki-mcp-server",
  "version": "1.0.0",
  "mcp_version": "2025-06-18",
  "features": {
    "vector_search": true,
    "sqlite_db": true,
    "git_analytics": true,
    "legacy_mcp": true
  }
}
```

### Server Statistics
```bash
GET http://localhost:8000/stats
```

**Response:**
```json
{
  "cached_items": 15194,
  "database_items": 15194,
  "tracked_changes": 1250,
  "vector_search_enabled": true,
  "last_cache_refresh": "2025-01-17T14:30:00",
  "wiki_directory": "/path/to/warframe-wiki"
}
```

### MCP Communication
```bash
# WebSocket for real-time communication
ws://localhost:8000/mcp

# HTTP POST for request-response
POST http://localhost:8000/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

## 🧪 Testing

### Run the Test Suite

```bash
# Test with automatic server startup
python test_mcp_server.py --start-server

# Test against running server
python test_mcp_server.py

# Start server only for manual testing
python test_mcp_server.py --server-only
```

### Manual Testing Examples

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test MCP initialization
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {"tools": true}
    }
  }'

# Test item search
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_items",
      "arguments": {"query": "braton", "limit": 3}
    }
  }'
```

## 🚀 Deployment

### Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "mcp_server.py", "--transport", "http", "--host", "0.0.0.0"]
```

Build and run:
```bash
docker build -t warframe-mcp-server .
docker run -p 8000:8000 -v $(pwd)/warframe-wiki:/app/warframe-wiki warframe-mcp-server
```

### Production Deployment

#### Using systemd Service

Create `/etc/systemd/system/warframe-mcp.service`:
```ini
[Unit]
Description=Warframe MCP Server
After=network.target

[Service]
Type=simple
User=warframe
WorkingDirectory=/opt/warframe-wiki
Environment=WIKI_PATH=/opt/warframe-wiki
ExecStart=/opt/warframe-wiki/venv/bin/python mcp_server.py --transport http --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable warframe-mcp
sudo systemctl start warframe-mcp
```

#### Using Nginx Reverse Proxy

Create `/etc/nginx/sites-available/warframe-mcp`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## 🔧 Advanced Configuration

### Vector Search Optimization

For optimal vector search performance:

1. **Use a dedicated Qdrant server:**
```bash
# Start Qdrant server
docker run -p 6333:6333 qdrant/qdrant

# Configure MCP server to use it
python mcp_server.py --vector-db-path http://localhost:6333
```

2. **Optimize collection settings:**
```python
# In populate_vector_db.py, adjust:
optimizers_config=CollectionParams(
    default_segment_number=4,      # More segments for large datasets
    memmap_threshold=10000,        # Lower for more memory usage
)
```

### Performance Tuning

1. **SQLite Optimization:**
```sql
-- Run these pragmas for better performance
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=memory;
```

2. **Increase cache expiry:**
```python
# In WarframeMCPServer.__init__()
self.cache_expiry = timedelta(hours=6)  # Cache for 6 hours
```

### Custom Embeddings Model

To use a different embeddings model:

```bash
# Use a larger model for better accuracy
python populate_vector_db.py --model all-MiniLM-L12-v2

# Use a model optimized for your language
python populate_vector_db.py --model paraphrase-multilingual-MiniLM-L12-v2
```

## 🔍 Monitoring and Logging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Performance

```bash
# Check vector database performance
curl http://localhost:8000/stats

# Monitor git operations
tail -f /var/log/warframe-mcp.log | grep "git"

# Watch for search performance
tail -f /var/log/warframe-mcp.log | grep "search"
```

## 🛠️ Troubleshooting

### Common Issues

#### Vector Search Not Working
```bash
# Check Qdrant connection
python -c "from qdrant_client import QdrantClient; client = QdrantClient('localhost', 6333); print(client.get_collections())"

# Rebuild vector database
python meta/scripts/populate_vector_db.py --force-recreate
```

#### Git Analytics Failing
```bash
# Ensure git repository is properly initialized
cd warframe-wiki && git status

# Check git history
git log --oneline | head -10
```

#### Performance Issues
```bash
# Check database size and indexes
sqlite3 warframe-wiki/warframe_data.db ".tables"
sqlite3 warframe-wiki/warframe_data.db ".schema"

# Monitor memory usage
ps aux | grep python
```

#### MCP Protocol Errors
```bash
# Test MCP initialization
python test_mcp_server.py --start-server

# Check MCP compliance
curl -X POST http://localhost:8000/mcp -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## 📚 Integration Examples

### Claude Desktop Integration

Add to Claude Desktop MCP config:
```json
{
  "mcp": {
    "servers": {
      "warframe-wiki": {
        "command": "python",
        "args": ["/path/to/warframe-wiki/mcp_server.py", "--transport", "stdio"],
        "env": {
          "WIKI_PATH": "/path/to/warframe-wiki"
        }
      }
    }
  }
}
```

### Python Client Example

```python
import asyncio
import json
from pathlib import Path

async def query_warframe_mcp():
    # Example of programmatic MCP usage
    import subprocess

    # Start MCP server
    process = subprocess.Popen([
        "python", "mcp_server.py", "--transport", "stdio"
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    # Send initialization
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"}
    }

    process.stdin.write(json.dumps(init_msg) + '\n')
    process.stdin.flush()

    # Read response
    response = process.stdout.readline()
    print("Init response:", response)

    # Query for weapons
    search_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_items",
            "arguments": {"query": "high damage weapons", "limit": 5}
        }
    }

    process.stdin.write(json.dumps(search_msg) + '\n')
    process.stdin.flush()

    response = process.stdout.readline()
    print("Search response:", response)

    process.terminate()

# Run the example
# asyncio.run(query_warframe_mcp())
```

## 🔄 Maintenance

### Regular Maintenance Tasks

1. **Update vector database:**
```bash
# Weekly rebuild of vectors
cd meta/scripts
python populate_vector_db.py --wiki-dir ../../ --vector-db ./vector_db
```

2. **Clean up old data:**
```bash
# Remove old cache entries
sqlite3 warframe_data.db "DELETE FROM items WHERE last_modified < date('now', '-30 days')"
```

3. **Monitor git repository:**
```bash
# Check for new commits
cd warframe-wiki && git pull origin main
```

4. **Backup important data:**
```bash
# Backup vector database
tar -czf vector_db_backup_$(date +%Y%m%d).tar.gz vector_db/

# Backup SQLite database
cp warframe_data.db warframe_data_backup_$(date +%Y%m%d).db
```

## 📖 API Reference

For complete API documentation, see the MCP 2025-06-18 specification at:
https://modelcontextprotocol.io/specification/2025-06-18

The Warframe MCP Server implements all required capabilities:
- ✅ Tools (search, analysis, prediction)
- ✅ Resources (git history, item database)
- ✅ Prompts (build recommendations, meta analysis)
- ✅ Multiple transports (stdio, HTTP+SSE, streamable HTTP)

## 🤝 Contributing

To contribute to the Warframe MCP Server:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite: `python test_mcp_server.py`
5. Submit a pull request

For bug reports or feature requests, please use the GitHub issues tracker.

---

**🎮 Happy Tenno! May your builds be optimal and your nerfs be minimal! 🎮**