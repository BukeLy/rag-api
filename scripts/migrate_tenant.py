#!/usr/bin/env python3
"""
Tenant Data Migration Script

Migrates all data for a tenant across Redis, Qdrant, and Memgraph databases.

Usage:
    python scripts/migrate_tenant.py <source_tenant_id> <target_tenant_id> [options]

Options:
    --redis-host HOST       Redis host (default: localhost)
    --redis-port PORT       Redis port (default: 6379)
    --qdrant-url URL        Qdrant URL (default: http://localhost:6333)
    --memgraph-host HOST    Memgraph host (default: localhost)
    --memgraph-port PORT    Memgraph port (default: 7687)
    --dry-run               Show migration plan without executing
    --skip-redis            Skip Redis migration
    --skip-qdrant           Skip Qdrant migration
    --skip-memgraph         Skip Memgraph migration
    --skip-config           Skip tenant config migration
    --api-url URL           API URL for config migration (default: http://localhost:8000)

Example:
    # Full migration
    python scripts/migrate_tenant.py siraya tenant_76920508

    # Dry run (show migration plan)
    python scripts/migrate_tenant.py siraya tenant_76920508 --dry-run

    # Only migrate Redis
    python scripts/migrate_tenant.py siraya tenant_76920508 --skip-qdrant --skip-memgraph --skip-config
"""

import argparse
import sys
import time
from typing import Dict, List

try:
    import redis
except ImportError:
    print("Error: redis-py library not found. Install with: pip install redis")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


def migrate_redis_keys(r: redis.Redis, source: str, target: str, dry_run: bool = False) -> Dict[str, int]:
    """Migrate all Redis keys from source tenant to target tenant"""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating Redis keys: {source} → {target}")

    # Scan all keys with source tenant prefix
    all_keys = []
    for key in r.scan_iter(match=f'*{source}*', count=1000):
        all_keys.append(key)

    total = len(all_keys)
    print(f"  Found {total} keys to migrate")

    if dry_run:
        return {'total': total, 'migrated': 0, 'failed': 0}

    # Batch migrate with pipeline
    batch_size = 500
    migrated = 0
    failed = 0

    for i in range(0, total, batch_size):
        batch = all_keys[i:i+batch_size]

        # Get values with pipeline
        pipe = r.pipeline()
        for key in batch:
            key_type = r.type(key)

            if key_type == b'string':
                pipe.get(key)
            elif key_type == b'hash':
                pipe.hgetall(key)
            elif key_type == b'list':
                pipe.lrange(key, 0, -1)
            elif key_type == b'set':
                pipe.smembers(key)
            elif key_type == b'zset':
                pipe.zrange(key, 0, -1, withscores=True)

        try:
            results = pipe.execute()
        except Exception as e:
            print(f"  Warning: Batch GET failed: {e}")
            failed += len(batch)
            continue

        # Set new keys with pipeline
        pipe = r.pipeline()
        for key, result in zip(batch, results):
            if result is None:
                continue

            new_key = key.replace(source.encode(), target.encode())
            key_type = r.type(key)

            try:
                if key_type == b'string':
                    pipe.set(new_key, result)
                elif key_type == b'hash':
                    for field, value in result.items():
                        pipe.hset(new_key, field, value)
                elif key_type == b'list' and result:
                    pipe.rpush(new_key, *result)
                elif key_type == b'set' and result:
                    pipe.sadd(new_key, *result)
                elif key_type == b'zset' and result:
                    pipe.zadd(new_key, dict(result))
            except Exception as e:
                print(f"  Warning: Failed to prepare key {key.decode()}: {e}")
                failed += 1

        try:
            pipe.execute()
            migrated += len(batch)
        except Exception as e:
            print(f"  Warning: Batch SET failed: {e}")
            failed += len(batch)

        if migrated % 5000 == 0 and migrated > 0:
            print(f"  Progress: {migrated}/{total} ({migrated*100//total}%)")

    # Verify
    final_count = len(list(r.scan_iter(match=f'*{target}*', count=1000)))

    return {
        'total': total,
        'migrated': migrated,
        'failed': failed,
        'final_count': final_count
    }


