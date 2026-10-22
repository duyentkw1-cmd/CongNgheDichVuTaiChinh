# Kết quả kiểm thử bản 2.0 Local AI

## Đã thực hiện

- **19 kiểm thử tự động đạt**: phân quyền/đăng nhập, tiền dương và giới hạn, không ghi trùng, sửa/xóa và cách ly hộ kinh doanh, nguồn vốn không tính vào doanh thu, tách chi cá nhân, ngưỡng cảnh báo, tính nhất quán Excel/CSV/PDF, đầu vào ảnh/âm thanh, tách tập dữ liệu và suy luận local.
- Kiểm thử dùng **cơ sở dữ liệu tạm riêng**, không ghi vào sổ của người chạy test.
- Build TypeScript/Vite thành công. Giao diện đã đóng gói trong frontend/dist, font cũng nằm local.
- Kiểm thử trình duyệt Chromium ở **390 × 844** và **1440 × 960**: đăng nhập, thử mô hình, liên kết CSV, phân tích văn bản, lưu giao dịch, đọc ảnh mẫu bằng OCR thật, tải âm thanh qua mô hình local, xem báo cáo. Không ghi nhận lỗi JavaScript hoặc yêu cầu mạng tới dịch vụ ngoài trong các luồng đó.
- OCR trên chứng từ mẫu: đọc đúng **650.000 VND**, phân loại nguyên liệu. Đây là kiểm tra một trường hợp, không phải số đo độ chính xác OCR tổng quát.
- Whisper base đã nạp và suy luận trên CPU khi chặn kết nối mạng từ Python. Luồng ghi âm/tải bản ghi đã đi đến màn hình kiểm tra qua mô hình thật.
- Kiểm tra bộ phụ thuộc có bản phân phối phù hợp Python 3.12/Windows x64 bằng pip dry-run: đạt. Điều này chỉ kiểm tra khả năng giải phụ thuộc, không thay thế chạy thử trên Windows.

## Giới hạn kiểm thử phải trình bày rõ

- Kiểm thử thực thi được làm trong môi trường Linux/Python 3.12. Chưa trực tiếp chạy file .bat và trình cài Tesseract trên một máy Windows thật.
- Chưa chạy Docker/PostgreSQL end-to-end; SQLite là đường chạy đã kiểm tra.
- Bản ghi dùng kiểm tra luồng là **giọng tổng hợp**, không phải bộ ghi âm người Việt thật. Whisper base chép sai một số từ và số tiền trong mẫu tổng hợp; ứng dụng giữ nguyên bản chép và yêu cầu sửa số tiền khi chưa rõ. Không báo WER hay tuyên bố “nhận tiếng Việt chính xác”. Cần thử với bản ghi của nhóm trước buổi trình bày; có lựa chọn nâng cấp Whisper small trong hướng dẫn.
- Bộ OCR là chữ in, chưa đánh giá chữ viết tay, hóa đơn mờ hoặc nhiều mẫu bố cục.
- Chỉ số 95,5%/89,4% là của **hai bộ phân loại trên CSV mô phỏng**, không phải chất lượng giọng nói/OCR hay tỷ lệ đúng toàn bộ ứng dụng.
- Không có thử nghiệm người dùng, kiểm toán bảo mật sản xuất hoặc kiểm chứng tính phù hợp sổ sách pháp lý.

## Tái chạy

### Bản sửa lỗi Windows ngày 21/10/2026

- Ảnh lỗi trên máy Windows cho thấy CTranslate2 4.6.0 không nhập được `pkg_resources`. Phiên bản setuptools cài tự động là 84.2.1; thành phần này đã bị bỏ từ setuptools 82.
- Đã cố định `setuptools==80.9.0`, bổ sung `sua-loi-giong-noi.bat`, giữ traceback trong cửa sổ máy chủ và đưa hướng dẫn riêng cho lỗi này.
- Bộ cài chỉ đánh dấu hoàn tất sau khi `doctor.py --speech` nạp mô hình, chạy VAD và suy luận trên một giây im lặng. Đây là kiểm tra hoạt động, không đo độ chính xác giọng người thật. Kiểm tra OCR vẫn là sự hiện diện của bộ cài.
- Đã xác nhận với setuptools 80.9.0: API `pkg_resources.resource_filename` mà nhánh Windows của CTranslate2 sử dụng có sẵn, và kiểm tra `MODEL OK`, `VAD OK`, `WHISPER OK` thành công trong môi trường Linux/Python 3.12. Chưa thay thế kiểm tra lại trên máy Windows của người dùng.

### Kiểm thử nghiệp vụ

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Không cần khóa API. Muốn kiểm thử OCR phải cài Tesseract và giữ thư mục models/tessdata. Huấn luyện lại bằng train-models.bat; kết quả mới nằm trong models/finance/metrics.json.
