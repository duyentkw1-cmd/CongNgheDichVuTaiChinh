"""Reproducible SYNTHETIC educational data. No real household records.

One semantic seed and all its variants belong to one split. Never split variants
randomly: this leaks almost identical sentences from train into evaluation.

v2: Greatly expanded augmentation — OCR‑noise, speech‑noise, casual Vietnamese,
abbreviations, synonyms, and more templates per seed.
"""
import csv
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.text import normalize

# 24 independently authored semantic seeds per category; last 8 held out.
SEEDS = {
 'sales': [
  'Thu tiền bán hàng tại quầy', 'Khách trả tiền mua cà phê của tiệm',
  'Bán bánh mì được tiền', 'Doanh thu bán đồ uống buổi sáng',
  'Nhận tiền bán cơm cho khách', 'Bán một thùng nước ngọt',
  'Khách thanh toán đơn hàng mua quần áo', 'Thu từ bán đồ gia dụng',
  'Tiền bán rau ngoài chợ', 'Bán mỹ phẩm nhận tiền mặt',
  'Thu tiền bán hàng qua mạng', 'Doanh thu bán sữa và bánh',
  'Khách chuyển tiền mua sản phẩm', 'Bán giày dép cho khách',
  'Thu tiền đơn hàng mang đi', 'Bán thịt trong buổi chiều',
  'Khách đã trả tiền mua chai nước', 'Cửa hàng bán gạo thu được tiền',
  'Tiền thu bán áo đồng phục', 'Doanh thu tại quầy trà sữa',
  'Nhận thanh toán hàng hóa đã bán', 'Bán hoa nhận tiền từ khách',
  'Thu doanh số bán cà phê cuối ngày', 'Tiệm bán sách cho khách thanh toán'],
 'service': [
  'Thu tiền dịch vụ sửa xe', 'Khách trả phí cắt tóc',
  'Nhận tiền giặt là quần áo', 'Thu phí sửa điện thoại cho khách',
  'Khách thanh toán tiền sửa máy tính', 'Thu từ dịch vụ giao hàng thuê',
  'Nhận tiền làm móng tay', 'Thu phí vệ sinh máy lạnh',
  'Tiền công may áo cho khách', 'Khách trả công sửa giày',
  'Thu phí chụp ảnh sản phẩm', 'Nhận tiền thiết kế biển hiệu cho khách',
  'Thu tiền rửa xe', 'Khách thanh toán dịch vụ in tài liệu',
  'Thu phí tư vấn lắp đặt thiết bị', 'Nhận tiền gia công theo đơn',
  'Thu phí sửa khóa cho khách', 'Tiền công bọc ghế khách vừa trả',
  'Thu từ dịch vụ gội đầu', 'Khách trả tiền sửa đồ điện',
  'Thu tiền công lắp camera', 'Nhận phí dịch vụ chăm sóc cây',
  'Khách thanh toán công thêu áo', 'Thu tiền làm dịch vụ bảo dưỡng xe'],
 'capital': [
  'Chủ tiệm bổ sung vốn vào quỹ', 'Nhận tiền vay ngân hàng',
  'Vay người thân để nhập hàng', 'Góp thêm vốn kinh doanh',
  'Nhận khoản vay từ bạn', 'Chuyển tiền tiết kiệm vào vốn cửa hàng',
  'Đối tác góp vốn mở tiệm', 'Nhận giải ngân khoản vay',
  'Chủ hộ nộp tiền vốn', 'Bổ sung vốn lưu động',
  'Mượn tiền anh trai để kinh doanh', 'Vốn góp của thành viên mới',
  'Nhận tiền vay hợp tác xã', 'Tăng vốn của cửa hàng',
  'Chủ quán đưa thêm tiền đầu tư', 'Vay vốn mua thiết bị',
  'Nhận vốn đầu tư từ gia đình', 'Ngân hàng chuyển tiền khoản vay kinh doanh',
  'Tiền mượn để duy trì quán', 'Bổ sung tiền chủ sở hữu vào quỹ',
  'Nhận vốn góp từ chị gái', 'Vay thêm tiền để mở rộng tiệm',
  'Nhận tiền mượn của bố mẹ làm vốn', 'Chủ cửa hàng góp thêm tiền'],
 'other_income': [
  'Ngân hàng trả lãi tiền gửi', 'Nhận tiền hoàn cọc thuê nhà',
  'Thu hồi khoản cho mượn trước đây', 'Nhà cung cấp hoàn tiền hàng lỗi',
  'Nhận tiền bồi thường hàng hỏng', 'Tiền thưởng từ nhà phân phối',
  'Thu bán phế liệu của cửa hàng', 'Nhận tiền hỗ trợ kinh doanh',
  'Đơn vị vận chuyển hoàn phí giao hàng', 'Thu tiền thanh lý kệ cũ',
  'Được hoàn tiền điện đóng thừa', 'Nhận lại tiền bảo đảm hợp đồng',
  'Khách bồi thường đồ làm vỡ', 'Thu lãi từ khoản tiền gửi',
  'Nhận khoản chiết khấu nhà cung cấp trả lại', 'Hoàn lại tiền đặt cọc thiết bị',
  'Thu thanh lý bàn ghế cũ', 'Nhận khoản bồi hoàn từ bảo hiểm',
  'Người quen trả lại khoản nợ cho tiệm', 'Được nhận trợ cấp kinh doanh',
  'Thu tiền lãi ngân hàng tháng này', 'Hoàn cọc mặt bằng về quỹ',
  'Nhà bán hàng trả lại khoản thanh toán thừa', 'Nhận tiền bán bao bì phế liệu'],
 'materials': [
  'Mua cà phê và sữa để pha bán', 'Nhập hàng quần áo từ xưởng',
  'Mua nguyên liệu cho quán', 'Thanh toán tiền nhập rau thịt',
  'Mua bột mì làm bánh', 'Nhập thùng nước ngọt để bán',
  'Chi tiền mua gạo cho tiệm cơm', 'Trả tiền nhà cung cấp nguyên liệu',
  'Mua thịt bò chế biến món ăn', 'Nhập lô mỹ phẩm về cửa hàng',
  'Mua trái cây để pha nước', 'Thanh toán lô hàng nhập kho',
  'Mua đường và đá cho quán nước', 'Nhập giày dép bán tại chợ',
  'Mua hộp đựng đồ ăn bán cho khách', 'Chi tiền mua hạt cà phê',
  'Nhập sữa tươi về pha chế', 'Mua gạo và dầu ăn cho bếp quán',
  'Thanh toán hàng hóa nhập từ đại lý', 'Chi mua trân châu làm trà sữa',
  'Mua hoa tươi để bán', 'Nhập sách về tiệm',
  'Trả tiền nguyên liệu bánh ngọt', 'Mua trà và siro bổ sung kho'],
 'rent': [
  'Trả tiền thuê mặt bằng', 'Thanh toán tiền thuê cửa hàng',
  'Chi thuê nhà để kinh doanh', 'Đóng tiền thuê quầy chợ',
  'Trả tiền thuê kho chứa hàng', 'Thanh toán tiền thuê ki ốt',
  'Chi phí mặt bằng tháng này', 'Chuyển tiền thuê gian hàng',
  'Nộp tiền thuê địa điểm bán hàng', 'Trả chủ nhà tiền thuê quán',
  'Thanh toán thuê xưởng sản xuất', 'Tiền thuê sạp bán rau',
  'Chi thuê phòng làm tiệm tóc', 'Trả tiền thuê chỗ bán cà phê',
  'Thuê nhà kho cho cửa hàng', 'Thanh toán hợp đồng thuê mặt bằng',
  'Chi tiền thuê chỗ kinh doanh', 'Đóng phí thuê quán ăn',
  'Trả chủ sạp tiền thuê tháng', 'Thanh toán thuê khu bán hàng',
  'Chuyển khoản tiền thuê tiệm', 'Nộp tiền thuê vị trí mở quầy',
  'Trả phí thuê kho cất hàng', 'Thanh toán mặt bằng cho chủ nhà'],
 'utilities': [
  'Đóng tiền điện cửa hàng', 'Trả tiền nước sinh hoạt của quán',
  'Thanh toán cước internet', 'Chi tiền mạng wifi của tiệm',
  'Đóng hóa đơn điện tháng này', 'Thanh toán tiền nước máy',
  'Nạp cước điện thoại phục vụ bán hàng', 'Trả phí mạng cáp quang',
  'Chi tiền điện cho máy lạnh cửa hàng', 'Thanh toán điện nước mặt bằng',
  'Trả cước đường truyền internet', 'Tiền nước dùng rửa ly trong quán',
  'Thanh toán cước viễn thông cửa hàng', 'Đóng tiền điện sản xuất',
  'Trả phí wifi hàng tháng', 'Chi hóa đơn nước kinh doanh',
  'Chuyển tiền điện cho điện lực', 'Thanh toán mạng internet tại quán',
  'Trả tiền sử dụng nước của tiệm', 'Đóng cước điện thoại cửa hàng',
  'Chi phí điện thắp sáng quầy', 'Thanh toán hóa đơn cấp nước',
  'Trả phí thuê bao mạng cho tiệm', 'Nộp tiền điện nước quán ăn'],
 'shipping': [
  'Trả phí giao hàng cho khách', 'Chi tiền vận chuyển hàng nhập',
  'Thanh toán cước gửi bưu kiện', 'Trả tiền ship đơn hàng',
  'Chi phí thuê xe chở hàng', 'Thanh toán phí chuyển phát nhanh',
  'Trả tiền giao đơn cho shipper', 'Chi cước bưu điện gửi hàng',
  'Thuê xe tải chở nguyên liệu', 'Trả phí vận chuyển từ kho về tiệm',
  'Thanh toán công giao hàng', 'Chi tiền gửi hàng liên tỉnh',
  'Trả cước xe giao sản phẩm', 'Thanh toán phí chở hàng cho khách',
  'Chi phí giao đồ ăn', 'Trả phí chuyển hàng cho đơn vị vận tải',
  'Chi tiền thuê người giao đơn', 'Thanh toán cước chuyển hàng đường bộ',
  'Trả phí ship cho cửa hàng', 'Chi tiền chở hàng ra bến xe',
  'Thanh toán tiền vận tải lô hàng', 'Trả bưu phí gửi đơn đi tỉnh',
  'Chi giao hàng tận nơi cho khách', 'Trả phí tài xế giao lô sản phẩm'],
 'salary': [
  'Trả lương nhân viên', 'Thanh toán tiền công phụ quán',
  'Chi lương người bán hàng', 'Ứng lương cho nhân viên',
  'Trả tiền công theo ca', 'Chi thưởng nhân viên cuối tháng',
  'Thanh toán lương thợ chính', 'Trả công nhân viên đóng gói',
  'Chi phụ cấp người làm thuê', 'Trả tiền tăng ca cho nhân viên',
  'Thanh toán lương phục vụ', 'Chi tiền công nhân viên thu ngân',
  'Trả lương người nấu bếp', 'Trả công người trông cửa hàng',
  'Chi tiền thưởng cho thợ', 'Thanh toán công nhật cho nhân viên',
  'Trả lương bạn phụ bán hàng', 'Chi tiền công nhân viên làm thêm',
  'Thanh toán lương tháng của thợ phụ', 'Trả thưởng người phục vụ quán',
  'Chi lương nhân viên pha chế', 'Thanh toán tiền công lao động thuê',
  'Trả phụ cấp ca tối cho nhân viên', 'Chi tiền lương thủ kho'],
 'other_expense': [
  'Mua kệ trưng bày cho cửa hàng', 'Trả phí sửa máy pha cà phê của tiệm',
  'Chi tiền quảng cáo trên mạng', 'Thanh toán phí phần mềm bán hàng',
  'Mua máy in hóa đơn', 'Trả phí vệ sinh cửa hàng',
  'Chi tiền bảo dưỡng tủ lạnh của quán', 'Mua bàn ghế cho tiệm',
  'Đóng thuế kinh doanh', 'Trả lãi vay ngân hàng',
  'Chi sửa bảng hiệu cửa hàng', 'Thanh toán phí ngân hàng',
  'Mua máy quét mã vạch', 'Trả tiền sửa mái che quán',
  'Chi mua dụng cụ vệ sinh', 'Thanh toán phí bảo hiểm kinh doanh',
  'Mua cân điện tử cho quầy', 'Chi sửa chữa thiết bị của quán',
  'Trả phí quảng bá cửa hàng', 'Chi tiền mua tủ trưng bày',
  'Thanh toán phí dịch vụ kế toán', 'Trả tiền sửa máy tính của tiệm',
  'Mua camera giám sát cửa hàng', 'Chi phí đăng ký kinh doanh'],
}
INCOME = {'sales', 'service', 'capital', 'other_income'}

