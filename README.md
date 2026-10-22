# Sổ Thu Chi AI Local · 2.0

Ứng dụng demo thu chi cho hộ kinh doanh nhỏ. Giao diện React/TypeScript ưu tiên mobile, mở bằng trình duyệt; backend Python/FastAPI và AI chạy trên máy. SQLite cho chạy nhanh; PostgreSQL tùy chọn qua Docker.

**Không dùng API AI trả phí. Không cần khóa, tài khoản Google Cloud hoặc OpenAI.** Hai mô hình phân loại đã được huấn luyện; giọng nói dùng Whisper base, đọc chữ dùng Tesseract với trọng số có sẵn. Có bộ dữ liệu và mã huấn luyện để nhóm mở rộng.

## Chạy trên Windows

Đọc [HUONG-DAN-WINDOWS.md](HUONG-DAN-WINDOWS.md). Tóm tắt:

1. Cài Python 3.12 64-bit, giải nén ZIP.
2. Chạy `setup-local.bat` (lần đầu cần mạng cài thư viện Python).
3. Chạy `install-ocr-windows.bat` để cài Tesseract nếu máy chưa có.
4. Chạy `start-demo.bat` → http://localhost:8000 → **Trải nghiệm với dữ liệu mẫu**.

Có sẵn frontend đã build, không cần Node.js để mở demo. Email demo `demo@sothuchi.vn`, mật khẩu `Demo123!`. Camera/micro cần cấp quyền, dùng localhost.

## Có gì trong gói?

| Thư mục / tệp | Nội dung |
|---|---|
| frontend/src | Toàn bộ mã React/TypeScript/CSS của giao diện mobile |
| frontend/dist | Giao diện đã build, kèm font offline |
| backend | Đăng nhập, giao dịch, báo cáo, cảnh báo, xuất Excel/CSV/PDF, AI local |
| ml | Sinh dữ liệu mô phỏng, huấn luyện, dự đoán bằng mô hình của nhóm |
| datasets | 1.584 mẫu CSV; train/validation/test tách nhóm câu |
| models/finance | Hai mô hình đã học, TF-IDF, chỉ số và dự đoán trên test |
| models/whisper-base | Trọng số có sẵn nhận giọng nói đa ngôn ngữ |
| models/tessdata | Dữ liệu OCR tiếng Việt/Anh có sẵn |
| installers | Trình cài OCR Windows 64-bit của nhà cung cấp |
| scripts | Cài môi trường, kiểm tra thành phần, chuẩn bị lại mô hình |
| tests | Kiểm thử backend, model, tiền, OCR và phân quyền |
| licenses | Giấy phép của các thành phần dùng lại |

## Chức năng

- Đăng nhập/đăng xuất phiên bằng cookie HttpOnly; demo có tài khoản dựng sẵn.
- Nhập text, nhập biểu mẫu, ghi/tải âm thanh, chụp/tải ảnh.
- Hai bộ phân loại học máy tự huấn luyện: Thu/Chi và 11 danh mục. Luôn kiểm tra trước khi lưu; cảnh báo khi điểm thấp hoặc hai bộ phân loại không thống nhất.
- Giọng nói và ảnh đi qua bộ nhận dạng local thật; các phép trích số tiền/ngày có quy tắc rõ ràng và có thể yêu cầu người dùng nhập bổ sung.
- Giao dịch có sửa/xóa, kiểm tra trùng, lịch sử sửa, tách chi cá nhân; vốn/tiền vay không cộng vào doanh thu bán hàng.
- Báo cáo theo ngày/tuần/tháng, cơ cấu chi, ngưỡng chi, Excel/CSV/PDF.
- Trang **AI trên máy**: tình trạng mô hình, thử phân loại, chỉ số thử nghiệm và tải CSV.

## Tự huấn luyện

Đọc [HUONG-DAN-HUAN-LUYEN.md](HUONG-DAN-HUAN-LUYEN.md), [datasets/README.md](datasets/README.md) và [MODEL-CARD.md](MODEL-CARD.md).

```bash
python -m ml.train
```

Windows: `train-models.bat` dùng đúng môi trường ảo. Tập dữ liệu mô phỏng không phải dữ liệu thu thập ngoài thực tế. Các chỉ số trong model card không phải cam kết độ chính xác sản phẩm.

## Phát triển giao diện

Cần Node.js 22+ nếu muốn sửa/build lại giao diện:

```bash
cd frontend
npm ci
npm run build
```

Backend đã phục vụ frontend/dist cùng origin. Có thể chạy Vite trong frontend bằng `npm run dev`; proxy /api tới backend cổng 8000. Đổi Python không ảnh hưởng mã giao diện.

## macOS / Linux

Cài Python 3.12 và Tesseract bằng bộ quản lý gói của máy. Ví dụ Ubuntu/Debian: `sudo apt install tesseract-ocr`; macOS: `brew install tesseract`. Dữ liệu vie/eng đã nằm trong gói.

```bash
python3 scripts/setup_local.py
bash start-demo.sh
```

Whisper được cấu hình CPU int8. Tốc độ phụ thuộc máy; bản base ưu tiên nhẹ, có thể nhận sai tiếng Việt hoặc số tiền. Có lệnh tải model small tùy chọn trong hướng dẫn Windows.

## PostgreSQL tùy chọn

Đã có Dockerfile và docker-compose.yml. Docker cần mạng lần build đầu để cài image, thư viện và build frontend; sau đó model được nạp từ thư mục gói.

```bash
docker compose up --build
```

Mở localhost:8000. Compose dùng mật khẩu minh họa, chỉ bind cổng ra localhost. Dữ liệu lưu trong volume riêng. Không chạy đồng thời với bản SQLite trên cùng cổng. Luồng Docker/PostgreSQL chưa được chạy end-to-end trong lần kiểm thử này; SQLite/Python là đường chạy đã kiểm tra.

## Kiểm thử

```bash
python -m unittest discover -s tests -v
```

Sau cài đặt, dùng `.venv\Scripts\python.exe` (Windows) hoặc `.venv/bin/python` (Linux) thay `python`. OCR integration test yêu cầu cài Tesseract, nếu chưa có sẽ được đánh dấu skip. Xem [KIEM-THU.md](KIEM-THU.md) để biết phạm vi đã thực sự kiểm tra.

## Giới hạn

Đây là bản demo học tập. Không có đăng ký người dùng, khôi phục mật khẩu, phân quyền quản trị hay dịch vụ đa thiết bị hoàn chỉnh. Chứng từ xuất ra là tổng hợp giao dịch, không phải hóa đơn điện tử. Nhận dạng cần người dùng kiểm tra. Không dùng trực tiếp cho quản lý dữ liệu nhạy cảm hoặc triển khai công khai mà chưa bổ sung kiểm soát sản phẩm.
