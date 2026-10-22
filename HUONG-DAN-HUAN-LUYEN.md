# Tự huấn luyện AI phân loại thu chi

## Phạm vi thực sự tự xây dựng

Nhóm xây dựng pipeline dữ liệu, đặc trưng, hai bộ phân loại, đánh giá và tích hợp vào backend. Thuật toán Logistic Regression và TF-IDF dùng thư viện scikit-learn; không tự viết lại thư viện đại số. Đây là mô hình được huấn luyện từ dữ liệu kèm dự án, không phải gọi API hay gán nhãn bằng bảng từ khóa.

| Thành phần | Nguồn | Có tự huấn luyện trong dự án? |
|---|---|---|
| Nhận diện Thu/Chi | `ml/train.py` + `datasets/train.csv` | Có: Logistic Regression nhị phân |
| Phân loại 11 danh mục | Cùng pipeline | Có: Logistic Regression đa lớp |
| Giọng nói | Whisper base đa ngôn ngữ, triển khai bằng faster-whisper | Không: dùng trọng số có sẵn |
| OCR tiếng Việt/Anh | Tesseract + tessdata_fast | Không: dùng trọng số có sẵn |
| Tiền, ngày, thanh toán | `backend/local_parse.py` | Quy tắc xử lý, không phải mô hình học máy |
| Vượt ngưỡng chi | Điều kiện trong backend | Quy tắc nghiệp vụ |

## Dữ liệu kèm theo

**Toàn bộ 1.584 câu là dữ liệu mô phỏng**, không phải dữ liệu thu thập từ hộ kinh doanh. Có 264 câu gốc/nhóm ngữ nghĩa, mỗi câu có 6 biến thể về cách diễn đạt, số tiền hoặc dấu tiếng Việt. Quy mô này dùng để minh họa quá trình học; các biến thể không tương đương 1.584 giao dịch độc lập ngoài thực tế.

- Train: 1.056 dòng (176 nhóm).
- Validation: 264 dòng (44 nhóm), dùng chọn hệ số C.
- Test: 264 dòng (44 nhóm), dùng đánh giá cuối.
- Cùng `group_id` không được xuất hiện ở nhiều tập. Script còn kiểm tra câu giống hệt sau chuẩn hóa và mã dòng trùng lặp.
- Các tập vẫn chia sẻ cách sinh mẫu và miền từ vựng. Dù tách nhóm, kết quả có thể lạc quan hơn dữ liệu thật. Cần bổ sung tập kiểm tra độc lập, tự viết/thu thập, có lỗi chính tả, ngôn ngữ địa phương và lỗi OCR/STT.

## Thuật toán và quy trình

1. Chuẩn hóa chữ thường, bỏ dấu, chuẩn hóa khoảng trắng và bỏ số trong đặc trưng phân loại. Số tiền vẫn được trích từ nội dung gốc bởi bộ xử lý tiền riêng.
2. TF-IDF trên n-gram ký tự trong từ, độ dài 3–5, tối đa 18.000 đặc trưng, `min_df=2`, `sublinear_tf=True`.
3. Hai mô hình Logistic Regression, `class_weight=balanced`, `max_iter=1000`, seed 42.
4. Thử C = 1, 4, 10. Chọn mô hình có macro-F1 tốt nhất trên validation; không chọn tham số bằng test.
5. Ghi accuracy, macro-F1, precision/recall từng lớp, ma trận nhầm lẫn, dự đoán từng dòng và mã băm dữ liệu/model.
6. Khi chạy app, mô hình danh mục cho gợi ý và chiều tương ứng. Mô hình Thu/Chi độc lập dùng đối chiếu; bất đồng sẽ hiển thị cảnh báo. Điểm thấp hoặc hai danh mục gần nhau cũng yêu cầu kiểm tra.

Điểm “gợi ý” trên app là đầu ra của mô hình, chưa được hiệu chỉnh thành xác suất chính xác ngoài thực tế. Ngưỡng kiểm tra 0,45 và khoảng cách 0,10 là quy tắc demo; không được xem là ngưỡng bảo đảm chất lượng. Mô hình vẫn có thể tự tin sai. Người dùng luôn xác nhận trước khi lưu.

## Lệnh chạy

Sau khi cài thư viện:

```powershell
.venv\Scripts\python.exe -m ml.train
```

Windows có sẵn `train-models.bat`. macOS/Linux:

```bash
.venv/bin/python -m ml.train
```

Kết quả nằm trong `models/finance/`:
- `vectorizer.joblib`: từ vựng và trọng số IDF chỉ học từ train.
- `kind.joblib`: trọng số bộ phân loại Thu/Chi.
- `category.joblib`: trọng số bộ phân loại danh mục.
- `metrics.json`: chỉ số đánh giá, phiên bản và mã băm.
- `test_predictions.csv`: so sánh nhãn thật/dự đoán từng dòng test.

Không tải file joblib không rõ nguồn vào thư mục model. Script chỉ nạp mô hình cố định của dự án; định dạng joblib có thể chứa mã thực thi khi giải tuần tự.

## Bổ sung dữ liệu của nhóm

1. Sao lưu CSV và mô hình hiện tại.
2. Gán nhãn theo nội dung/ngữ cảnh, không theo một từ riêng lẻ. “Khách trả phí sửa máy” là **thu dịch vụ**, “Tiệm trả phí sửa máy” là **chi khác**. “Mua sữa cho con” là **cá nhân**, “mua sữa để pha bán” là **nguyên liệu**.
3. Thêm dữ liệu đa dạng cho tất cả các lớp. Không có số lượng nhỏ cố định nào bảo đảm chính xác; bắt đầu bằng tập rõ nhãn và kiểm tra lỗi, rồi bổ sung các dạng mô hình còn yếu.
4. Những câu cùng một giao dịch hoặc chỉ thay số tiền/tên/đổi dấu cần cùng group_id và cùng split. Nếu thu dữ liệu thực, ưu tiên tách theo cửa hàng/người viết/thời gian để đo khả năng tổng quát.
5. Khóa tập test trước khi thử nhiều lần. Không sửa mô hình để “học thuộc” lỗi riêng của tập test rồi vẫn báo đó là kiểm tra độc lập.
6. Huấn luyện lại, xem ma trận nhầm lẫn và các dòng dự đoán sai trước khi tích hợp.

**Không chạy `python -m ml.build_dataset` sau khi đã chỉnh CSV nếu chưa sao lưu.** Lệnh này tái tạo và ghi đè bộ dữ liệu mô phỏng ban đầu. `train-models.bat` không gọi lệnh đó.

## Kiểm thử ảnh và giọng nói

Muốn đánh giá cả hệ thống, cần tách ba bước:
- STT: đối chiếu bản chép với lời nói thật; chú ý số tiền và vùng miền.
- OCR: đối chiếu chữ/số đọc được với chứng từ thật.
- Phân loại/trích xuất: đánh giá trên đầu ra STT/OCR, không chỉ văn bản sạch.

Dữ liệu CSV hiện chỉ huấn luyện **phân loại văn bản**. Không có bộ dữ liệu ảnh/âm thanh dùng huấn luyện từ đầu OCR hay Whisper trong gói này. Không tuyên bố nhóm tự huấn luyện các mô hình có sẵn đó.