# v3: extra seed families for real-life wording: market vendors' speech, short
# notes, receipt item lists, and the boundaries the v2 model confused
# (buying tools vs. stock, services vs. selling goods, selling scrap vs. sales).
# Written to avoid the exact items/phrases of datasets/challenge.csv, so the
# challenge set still measures generalization to unseen wording.
SEEDS_V3 = {
 'sales': [
  'Bán ba ký cà chua cho khách', 'Khách lấy hai chục bánh bao trả tiền',
  'Bán hết mẻ chè buổi tối', 'Thu tiền bán mấy nải chuối',
  'Bán được mười hộp cơm trưa', 'Khách sỉ lấy năm thùng mì gói',
  'Bán tạp hóa cả ngày thu được', 'Cô bán bún thu tiền khách ăn',
  'Bán vịt quay cho khách đặt', 'Tiền hàng khách trả qua ví điện tử',
  'Bán bình hoa cho khách', 'Khách lấy ba cân thịt bò',
  'Đơn hàng online đã giao thu tiền', 'Thu tiền khách mua sỉ nước suối',
  'Bán bột giặt và nước rửa chén', 'Bán dừa tươi ở sạp',
  'Thu tiền mấy ly sinh tố', 'Khách mua bộ đồ ngủ trả tiền',
  'Bán đồ chơi trẻ em được tiền', 'Thu tiền bán hải sản buổi sáng',
  'Bán quà vặt ở cổng trường', 'Khách trả tiền mua hai ổ bánh mì',
  'Bán được mấy chục ký khoai lang', 'Hôm nay bán hàng lời được'],
 'service': [
  'Thu tiền bơm bánh xe cho khách', 'Khách trả công thay má phanh',
  'Nhận tiền sửa quạt máy cho khách', 'Thu tiền giặt hấp chăn mền',
  'Khách trả tiền uốn tóc nhuộm tóc', 'Thu phí chụp hình cưới',
  'Nhận tiền dạy nấu ăn cho học viên', 'Thu tiền công sửa ống nước',
  'Khách trả tiền thông cống', 'Thu phí khắc dấu cho khách',
  'Thu tiền đánh chìa khóa', 'Khách trả tiền đánh giày',
  'Thu phí cho thuê xe máy', 'Nhận tiền công dán phim điện thoại',
  'Thu tiền xông hơi cho khách', 'Khách trả tiền chăm sóc da mặt',
  'Thu tiền công lắp đặt máy giặt', 'Nhận tiền nấu ăn thuê cho đám tiệc',
  'Thu phí giữ đồ cho khách', 'Khách thanh toán tiền sửa ti vi',
  'Thu tiền công vệ sinh nhà cửa thuê', 'Nhận tiền đưa đón học sinh',
  'Khách trả tiền cài đặt máy tính', 'Thu tiền công xăm lông mày'],
 'capital': [
  'Vay chị hàng xóm tiền để lấy hàng', 'Mượn tiền bạn để mở thêm quầy',
  'Ngân hàng chính sách cho vay vốn', 'Chủ sạp bỏ tiền túi vào làm vốn',
  'Vay tiền góp để buôn bán', 'Nhận tiền vay từ quỹ hỗ trợ phụ nữ',
  'Bố cho thêm tiền làm vốn kinh doanh', 'Mượn tạm em gái để xoay vòng vốn',
  'Vay thế chấp sổ đỏ lấy vốn', 'Bạn bè góp tiền chung mở quán',
  'Rút tiền tiết kiệm bỏ vào kinh doanh', 'Nhận tiền vay để mua xe hàng',
  'Vay mượn họ hàng nhập hàng tết', 'Đem tiền nhà bỏ vào vốn tiệm',
  'Vay tiền qua thẻ tín dụng làm vốn', 'Người nhà góp thêm vốn cho sạp',
  'Nhận vốn vay ưu đãi cho hộ kinh doanh', 'Mượn tiền chủ hụi để nhập hàng',
  'Vay trả góp để đầu tư quầy hàng', 'Chủ quán đưa tiền riêng vào quỹ chung',
  'Nhận tiền mượn của đồng nghiệp làm vốn', 'Vay thêm để mở chi nhánh',
  'Góp vốn cùng bạn mở xe bán đồ ăn', 'Cô chú cho vay không lãi làm vốn'],
 'other_income': [
  'Bán giấy vụn và thùng các tông cũ', 'Bán sắt vụn cho người thu mua',
  'Bán lại lon nhựa đã dùng', 'Thanh lý quạt cũ của tiệm',
  'Bán lại máy cũ không dùng nữa', 'Nhận tiền hoàn trả từ sàn thương mại',
  'Được trả lại tiền đặt hàng bị hủy', 'Nhận lãi tài khoản tiết kiệm',
  'Người mượn trả lại tiền cho quán', 'Nhận tiền bồi thường do giao hàng mất',
  'Được hoàn tiền thuế', 'Nhận tiền thưởng từ chương trình của hãng',
  'Được nhà nước hỗ trợ tiền mùa dịch', 'Thu lại tiền đặt cọc vỏ bình gas',
  'Nhận tiền hoàn từ ví điện tử', 'Bán phế liệu nhôm đồng',
  'Được tặng tiền mừng mở hàng', 'Thanh lý tủ kính cũ',
  'Nhận lại tiền cọc thuê thiết bị', 'Được bồi hoàn tiền hàng thiếu',
  'Nhận tiền giới thiệu khách từ đối tác', 'Thu tiền cho thuê lại chỗ để xe một lần',
  'Hãng trả tiền trưng bày sản phẩm', 'Nhận tiền hoàn do thanh toán trùng'],
 'materials': [
  'Mua Bánh tráng, Mắm ruốc, Rau răm', 'Mua Cà rốt, Khoai tây, Hành tây',
  'Mua Mực, Tôm, Nghêu', 'Mua Đường, Bột ngọt, Hạt nêm',
  'Lấy hàng ở vựa trái cây', 'Đi chợ sỉ nhập rau củ',
  'Nhập nước ngọt từ đại lý về bán', 'Lấy mấy thùng sữa về bán lẻ',
  'Mua xương heo nấu nước dùng', 'Mua đậu xanh đậu đỏ nấu chè',
  'Nhập vải về may đồ bán', 'Lấy bánh kẹo của nhà phân phối',
  'Mua gà vịt về làm thịt bán', 'Nhập hàng tạp hóa cho cửa hàng',
  'Mua chanh tắc đường để pha nước', 'Mua giấy gói và túi đựng hàng bán',
  'Nhập thuốc lá bia rượu về bán', 'Mua sả ớt gừng nấu món ăn',
  'Lấy hàng điện thoại phụ kiện về bán', 'Mua bún tươi cho quán bún',
  'Mua bánh phở tươi mỗi sáng', 'Nhập hạt điều đóng gói bán',
  'Mua nước cốt dừa làm bánh', 'Nhập cá khô mực khô về bán'],
 'rent': [
  'Đóng tiền chỗ bán ở chợ', 'Trả tiền thuê sạp mỗi tháng',
  'Nộp phí mặt bằng cho ban quản lý chợ', 'Trả tiền thuê lô trong chợ',
  'Thuê lề đường để bày hàng', 'Trả tiền thuê nhà nguyên căn kinh doanh',
  'Đóng tiền thuê quầy ở trung tâm thương mại', 'Trả tiền thuê container làm kho',
  'Thuê thêm phòng để chứa hàng', 'Chuyển tiền nhà cho chủ trọ',
  'Đặt cọc thuê sạp mới', 'Trả tiền thuê bếp chung để nấu',
  'Thuê sân để tổ chức bán hàng', 'Đóng tiền thuê mặt tiền quán',
  'Trả tiền thuê tầng trệt mở tiệm', 'Thuê chỗ đậu xe bán đồ ăn',
  'Trả phí thuê gian hàng chợ phiên', 'Trả chủ nhà tiền thuê quý',
  'Nộp tiền thuê kiot cho chợ', 'Thanh toán tiền thuê nhà xưởng',
  'Trả tiền thuê văn phòng nhỏ', 'Trả tiền thuê chỗ ngồi bán vé số',
  'Tiền thuê nhà tháng này cho cửa hàng', 'Gia hạn hợp đồng thuê mặt bằng'],
 'utilities': [
  'Trả tiền điện cho chủ nhà', 'Đóng tiền nước cho ban quản lý',
  'Nạp tiền mạng di động', 'Thanh toán gói cước truyền hình internet',
  'Trả tiền điện tính theo số công tơ', 'Đóng tiền nước sạch',
  'Thanh toán hóa đơn viễn thông', 'Trả tiền thuê bao điện thoại bàn',
  'Đóng phí thu gom rác thải', 'Trả tiền điện ba pha của xưởng',
  'Nạp thẻ điện thoại để gọi khách', 'Thanh toán tiền điện qua ứng dụng',
  'Đóng tiền nước giếng khoan bơm', 'Trả phí dịch vụ internet cho cửa hàng',
  'Gia hạn gói data cho máy bán hàng', 'Hóa đơn điện nước của sạp',
  'Trả tiền điện tháng trước còn nợ', 'Thanh toán tiền nước theo đồng hồ',
  'Đóng tiền điện chiếu sáng biển hiệu', 'Trả cước sim dùng cho máy quẹt thẻ',
  'Đóng tiền vệ sinh môi trường hàng tháng', 'Thanh toán phí wifi quán cà phê',
  'Trả tiền điện chạy máy lạnh', 'Nộp tiền nước cho tổ dân phố'],
 'shipping': [
  'Trả tiền xe chở hàng từ chợ về', 'Thuê ba gác chở đồ',
  'Gửi hàng qua nhà xe', 'Trả cước gửi hàng qua bưu cục',
  'Trả tiền xe ôm giao hàng cho khách', 'Phí giao hàng cho đơn online',
  'Thuê xe tải nhỏ chở hàng tết', 'Trả tiền vận chuyển hàng ra sạp',
  'Gửi hàng đi tỉnh qua xe khách', 'Trả công chở hàng bằng xe máy',
  'Cước vận chuyển đơn đi miền Bắc', 'Trả phí ship cho tài xế công nghệ',
  'Thuê xe chở đá cho quán', 'Trả tiền cước chở hàng đường thủy',
  'Phí vận chuyển nguyên liệu về bếp', 'Trả tiền xe kéo chở hàng',
  'Gửi chuyển phát hàng mẫu cho khách', 'Trả tiền ship hàng hoàn',
  'Thuê xe chở hàng đi hội chợ', 'Phí gửi hàng qua dịch vụ hỏa tốc',
  'Trả tiền cho người chở hàng thuê', 'Cước xe chở hàng từ kho ra chợ',
  'Trả tiền giao hàng nội thành', 'Phí vận chuyển hàng nhập từ xưởng'],
 'salary': [
  'Trả tiền công cho người làm theo ngày', 'Phát lương cho phụ việc',
  'Trả lương em phụ quán tháng này', 'Ứng tiền công cho thợ',
  'Trả công người phụ dọn dẹp quán', 'Trả lương người giao hàng của tiệm',
  'Trả tiền làm thêm cuối tuần cho nhân viên', 'Thưởng lễ cho người làm',
  'Trả lương kế toán làm bán thời gian', 'Trả công người trông sạp',
  'Trả tiền công phụ hồ cho tiệm', 'Trả công người làm bánh thuê',
  'Chi lương cho nhân viên bán hàng online', 'Trả lương người chạy bàn',
  'Trả tiền công người lặt rau', 'Ứng lương giữa tháng cho phụ bếp',
  'Trả công người bưng bê đám tiệc', 'Trả lương tháng mười ba cho nhân viên',
  'Trả công thợ phụ xưởng may', 'Trả tiền công khuân vác hàng',
  'Trả lương người pha chế ca sáng', 'Thanh toán tiền công thời vụ',
  'Trả lương nhân viên giữ xe', 'Thưởng chuyên cần cho nhân viên'],
 'other_expense': [
  'Mua quạt máy cho quán', 'Mua nồi cơm điện cho bếp',
  'Mua chảo và xoong nồi mới', 'Mua bạt che mưa cho sạp',
  'Mua thùng đá giữ lạnh', 'Mua máy hút chân không',
  'Mua giấy in hóa đơn', 'Mua kéo và băng keo cho cửa hàng',
  'Sửa quạt máy của quán', 'Sửa xe đẩy bán hàng',
  'Thay bóng đèn cho cửa hàng', 'Sơn lại tường cửa hàng',
  'Nộp thuế môn bài', 'Đóng phí kiểm định cân điện tử',
  'Trả phí chuyển khoản ngân hàng', 'Trả tiền lãi khoản vay',
  'Đăng tin quảng cáo trên mạng xã hội', 'In danh thiếp cho cửa hàng',
  'Mua bảng menu cho quán', 'Mua tủ mát trưng bày',
  'Mua ổ khóa cửa cho tiệm', 'Mua máy tính tiền',
  'Đóng phí bảo trì thang máy', 'Mua đồng phục cho nhân viên'],
}

