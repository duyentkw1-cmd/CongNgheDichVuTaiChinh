# Sổ Thu Chi AI Local — hướng dẫn Windows

Bản 2.0 này chạy **giao diện + backend + AI trên máy**. Không cần khóa OpenAI, Gemini, Google Cloud; không cần billing. Có sẵn giao diện đã build, hai mô hình phân loại đã huấn luyện, trọng số Whisper base và dữ liệu OCR tiếng Việt/Anh.

## 1. Chuẩn bị một lần

- Máy Windows 10/11 **64-bit**, Python **3.12 64-bit**. Python 3.11–3.13 được bộ cài chấp nhận; khuyến nghị 3.12 để dùng đúng môi trường đã thử.
- Nếu chưa có Python: https://www.python.org/downloads/ — khi cài chọn **Add python.exe to PATH**.
- Nên có RAM 8 GB trở lên và vài GB ổ đĩa trống. Đây là gợi ý thực hành cho demo, không phải cấu hình tối thiểu đã đo. Whisper chạy CPU, không bắt buộc GPU. Máy yếu có thể xử lý bản ghi chậm.
- Có Internet trong lần cài thư viện Python đầu tiên. Khi đã cài đủ, các chức năng nhận dạng và phân loại chạy offline. ZIP không đóng gói Python hoặc toàn bộ thư viện hệ điều hành.

## 2. Mở demo: ba tệp cần bấm

