"""Semantic Memory Extractor with Strict Allow-List Governance."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from config import ALLOWED_MEMORY_KEYS
from llm import get_chat_model
from memory.store import get_memory_store


PROVINCES = [
    "Hà Nội", "Hồ Chí Minh", "TP.HCM", "Long An", "Bình Dương", "Đồng Nai",
    "Đà Nẵng", "Hải Phòng", "Cần Thơ", "Quảng Ninh", "Bắc Ninh", "Khánh Hòa",
    "Bà Rịa - Vũng Tàu", "Thừa Thiên Huế", "Lâm Đồng", "Tiền Giang",
]

BUSINESS_TYPES = [
    ("công ty tnhh một thành viên", "Công ty TNHH 1 thành viên"),
    ("công ty tnhh 1 thành viên", "Công ty TNHH 1 thành viên"),
    ("công ty tnhh hai thành viên", "Công ty TNHH 2 thành viên trở lên"),
    ("công ty tnhh 2 thành viên", "Công ty TNHH 2 thành viên trở lên"),
    ("công ty tnhh", "Công ty TNHH"),
    ("tnhh", "Công ty TNHH"),
    ("công ty cổ phần", "Công ty Cổ phần"),
    ("cổ phần", "Công ty Cổ phần"),
    ("doanh nghiệp tư nhân", "Doanh nghiệp tư nhân"),
    ("công ty hợp danh", "Công ty Hợp danh"),
]

INDUSTRIES = [
    ("xây dựng", "Xây dựng"),
    ("thương mại điện tử", "Thương mại điện tử"),
    ("bán lẻ", "Bán lẻ"),
    ("sản xuất", "Sản xuất chế biến"),
    ("công nghệ thông tin", "Công nghệ thông tin / Phần mềm"),
    ("logistics", "Vận tải / Logistics"),
    ("du lịch", "Dịch vụ du lịch"),
    ("y tế", "Y tế / Dược phẩm"),
    ("giáo dục", "Giáo dục / Đào tạo"),
]


def extract_memories_heuristic(text: str) -> List[Dict[str, Any]]:
    """Rule-based pattern extraction for corporate entity attributes."""
    extracted = []
    text_lower = text.lower()

    # 1. Business Type
    for pattern, normalized in BUSINESS_TYPES:
        if pattern in text_lower:
            extracted.append({
                "key": "business_type",
                "value": normalized,
                "confidence": 0.95,
            })
            break

    # 2. Province / Location
    for prov in PROVINCES:
        p_lower = prov.lower()
        if f"tại {p_lower}" in text_lower or f"ở {p_lower}" in text_lower or f"tỉnh {p_lower}" in text_lower or f"tp {p_lower}" in text_lower:
            extracted.append({
                "key": "province",
                "value": prov,
                "confidence": 0.90,
            })
            break

    # 3. Industry
    for ind_kw, ind_norm in INDUSTRIES:
        if ind_kw in text_lower:
            extracted.append({
                "key": "industry",
                "value": ind_norm,
                "confidence": 0.85,
            })
            break

    # 4. Frequent Topic
    if any(k in text_lower for k in ["lao động", "thử việc", "hợp đồng lao động", "sa thải", "lương"]):
        extracted.append({
            "key": "frequent_topic",
            "value": "Pháp luật lao động",
            "confidence": 0.80,
        })
    elif any(k in text_lower for k in ["thành lập", "đăng ký doanh nghiệp", "vốn điều lệ", "cổ đông", "điều lệ"]):
        extracted.append({
            "key": "frequent_topic",
            "value": "Đăng ký & Quản trị doanh nghiệp",
            "confidence": 0.80,
        })
    elif any(k in text_lower for k in ["bảo hiểm xã hội", "bhxh", "hưu trí", "thai sản", "ốm đau"]):
        extracted.append({
            "key": "frequent_topic",
            "value": "Bảo hiểm xã hội",
            "confidence": 0.80,
        })

    return extracted


def extract_and_save_memories(client_id: str, text: str) -> List[Dict[str, Any]]:
    """Extract semantic memories from user utterance and persist to client_memories."""
    store = get_memory_store()
    memories = extract_memories_heuristic(text)

    # If LLM is available and heuristic got nothing, try LLM
    if not memories:
        llm = get_chat_model()
        if llm is not None:
            prompt = f"""Hãy đọc câu nói của người dùng và trích xuất thông tin hồ sơ doanh nghiệp nếu có.
Chỉ trích xuất các thuộc tính nằm trong ALLOWED_MEMORY_KEYS sau:
- business_type (e.g. Công ty TNHH, Công ty Cổ phần)
- industry (e.g. Xây dựng, Bán lẻ)
- province (e.g. Hà Nội, TP.HCM, Long An)
- frequent_topic (e.g. Lao động, Doanh nghiệp)
- preferred_answer (e.g. Ngắn gọn, Chi tiết)

TUYỆT ĐỐI KHÔNG trích xuất mật khẩu, số CCCD/CMND, bí mật kinh doanh.
Định dạng JSON mảng: [{{"key": "...", "value": "...", "confidence": 0.9}}]
Nếu không có thông tin phù hợp, trả về mảng rỗng [].

CÂU NÓI: {text}
"""
            try:
                res = llm.invoke(prompt)
                raw = res.content if hasattr(res, "content") else str(res)
                m = re.search(r"\[[\s\S]*\]", raw)
                if m:
                    parsed = json.loads(m.group(0))
                    for item in parsed:
                        k = item.get("key", "").lower().strip()
                        if k in ALLOWED_MEMORY_KEYS:
                            memories.append({
                                "key": k,
                                "value": item.get("value", "").strip(),
                                "confidence": float(item.get("confidence", 0.8)),
                            })
            except Exception:
                pass

    # Persist to database
    saved = []
    for mem in memories:
        k = mem["key"]
        v = mem["value"]
        conf = mem.get("confidence", 1.0)
        if store.set_client_memory(client_id, k, v, confidence=conf):
            saved.append(mem)

    return saved