# v4: semantic boundary seeds (directionality Thu vs Chi, colloquial market
# phrasing, short service notes, symmetric refund/deposit/debt pairs, durable
# equipment vs consumable stock). Written to avoid duplicating challenge.csv
# or independent_eval.csv.
SEEDS_V4 = {
 'sales': [
  'Bà Tư lấy năm ký bún trả tiền', 'Anh Minh mua hai hộp cơm sườn trả tiền',
  'Cô Mai lấy ba ký cam trả tiền', 'Chú Bảy lấy mười gói mì trả tiền mặt',
  'Khách chuyển khoản đặt trước tiền mua bánh', 'Khách cọc tiền đặt giỏ quà tết',
  'Bán lẻ mười ly nước ép buổi trưa', 'Chốt đơn bán sáu bộ áo thun cho khách',
  'Khách quen trả nợ tiền hàng mua hôm qua', 'Thu tiền bán trái cây gọt sẵn tại quầy',
  'Tiền bán hàng trên sàn thương mại điện tử về ví', 'Đơn hàng bán đồ gia dụng đã thu tiền',
  'Bán hết hai khay xôi mặn buổi sáng', 'Khách mua hai chục cái nem chua trả tiền',
  'Thu tiền bán trà tắc và bánh tráng trộn', 'Khách chuyển khoản mua hai ký chả lụa',
  'Bán buôn năm lốc sữa tươi thu tiền', 'Khách lấy hàng tại sạp thanh toán đủ',
  'Doanh thu bán hàng ăn vặt cả buổi tối', 'Bán được mấy ký tôm sú cho nhà hàng',
  'Khách trả tiền mua bó hoa tươi', 'Thu tiền đơn đặt hàng bánh kem của khách',
  'Bán năm ký cam sành cho khách quen', 'Tiền thu bán hàng tạp hóa buổi chiều'],
 'service': [
  'Vá ruột xe cho khách', 'Cắt tóc nam', 'Gội đầu thư giãn', 'Giặt ủi quần áo',
  'Bơm hơi bánh xe cho khách', 'Sửa bình nóng lạnh cho nhà anh Tuấn lấy công',
  'Sửa máy bơm nước cho nhà cô Sáu lấy tiền', 'Thu hộ phí giao hàng cho khách giúp người gửi',
  'Thu tiền công chạy việc giao nhận giúp khách', 'Nhận làm thuê dịch vụ trang trí tiệc cưới',
  'Thu tiền công tháo lắp máy lạnh cho khách', 'Thay màn hình tivi cho khách lấy tiền công',
  'Nhận tiền công sửa chữa đồ gỗ tại nhà', 'Khách trả tiền làm tóc uốn duỗi nhuộm',
  'Thu tiền dịch vụ đánh bóng xe hơi', 'Nhận công chỉnh sửa quần áo cho khách',
  'Thu phí trông giữ xe máy theo ngày', 'Khách trả tiền thuê thợ chụp ảnh sự kiện',
  'Nhận tiền công cài phần mềm cho khách', 'Thu phí dịch vụ sửa ống khói bếp cho khách',
  'Làm móng chân đắp bột cho khách thu tiền', 'Thay pin điện thoại cho khách lấy công',
  'Nhận tiền vệ sinh sofa tại nhà khách', 'Thu tiền công hàn khung sắt cho khách'],
 'capital': [
  'Vay nóng tiền để nhập trái cây về bán', 'Vay tín chấp lấy vốn nhập lô hàng mới',
  'Mượn tiền người quen để nhập thêm cá thịt', 'Vay tiền bạn bè xoay vòng nhập hàng hóa',
  'Rút tiền tiết kiệm cá nhân bỏ vào vốn quán', 'Chủ hộ rút sổ tiết kiệm đầu tư mở sạp',
  'Hùn vốn chung với anh em mở tiệm ăn', 'Góp vốn thêm với bạn mở quán trà sữa',
  'Mẹ ruột cho mượn tiền làm vốn buôn bán', 'Chị gái chuyển tiền cho mượn bổ sung vốn',
  'Vay vốn ngân hàng thương mại đầu tư cửa hàng', 'Nhận giải ngân khoản vay kinh doanh nhỏ',
  'Bỏ tiền riêng của chủ quán vào quỹ nhập hàng', 'Nạp thêm vốn lưu động vào két tiền mặt',
  'Vay tiền từ người thân để mở rộng kho hàng', 'Nhận tiền góp vốn cổ phần từ đối tác',
  'Mượn tạm tiền gia đình xoay sở vốn tiệm', 'Vay quỹ tín dụng nhân dân làm vốn buôn bán',
  'Chồng góp thêm vốn cho vợ bán hàng ngoài chợ', 'Vay tiền trả góp bổ sung nguồn vốn nhập đồ',
  'Nhận tiền hỗ trợ vốn khởi nghiệp từ gia đình', 'Đem tiền dành dụm bỏ vào làm vốn cửa hàng',
  'Vay ngân hàng chính sách xã hội lấy vốn', 'Bổ sung nguồn vốn kinh doanh đầu tháng'],
 'other_income': [
  'Bán đống chai nhựa và giấy bìa phế liệu', 'Bán phế liệu gom trong kho',
  'Bán đồng nát phế liệu dọn cửa hàng', 'Thanh lý kệ sắt trưng bày cũ không dùng',
  'Thanh lý máy tính bàn cũ của quán', 'Bán thanh lý bàn ghế cũ dư dùng',
  'Nhà cung cấp chuyển khoản hoàn lại tiền hàng thiếu', 'Đại lý hoàn tiền chiết khấu hàng bị lỗi',
  'Sàn thương mại hoàn trả tiền đơn hàng bị hủy', 'Hãng trả lại tiền khuyến mãi trưng bày',
  'Được hoàn lại tiền cọc thuê mặt bằng về quỹ', 'Được hoàn tiền phí dịch vụ thu thừa',
  'Thu hồi tiền đã cho người quen vay trước kia', 'Bạn cũ chuyển trả khoản nợ mượn năm ngoái',
  'Đơn vị bảo hiểm chi trả tiền bồi thường sự cố', 'Khách hàng đền bù tiền làm vỡ đồ của quán',
  'Đơn vị giao hàng bồi thường tiền hàng thất lạc', 'Nhận tiền lãi tài khoản tiết kiệm ngân hàng',
  'Ngân hàng cộng tiền lãi số dư hàng tháng', 'Cho thuê lại một góc sạp dư thu tiền',
  'Thu tiền cho người khác thuê lại chỗ để xe dư', 'Nhận lại tiền cọc vỏ bình nước của đại lý',
  'Được nhận khoản trợ cấp hỗ trợ tiểu thương', 'Bán phế liệu thùng xốp cũ không dùng'],
 'materials': [
  'Mua ly giấy ống hút và hộp đựng bán nước', 'Mua túi nilon và hộp nhựa đựng thức ăn mang về',
  'Mua bao bì túi bóng đựng hàng bán cho khách', 'Mua màng bọc thực phẩm và hộp giấy bán đồ ăn',
  'Chuyển khoản trả tiền hàng cho nhà cung cấp', 'Trả tiền nhập hàng cho nhà cung cấp',
  'Đi chợ đầu mối lấy nông sản về chế biến', 'Thanh toán tiền hàng nhập kho từ đại lý',
  'Lấy mấy thùng nước giải khát từ kho sỉ về bán', 'Mua nguyên liệu bột đường sữa để làm bánh',
  'Mua thịt heo cá tươi về nấu món ăn bán', 'Nhập gạo nếp đậu xanh về bán tại sạp',
  'Mua gia vị dầu ăn hạt nêm cho bếp quán', 'Lấy lô hàng quần áo từ xưởng may về bán',
  'Mua trái cây tươi về xay sinh tố bán cho khách', 'Nhập mì gói bánh kẹo từ nhà phân phối',
  'Mua trà khô trân châu và siro pha chế đồ uống', 'Lấy hàng hải sản tươi từ ghe về bán',
  'Mua trứng gà trứng vịt về bán lẻ ngoài chợ', 'Nhập vật tư tiêu hao bao tay giấy ăn cho quán',
  'Mua cà phê hạt và sữa đặc pha bán hàng ngày', 'Lấy hàng tạp hóa các loại về bày kệ bán',
  'Mua than đá củi lửa phục vụ nấu nướng bán hàng', 'Nhập bia nước ngọt từ đại lý giao tới'],
 'rent': [
  'Nộp tiền chỗ ngồi bán hàng tại chợ truyền thống', 'Đóng lệ phí chỗ bán hàng ngoài chợ cho ban quản lý',
  'Chuyển khoản tiền thuê mặt bằng hàng tháng cho chủ nhà', 'Trả tiền thuê sạp bán thịt cá trong chợ',
  'Đóng tiền thuê ki ốt bán hàng tại chợ đầu mối', 'Thanh toán tiền thuê gian hàng trong siêu thị',
  'Gia hạn tiền thuê kho bãi chứa hàng hóa', 'Đặt cọc thuê mặt bằng mới để mở rộng tiệm',
  'Trả tiền thuê nhà nguyên căn mở cửa hàng', 'Thuê vỉa hè trước nhà bày bán buổi sáng',
  'Nộp tiền thuê quầy bán hàng lưu động cuối tuần', 'Chuyển tiền thuê chỗ bán cà phê vỉa hè',
  'Thanh toán hợp đồng thuê xưởng sản xuất theo quý', 'Trả chủ trọ tiền thuê ki ốt kinh doanh',
  'Đóng tiền thuê mặt tiền cửa hàng tháng này', 'Thuê thêm phòng bên cạnh làm kho chứa đồ',
  'Trả phí thuê bãi đỗ xe giao hàng của tiệm', 'Nộp tiền thuê lô sạp bán quần áo chợ đêm',
  'Thanh toán tiền thuê mặt bằng quý hai cho chủ', 'Chi tiền thuê sạp rau củ tại chợ phường',
  'Trả tiền thuê chỗ đặt tủ bán nước mía', 'Đóng phí thuê địa điểm bán hàng hội chợ',
  'Chuyển khoản tiền nhà thuê làm tiệm tóc', 'Gia hạn hợp đồng thuê cửa hàng thêm một năm'],
 'utilities': [
  'Đóng tiền điện kinh doanh tháng này cho điện lực', 'Thanh toán hóa đơn tiền điện ba pha của xưởng',
  'Nộp tiền nước sinh hoạt và phí thu gom rác', 'Đóng tiền nước máy theo đồng hồ cho cửa hàng',
  'Trả cước internet cáp quang wifi cho tiệm', 'Gia hạn gói cước mạng viễn thông của quán',
  'Nạp tiền điện thoại di động để gọi giao hàng', 'Đóng cước điện thoại bàn cố định tại quầy',
  'Mua gói data di động dùng cho máy quẹt thẻ', 'Thanh toán tiền điện nước mặt bằng hàng tháng',
  'Đóng phí vệ sinh môi trường và tiền rác chợ', 'Trả tiền điện chạy tủ đông bảo quản hàng',
  'Thanh toán cước truyền hình cáp cho quán ăn', 'Nộp tiền điện chiếu sáng khu vực bán hàng',
  'Chuyển khoản đóng tiền nước sạch hàng tháng', 'Trả phí thuê bao đường truyền mạng bán hàng',
  'Đóng hóa đơn tiền điện nước của sạp chợ', 'Nạp thẻ cào điện thoại liên lạc với khách',
  'Thanh toán tiền điện tháng trước còn thiếu', 'Trả tiền internet và truyền hình cho cửa hàng',
  'Đóng phí cấp thoát nước hàng tháng của tiệm', 'Thanh toán cước viễn thông di động trả sau',
  'Chi tiền điện điều hòa nhiệt độ cho quán', 'Nộp hóa đơn điện lực qua ví điện tử'],
 'shipping': [
  'Trả tiền ship cho tài xế giao hàng cho khách', 'Thanh toán phí giao hàng tiết kiệm đơn online',
  'Gửi chành xe lô hàng đi các tỉnh miền Tây', 'Trả cước nhà xe gửi thùng hàng về quê',
  'Thuê xe ba gác chở hàng hóa từ chợ về kho', 'Thuê xe tải nhỏ chở nguyên liệu về cửa hàng',
  'Trả tiền xe ôm giao gấp đơn hàng cho khách', 'Thanh toán phí chuyển phát nhanh bưu điện',
  'Cước gửi bưu kiện hàng bán qua bưu cục', 'Phí vận chuyển hàng nhập từ nhà cung cấp',
  'Trả tiền cước xe khách chở hàng lên phố', 'Thuê shipper giao mười đơn hàng trong ngày',
  'Trả phí giao hàng nội thành qua ứng dụng công nghệ', 'Chi tiền chở hàng ra bến xe gửi đi tỉnh',
  'Phí ship hàng hoàn trả về lại kho cửa hàng', 'Trả công cho người chở hàng thuê bằng xe máy',
  'Thanh toán cước vận tải đường bộ lô hàng mới', 'Thuê xe lôi chở rau quả từ đầu mối về sạp',
  'Chi phí giao đồ ăn tận nơi cho khách đặt', 'Trả phí gửi hàng hỏa tốc cho khách ở xa',
  'Thanh toán tiền bốc dỡ và vận chuyển hàng hóa', 'Cước phí giao nhận đơn hàng thương mại điện tử',
  'Trả tiền xe chở hàng từ cảng cá về chợ', 'Phí chuyển hàng liên tỉnh qua đơn vị vận tải'],
 'salary': [
  'Trả lương hàng tháng cho nhân viên bán hàng', 'Phát lương cuối tháng cho bạn phụ quán',
  'Ứng trước tiền lương giữa tháng cho thợ phụ', 'Trả tiền công theo ca cho nhân viên thu ngân',
  'Thưởng doanh số bán hàng cho nhân viên xuất sắc', 'Chi tiền thưởng lễ tết cho người làm trong tiệm',
  'Trả tiền công người rửa chén dọn dẹp quán ăn', 'Thanh toán tiền công cho thợ sửa chữa chính',
  'Trả lương nhân viên pha chế và phục vụ bàn', 'Chi tiền công tăng ca buổi tối cho nhân viên',
  'Trả tiền công người bốc xếp dỡ hàng hóa nhập', 'Thanh toán lương công nhật cho lao động thời vụ',
  'Trả lương cho nhân viên giữ xe trước cửa hàng', 'Chi phụ cấp ăn trưa chuyên cần cho nhân viên',
  'Trả tiền công người phụ bếp nấu ăn hàng ngày', 'Thanh toán tiền lương bảo vệ ca đêm của tiệm',
  'Trả công cho bạn sinh viên làm bán thời gian', 'Chi lương cho nhân viên đóng gói giao đơn hàng',
  'Trả tiền công người trông coi sạp hàng buổi trưa', 'Thanh toán lương cho kế toán làm bán thời gian',
  'Thưởng thêm tiền công làm ngày lễ cho nhân viên', 'Trả lương thợ may gia công tại xưởng nhỏ',
  'Chi tiền công thuê người đứng bán hộ một ngày', 'Ứng tiền công cho nhân viên giao hàng của quán'],
 'other_expense': [
  'Hoàn tiền lại cho khách do giao sai mẫu hàng', 'Bồi thường cho khách do làm hỏng đồ của họ',
  'Trả lại tiền cọc cho người thuê cũ rời sạp', 'Thanh toán kỳ nợ vay vốn hàng tháng',
  'Trả nợ tiền gốc khoản vay kinh doanh', 'Trả lại tiền đã mượn của bạn bè tháng trước',
  'Trả tiền lãi vay vốn định kỳ hàng tháng', 'Chi sửa tủ lạnh bị hỏng tại cửa hàng',
  'Sửa máy lạnh bị chảy nước của quán', 'Sửa chữa tủ đông và bếp gas của tiệm',
  'Bảo dưỡng xe đẩy hàng và máy pha cà phê', 'Mua máy quét mã vạch và hộp đựng tiền quầy',
  'Sắm bộ dao thớt xoong nồi mới cho bếp quán', 'Mua đồ lau dọn thùng đựng rác vệ sinh tiệm',
  'Mua bàn ghế nhựa và kệ trưng bày cho tiệm', 'Mua tủ mát và máy xay dùng trong bếp quán',
  'Làm biển hiệu mới và mua dù che nắng cho sạp', 'Mua văn phòng phẩm sổ sách ghi chép quầy',
  'Đóng thuế môn bài và thuế khoán kinh doanh', 'Nộp tiền thuế hộ kinh doanh hàng quý',
  'Chạy quảng cáo mạng xã hội và in tờ rơi phát', 'Thanh toán phí duy trì phần mềm quản lý bán hàng',
  'Trả phí dịch vụ kế toán và phí ngân hàng', 'Đóng bảo hiểm cháy nổ và phí kiểm định cân'],
}
# ── Augmentation helpers ───────────────────────────────────────────────

