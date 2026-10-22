# Model card — local-finance-v1

**Mục đích:** gợi ý Thu/Chi và danh mục cho một giao dịch tiếng Việt, phục vụ demo học tập. Luôn có bước người dùng xác nhận.

**Nguồn mô hình:** hai Logistic Regression huấn luyện mới từ CSV mô phỏng của dự án. Đặc trưng TF-IDF dùng scikit-learn. Mô hình không được huấn luyện bằng dữ liệu thực tế của hộ kinh doanh.

**Dữ liệu:** 1.584 dòng = 264 nhóm câu gốc × 6 biến thể. Train 1.056, validation 264, test 264. Các nhóm không giao nhau; từ vựng và quy trình sinh vẫn giống nhau nên không suy rộng kết quả sang thực tế.

## Kết quả trên tập test mô phỏng

| Mô hình | Accuracy | Macro-F1 | C được chọn trên validation |
|---|---:|---:|---:|
| Thu/Chi | 0.9545 | 0.9509 | 1.0 |
| Danh mục | 0.8939 | 0.8948 | 1.0 |

## Theo danh mục (chỉ tập test mô phỏng)

| Danh mục | Precision | Recall | F1 | Số mẫu |
|---|---:|---:|---:|---:|
| Vốn / khoản vay | 1.000 | 1.000 | 1.000 | 24 |
| Nguyên liệu / nhập hàng | 1.000 | 1.000 | 1.000 | 24 |
| Chi khác | 0.750 | 0.750 | 0.750 | 24 |
| Thu khác | 0.857 | 1.000 | 0.923 | 24 |
| Chi cá nhân | 1.000 | 0.750 | 0.857 | 24 |
| Thuê mặt bằng | 0.667 | 1.000 | 0.800 | 24 |
| Lương nhân viên | 1.000 | 0.750 | 0.857 | 24 |
| Tiền bán hàng | 1.000 | 0.833 | 0.909 | 24 |
| Dịch vụ | 0.800 | 1.000 | 0.889 | 24 |
| Vận chuyển | 1.000 | 1.000 | 1.000 | 24 |
| Điện nước Internet | 1.000 | 0.750 | 0.857 | 24 |

Xem `models/finance/metrics.json` để xem ma trận nhầm lẫn và mã băm; `test_predictions.csv` chứa toàn bộ dự đoán kiểm tra.

## Giới hạn và cách xử lý

- Nhãn mơ hồ, giao dịch nhiều khoản, tiếng lóng, lỗi chính tả/OCR/STT và ngành hàng chưa có trong tập học có thể bị phân loại sai.
- Điểm mô hình chưa hiệu chỉnh; không được diễn giải thành tỷ lệ đúng ngoài thực tế.
- Thu/Chi ở bản nháp lấy theo danh mục gợi ý để luôn nhất quán. Mô hình Thu/Chi độc lập dùng đối chiếu và cảnh báo; bảng kết quả phía trên đo riêng từng mô hình.
- Trích số tiền/ngày là quy tắc, không phải năng lực của bộ phân loại. Thiếu số tiền, nhiều giá trị hoặc ngoại tệ được yêu cầu nhập lại.
- OCR và STT dùng model có sẵn, không được đánh giá bằng các chỉ số của bộ phân loại.
- Chưa đánh giá với người dùng thật hoặc triển khai sản xuất; chưa có WER/CER của tiếng nói/chứng từ thực tế.

## Môi trường huấn luyện

Python 3.12.14; scikit-learn 1.8.0; số đặc trưng thực tế: 1132.

## Nguồn tham khảo chính

- https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html
- https://github.com/openai/whisper
- https://github.com/SYSTRAN/faster-whisper
- https://tesseract-ocr.github.io/tessdoc/