def migrate_qdrant_points(qdrant_url: str, source: str, target: str, dry_run: bool = False) -> Dict[str, int]:
    """Migrate Qdrant vector points from source to target tenant"""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating Qdrant points: {source} → {target}")

    collections = ['lightrag_vdb_chunks', 'lightrag_vdb_entities', 'lightrag_vdb_relationships']
    total_migrated = 0

    for collection in collections:
        print(f"  Collection: {collection}")

        # Count points with source workspace_id
        count_response = requests.post(
            f'{qdrant_url}/collections/{collection}/points/scroll',
            json={
                'limit': 1,
                'with_payload': False,
                'with_vector': False,
                'filter': {
                    'must': [{'key': 'workspace_id', 'match': {'value': source}}]
                }
            }
        )

        if count_response.status_code != 200:
            print(f"    Warning: Failed to access collection: {count_response.text}")
            continue

        # Migrate points
        offset = None
        migrated = 0

        while True:
            scroll_data = {
                'limit': 100,
                'with_payload': True,
                'with_vector': False,
                'filter': {
                    'must': [{'key': 'workspace_id', 'match': {'value': source}}]
                }
            }
            if offset:
                scroll_data['offset'] = offset

            response = requests.post(
                f'{qdrant_url}/collections/{collection}/points/scroll',
                json=scroll_data
            )

            if response.status_code != 200:
                break

            result = response.json()['result']
            points = result['points']

            if not points:
                break

            if dry_run:
                migrated += len(points)
            else:
                # Update workspace_id
                point_ids = [p['id'] for p in points]

                update_response = requests.post(
                    f'{qdrant_url}/collections/{collection}/points/payload',
                    json={
                        'points': point_ids,
                        'payload': {'workspace_id': target}
                    }
                )

                if update_response.status_code == 200:
                    migrated += len(points)

            offset = result.get('next_page_offset')
            if not offset:
                break

            time.sleep(0.1)

        print(f"    Migrated: {migrated} points")
        total_migrated += migrated

    return {'total': total_migrated, 'migrated': total_migrated, 'failed': 0}


def migrate_memgraph_nodes(host: str, port: int, source: str, target: str, dry_run: bool = False) -> Dict[str, int]:
    """Migrate Memgraph graph nodes from source to target tenant"""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating Memgraph nodes: {source} → {target}")

    try:
        from mgclient import connect
    except ImportError:
        print("  Warning: mgclient not found. Install with: pip install mgclient")
        return {'total': 0, 'migrated': 0, 'failed': 0}

    try:
        conn = connect(host=host, port=port, use_ssl=False)
        cursor = conn.cursor()

        # Count nodes
        cursor.execute(f"MATCH (n:{source}) RETURN count(n)")
        count = cursor.fetchone()[0]
        print(f"  Found {count} nodes")

        if dry_run:
            conn.close()
            return {'total': count, 'migrated': 0, 'failed': 0}

        # Add new label
        cursor.execute(f"MATCH (n:{source}) SET n:{target}")

        # Remove old label
        cursor.execute(f"MATCH (n:{source}) REMOVE n:{source}")

        # Verify
        cursor.execute(f"MATCH (n:{target}) RETURN count(n)")
        final_count = cursor.fetchone()[0]

        conn.close()

        return {'total': count, 'migrated': final_count, 'failed': 0}
    except Exception as e:
        print(f"  Error: {e}")
        return {'total': 0, 'migrated': 0, 'failed': 0}


