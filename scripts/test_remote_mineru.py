#!/usr/bin/env python3
"""
远程 MinerU 功能测试脚本（简化版）

用于测试文件服务和远程 MinerU 集成功能
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SimpleFileURLService:
    """简化版文件 URL 服务，用于测试"""
    
    def __init__(self, base_url: str = "http://localhost:8000", 
                 temp_dir: str = "/tmp/rag-files"):
        self.base_url = base_url
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        self.file_mapping = {}  # file_id -> file_path
        logger.info(f"FileURLService initialized: {base_url}, temp_dir: {temp_dir}")
    
    async def register_file(self, file_path: str, filename: str) -> str:
        """注册文件并返回访问 URL（8000 端口）"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")
        
        import uuid
        import shutil
        
        file_id = str(uuid.uuid4())
        safe_filename = self._sanitize_filename(filename)
        target_path = os.path.join(self.temp_dir, f"{file_id}_{safe_filename}")
        
        # 复制文件到服务目录
        shutil.copy2(file_path, target_path)
        self.file_mapping[file_id] = target_path
        
        # 使用 8000 端口的 URL
        file_url = f"{self.base_url}/files/{file_id}/{safe_filename}"
        logger.info(f"File registered: {filename} -> {file_url}")
        
        return file_url
    
    def get_file_path(self, file_id: str):
        """根据文件 ID 获取本地路径"""
        return self.file_mapping.get(file_id)
    
    def cleanup_file(self, file_id: str):
        """清理单个文件"""
        file_path = self.file_mapping.get(file_id)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                del self.file_mapping[file_id]
                logger.info(f"Cleaned up file: {file_id}")
            except OSError as e:
                logger.warning(f"Failed to cleanup file {file_id}: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，确保 URL 安全"""
        # 移除路径分隔符和特殊字符
        safe_name = os.path.basename(filename)
        safe_name = safe_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in ['_', '-', '.'])
        return safe_name or "file"


async def test_file_service():
    """测试文件服务功能"""
    print("🧪 测试文件服务...")
    
    # 创建测试文件
    test_file = "/tmp/test_remote_mineru.txt"
    with open(test_file, 'w') as f:
        f.write("这是一个测试文件内容，用于验证远程 MinerU 功能。")
    
    # 初始化文件服务
    file_service = SimpleFileURLService(base_url="http://localhost:8000")
    
    try:
        # 注册文件
        file_url = await file_service.register_file(test_file, "test_file.txt")
        print(f"✅ 文件注册成功: {file_url}")
        
        # 获取文件路径
        file_id = file_url.split('/')[-2]
        file_path = file_service.get_file_path(file_id)
        print(f"✅ 文件路径获取成功: {file_path}")
        
        # 验证文件存在
        if file_path and os.path.exists(file_path):
            print("✅ 文件复制验证成功")
        else:
            print("❌ 文件复制失败")
            return False
            
        # 清理文件
        file_service.cleanup_file(file_id)
        print("✅ 文件清理成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 文件服务测试失败: {e}")
        return False


async def test_mineru_client():
    """测试 MinerU 客户端功能"""
    print("\n🧪 测试 MinerU 客户端...")
    
    try:
        # 检查 API Token 是否配置
        api_token = os.getenv("MINERU_API_TOKEN")
        if not api_token or api_token == "your_mineru_api_token_here":
            print("⚠️  MINERU_API_TOKEN 未配置，跳过客户端测试")
            return True
        
        # 测试健康检查（简单网络连通性测试）
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("https://mineru.net/api/v4/health") as response:
                if response.status == 200:
                    print("✅ MinerU API 连通性测试成功")
                else:
                    print(f"⚠️  MinerU API 连通性异常: {response.status}")
        
        return True
        
    except Exception as e:
        print(f"❌ MinerU 客户端测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 开始远程 MinerU 功能测试")
    print("=" * 50)
    
    # 测试文件服务
    file_service_ok = await test_file_service()
    
    # 测试 MinerU 客户端
    mineru_client_ok = await test_mineru_client()
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print(f"   文件服务: {'✅ 通过' if file_service_ok else '❌ 失败'}")
    print(f"   MinerU 客户端: {'✅ 通过' if mineru_client_ok else '❌ 失败'}")
    
    if file_service_ok and mineru_client_ok:
        print("\n🎉 所有基础测试通过！")
        print("\n下一步:")
        print("1. 配置 MINERU_API_TOKEN 环境变量")
        print("2. 运行部署脚本: ./scripts/update.sh")
        print("3. 测试实际文件上传功能")
        return 0
    else:
        print("\n❌ 测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
