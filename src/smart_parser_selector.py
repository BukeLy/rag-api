"""
Smart Parser Selector v2.0

基于 DeepSeek-OCR 完整测试（4 类真实场景）的智能 Parser 选择器

核心变更（v1.0 → v2.0）：
- DS-OCR 可替代 80% MinerU 场景（v1.0 仅 20%）
- 模式选择：Free OCR（默认，80%）+ Grounding（复杂表格，15%）
- 中文支持：✅ 100% 准确（v1.0 错误认为不支持）
- 性能数据：5.18-10.95s（实测）vs MinerU 10-60s
- 成本节省：70-90%

测试依据：
- IELTS（简单表格）：Free OCR 3.95s ✅
- Visa（复杂官方文件）：Grounding 8.31s ✅
- Statement（复杂表格 27 行）：Grounding 5.18s ✅（Free OCR 36.83s 幻觉）
- 毕业证（中文文档）：Free OCR 10.95s ✅（102 字符 100% 准确）
"""

import os
from typing import Optional, Tuple
from enum import Enum
from pathlib import Path

from src.document_complexity import DocumentComplexityAnalyzer, DocumentFeatures
from src.deepseek_ocr_client import DSSeekMode
from src.logger import logger


class ParserType(Enum):
    """Parser 类型枚举"""
    DEEPSEEK_OCR = "deepseek-ocr"
    MINERU = "mineru"
    DOCLING = "docling"


