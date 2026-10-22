# Dataset thu chi tiếng Việt (mô phỏng)

Nguồn: câu gốc do người tạo dự án biên soạn cho demo, sau đó sinh biến thể có kiểm soát bằng `ml/build_dataset.py`, seed 20261021. Không lấy dữ liệu thật, không có thông tin cá nhân.

1.584 dòng; 264 nhóm câu gốc; 11 lớp. Các tệp CSV mã hóa UTF-8 có BOM, có thể mở bằng Excel. Mỗi dòng là một khoản thu/chi, không gộp nhiều nghiệp vụ.

| Cột | Ý nghĩa |
|---|---|
| id | Mã duy nhất toàn bộ tập dữ liệu |
| text | Câu giao dịch tiếng Việt |
| kind | income hoặc expense |
| category | Mã trong bảng dưới |
| group_id | Nhóm ngữ nghĩa; các biến thể giữ chung nhóm |
| split | train, validation hoặc test; phải khớp tên tệp |
| origin | Nguồn dữ liệu, ví dụ synthetic_authored_template_v1 hoặc nhom_tu_viet |

| category | Nhãn | kind |
|---|---|---|
| sales | Tiền bán hàng | income |
| service | Thu dịch vụ | income |
| capital | Vốn bổ sung / khoản vay nhận về | income |
| other_income | Thu khác | income |
| materials | Nguyên liệu / nhập hàng | expense |
| rent | Thuê mặt bằng | expense |
| utilities | Điện, nước, Internet | expense |
| shipping | Vận chuyển | expense |
| salary | Lương nhân viên | expense |
| personal | Chi cá nhân | expense |
| other_expense | Chi khác | expense |

Ví dụ một dòng bổ sung trong train.csv:

```csv
nhom-001-a,Hôm nay trả công nhân viên phụ quán 200 nghìn,expense,salary,nhom-001,train,nhom_tu_viet
```

Nếu câu có dấu phẩy, dùng dấu nháy kép bao quanh trường text hoặc dùng trình đọc/ghi CSV chuẩn. Các biến thể của nhom-001 phải cùng nằm trong train.

Bộ dữ liệu này được cung cấp theo CC0 1.0: https://creativecommons.org/publicdomain/zero/1.0/ . Chỉ dùng như dữ liệu khởi đầu học tập; không dùng kết quả đánh giá để quảng cáo độ chính xác thực tế.
