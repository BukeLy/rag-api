-- ============================================================
-- PostgreSQL 初始化脚本
-- 用途：为 LightRAG 配置 PostgreSQL + pgvector 扩展
-- ============================================================
-- 使用说明：
-- 此脚本会在 PostgreSQL 容器首次启动时自动执行
-- 挂载路径：/docker-entrypoint-initdb.d/init.sql
-- ============================================================

-- ==================== 扩展安装 ====================

-- 启用 pgvector 扩展（用于向量存储和相似度搜索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展安装成功
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';

-- ==================== 性能优化 ====================

-- 注意：以下性能参数应在 postgresql.conf 中配置
-- 此处仅作文档说明

-- shared_buffers = 256MB          -- 共享缓冲区
-- effective_cache_size = 1GB       -- 有效缓存大小
-- work_mem = 16MB                  -- 排序/哈希操作内存
-- maintenance_work_mem = 128MB     -- 维护操作内存
-- max_connections = 100            -- 最大连接数

-- ==================== 用户权限 ====================

-- 授予 lightrag 用户完全权限
GRANT ALL PRIVILEGES ON DATABASE lightrag TO lightrag;
GRANT ALL PRIVILEGES ON SCHEMA public TO lightrag;

-- 允许创建扩展
ALTER USER lightrag WITH CREATEDB CREATEROLE;

-- ==================== 监控视图 ====================

-- 数据库大小监控视图
CREATE OR REPLACE VIEW v_database_size AS
SELECT
    pg_database.datname AS database_name,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE pg_database.datname = 'lightrag';

-- 表大小监控视图
CREATE OR REPLACE VIEW v_table_sizes AS
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- ==================== 完成 ====================

DO $$
BEGIN
    RAISE NOTICE '✓ PostgreSQL 初始化完成';
    RAISE NOTICE '   - pgvector 扩展已启用';
    RAISE NOTICE '   - lightrag 用户权限已配置';
    RAISE NOTICE '   - 监控视图已创建';
END $$;
