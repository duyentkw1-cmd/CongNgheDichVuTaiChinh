# Model card — local-finance-v3

**Mục đích:** gợi ý Thu/Chi và danh mục cho một giao dịch tiếng Việt, phục vụ demo học tập. Luôn có bước người dùng xác nhận.

**Nguồn mô hình:** hai Logistic Regression huấn luyện từ CSV mô phỏng của dự án. Đặc trưng TF-IDF (n-gram ký tự 2–5 + n-gram từ 1–3) dùng scikit-learn. Mô hình không được huấn luyện bằng dữ liệu thực tế của hộ kinh doanh.

**Dữ liệu:** 18.240 dòng sinh từ 544 câu gốc (10 danh mục). Train 16.320, validation 960, test 960. Các nhóm câu gốc không giao nhau giữa các tập.

- v2: 24 câu gốc mỗi danh mục.
- v3 (bản này): thêm 24 câu gốc mỗi danh mục theo cách nói đời thực — tiểu thương ngoài chợ, ghi chú ngắn, dòng hóa đơn — và các ranh giới mô hình v2 hay nhầm: mua đồ dùng (Chi khác) với mua hàng để bán (Nguyên liệu), dịch vụ với bán hàng, bán phế liệu (Thu khác) với bán hàng.

## Kết quả

### Bộ kiểm tra viết tay — `datasets/challenge.csv`

200 câu viết tay kiểu đời thực (20 câu mỗi danh mục), **không dùng để huấn luyện hay chọn tham số**. Câu gốc v3 được viết tránh các món/cách nói trong bộ này để đo khả năng tổng quát sang từ ngữ chưa gặp. Chạy: `python -m ml.evaluate`.

| Mô hình | Thu/Chi đúng | Danh mục đúng |
|---|---:|---:|
| v2 (trước) | 93,5% | 84,5% |
| **v3 (bản này)** | **97,5%** | **93,0%** |

| Danh mục | v2 | v3 |
|---|---:|---:|
| Tiền bán hàng | 85% | 85% |
| Thu dịch vụ | 60% | 85% |
| Vốn / khoản vay | 90% | 95% |
| Thu khác | 90% | 90% |
| Nguyên liệu / nhập hàng | 85% | 95% |
| Thuê mặt bằng | 85% | 95% |
| Điện nước Internet | 95% | 100% |
| Vận chuyển | 100% | 100% |
| Lương nhân viên | 100% | 100% |
| Chi khác | 55% | 85% |

Bộ này nhỏ (20 câu/lớp, mỗi câu ≈ 5%) và do người làm dự án viết, nên chỉ dùng để so sánh tương đối giữa các phiên bản.

### Tập test mô phỏng

| Mô hình | Accuracy | Macro-F1 | C chọn trên validation |
|---|---:|---:|---:|
| Thu/Chi | 0.9469 | 0.9446 | 1.0 |
| Danh mục | 0.9208 | 0.9186 | 16.0 |

| Danh mục | Precision | Recall | F1 | Số mẫu |
|---|---:|---:|---:|---:|
| Vốn / khoản vay | 1.000 | 1.000 | 1.000 | 96 |
| Nguyên liệu / nhập hàng | 0.965 | 0.865 | 0.912 | 96 |
| Chi khác | 0.822 | 0.625 | 0.710 | 96 |
| Thu khác | 0.787 | 1.000 | 0.881 | 96 |
| Thuê mặt bằng | 0.960 | 1.000 | 0.980 | 96 |
| Lương nhân viên | 0.886 | 0.969 | 0.925 | 96 |
| Tiền bán hàng | 1.000 | 0.885 | 0.939 | 96 |
| Dịch vụ | 0.888 | 0.990 | 0.936 | 96 |
| Vận chuyển | 1.000 | 1.000 | 1.000 | 96 |
| Điện nước Internet | 0.933 | 0.875 | 0.903 | 96 |

Tập test v3 lớn hơn và khác v2 (thêm câu gốc mới), nên không so trực tiếp số này với bản trước; dùng bộ viết tay ở trên để so sánh. Xem `models/finance/metrics.json` (ma trận nhầm lẫn, mã băm) và `test_predictions.csv`.

## Giới hạn và cách xử lý

- Nhãn mơ hồ vẫn bị nhầm, ví dụ "bán ve chai" (Thu khác) dễ bị đoán Tiền bán hàng; "mua dao thớt" (Chi khác) dễ bị đoán Nguyên liệu. Câu thiếu ngữ cảnh như "sửa tủ lạnh 400 nghìn" có thể là thu dịch vụ hoặc chi sửa chữa.
- Giao dịch nhiều khoản, tiếng lóng, lỗi chính tả/OCR/STT và ngành hàng chưa có trong tập học có thể bị phân loại sai.
- Điểm mô hình chưa hiệu chỉnh; không được diễn giải thành tỷ lệ đúng ngoài thực tế.
- Thu/Chi ở bản nháp lấy theo danh mục gợi ý để luôn nhất quán. Mô hình Thu/Chi độc lập dùng đối chiếu và cảnh báo.
- Trích số tiền/ngày là quy tắc, không phải năng lực của bộ phân loại.
- OCR và STT dùng model có sẵn, không được đánh giá bằng các chỉ số của bộ phân loại.
- Chưa đánh giá với người dùng thật hoặc dữ liệu thật của hộ kinh doanh.

## Môi trường huấn luyện

Python 3.12.9; scikit-learn 1.8.0; số đặc trưng thực tế: 9.297.

## Nguồn tham khảo chính

- https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html
- https://github.com/openai/whisper
- https://github.com/SYSTRAN/faster-whisper
- https://tesseract-ocr.github.io/tessdoc/