def migrate_tenant_config(api_url: str, source: str, target: str, dry_run: bool = False) -> bool:
    """Migrate tenant configuration via API"""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating tenant config: {source} → {target}")

    # Get source config
    response = requests.get(f'{api_url}/tenants/{source}/config')

    if response.status_code != 200:
        print(f"  Warning: Failed to get source config: {response.status_code}")
        return False

    config = response.json()
    print(f"  Source config found: {config.get('tenant_id')}")

    if dry_run:
        return True

    # Create target config
    config['tenant_id'] = target
    config.pop('created_at', None)

    response = requests.put(f'{api_url}/tenants/{target}/config', json=config)

    if response.status_code == 200:
        print(f"  Target config created")
        return True
    else:
        print(f"  Warning: Failed to create target config: {response.status_code}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Migrate tenant data across all storage systems',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('source_tenant_id', help='Source tenant ID')
    parser.add_argument('target_tenant_id', help='Target tenant ID')

    parser.add_argument('--redis-host', default='localhost', help='Redis host')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port')
    parser.add_argument('--qdrant-url', default='http://localhost:6333', help='Qdrant URL')
    parser.add_argument('--memgraph-host', default='localhost', help='Memgraph host')
    parser.add_argument('--memgraph-port', type=int, default=7687, help='Memgraph port')
    parser.add_argument('--api-url', default='http://localhost:8000', help='API URL')

    parser.add_argument('--dry-run', action='store_true', help='Show migration plan without executing')
    parser.add_argument('--skip-redis', action='store_true', help='Skip Redis migration')
    parser.add_argument('--skip-qdrant', action='store_true', help='Skip Qdrant migration')
    parser.add_argument('--skip-memgraph', action='store_true', help='Skip Memgraph migration')
    parser.add_argument('--skip-config', action='store_true', help='Skip config migration')

    args = parser.parse_args()

    print("=" * 60)
    print(f"Tenant Data Migration: {args.source_tenant_id} → {args.target_tenant_id}")
    print("=" * 60)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No data will be modified")

    results = {}

    # Migrate tenant config
    if not args.skip_config:
        results['config'] = migrate_tenant_config(
            args.api_url,
            args.source_tenant_id,
            args.target_tenant_id,
            dry_run=args.dry_run
        )

    # Migrate Redis
    if not args.skip_redis:
        try:
            r = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=False)
            r.ping()
            results['redis'] = migrate_redis_keys(
                r,
                args.source_tenant_id,
                args.target_tenant_id,
                dry_run=args.dry_run
            )
        except Exception as e:
            print(f"\nError connecting to Redis: {e}")
            results['redis'] = {'total': 0, 'migrated': 0, 'failed': 0}

    # Migrate Qdrant
    if not args.skip_qdrant:
        results['qdrant'] = migrate_qdrant_points(
            args.qdrant_url,
            args.source_tenant_id,
            args.target_tenant_id,
            dry_run=args.dry_run
        )

    # Migrate Memgraph
    if not args.skip_memgraph:
        results['memgraph'] = migrate_memgraph_nodes(
            args.memgraph_host,
            args.memgraph_port,
            args.source_tenant_id,
            args.target_tenant_id,
            dry_run=args.dry_run
        )

    # Summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)

    if 'config' in results:
        status = "✅ Created" if results['config'] else "❌ Failed"
        print(f"Tenant Config: {status}")

    if 'redis' in results:
        r = results['redis']
        print(f"Redis: {r['migrated']}/{r['total']} keys (failed: {r['failed']})")
        if 'final_count' in r:
            print(f"  Final count: {r['final_count']} keys")

    if 'qdrant' in results:
        q = results['qdrant']
        print(f"Qdrant: {q['migrated']} points")

    if 'memgraph' in results:
        m = results['memgraph']
        print(f"Memgraph: {m['migrated']} nodes")

    print("=" * 60)

    if args.dry_run:
        print("\n⚠️  This was a DRY RUN. Re-run without --dry-run to execute migration.")
    else:
        print("\n✅ Migration completed!")


if __name__ == '__main__':
    main()