# Common OCR errors for Vietnamese text
OCR_NOISE_MAP = {
    'ă': ['a', 'ắ', 'ằ'], 'â': ['a', 'ầ', 'ấ'], 'đ': ['d', 'ð'],
    'ê': ['e', 'ế', 'ề'], 'ô': ['o', 'ổ', 'ố'], 'ơ': ['o', 'oi'],
    'ư': ['u', 'ừ'], 'ị': ['i'], 'ọ': ['o'], 'ụ': ['u'],
    'ả': ['a'], 'ẻ': ['e'], 'ỉ': ['i'], 'ỏ': ['o'], 'ủ': ['u'],
    'à': ['a'], 'è': ['e'], 'ì': ['i'], 'ò': ['o'], 'ù': ['u'],
    'á': ['a'], 'é': ['e'], 'í': ['i'], 'ó': ['o'], 'ú': ['u'],
    'ã': ['a'], 'õ': ['o'], 'ũ': ['u'], 'ẽ': ['e'], 'ĩ': ['i'],
    'ạ': ['a'], 'ặ': ['a'], 'ậ': ['a'], 'ắ': ['a'], 'ằ': ['a'],
}

# Common speech recognition errors — updated with real Whisper STT misrecognitions
SPEECH_NOISE_MAP = {
    'tiền': ['tiên', 'tiến'],
    'nghìn': ['ngàn', 'nghìng', 'nhin', 'nn'],
    'triệu': ['triều', 'trieu', 'chieu'],
    'trăm': ['chăm', 'cham', 'tram'],
    'bán': ['bàn', 'ban'],
    'mua': ['mùa', 'múa'],
    'thuê': ['thue', 'thuế'],
    'lương': ['luong', 'lướng'],
    'hàng': ['hang', 'hàn'],
    'nhập': ['nhap', 'nhặp'],
    'trả': ['tra', 'trà', 'chả'],
    'phí': ['phi', 'phì'],
    'tiệm': ['tiêm', 'tiem'],
    'quán': ['quan', 'quàn'],
    'vốn': ['von', 'vôn'],
    'nghìn đồng': ['nhin dong', 'nhan dong', 'nđ'],
    'rưỡi': ['rưi', 'rượi'],
    'chính': ['chinh'],
    'khoản': ['khoan'],
    'chuyển khoản': ['chuyen khoan', 'chuyen'],
    'tiền mặt': ['tien mat', 'mat'],
}