1. **Giải nén toàn bộ ZIP** vào đường dẫn ngắn, ví dụ `D:\SoThuChiLocal\`. Không chạy trực tiếp bên trong cửa sổ ZIP.
2. Mở thư mục `so-thu-chi-ai-local`, nhấp đúp **setup-local.bat**. Đợi cài thư viện và hiện kết quả kiểm tra. Lần đầu có thể mất vài phút tùy mạng. Dữ liệu và mô hình phân loại không bị tạo lại nếu đã có.
3. Nhấp đúp **install-ocr-windows.bat**. Trình cài Tesseract Windows sẽ mở. Giữ đường dẫn mặc định **C:\Program Files\Tesseract-OCR**, chọn Next/Install theo cửa sổ cài. Bộ tiếng Việt/Anh đã có riêng trong `models/tessdata`; không cần đăng nhập Google hay tải ngôn ngữ trong trình cài. Nếu máy đã cài Tesseract ở đường dẫn mặc định thì bỏ qua bước này.
4. Nhấp đúp **start-demo.bat**. Giữ cửa sổ terminal mở. Trình duyệt sẽ mở **http://localhost:8000**. Nếu chưa tự mở, tự nhập địa chỉ này vào Chrome/Edge.
5. Bấm **Trải nghiệm với dữ liệu mẫu**, hoặc đăng nhập:
   - Email: `demo@sothuchi.vn`
   - Mật khẩu: `Demo123!`
6. Vào **Tài khoản → AI trên máy**. Ba thành phần cần hiện **Đã có**. Đây là kiểm tra sự hiện diện; thử từng tính năng bên dưới để kiểm tra hoạt động.

Lần mở tiếp theo chỉ cần **start-demo.bat**. Không cần chạy lại setup hoặc huấn luyện lại. Đóng ứng dụng bằng Ctrl+C ở cửa sổ terminal. Bản local này nên chạy trong thư mục riêng, không chép đè vào phiên bản gọi API trước đây.

## 3. Xem đúng giao diện mobile trên web

- Trên màn hình máy tính, app đã hiện trong khung điện thoại.
- Muốn xem kích thước thật: Chrome/Edge → **F12** → **Ctrl+Shift+M** → chọn Responsive, rộng **390**, cao **844** → tải lại trang.
- Camera và micro cần bạn cấp quyền. Dùng địa chỉ `localhost`, không mở `frontend/dist/index.html` bằng cách nhấp đúp.
- Đây là demo mobile web; AI chạy trên laptop, không phải mô hình nhúng trực tiếp vào điện thoại. Truy cập qua IP LAN thường không cho camera/micro hoạt động do trình duyệt yêu cầu HTTPS. Demo bằng khung điện thoại trên localhost là cách đơn giản nhất.

## 4. Thử đủ chức năng

**Văn bản:** bấm dấu **+ → Tự nhập**, nhập `Hôm nay mua nguyên liệu 350 nghìn, trả tiền mặt` → Phân tích & phân loại → kiểm tra → Xác nhận & lưu.

**Giọng nói:** Trang chủ → Giọng nói → cấp quyền micro → nói một giao dịch rõ ràng → dừng → Nhận dạng bản ghi → kiểm tra bản chép, số tiền, danh mục → lưu. Có thể tải WAV/MP3/WebM/M4A tối đa 5 MB, khoảng 30 giây. Lần nhận dạng đầu cần thời gian nạp model. Nút “Thử câu mẫu (văn bản)” chỉ thử mô hình phân loại, không thử nhận dạng tiếng nói.

**Ảnh:** Hình ảnh → chụp hoặc tải ảnh → Đọc thông tin từ ảnh → kiểm tra tổng tiền. Nút “Thử chứng từ mẫu” chạy OCR thật trên ảnh mẫu, không lấy kết quả lập sẵn. Nên dùng ảnh chữ in, rõ, thẳng, đủ tổng tiền. Tesseract không bảo đảm nhận đúng chữ viết tay hoặc ảnh mờ.

**Báo cáo:** giao dịch chỉ được tính sau khi bạn xác nhận lưu. Vốn bổ sung/tiền vay không tính thành doanh thu bán hàng. Chi cá nhân được tách khỏi báo cáo kinh doanh mặc định.

**Cảnh báo:** Tài khoản → Ngưỡng cảnh báo → đặt ngưỡng cho một danh mục. Chỉ cảnh báo vượt khi số chi **lớn hơn** ngưỡng. Đây là quy tắc nghiệp vụ, không phải mô hình phát hiện bất thường đã huấn luyện.

**Xuất sổ:** chọn kỳ và phạm vi → tải Excel, CSV hoặc PDF. Đây là bảng tổng hợp phục vụ demo, không phải hóa đơn điện tử hay sổ kế toán được chứng nhận.

## 5. Huấn luyện lại mô hình của nhóm

1. Đọc **HUONG-DAN-HUAN-LUYEN.md** và **datasets/README.md**.
2. Sửa/thêm dữ liệu trong `datasets/train.csv`, `validation.csv`, `test.csv` bằng CSV UTF-8. Không để biến thể cùng câu xuất hiện ở nhiều tập.
3. Đóng máy chủ đang chạy (Ctrl+C).
4. Nhấp **train-models.bat**. Script tự học từ train, chọn tham số bằng validation, đánh giá trên test và ghi đè các mô hình trong `models/finance/`.
5. Mở lại **start-demo.bat**. Màn hình AI trên máy sẽ cập nhật kết quả mới.

Script huấn luyện không cần Internet, không gọi AI ngoài, không dùng giao dịch của bạn làm dữ liệu học một cách tự động.

## 6. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `python`/`py` không được nhận diện | Cài Python 3.12 64-bit, chọn Add to PATH, mở lại cửa sổ |
| Cài thư viện thất bại | Đọc dòng lỗi; kiểm tra Internet, dùng Python 3.12. Chạy lại setup-local.bat |
| `No module named 'pkg_resources'` | Chạy `sua-loi-giong-noi.bat`, hoặc `.venv\Scripts\python.exe -m pip install "setuptools==80.9.0"`. Dừng máy chủ cũ bằng Ctrl+C rồi mở lại `start-demo.bat`. CTranslate2 4.6.0 cần thành phần này trên Windows; setuptools từ 82 đã bỏ nó. |
| Lỗi DLL khi nhận giọng nói | Cài Microsoft Visual C++ Redistributable x64 từ https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist rồi mở lại app |
| AI trên máy báo thiếu OCR | Chạy install-ocr-windows.bat. Nếu cài khác đường dẫn, tạo `.env` từ `.env.example`, đặt `TESSERACT_CMD` tới tesseract.exe |
| Thiếu model giọng nói | Chạy lại setup-local.bat, hoặc `.venv\Scripts\python.exe scripts\prepare_models.py` khi có mạng |
| Cổng 8000 đang dùng | Đóng cửa sổ bản demo cũ rồi mở bản mới. Hoặc chạy `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001` và mở localhost:8001 |
| Micro/camera bị từ chối | Bấm biểu tượng quyền cạnh địa chỉ trên trình duyệt, cho phép micro/camera; dùng localhost |
| Nhận giọng nói sai | Nói chậm, rõ, một khoản/lần; nghe lại và sửa bản chép. Whisper base là bản gọn, cần đánh giá với giọng thực tế |
| Không xác định số tiền | Ghi rõ đơn vị đồng/nghìn/triệu; mỗi lần một giao dịch. Nhiều số tiền không rõ tổng sẽ yêu cầu nhập tay |

Nâng cấp tùy chọn sang Whisper small: chạy `.venv\Scripts\python.exe scripts\prepare_models.py --upgrade-small`, đặt `WHISPER_MODEL_PATH=models/whisper-small` trong `.env`, khởi động lại. Cần thêm dung lượng/RAM và có thể chậm hơn; không phải mô hình nhóm tự huấn luyện.

Kiểm tra nhận giọng nói sau cài đặt: `.venv\Scripts\python.exe scripts\doctor.py --speech`. Ba dòng `MODEL OK`, `VAD OK`, `WHISPER OK` xác nhận đã nạp mô hình và chạy thử với một giây im lặng; đây không phải đánh giá độ chính xác với lời nói thực. Bộ cài đã chạy kiểm tra này trước khi báo `Setup complete`. Tesseract được kiểm tra sự hiện diện riêng và vẫn cần thử OCR trên ảnh.

## 7. Dữ liệu nằm ở đâu?

- Giao dịch và tài khoản demo: `data/demo.sqlite3` (tự tạo khi mở lần đầu).
- Ảnh chỉ lưu khi tích “Lưu ảnh kèm giao dịch”: `data/attachments/`.
- Âm thanh xử lý trong bộ nhớ, không lưu thành hồ sơ âm thanh sau nhận dạng.
- Mẫu huấn luyện: `datasets/`, tách riêng khỏi giao dịch ứng dụng.
- Sao lưu: dừng máy chủ và sao chép thư mục `data`. Không cần xóa dữ liệu để huấn luyện lại.

Tài khoản demo dùng chung và mật khẩu đã công khai trong hướng dẫn. Chỉ dùng dữ liệu minh họa, không triển khai công khai như một sản phẩm hoàn chỉnh.
