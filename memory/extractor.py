"""Schema-driven dynamic semantic memory extractor."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import ALLOWED_MEMORY_KEYS
from llm import get_chat_model_with_fallback as get_chat_model
from memory.store import get_memory_store


class MemoryFieldSpec(BaseModel):
    """Specification of a permissible memory attribute."""
    key: str
    display_name: str
    description: str
    examples: List[str] = Field(default_factory=list)


# Schema definitions for allowed memory fields
MEMORY_FIELD_SPECS: Dict[str, MemoryFieldSpec] = {
    "business_type": MemoryFieldSpec(
        key="business_type",
        display_name="Loại hình doanh nghiệp",
        description="Mô hình pháp lý của doanh nghiệp (TNHH, Cổ phần, Doanh nghiệp tư nhân, Hợp danh...)",
        examples=["Công ty TNHH", "Công ty Cổ phần", "Doanh nghiệp tư nhân"],
    ),
    "province": MemoryFieldSpec(
        key="province",
        display_name="Địa bàn hoạt động / Trụ sở",
        description="Tỉnh, thành phố hoặc địa bàn đặt trụ sở chính của doanh nghiệp tại Việt Nam",
        examples=["Hà Nội", "TP.HCM", "Long An", "Bình Dương", "Đà Nẵng"],
    ),
    "industry": MemoryFieldSpec(
        key="industry",
        display_name="Ngành nghề kinh doanh",
        description="Lĩnh vực hoạt động sản xuất, kinh doanh chính của doanh nghiệp",
        examples=["Xây dựng", "Thương mại điện tử", "Công nghệ thông tin", "Dệt may", "Logistics"],
    ),
    "frequent_topic": MemoryFieldSpec(
        key="frequent_topic",
        display_name="Chủ đề quan tâm thường xuyên",
        description="Nhóm văn bản hoặc chế độ pháp lý mà doanh nghiệp thường xuyên tra cứu",
        examples=["Pháp luật lao động", "Đăng ký doanh nghiệp", "Bảo hiểm xã hội", "Thuế"],
    ),
    "preferred_answer": MemoryFieldSpec(
        key="preferred_answer",
        display_name="Phong cách trả lời ưa thích",
        description="Yêu cầu định dạng câu trả lời mong muốn của người dùng",
        examples=["Ngắn gọn", "Chi tiết kèm viện dẫn điều khoản", "Bảng biểu tóm tắt"],
    ),
}


class ExtractedMemoryItem(BaseModel):
    """Structured memory attribute extracted from conversation."""
    key: str = Field(..., description="Key belonging to ALLOWED_MEMORY_KEYS")
    value: str = Field(..., min_length=1, description="Extracted entity value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None


def extract_memories_dynamically(text: str) -> List[ExtractedMemoryItem]:
    """Extract memory attributes dynamically using LLM structured output or generalized grammar patterns."""
    text_clean = text.strip()
    if not text_clean:
        return []

    # 1. Primary: LLM structured entity extraction if model is available
    llm = get_chat_model()
    if llm is not None:
        llm_results = _extract_with_llm(llm, text_clean)
        if llm_results:
            return llm_results

    # 2. Fallback: Generalized grammar-based extraction (zero hardcoded city/industry dictionaries)
    return _extract_with_grammar_patterns(text_clean)


def _extract_with_llm(llm: Any, text: str) -> List[ExtractedMemoryItem]:
    """Extract entities adhering to MEMORY_FIELD_SPECS via LLM."""
    specs_summary = "\n".join([
        f"- {s.key} ({s.display_name}): {s.description}"
        for s in MEMORY_FIELD_SPECS.values()
    ])

    prompt = f"""Bạn là bộ trích xuất hồ sơ doanh nghiệp (Entity Memory Extractor) cho trợ lý pháp lý.
Hãy đọc câu nói của người dùng và trích xuất các thông tin bền vững nếu có:

DANH MỤC THUỘC TÍNH CHO PHÉP:
{specs_summary}

NGUYÊN TẮC BẢO MẬT BẮT BUỘC:
1. Tuyệt đối KHÔNG trích xuất mật khẩu, số CCCD/CMND, mã số thuế bí mật, bí mật kinh doanh.
2. Chỉ trích xuất khi người dùng tự nêu thông tin về hoàn cảnh công ty/doanh nghiệp của họ.
3. Nếu không có thông tin thuộc danh mục trên, trả về mảng rỗng [].

Định dạng JSON đầu ra:
[
  {{"key": "business_type", "value": "Công ty TNHH", "confidence": 0.95}},
  {{"key": "province", "value": "Long An", "confidence": 0.90}}
]

