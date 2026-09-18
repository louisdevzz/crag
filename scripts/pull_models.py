"""Model downloader and verification script for the Legal CRAG assistant."""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import EMBEDDING_MODEL, EMBEDDING_PROVIDER, RERANKER_MODEL
from logging_config import get_logger

log = get_logger("pull_models")


def pull_huggingface_model(
    repo_id: str,
    hf_token: str | None = None,
    verify_type: str | None = None,
) -> bool:
    """Download a model repository from Hugging Face Hub with progress tracking."""
    print(f"\n📥 [Hugging Face] Đang tải mô hình: {repo_id}")
    start_time = time.time()

    try:
        from huggingface_hub import snapshot_download

        # Exclude redundant large file formats (e.g., onnx, tf, msgpack) to minimize download size
        ignore_patterns = [
            "*.onnx*",
            "onnx/*",
            "*.msgpack",
            "*.h5",
            "*.ot",
            "flax_model.msgpack",
            "tf_model.h5",
        ]

        token = hf_token or os.getenv("HF_TOKEN") or None

        local_path = snapshot_download(
            repo_id=repo_id,
            token=token,
            ignore_patterns=ignore_patterns,
            max_workers=4,
        )

        elapsed = time.time() - start_time
        print(f"✅ Tải thành công '{repo_id}' trong {elapsed:.1f}s")
        print(f"   📂 Vị trí lưu trữ: {local_path}")

        if verify_type == "embedding":
            return verify_embedding_model(repo_id)
        elif verify_type == "reranker":
            return verify_reranker_model(repo_id)

        return True

    except Exception as exc:
        print(f"❌ Lỗi khi tải mô hình '{repo_id}': {exc}", file=sys.stderr)
        return False


def verify_embedding_model(model_name: str) -> bool:
    """Verify that the embedding model can be loaded and generates valid vectors."""
    print(f"🔍 [Kiểm định] Đang nạp mô hình Embedding '{model_name}'...")
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        sample_query = "Quy định về đăng ký kinh doanh và quyền thành lập doanh nghiệp"
        vec = embeddings.embed_query(sample_query)

        print(f"✅ Kiểm định Embedding thành công!")
        print(f"   - Chiều không gian vector (Dimension): {len(vec)}")
        print(f"   - Mẫu vector [0:5]: {[round(x, 4) for x in vec[:5]]}")
        return True
    except Exception as exc:
        print(f"❌ Kiểm định Embedding thất bại: {exc}", file=sys.stderr)
        return False


def verify_reranker_model(model_name: str) -> bool:
    """Verify that the cross-encoder reranker model can be loaded and scores pairs."""
    print(f"🔍 [Kiểm định] Đang nạp mô hình Reranker '{model_name}'...")
    try:
        from FlagEmbedding import FlagReranker

        reranker = FlagReranker(model_name, use_fp16=False)
        test_pairs = [
            ("Thành lập công ty TNHH", "Người thành lập nộp hồ sơ đăng ký tại Cơ quan đăng ký kinh doanh.")
        ]
        scores = reranker.compute_score(test_pairs)
        raw_score = scores[0] if isinstance(scores, list) else scores

        print(f"✅ Kiểm định Reranker thành công!")
        print(f"   - Điểm logit mẫu: {raw_score:.4f}")
        return True
    except Exception:
        # Fallback verification with sentence-transformers CrossEncoder
        try:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(model_name)
            scores = model.predict([
                ("Thành lập công ty TNHH", "Người thành lập nộp hồ sơ đăng ký tại Cơ quan đăng ký kinh doanh.")
            ])
            print(f"✅ Kiểm định CrossEncoder Reranker thành công!")
            print(f"   - Điểm dự đoán mẫu: {scores[0]:.4f}")
            return True
        except Exception as exc:
            print(f"❌ Kiểm định Reranker thất bại: {exc}", file=sys.stderr)
            return False


def pull_ollama_model(model_name: str) -> bool:
    """Pull model via Ollama CLI or HTTP API."""
    print(f"\n🦙 [Ollama] Đang kéo mô hình: {model_name}")
    import subprocess
    try:
        res = subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"✅ Ollama kéo thành công mô hình '{model_name}'")
        return res.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"❌ Lệnh 'ollama pull {model_name}' thất bại: {exc}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Model Puller & Validator for Legal CRAG Assistant",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Tải và kiểm định cả mô hình Embedding và Reranker (mặc định nếu không chỉ định cờ khác)",
    )
    parser.add_argument(
        "--embedding",
        "-e",
        action="store_true",
        help="Chỉ tải mô hình Embedding (mặc định cấu hình: BAAI/bge-m3)",
    )
    parser.add_argument(
        "--reranker",
        "-r",
        action="store_true",
        help="Chỉ tải mô hình Reranker (mặc định cấu hình: BAAI/bge-reranker-v2-m3)",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Tên định danh mô hình tùy chọn trên Hugging Face Hub (ví dụ: BAAI/bge-m3)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default=None,
        choices=["huggingface", "ollama"],
        help="Provider để kéo mô hình ('huggingface' hoặc 'ollama')",
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=None,
        help="Hugging Face User Access Token (tùy chọn, để tăng tốc độ tải và vượt rate limit)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Bỏ qua bước kiểm định nạp thử mô hình sau khi tải xong",
    )

    args = parser.parse_args()

    # Determine what to download
    download_all = args.all or (not args.embedding and not args.reranker and not args.model)
    verify = not args.no_verify

    emb_model = args.model if args.embedding and args.model else EMBEDDING_MODEL
    rerank_model = args.model if args.reranker and args.model else RERANKER_MODEL
    provider = args.provider or EMBEDDING_PROVIDER

    print("=" * 70)
    print("LEGAL CRAG ASSISTANT — BỘ TẢI & KIỂM ĐỊNH MÔ HÌNH THỰC TẾ")
    print(f"• Embedding Provider: {provider}")
    print(f"• Embedding Model:    {emb_model}")
    print(f"• Reranker Model:     {rerank_model}")
    print("=" * 70)

    success = True

    # 1. Handle custom single model
    if args.model and not args.embedding and not args.reranker:
        if provider == "ollama":
            ok = pull_ollama_model(args.model)
        else:
            ok = pull_huggingface_model(args.model, hf_token=args.hf_token)
        sys.exit(0 if ok else 1)

    # 2. Embedding Model
    if download_all or args.embedding:
        if provider == "ollama":
            ok = pull_ollama_model(emb_model)
        else:
            ok = pull_huggingface_model(
                emb_model,
                hf_token=args.hf_token,
                verify_type="embedding" if verify else None,
            )
        if not ok:
            success = False

    # 3. Reranker Model
    if download_all or args.reranker:
        ok = pull_huggingface_model(
            rerank_model,
            hf_token=args.hf_token,
            verify_type="reranker" if verify else None,
        )
        if not ok:
            success = False

    print("\n" + "=" * 70)
    if success:
        print("🎉 TẤT CẢ MÔ HÌNH ĐÃ SẴN SÀNG ĐỂ SỬ DỤNG!")
        print("👉 Bước tiếp theo: Chạy 'python ingest.py' để nạp dữ liệu vào VectorDB.")
    else:
        print("⚠️ Có lỗi xảy ra trong quá trình tải hoặc kiểm định một số mô hình.")
        print("   Vui lòng kiểm tra lại kết nối mạng hoặc cờ cấu hình.")
    print("=" * 70)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
