#!/usr/bin/env python3
"""
pn¡˚,áˆX® í Ëpnì

(
∞	Ñ LightRAG áˆX®pn¡˚0ËpnìRedis + PostgreSQL + Neo4j	

(π’:
  python scripts/migrate_to_external_storage.py --dry-run    # ÑûEôe	
  python scripts/migrate_to_external_storage.py --execute    # gL¡˚

Ë
1. n› .env áˆ-ÚMnËX®ﬁ•·o
2. n›Ópnì°Ú/®vÔøÓ
3. ˙ÆH–L --dry-run !¿Âpn
"""

import os
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# †}ØÉÿœ
load_dotenv()


class DataMigrator:
    """pn¡˚hŒáˆX®¡˚0Ëpnì"""

    def __init__(self, source_dir: str, dry_run: bool = True):
        """
        À¡˚h

        Args:
            source_dir: êpnÓU8/ ./rag_local_storage	
            dry_run: /&:Ñ!True=ûEôeFalse=gL¡˚	
        """
        self.source_dir = Path(source_dir)
        self.dry_run = dry_run
        self.stats = {
            "kv_entries": 0,
            "vectors": 0,
            "graph_nodes": 0,
            "graph_edges": 0
        }

    async def migrate_kv_storage(self):
        """¡˚ KV X®JSON í Redis"""
        print("\n= Migrating KV storage (JSON í Redis)...")

        # KV X®áˆh
        kv_files = [
            "kv_store_full_docs.json",
            "kv_store_text_chunks.json",
            "kv_store_llm_response_cache.json",
        ]

        if self.dry_run:
            # Ñ!Íﬂ°pn
            for file in kv_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.stats["kv_entries"] += len(data)
                            print(f"   Found {len(data)} entries in {file}")
                    except Exception as e:
                        print(f"  †  Failed to read {file}: {e}")
                else:
                    print(f"  †  File not found: {file}")
        else:
            # ûE¡˚!
            try:
                from lightrag.kg.redis_impl import RedisKVStorage
            except ImportError:
                print("  L RedisKVStorage not available. Please install required dependencies.")
                return

            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))

            print(f"  Connecting to Redis: {redis_host}:{redis_port} (db={redis_db})")

            redis = RedisKVStorage(
                namespace="lightrag",
                global_config={},
                embedding_func=None,
                host=redis_host,
                port=redis_port,
                db=redis_db
            )

            for file in kv_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            for key, value in data.items():
                                await redis.set(key, value)
                            self.stats["kv_entries"] += len(data)
                            print(f"   Migrated {len(data)} entries from {file}")
                    except Exception as e:
                        print(f"  L Failed to migrate {file}: {e}")
                else:
                    print(f"  †  File not found: {file}")

    async def migrate_vector_storage(self):
        """¡˚œX®NanoVectorDB (JSON) í PostgreSQL"""
        print("\n= Migrating vector storage (JSON í PostgreSQL)...")

        # œX®áˆh
        vector_files = [
            "vdb_entities.json",
            "vdb_relationships.json",
            "vdb_chunks.json"
        ]

        if self.dry_run:
            # Ñ!Íﬂ°pn
            for file in vector_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            self.stats["vectors"] += len(data)
                            print(f"   Found {len(data)} vectors in {file}")
                    except Exception as e:
                        print(f"  †  Failed to read {file}: {e}")
                else:
                    print(f"  †  File not found: {file}")
        else:
            # ûE¡˚!
            try:
                from lightrag.kg.postgres_impl import PGVectorStorage
            except ImportError:
                print("  L PGVectorStorage not available. Please install required dependencies.")
                return

            postgres_host = os.getenv("POSTGRES_HOST", "localhost")
            postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
            postgres_db = os.getenv("POSTGRES_DB", "lightrag")
            postgres_user = os.getenv("POSTGRES_USER", "lightrag")

            print(f"  Connecting to PostgreSQL: {postgres_host}:{postgres_port}/{postgres_db}")

            pg_vector = PGVectorStorage(
                namespace="lightrag",
                global_config={},
                embedding_func=None,
                host=postgres_host,
                port=postgres_port,
                database=postgres_db,
                user=postgres_user,
                password=os.getenv("POSTGRES_PASSWORD", "")
            )

            await pg_vector.initialize()

            for file in vector_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            for key, item in data.items():
                                await pg_vector.insert(
                                    id=key,
                                    embedding=item["embedding"],
                                    metadata=item.get("metadata", {})
                                )
                            self.stats["vectors"] += len(data)
                            print(f"   Migrated {len(data)} vectors from {file}")
                    except Exception as e:
                        print(f"  L Failed to migrate {file}: {e}")
                else:
                    print(f"  †  File not found: {file}")

    async def migrate_graph_storage(self):
        """¡˚˛X®NetworkX/GraphML í Neo4j"""
        print("\n= Migrating graph storage (GraphML í Neo4j)...")

        graph_file = self.source_dir / "graph_chunk_entity_relation.graphml"

        if not graph_file.exists():
            print("  †  GraphML file not found, skipping graph migration")
            return

        if self.dry_run:
            # Ñ!Íﬂ°pn
            try:
                import networkx as nx
                G = nx.read_graphml(graph_file)
                self.stats["graph_nodes"] = G.number_of_nodes()
                self.stats["graph_edges"] = G.number_of_edges()
                print(f"   Found {self.stats['graph_nodes']} nodes and {self.stats['graph_edges']} edges")
            except Exception as e:
                print(f"  L Failed to read GraphML: {e}")
        else:
            # ûE¡˚!
            try:
                import networkx as nx
                from neo4j import AsyncGraphDatabase
            except ImportError:
                print("  L Required libraries not available. Please install networkx and neo4j.")
                return

            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "")

            print(f"  Connecting to Neo4j: {neo4j_uri}")

            G = nx.read_graphml(graph_file)

            driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_username, neo4j_password)
            )

            try:
                async with driver.session() as session:
                    # ˙Çπ
                    print(f"  Migrating {G.number_of_nodes()} nodes...")
                    for node_id, node_data in G.nodes(data=True):
                        await session.run(
                            "MERGE (n:Entity {id: $id}) SET n += $properties",
                            id=node_id,
                            properties=dict(node_data)
                        )
                    self.stats["graph_nodes"] = G.number_of_nodes()

                    # ˙π
                    print(f"  Migrating {G.number_of_edges()} edges...")
                    for src, tgt, edge_data in G.edges(data=True):
                        await session.run(
                            "MATCH (a:Entity {id: $src}), (b:Entity {id: $tgt}) "
                            "MERGE (a)-[r:RELATES_TO]->(b) SET r += $properties",
                            src=src,
                            tgt=tgt,
                            properties=dict(edge_data)
                        )
                    self.stats["graph_edges"] = G.number_of_edges()

                print(f"   Migrated {self.stats['graph_nodes']} nodes and {self.stats['graph_edges']} edges")
            finally:
                await driver.close()

    async def run(self):
        """gLåt¡˚A"""
        print("=" * 70)
        print(f"{'>Í DRY RUN MODE' if self.dry_run else '° LIVE MIGRATION MODE'}")
        print(f"Source directory: {self.source_dir}")
        print("=" * 70)

        # ¿ÂêÓU/&X(
        if not self.source_dir.exists():
            print(f"\nL Source directory not found: {self.source_dir}")
            print("   Please ensure LightRAG has been initialized with file storage first.")
            return

        # gL¡˚
        await self.migrate_kv_storage()
        await self.migrate_vector_storage()
        await self.migrate_graph_storage()

        # ì˙ﬂ°·o
        print("\n" + "=" * 70)
        print("=  Migration Summary")
        print("=" * 70)
        print(f"  KV Entries:   {self.stats['kv_entries']}")
        print(f"  Vectors:      {self.stats['vectors']}")
        print(f"  Graph Nodes:  {self.stats['graph_nodes']}")
        print(f"  Graph Edges:  {self.stats['graph_edges']}")
        print("=" * 70)

        if self.dry_run:
            print("\n Dry run completed. Run with --execute to perform actual migration.")
        else:
            print("\n Migration completed successfully!")
            print("   You can now set USE_EXTERNAL_STORAGE=true in .env and restart the service.")


async def main():
    parser = argparse.ArgumentParser(
        description="Migrate LightRAG data from file storage to external databases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration (recommended first step)
  python scripts/migrate_to_external_storage.py --dry-run

  # Execute actual migration
  python scripts/migrate_to_external_storage.py --execute

  # Specify custom source directory
  python scripts/migrate_to_external_storage.py --execute --source-dir /path/to/rag_local_storage
        """
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate migration without writing data (recommended first)")
    parser.add_argument("--execute", action="store_true",
                        help="Execute actual migration")
    parser.add_argument("--source-dir", default="./rag_local_storage",
                        help="Source directory for file storage (default: ./rag_local_storage)")

    args = parser.parse_args()

    # å¡¬p
    if not args.dry_run and not args.execute:
        print("L Error: Must specify either --dry-run or --execute")
        parser.print_help()
        return

    # ˙¡˚hv–L
    migrator = DataMigrator(
        source_dir=args.source_dir,
        dry_run=args.dry_run
    )

    await migrator.run()


if __name__ == "__main__":
    asyncio.run(main())