CÂU NÓI: "{text}"
"""
    try:
        res = llm.invoke(prompt)
        raw = res.content if hasattr(res, "content") else str(res)
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            items = json.loads(m.group(0))
            validated = []
            for item in items:
                k = item.get("key", "").strip().lower()
                v = item.get("value", "").strip()
                if k in ALLOWED_MEMORY_KEYS and v:
                    validated.append(ExtractedMemoryItem(
                        key=k,
                        value=v,
                        confidence=float(item.get("confidence", 0.85)),
                    ))
            return validated
    except Exception:
        pass

    return []


def _extract_with_grammar_patterns(text: str) -> List[ExtractedMemoryItem]:
    """Generalized grammar and entity pattern matching without hardcoded entity dictionaries."""
    extracted = []
    text_lower = text.lower()

    # Pattern 1: Business Type (generalized recognition of company legal structures)
    # Matches: công ty TNHH (1 hoặc 2 thành viên), công ty cổ phần, doanh nghiệp tư nhân, hợp danh
    bt_match = re.search(
        r"(?:doanh nghiệp|công ty)\s+(tnhh(?:\s+[0-9a-zA-Z\s]+thành viên)?|cổ phần|hợp danh|tư nhân|liên doanh)",
        text_lower,
    )
    if bt_match:
        matched_str = bt_match.group(0)
        norm_val = "Công ty TNHH"
        if "cổ phần" in matched_str:
            norm_val = "Công ty Cổ phần"
        elif "tư nhân" in matched_str:
            norm_val = "Doanh nghiệp tư nhân"
        elif "hợp danh" in matched_str:
            norm_val = "Công ty Hợp danh"
        elif "tnhh" in matched_str:
            if "1" in matched_str or "một" in matched_str:
                norm_val = "Công ty TNHH 1 thành viên"
            elif "2" in matched_str or "hai" in matched_str:
                norm_val = "Công ty TNHH 2 thành viên trở lên"
            else:
                norm_val = "Công ty TNHH"

        extracted.append(ExtractedMemoryItem(
            key="business_type",
            value=norm_val,
            confidence=0.95,
            reasoning="Phát hiện qua cấu trúc loại hình doanh nghiệp",
        ))

    # Pattern 2: Geographic Proper Noun (captures ANY capitalized province/city name after locative prepositions)
    # e.g.: "tại Long An", "ở Hà Nội", "trụ sở tại Đà Nẵng", "tại Bình Dương", "ở Cà Mau"
    # Uses Vietnamese capitalized word sequence recognition
    loc_match = re.search(
        r"(?:tại|ở|trụ sở tại|địa bàn|khu vực|tỉnh|thành phố|tp\.?)\s+([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)*)",
        text,
    )
    if loc_match:
        province_val = loc_match.group(1).strip()
        # Exclude common false positives
        if province_val.lower() not in ("việt nam", "công ty", "doanh nghiệp", "bộ luật", "luật"):
            extracted.append(ExtractedMemoryItem(
                key="province",
                value=province_val,
                confidence=0.90,
                reasoning=f"Nhận diện địa danh ngữ pháp: {province_val}",
            ))

    # Pattern 3: Industry / Domain
    # Matches: "ngành xây dựng", "lĩnh vực bán lẻ", "hoạt động trong thương mại điện tử"
    ind_match = re.search(r"(?:ngành|lĩnh vực|hoạt động trong(?:\s+mảng)?)\s+([A-Za-zÀ-ỹ\s]{3,30}?)(?=[,.;\?]|$|\s+muốn|\s+cần)", text, re.IGNORECASE)
    if ind_match:
        ind_val = ind_match.group(1).strip().capitalize()
        extracted.append(ExtractedMemoryItem(
            key="industry",
            value=ind_val,
            confidence=0.85,
            reasoning=f"Nhận diện lĩnh vực kinh doanh: {ind_val}",
        ))

    # Pattern 4: Frequent Topic
    topic_keywords = {
        "Pháp luật lao động": ["lao động", "thử việc", "hợp đồng", "sa thải", "tiền lương", "nghỉ phép"],
        "Đăng ký & Quản trị doanh nghiệp": ["thành lập", "đăng ký doanh nghiệp", "vốn điều lệ", "cổ đông", "hội đồng"],
        "Bảo hiểm xã hội": ["bảo hiểm xã hội", "bhxh", "hưu trí", "thai sản", "ốm đau", "mai táng"],
    }
    for topic_name, keywords in topic_keywords.items():
        if any(kw in text_lower for kw in keywords):
            extracted.append(ExtractedMemoryItem(
                key="frequent_topic",
                value=topic_name,
                confidence=0.80,
            ))
            break

    return extracted


def extract_and_save_memories(client_id: str, text: str) -> List[Dict[str, Any]]:
    """Top-level pipeline function: extract dynamic memories and persist to store."""
    store = get_memory_store()
    items = extract_memories_dynamically(text)

    saved = []
    for item in items:
        if store.set_client_memory(client_id, item.key, item.value, confidence=item.confidence):
            saved.append(item.model_dump())

    return saved