def _strip_diacritics(text):
    """Remove Vietnamese diacritics but keep đ→d."""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _ocr_noise(text, rng, intensity=0.15):
    """Simulate OCR misreads: drop diacritics, swap chars."""
    chars = list(text.lower())
    for i, ch in enumerate(chars):
        if ch in OCR_NOISE_MAP and rng.random() < intensity:
            chars[i] = rng.choice(OCR_NOISE_MAP[ch])
    return ''.join(chars)


def _speech_noise(text, rng, intensity=0.3):
    """Simulate Whisper misrecognitions."""
    result = text
    for word, replacements in SPEECH_NOISE_MAP.items():
        if word in result.lower() and rng.random() < intensity:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(rng.choice(replacements), result, count=1)
    return result


def _word_dropout(text, rng, rate=0.1):
    """Randomly drop words to simulate truncated input."""
    words = text.split()
    if len(words) <= 3:
        return text
    return ' '.join(w for w in words if rng.random() > rate)


def _shuffle_words(text, rng, max_swaps=2):
    """Slightly reorder words."""
    words = text.split()
    if len(words) <= 3:
        return text
    for _ in range(min(max_swaps, len(words) // 3)):
        i = rng.randint(0, len(words) - 2)
        words[i], words[i + 1] = words[i + 1], words[i]
    return ' '.join(words)


# STT-style templates simulating how Whisper transcribes spoken Vietnamese
# These reflect natural speech patterns and common STT output forms
STT_TEMPLATES = [
    # Whisper mishears tram/nghin
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//100000} cham {(a%100000)//1000} nhin' if a >= 100000 else f'{_strip_diacritics(s.lower())} {a//1000} nhin',
    # Slang: cu = 1M, xi = 100k
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000000} cu' if a >= 1000000 else f'{_strip_diacritics(s.lower())} {a//100000} xi',
    # Casual "ruoi" = half
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000000} trieu ruoi tien mat' if 1000000 <= a < 2000000 else f'{_strip_diacritics(s.lower())} {a//1000} nghin tien mat',
    # No-diacritics voice output
    lambda s, a: f'hom nay {_strip_diacritics(s.lower())} het {a//1000} nghin dong',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000} nghin tien mat',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000} ngan chuyen khoan',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a} dong tien mat',
    # Extremely casual voice note
    lambda s, a: f'{_strip_diacritics(s.lower())} het {a//1000}k roi',
    lambda s, a: f'ghi {_strip_diacritics(s.lower())} {a//1000}k nhe',
    lambda s, a: f'{_strip_diacritics(s.lower())} tieu {a//1000}k',
    # Mix diacritics + casual number
    lambda s, a: f'{s.lower()} hết {a//1000}k tiền mặt',
    lambda s, a: f'{s.lower()} tổng cộng {a//1000} nghìn',
    # Common spoken pattern: verb + item + amount
    lambda s, a: f'chi {a//1000}k cho {_strip_diacritics(s.lower())}',
    lambda s, a: f'thu {a//1000}k tu {_strip_diacritics(s.lower())}',
]