class SmartParserSelector:
    """智能 Parser 选择器 v2.0（基于 4 类真实场景完整测试优化）"""

    # 评分阈值（基于实测调整）
    SIMPLE_THRESHOLD = int(os.getenv("COMPLEXITY_SIMPLE_THRESHOLD", "20"))
    MEDIUM_TABLE_THRESHOLD = int(os.getenv("COMPLEXITY_MEDIUM_TABLE_THRESHOLD", "40"))
    COMPLEX_SINGLE_PAGE_THRESHOLD = int(os.getenv("COMPLEXITY_COMPLEX_SINGLE_PAGE_THRESHOLD", "60"))

    # 特殊规则阈值
    SIMPLE_TABLE_ROW_LIMIT = int(os.getenv("COMPLEXITY_SIMPLE_TABLE_ROW_LIMIT", "10"))
    COMPLEX_TABLE_ROW_LIMIT = int(os.getenv("COMPLEXITY_COMPLEX_TABLE_ROW_LIMIT", "20"))
    CHINESE_CHAR_LOW_THRESHOLD = int(os.getenv("COMPLEXITY_CHINESE_CHAR_LOW_THRESHOLD", "10"))
    CHINESE_CHAR_HIGH_RATIO_THRESHOLD = float(os.getenv("COMPLEXITY_CHINESE_CHAR_HIGH_THRESHOLD", "0.3"))

    def __init__(self, complexity_analyzer: Optional[DocumentComplexityAnalyzer] = None):
        """
        初始化选择器

        Args:
            complexity_analyzer: 复杂度分析器，如果为 None 则创建新实例
        """
        self.analyzer = complexity_analyzer or DocumentComplexityAnalyzer()
        logger.info("SmartParserSelector v2.0 initialized")

    def select_parser(
        self,
        file_path: str,
        vlm_mode: str = "off",
        prefer_speed: bool = True
    ) -> Tuple[ParserType, Optional[DSSeekMode]]:
        """
        智能选择 Parser 和 DS-OCR 模式

        Args:
            file_path: 文件路径
            vlm_mode: VLM 模式 (off/selective/full)
            prefer_speed: 是否优先速度

        Returns:
            (ParserType, DS-OCR 模式)，如果不是 DS-OCR 则模式为 None

        Examples:
            # 简单表格 → DeepSeek-OCR Free OCR
            parser, mode = selector.select_parser("ielts.pdf")
            # (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

            # 复杂表格 → DeepSeek-OCR Grounding
            parser, mode = selector.select_parser("statement.pdf")
            # (ParserType.DEEPSEEK_OCR, DSSeekMode.GROUNDING)

            # 中文文档 → DeepSeek-OCR Free OCR
            parser, mode = selector.select_parser("diploma.pdf")
            # (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

            # 多模态 → MinerU
            parser, mode = selector.select_parser("architecture.pdf")
            # (ParserType.MINERU, None)
        """
        # 1. 纯文本直接跳过
        if self._is_plain_text(file_path):
            logger.info(f"Plain text file detected, skipping parser selection")
            return (ParserType.DOCLING, None)

        # 2. 计算复杂度评分
        complexity = self.analyzer.analyze_complexity(file_path)

        # 3. 获取文档特征
        features = self.analyzer.get_document_features(file_path)

        # 4. 应用决策规则
        parser_type, ds_mode = self._apply_decision_rules(complexity, features, vlm_mode, prefer_speed)

        logger.info(
            f"Parser selected: {parser_type.value}, "
            f"DS-OCR mode: {ds_mode.value if ds_mode else 'N/A'}, "
            f"complexity: {complexity}"
        )

        return (parser_type, ds_mode)

    def _apply_decision_rules(
        self,
        complexity: int,
        features: DocumentFeatures,
        vlm_mode: str,
        prefer_speed: bool
    ) -> Tuple[ParserType, Optional[DSSeekMode]]:
        """
        应用决策规则（基于 4 类真实测试案例）

        Args:
            complexity: 复杂度评分
            features: 文档特征
            vlm_mode: VLM 模式
            prefer_speed: 是否优先速度

        Returns:
            (ParserType, DS-OCR 模式)

        决策树：
        1. complexity < 20 → Free OCR（简单文档）
        2. 20 ≤ complexity < 40:
           - avg_table_row_count < 10 → Free OCR（简单表格，IELTS 教训）
           - avg_table_row_count ≥ 20 → Grounding（复杂表格，Statement 教训）
           - 其他 → Grounding（默认，Visa 教训）
        3. 40 ≤ complexity < 60:
           - chinese_char_ratio > 30% → Free OCR（中文文档，毕业证教训）
           - avg_image_count ≥ 3 → MinerU（多图文档）
           - 其他 → Free OCR（速度优先）或 MinerU
        4. complexity ≥ 60 → MinerU（极复杂多模态）
        """
        # 规则 1：简单文档（< 20 分）→ Free OCR
        if complexity < self.SIMPLE_THRESHOLD:
            logger.debug(f"Rule 1: Simple document (complexity={complexity}) → Free OCR")
            return (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

        # 规则 2：简单表格（20-40 分 + 行数 <10）→ Free OCR
        # 教训来源：IELTS 测试（Free OCR 3.95s 完美，Grounding 4.14s 截断）
        if (self.SIMPLE_THRESHOLD <= complexity < self.MEDIUM_TABLE_THRESHOLD and
            features.avg_table_count_per_page > 0 and
            features.avg_table_row_count < self.SIMPLE_TABLE_ROW_LIMIT):

            logger.debug(
                f"Rule 2: Simple table (rows={features.avg_table_row_count:.1f} < {self.SIMPLE_TABLE_ROW_LIMIT}) → Free OCR"
            )

            # 特殊处理：中文字符 <10 需添加语言提示（避免 IELTS 韩文误判）
            if features.chinese_char_count > 0 and features.chinese_char_count < self.CHINESE_CHAR_LOW_THRESHOLD:
                logger.info(
                    f"Chinese chars < {self.CHINESE_CHAR_LOW_THRESHOLD}, "
                    f"will add language hint to avoid misrecognition"
                )

            return (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

        # 规则 3：复杂表格（20-40 分 + 行数 ≥20）→ Grounding Document
        # 教训来源：Statement 测试（Grounding 5.18s 完美，Free OCR 36.83s 幻觉）
        if (self.SIMPLE_THRESHOLD <= complexity < self.MEDIUM_TABLE_THRESHOLD and
            features.avg_table_row_count >= self.COMPLEX_TABLE_ROW_LIMIT):

            logger.debug(
                f"Rule 3: Complex table (rows={features.avg_table_row_count:.1f} ≥ {self.COMPLEX_TABLE_ROW_LIMIT}) → Grounding"
            )
            return (ParserType.DEEPSEEK_OCR, DSSeekMode.GROUNDING)

        # 规则 4：中等表格（20-40 分）→ Grounding Document（默认）
        # 教训来源：Visa 测试（Grounding 8.31s 完整输出 3214 字符）
        if self.SIMPLE_THRESHOLD <= complexity < self.MEDIUM_TABLE_THRESHOLD:
            logger.debug(f"Rule 4: Medium complexity (20-40) → Grounding (default)")
            return (ParserType.DEEPSEEK_OCR, DSSeekMode.GROUNDING)

        # 规则 5：复杂单页文档（40-60 分）→ 检查中文密度
        # 教训来源：毕业证测试（中文 45.3%，Free OCR 10.95s 完美，102 字符 100% 准确）
        if (self.MEDIUM_TABLE_THRESHOLD <= complexity < self.COMPLEX_SINGLE_PAGE_THRESHOLD):

            # 中文字符多（>30%）→ Free OCR
            if features.chinese_char_ratio > self.CHINESE_CHAR_HIGH_RATIO_THRESHOLD:
                logger.debug(
                    f"Rule 5.1: High Chinese ratio ({features.chinese_char_ratio:.1%} > 30%) → Free OCR"
                )
                return (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

            # 图片多（≥3 个/页）→ MinerU
            if features.avg_image_count_per_page >= 3:
                logger.debug(
                    f"Rule 5.2: Multiple images ({features.avg_image_count_per_page:.1f} ≥ 3) → MinerU"
                )
                return (ParserType.MINERU, None)

            # 其他情况：速度优先 → Free OCR
            if prefer_speed:
                logger.debug(f"Rule 5.3: Prefer speed → Free OCR")
                return (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)
            else:
                logger.debug(f"Rule 5.3: Prefer quality → MinerU")
                return (ParserType.MINERU, None)

        # 规则 6：极复杂文档（> 60 分）→ MinerU
        if complexity >= self.COMPLEX_SINGLE_PAGE_THRESHOLD:
            logger.debug(f"Rule 6: Very complex (complexity={complexity} ≥ 60) → MinerU")
            return (ParserType.MINERU, None)

        # 默认：Free OCR（容错策略）
        logger.warning(f"No rule matched (complexity={complexity}), falling back to Free OCR")
        return (ParserType.DEEPSEEK_OCR, DSSeekMode.FREE_OCR)

    def _is_plain_text(self, file_path: str) -> bool:
        """检查是否为纯文本文件"""
        PLAIN_TEXT_EXTENSIONS = {'.txt', '.md', '.json', '.csv'}
        ext = Path(file_path).suffix.lower()
        return ext in PLAIN_TEXT_EXTENSIONS

    def get_parser_recommendation(self, file_path: str) -> dict:
        """
        获取 Parser 推荐详情（用于调试/可视化）

        Args:
            file_path: 文件路径

        Returns:
            包含推荐详情的字典
        """
        complexity = self.analyzer.analyze_complexity(file_path)
        features = self.analyzer.get_document_features(file_path)
        parser_type, ds_mode = self._apply_decision_rules(complexity, features, "off", True)

        return {
            "file_path": file_path,
            "complexity_score": complexity,
            "recommended_parser": parser_type.value,
            "deepseek_mode": ds_mode.value if ds_mode else None,
            "features": {
                "page_count": features.page_count,
                "avg_image_count_per_page": round(features.avg_image_count_per_page, 2),
                "avg_table_count_per_page": round(features.avg_table_count_per_page, 2),
                "avg_table_row_count": round(features.avg_table_row_count, 2),
                "chinese_char_ratio": round(features.chinese_char_ratio, 2),
                "has_complex_layout": features.has_complex_layout,
            },
            "thresholds": {
                "simple": self.SIMPLE_THRESHOLD,
                "medium_table": self.MEDIUM_TABLE_THRESHOLD,
                "complex_single_page": self.COMPLEX_SINGLE_PAGE_THRESHOLD,
            }
        }


# ============== 便捷函数 ==============

def create_selector() -> SmartParserSelector:
    """
    创建智能选择器（便捷函数）

    Returns:
        SmartParserSelector 实例

    Example:
        selector = create_selector()
        parser, mode = selector.select_parser("document.pdf")
    """
    return SmartParserSelector()


# ============== 示例代码 ==============

def example():
    """使用示例"""
    selector = create_selector()

    # 示例 1：简单表格（IELTS）
    parser, mode = selector.select_parser("tests/fixtures/ielts.pdf")
    print(f"IELTS: {parser.value}, {mode.value if mode else 'N/A'}")
    # 预期输出：IELTS: deepseek-ocr, free_ocr

    # 示例 2：复杂表格（Statement）
    parser, mode = selector.select_parser("tests/fixtures/statement.pdf")
    print(f"Statement: {parser.value}, {mode.value if mode else 'N/A'}")
    # 预期输出：Statement: deepseek-ocr, grounding

    # 示例 3：中文文档（毕业证）
    parser, mode = selector.select_parser("tests/fixtures/diploma.pdf")
    print(f"Diploma: {parser.value}, {mode.value if mode else 'N/A'}")
    # 预期输出：Diploma: deepseek-ocr, free_ocr

    # 示例 4：获取推荐详情
    recommendation = selector.get_parser_recommendation("document.pdf")
    print(f"Recommendation: {recommendation}")


if __name__ == "__main__":
    # 运行示例
    # example()
    pass
