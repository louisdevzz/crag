# Installation Guide — Legal CRAG Assistant

> Hướng dẫn này dùng cho **lần cài đặt đầu tiên** trên máy mới.  
> Sau khi hoàn tất, tiếp tục tại [SETUP_AND_RUN.md](SETUP_AND_RUN.md) để cấu hình và chạy dự án.

## 1. Môi trường khuyến nghị

- Ubuntu 22.04 / 24.04 LTS hoặc WSL2.
- Git.
- `uv`.
- Python **3.13**.
- NVM.
- Node.js **24 LTS**.
- pnpm **11.18.0**.
- Ollama nếu chạy LLM local.

> Repository khai báo `requires-python >=3.12`, nhưng tài liệu này chuẩn hóa môi trường phát triển bằng **Python 3.13**.

## 2. Cài các gói hệ thống

Ubuntu / WSL2:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates build-essential
```

Kiểm tra:

```bash
git --version
curl --version
```

## 3. Clone dự án

```bash
git clone https://github.com/louisdevzz/crag.git
cd crag
```

Từ đây, mọi lệnh được giả định chạy từ thư mục gốc `crag/`, trừ khi có ghi chú khác.

## 4. Cài `uv`

Linux / macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Nạp lại shell:

```bash
source ~/.bashrc
```

Nếu dùng Zsh:

```bash
source ~/.zshrc
```

Kiểm tra:

```bash
uv --version
```

Tài liệu chính thức: <https://docs.astral.sh/uv/getting-started/installation/>

## 5. Cài Python 3.13 bằng `uv`

```bash
uv python install 3.13
```

Kiểm tra:

```bash
uv python list
```

Python của dự án sẽ được tạo trong `.venv` khi chạy `uv sync` ở bước setup. Không cần thay đổi Python hệ thống.

## 6. Cài NVM

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash
```

Nạp lại shell:

```bash
source ~/.bashrc
```

Nếu dùng Zsh:

```bash
source ~/.zshrc
```

Kiểm tra:

```bash
command -v nvm
nvm --version
```

> Nếu `nvm` chưa được nhận diện, đóng terminal và mở lại.

Tài liệu chính thức: <https://github.com/nvm-sh/nvm>

## 7. Cài Node.js bằng NVM

Dự án frontend được chuẩn hóa với Node.js 24 LTS:

```bash
nvm install 24
nvm alias default 24
nvm use 24
```

Kiểm tra:

```bash
node --version
npm --version
```

## 8. Cài pnpm

Frontend khai báo `pnpm@11.18.0`, vì vậy dùng đúng version này:

```bash
npm install -g pnpm@11.18.0
```

Kiểm tra:

```bash
pnpm --version
```

Kết quả mong đợi:

```text
11.18.0
```

## 9. Cài Ollama

Ollama chỉ bắt buộc khi dùng provider `ollama`. Nếu dùng Groq, OpenAI hoặc OpenRouter thì có thể bỏ qua phần này.

Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Kiểm tra:

```bash
ollama --version
ollama list
```

Nếu service chưa chạy trên Ubuntu có systemd:

```bash
sudo systemctl enable --now ollama
sudo systemctl status ollama
```

Nếu môi trường không dùng systemd, chạy ở một terminal riêng:

```bash
ollama serve
```

Tài liệu chính thức: <https://ollama.com/download/linux>

### Tải model local

Chỉ cần tải model nếu cấu hình:

```ini
LLM_PROVIDER=ollama
```

Liệt kê model hiện có:

```bash
ollama list
```

Tải model mong muốn:

```bash
ollama pull <model-name>
```

Sau đó đặt đúng tên model trong `.env`:

```ini
LLM_PROVIDER=ollama
LLM_MODEL=<model-name>
OLLAMA_BASE_URL=http://localhost:11434
```

## 10. Kiểm tra toàn bộ môi trường

Từ thư mục `crag/`:

```bash
git --version
uv --version
uv run --python 3.13 python --version
nvm --version
node --version
pnpm --version
ollama --version
```

| Thành phần | Yêu cầu |
|---|---|
| Python | 3.13.x |
| uv | Đã cài |
| Node.js | 24.x |
| pnpm | 11.18.0 |
| Git | Đã cài |
| Ollama | Tùy chọn nếu chạy local LLM |

## 11. Bước tiếp theo

Sau khi hoàn tất cài đặt công cụ hệ thống:

➡️ [Cấu hình và chạy dự án — SETUP_AND_RUN.md](SETUP_AND_RUN.md)

```text
Install system tools
        ↓
Clone repository
        ↓
uv + Python 3.13
        ↓
NVM + Node.js
        ↓
pnpm
        ↓
Ollama (optional)
        ↓
SETUP_AND_RUN.md
```
