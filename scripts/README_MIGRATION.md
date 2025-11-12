# Tenant Migration Guide

## Overview

The `migrate_tenant.py` script provides a unified tool for migrating all tenant data across multiple storage systems:
- **Redis/DragonflyDB**: Key-value store with tenant key prefixes
- **Qdrant**: Vector database with workspace_id payload filtering
- **Memgraph**: Graph database with node label-based isolation
- **Tenant Config**: API-based configuration management

## Prerequisites

```bash
# Install required Python packages
pip install redis requests

# Optional: For Memgraph support
pip install mgclient
```

## Basic Usage

### Full Migration
```bash
python scripts/migrate_tenant.py <source_tenant_id> <target_tenant_id>
```

**Example:**
```bash
python scripts/migrate_tenant.py siraya tenant_76920508
```

### Dry Run (Preview Migration)
```bash
python scripts/migrate_tenant.py siraya tenant_76920508 --dry-run
```

### Selective Migration
```bash
# Only migrate Redis data
python scripts/migrate_tenant.py siraya tenant_76920508 --skip-qdrant --skip-memgraph --skip-config

# Only migrate Qdrant vectors
python scripts/migrate_tenant.py siraya tenant_76920508 --skip-redis --skip-memgraph --skip-config
```

## Remote Server Migration

### Option 1: Port Forwarding (Recommended)
```bash
# Forward remote ports to local machine
ssh -L 6379:localhost:6379 \
    -L 6333:localhost:6333 \
    -L 7687:localhost:7687 \
    -L 8000:localhost:8000 \
    root@45.78.223.205

# Run migration on local machine (in another terminal)
python scripts/migrate_tenant.py siraya tenant_76920508
```

### Option 2: Run on Remote Server
```bash
# Copy script to remote server
scp scripts/migrate_tenant.py root@45.78.223.205:/tmp/

# SSH into server and run
ssh root@45.78.223.205
cd /tmp
python3 migrate_tenant.py siraya tenant_76920508
```

## Advanced Options

### Custom Hostnames/Ports
```bash
python scripts/migrate_tenant.py siraya tenant_76920508 \
  --redis-host 192.168.1.100 \
  --redis-port 6380 \
  --qdrant-url http://192.168.1.101:6333 \
  --memgraph-host 192.168.1.102 \
  --memgraph-port 7687 \
  --api-url http://192.168.1.103:8000
```

## Migration Process

The script performs migrations in this order:

1. **Tenant Config** (via API)
   - Gets source tenant config from `/tenants/{source}/config`
   - Creates target tenant config at `/tenants/{target}/config`

2. **Redis Keys** (using pipeline batching)
   - Scans all keys matching `*{source}*` pattern
   - Supports all Redis data types: string, hash, list, set, zset
   - Batch size: 500 keys per pipeline
   - Progress updates every 5,000 keys

3. **Qdrant Vectors** (using scroll + batch payload updates)
   - Scrolls through all collections
   - Filters by `workspace_id: {source}`
   - Updates `workspace_id` to target in batches of 100 points

4. **Memgraph Nodes** (using Cypher label operations)
   - Adds target label to all source nodes
   - Removes source label
   - Atomic operation via Cypher queries

## Performance Expectations

Based on the siraya → tenant_76920508 migration (dev server):

| Storage | Data Volume | Duration | Throughput |
|---------|-------------|----------|------------|
| Redis | 38,491 keys | ~2 min | ~300 keys/sec |
| Qdrant | 39,114 points | ~4 min | ~160 points/sec |
| Memgraph | 13,613 nodes | <10 sec | >1,300 nodes/sec |
| Config | 1 record | <1 sec | - |

**Total**: ~6 minutes for complete migration

## Output Example

```
============================================================
Tenant Data Migration: siraya → tenant_76920508
============================================================

Migrating tenant config: siraya → tenant_76920508
  Source config found: siraya
  Target config created

Migrating Redis keys: siraya → tenant_76920508
  Found 38490 keys to migrate
  Progress: 5000/38490 (12%)
  Progress: 10000/38490 (25%)
  ...
  Final count: 38491 keys

Migrating Qdrant points: siraya → tenant_76920508
  Collection: lightrag_vdb_chunks
    Migrated: 544 points
  Collection: lightrag_vdb_entities
    Migrated: 15644 points
  Collection: lightrag_vdb_relationships
    Migrated: 22926 points

Migrating Memgraph nodes: siraya → tenant_76920508
  Found 13613 nodes

============================================================
Migration Summary
============================================================
Tenant Config: ✅ Created
Redis: 37990/38490 keys (failed: 500)
  Final count: 38491 keys
Qdrant: 39114 points
Memgraph: 13613 nodes
============================================================

✅ Migration completed!
```

## Troubleshooting

### Connection Errors
```bash
# Test Redis connection
docker exec rag-dragonflydb redis-cli ping

# Test Qdrant
curl http://localhost:6333/collections

# Test Memgraph
docker exec rag-memgraph bash -c 'echo "MATCH (n) RETURN count(n) LIMIT 1;" | mgconsole --host 127.0.0.1 --port 7687 --use-ssl=False'

# Test API
curl http://localhost:8000/tenants/{tenant_id}/config
```

### Partial Migration Failures
If migration fails partway through, you can:

1. **Check existing data**:
   ```bash
   # Check Redis
   docker exec rag-dragonflydb redis-cli --scan --pattern '*target_tenant*' | wc -l

   # Check Qdrant
   curl -X POST http://localhost:6333/collections/lightrag_vdb_chunks/points/scroll \
     -H 'Content-Type: application/json' \
     -d '{"limit": 1, "filter": {"must": [{"key": "workspace_id", "match": {"value": "target_tenant"}}]}}'
   ```

2. **Re-run migration**: The script is idempotent - it will skip already-migrated data

3. **Selective retry**: Use `--skip-*` flags to skip completed migrations

## Security Notes

- **SSH Keys**: Store SSH keys securely (e.g., `~/Downloads/chengjie.pem`)
- **Permissions**: Ensure script has execute permission: `chmod +x scripts/migrate_tenant.py`
- **Credentials**: Never commit API keys or credentials to version control
- **Production**: Always test migrations on dev environment first

## Integration with CI/CD

```bash
# In deployment pipeline
./scripts/migrate_tenant.py old_tenant new_tenant \
  --redis-host $REDIS_HOST \
  --qdrant-url $QDRANT_URL \
  --api-url $API_URL
```

## Related Files

- [scripts/migrate_tenant.py](./migrate_tenant.py) - Main migration script
- [DEPLOYMENT_PRIVATE.md](../DEPLOYMENT_PRIVATE.md) - Server credentials (local only, git-ignored)