# Additional paraphrase templates for more diversity
EXTRA_TEMPLATES = [
    # Casual Vietnamese
    lambda s, a: f'{s.lower()}, tổng {a} đ',
    lambda s, a: f'ghi nhé: {s.lower()} - {a} đồng',
    lambda s, a: f'{s}. Số tiền: {a:,} VND'.replace(',', '.'),
    # Question-like
    lambda s, a: f'Ghi cho tôi khoản {s.lower()} {a} VND được không',
    # Receipt-like
    lambda s, a: f'Nội dung: {s}\nSố tiền: {a:,} VND\nNgày: hôm nay'.replace(',', '.'),
    # Short command
    lambda s, a: f'{s.lower()} {a//1000}k',
    lambda s, a: f'{s.lower()} - {a//1000}k',
    lambda s, a: f'{s.lower()} - {a} dong',
    lambda s, a: f'{s.lower()} - {a//1000} nghin',
    lambda s, a: f'{s.lower()} - {a//1000} ngàn',
    lambda s, a: f'{s.lower()} : {a//1000}k',
    # With date prefix
    lambda s, a: f'Sáng nay {s.lower()} hết {a:,} đồng'.replace(',', '.'),
    lambda s, a: f'Chiều nay {s.lower()}, chi {a:,} đ'.replace(',', '.'),
    # With payment method embedded
    lambda s, a: f'{s}, {a:,} đồng, thanh toán bằng tiền mặt'.replace(',', '.'),
    lambda s, a: f'{s}, {a:,} VND, chuyển khoản qua ngân hàng'.replace(',', '.'),
    # Informal
    lambda s, a: f'{s.lower()} tốn {a//1000} nghìn',
    lambda s, a: f'Tốn {a//1000000} triệu cho {s.lower()}' if a >= 1000000 else f'Tốn {a//1000}k cho {s.lower()}',
    # With context
    lambda s, a: f'Hôm nay đi {s.lower()}, hết {a:,} đồng, ghi vào sổ'.replace(',', '.'),
    lambda s, a: f'Xong rồi, {s.lower()} {a:,} đ'.replace(',', '.'),
]


