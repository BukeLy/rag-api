"""
测试 LightRAG doc_status API 的实际行为

目的：验证 get_docs_paginated() 等方法是否真实存在，返回格式是什么
"""

import asyncio
import sys
from src.multi_tenant import get_multi_tenant_manager
from src.logger import logger

async def test_doc_status_api():
    """测试 doc_status API 的实际行为"""

    print("=" * 70)
    print("🧪 测试 LightRAG doc_status API")
    print("=" * 70)

    # 获取多租户管理器
    manager = get_multi_tenant_manager()

    # 使用测试租户
    test_tenant_id = "test_doc_status"

    try:
        # 获取 LightRAG 实例
        print(f"\n1. 获取租户实例: {test_tenant_id}")
        lightrag = await manager.get_instance(test_tenant_id)
        print(f"✓ 实例类型: {type(lightrag)}")

        # 检查 doc_status 属性
        print(f"\n2. 检查 doc_status 属性")
        if hasattr(lightrag, 'doc_status'):
            print(f"✓ lightrag.doc_status 存在")
            print(f"  类型: {type(lightrag.doc_status)}")
            print(f"  模块: {type(lightrag.doc_status).__module__}")
            print(f"  类名: {type(lightrag.doc_status).__name__}")
        else:
            print(f"✗ lightrag.doc_status 不存在")
            return False

        # 检查可用方法
        print(f"\n3. 检查可用方法")
        doc_status_methods = [m for m in dir(lightrag.doc_status) if not m.startswith('_')]
        print(f"公开方法列表:")
        for method in doc_status_methods:
            print(f"  - {method}")

        # 测试 get_docs_paginated
        print(f"\n4. 测试 get_docs_paginated()")
        if hasattr(lightrag.doc_status, 'get_docs_paginated'):
            print(f"✓ get_docs_paginated 方法存在")

            try:
                result = await lightrag.doc_status.get_docs_paginated(
                    status_filter=None,
                    page=1,
                    page_size=10,
                    sort_field="created_at",
                    sort_direction="desc"
                )

                print(f"\n返回值分析:")
                print(f"  类型: {type(result)}")

                if isinstance(result, tuple):
                    print(f"  元组长度: {len(result)}")
                    if len(result) >= 2:
                        docs, total = result[0], result[1]
                        print(f"  docs 类型: {type(docs)}")
                        print(f"  total 类型: {type(total)}")
                        print(f"  total 值: {total}")

                        if isinstance(docs, dict):
                            print(f"  docs 是字典，keys 数量: {len(docs)}")
                            if docs:
                                first_key = next(iter(docs))
                                first_value = docs[first_key]
                                print(f"  第一个 key: {first_key}")
                                print(f"  第一个 value 类型: {type(first_value)}")
                        elif isinstance(docs, list):
                            print(f"  docs 是列表，长度: {len(docs)}")
                            if docs:
                                print(f"  第一个元素类型: {type(docs[0])}")
                else:
                    print(f"  不是元组: {result}")

            except NotImplementedError as e:
                print(f"✗ get_docs_paginated 未实现: {e}")
                return False
            except Exception as e:
                print(f"✗ 调用失败: {e}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print(f"✗ get_docs_paginated 方法不存在")
            return False

        # 测试 get_all_status_counts
        print(f"\n5. 测试 get_all_status_counts()")
        if hasattr(lightrag.doc_status, 'get_all_status_counts'):
            print(f"✓ get_all_status_counts 方法存在")

            try:
                counts = await lightrag.doc_status.get_all_status_counts()
                print(f"\n返回值分析:")
                print(f"  类型: {type(counts)}")
                print(f"  内容: {counts}")

            except NotImplementedError as e:
                print(f"✗ get_all_status_counts 未实现: {e}")
            except Exception as e:
                print(f"⚠️  调用失败: {e}")
        else:
            print(f"⚠️  get_all_status_counts 方法不存在")

        # 测试 count_by_status
        print(f"\n6. 测试 count_by_status()")
        if hasattr(lightrag.doc_status, 'count_by_status'):
            print(f"✓ count_by_status 方法存在")

            try:
                count = await lightrag.doc_status.count_by_status("processed")
                print(f"\n返回值分析:")
                print(f"  类型: {type(count)}")
                print(f"  值: {count}")

            except NotImplementedError as e:
                print(f"✗ count_by_status 未实现: {e}")
            except Exception as e:
                print(f"⚠️  调用失败: {e}")
        else:
            print(f"⚠️  count_by_status 方法不存在")

        print(f"\n" + "=" * 70)
        print(f"✅ 测试完成")
        print(f"=" * 70)
        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_doc_status_api())
    sys.exit(0 if success else 1)