def build():
    out = ROOT / 'datasets'
    out.mkdir(exist_ok=True)
    rows = []
    rng = random.Random(20261021)
    rng_v3 = random.Random(20261125)  # separate stream so v2 rows stay identical
    rng_v4 = random.Random(20261128)
    for category, base_seeds in SEEDS.items():
        assert len(base_seeds) == 24, category
        seeds = base_seeds + SEEDS_V3.get(category, []) + SEEDS_V4.get(category, [])
        for i, seed in enumerate(seeds):
            if i < 24:  # v2 seeds keep their original split
                split = 'train' if i < 16 else 'validation' if i < 20 else 'test'
            elif i < 48:  # v3 seeds: 4 train, 1 validation, 1 test out of every 6
                k = (i - 24) % 6
                split = 'train' if k < 4 else 'validation' if k == 4 else 'test'
            else:  # v4 seeds: 4 train, 1 validation, 1 test out of every 6
                k = (i - 48) % 6
                split = 'train' if k < 4 else 'validation' if k == 4 else 'test'
            group = f'{category}-{i:02}'
            g = rng if i < 24 else rng_v3 if i < 48 else rng_v4
            amount = g.choice([85000, 150000, 350000, 650000, 1200000, 2500000])
            # ── Core variants (backward compatible) ──
            variants = [
                f'{seed} {amount:,} đồng'.replace(',', '.'),
                f'Hôm nay {seed.lower()}, số tiền {amount} VND, chuyển khoản.',
                f'Hôm qua {seed.lower()} hết {amount // 1000} nghìn, trả tiền mặt.',
                f'Ghi giúp tôi: {seed.lower()}, {amount // 1000}k.',
                f'{seed.upper()}. Tổng cộng: {amount} đồng.',
                f'{normalize(seed)} {amount} dong',
                f'{seed.lower()} - {amount // 1000}k',
                f'{seed.lower()} - {amount} dong',
            ]
            # ── Extended augmentation variants (only for train split) ──
            if split == 'train':
                # Extra paraphrase templates
                for template_fn in EXTRA_TEMPLATES:
                    variants.append(template_fn(seed, amount))
                # STT-style variants: simulate Whisper transcription output
                for template_fn in STT_TEMPLATES:
                    try:
                        variants.append(template_fn(seed, amount))
                    except Exception:
                        pass
                # OCR noise variants
                variants.append(_ocr_noise(f'{seed} {amount:,} đồng'.replace(',', '.'), g, 0.15))
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), g, 0.25))
                # Speech noise & colloquial typo variants
                variants.append(_speech_noise(f'{seed.lower()} {amount // 1000} nghìn', g, 0.3))
                variants.append(_speech_noise(f'hôm nay {seed.lower()} {amount} đồng', g, 0.4))
                variants.append(_speech_noise(f'{seed.lower()} {amount // 1000}k', g, 0.5))
                # Stripped diacritics (simulating no-accent Vietnamese / STT output)
                variants.append(f'{_strip_diacritics(seed)} {amount} dong')
                variants.append(f'{_strip_diacritics(seed.lower())} het {amount // 1000} nghin')
                variants.append(f'{_strip_diacritics(seed.lower())} {amount // 1000} ngan tien mat')
                variants.append(f'{_strip_diacritics(seed.lower())} {amount // 1000} nhin dong')
                # Word dropout
                variants.append(_word_dropout(f'Hôm nay {seed.lower()} hết {amount:,} đồng chuyển khoản'.replace(',', '.'), g))
                # Word shuffle (mild)
                variants.append(_shuffle_words(f'{seed} hết {amount // 1000} nghìn tiền mặt', g))
                # Terse short notes (common in quick manual/voice entries)
                variants.append(f'{seed.lower()}')
                variants.append(f'{_strip_diacritics(seed.lower())} {amount // 1000}k')
            elif split == 'validation':
                # Fewer augmentations for validation — still unseen patterns
                variants.append(f'ghi nhé: {seed.lower()} {amount:,} đồng'.replace(',', '.'))
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), g, 0.15))
                variants.append(f'{_strip_diacritics(seed.lower())} {amount} dong')
                variants.append(f'Hôm qua {seed.lower()} tốn {amount // 1000}k')
            else:  # test
                # Test also gets a few more variants for better eval
                variants.append(f'{seed.lower()}, tổng {amount} đ')
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), g, 0.2))
                variants.append(_speech_noise(f'{seed.lower()} {amount // 1000} nghìn đồng', g, 0.3))
                variants.append(f'{_strip_diacritics(seed)} {amount} dong')

            for j, text in enumerate(variants):
                rows.append({'id': f'{group}-{j}', 'text': text,
                             'kind': 'income' if category in INCOME else 'expense',
                             'category': category, 'group_id': group, 'split': split,
                             'origin': 'synthetic_authored_template_v2' if i < 24 else 'synthetic_authored_template_v3' if i < 48 else 'synthetic_authored_template_v4'})
    fields = list(rows[0])
    for split in ('train', 'validation', 'test'):
        with (out / f'{split}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(row for row in rows if row['split'] == split)
    meta = {'origin': 'Synthetic educational data, authored seed families + deterministic variants + augmentation v2; v3 seed families (real-life wording)',
            'seed': 20261021, 'total': len(rows), 'categories': len(SEEDS),
            'split_counts': {s: sum(r['split'] == s for r in rows) for s in ('train', 'validation', 'test')},
            'group_policy': 'A semantic seed and all variants stay in exactly one split. Evaluation is synthetic, not real-world accuracy.',
            'augmentation': 'OCR noise, speech noise, diacritic stripping, word dropout, word shuffle, casual templates'}
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
