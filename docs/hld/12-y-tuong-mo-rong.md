# 12. Ý tưởng mở rộng: từ cảnh báo đến "copilot biết người và biết đường"

Đồ án không bị ràng buộc bởi thực tế sản xuất, nên phần này đề xuất các hướng đi xa hơn cảnh báo, kèm hướng giải quyết và cách thử nhanh. Mỗi ý tưởng đều ghi rõ **phần nào đã kiểm chứng, phần nào là suy đoán**. Không ý tưởng nào là cam kết; mục 12.5 đề xuất cách chọn.

## 12.1 Khung nhìn

Trợ lý giọng nói kiểu "Hey AI" hiện chỉ làm việc **theo lệnh**: nghe, hiểu, bật điều hòa hay hạ kính. Nó không biết người lái đang ra sao, không biết đường phía trước ra sao, không tự đề xuất gì. DriveFocus có thể đi xa hơn theo bốn trục:

| Trục | Câu hỏi | Có sẵn trong thiết kế |
|---|---|---|
| **Hiểu người lái** | Anh/chị đang buồn ngủ, mất tập trung, hay ổn? | Có (file 4) |
| **Hiểu cabin và xung quanh** | Ai ngồi đâu, có trẻ bị bỏ quên không, có xe trong điểm mù không? | Chưa, K230 có 3 cổng camera |
| **Hành động có rào chắn** | Hạ kính, điều hòa, đổi nhạc, gọi SOS, gợi ý chỗ nghỉ | Chưa |
| **Học từ đám đông** | Đoạn đường nào hay buồn ngủ, nơi nào đang có sự cố | Có nền (Traffic-SM) |

Ý tưởng trung tâm: **trợ lý nhận ngữ cảnh từ cả người lái và con đường để chủ động hành động, nhưng mọi hành động đi qua một lớp chính sách an toàn**.

## 12.2 K230 làm được gì ngoài cảnh báo

Đối chiếu ngày 09/11/2026: thư mục `src/reference/ai_poc` của [kendryte/k230_sdk](https://github.com/kendryte/k230_sdk) có sẵn các demo dưới đây (đã đọc phần giới thiệu của từng demo, **chưa chạy thử trên board**). Chip có 3 cổng MIPI CSI (1×4 làn + 1×2 làn, hoặc 3×2 làn) theo brief.

| Demo SDK | Làm gì | Dùng cho ý tưởng | Giới hạn đã thấy |
|---|---|---|---|
| `kws` | Nhận từ khóa đánh thức; mô hình huấn luyện bằng WeNet với từ "xiaonan" | I2 (lệnh bằng giọng nói) | Từ khóa tiếng Trung; muốn từ khóa tiếng Việt phải tự thu âm và huấn luyện lại |
| `dynamic_gesture` | Nhận cử chỉ tay động (phát hiện lòng bàn tay, điểm mốc bàn tay, TSM) | I3 | |
| `face_verification` | Xác minh khuôn mặt hai ảnh có cùng người không | I10 | Dữ liệu sinh trắc, cần opt-in |
| `face_emotion` | 7 lớp biểu cảm | I12 | Độ tin cậy khoa học của nhận diện cảm xúc còn tranh cãi |
| `yolop_lane_seg` | Phân vùng làn đường và vùng lái được | I4, I12 | Cần camera hướng phía trước |
| `traffic_light_detect` | Phát hiện đèn giao thông, tách đỏ và vàng | I4 | Cần camera phía trước |
| `person_detect`, `person_distance` | Phát hiện người đi bộ, ước lượng khoảng cách từ kích thước khung | I4, I9 | Ước lượng thô theo kích thước khung |
| `falldown_detect` | Phát hiện ngã | I5, I9 | Hướng gốc là giám sát nhà/nơi công cộng |
| `tts_zh` | Chuyển chữ thành giọng nói | I1 | **Chỉ tiếng Trung**; tiếng Việt phải dùng phương án khác (phát tệp ghi sẵn hoặc TTS ở điện thoại/đám mây) |
| `llamac` | Chạy mô hình ngôn ngữ nhỏ, chỉ trên lõi nhỏ | (Không dùng) | Demo chỉ nối tiếp một từ tiếng Anh, **không phải trợ lý hội thoại** |
| `face_pose`, `eye_gaze`, `face_landmark`, `dms_system` | Đã dùng ở file 4 | Nền cho I2, I4, I5 | |

Kết luận quan trọng: **K230 mạnh về thị giác nhẹ và từ khóa, yếu về hiểu ngôn ngữ**. Phần hiểu câu lệnh tiếng Việt nên đặt ở điện thoại, máy tính hoặc đám mây; K230 chỉ làm từ khóa đánh thức và mọi thứ thuộc về thị giác.

## 12.3 Các ý tưởng

Ký hiệu công sức: S (vài ngày), M (1 đến 2 tuần), L (hơn 2 tuần). "Wow" là cảm nhận chủ quan khi trình diễn.

### I1. Copilot chủ động, có rào chắn an toàn

**Ý tưởng.** Khi DriveFocus thấy tài xế mệt mức 1 hoặc 2, trợ lý không chỉ bíp. Nó nói "Anh có vẻ mệt. Em hạ nhiệt độ xuống 20 độ và mở hé cửa kính nhé? Cách 4 km có trạm nghỉ." và thực hiện nếu được đồng ý.

**Hướng giải quyết.**
- Một **API hành động xe trừu tượng** (cửa kính, điều hòa, nhạc, đèn nội thất, điều hướng, gọi điện, SOS). Bản demo cài đặt bằng một "bảng điều khiển cabin ảo"; bản xe thật nối vào CAN hoặc lớp trừu tượng của hệ thống giải trí, tùy nền tảng xe mà bạn biết rõ hơn tôi.
- **Chính sách phân bậc hành động** làm lớp chặn trước mọi hành động:

| Bậc | Ví dụ | Điều kiện khi xe chạy |
|---|---|---|
| 0, thông tin | Đọc giờ, hỏi đường | Luôn được, câu ngắn |
| 1, tiện nghi | Điều hòa, cửa kính, nhạc, đèn nội thất | Được, có xác nhận bằng giọng khi tài xế đang mệt |
| 2, điều hướng và liên lạc | Đổi đích, gọi điện rảnh tay | Được với giới hạn (câu ngắn, không đối thoại dài) |
| 3, động lực học | Giảm tốc, phanh, đánh lái | **Ngoài phạm vi**, chỉ mô phỏng (I5) |

- Chính sách đọc trạng thái từ file 4: tài xế mất tập trung thì **không bắt đối thoại dài**; đang mức 3 trở lên thì ưu tiên cảnh báo, hoãn mọi đề xuất tiện nghi.

**Lưu ý trung thực.** Nghiên cứu về chống buồn ngủ cho thấy các can thiệp trong cabin (lạnh, mở cửa kính, nhạc) chỉ có tác dụng ngắn. Biện pháp hiệu quả là nghỉ ngơi. Vì vậy ý tưởng này nên **luôn kết thúc bằng đề xuất dừng nghỉ** (xem I6), không coi điều hòa là giải pháp. Đây cũng là điểm khoa học đáng nêu trong báo cáo.

**Công sức:** M. **Wow:** cao (khác biệt rõ với "Hey AI" nghe lệnh).

### I2. Lệnh đa phương thức theo ánh nhìn: "hạ kính này"

**Ý tưởng.** Tài xế nhìn sang cửa kính bên phụ và nói "hạ cái này xuống". Hệ thống biết "cái này" là gì nhờ **vùng đang nhìn**. Tương tự "tăng âm lượng ở đây" khi nhìn về phía loa phía sau, "mở cái này" khi nhìn màn hình.

**Hướng giải quyết.**
- Dùng tư thế đầu và hướng nhìn (đã có ở file 4) để phân loại **vùng nhìn**: kính trước, gương trái, gương phải, gương giữa, bảng đồng hồ, màn hình giữa, cửa kính phụ, cửa kính sau. Hiệu chỉnh bằng cách yêu cầu tài xế nhìn lần lượt từng vùng khi bắt đầu (giống bước hiệu chỉnh trung tính). Đây là **thuật toán thuần**, không cần mô hình mới.
- Từ khóa đánh thức ở K230 (`kws` huấn luyện lại), câu lệnh được nhận dạng ở máy cạnh thiết bị, rồi **hợp nhất** lệnh với vùng nhìn trong cửa sổ ±1,5 s quanh lúc nói.
- Bắt đầu với một tập lệnh nhỏ theo ngữ pháp cố định (khoảng 15 đến 20 câu), sau đó mới thử LLM gọi hàm.

**Rủi ro.** Độ phân giải vùng nhìn từ đầu và mống mắt khá thô (vùng lớn thì ổn, vùng nhỏ thì khó); nhận dạng giọng nói tiếng Việt trong xe ồn cần đo. Đối với giọng nói tiếng Việt, ví dụ phương án có thể thử là các mô hình nhận dạng giọng nói tiếng Việt mã nguồn mở (như PhoWhisper của VinAI; cần kiểm tra giấy phép và yêu cầu tài nguyên).

**Công sức:** M. **Wow:** rất cao (trình diễn trực quan, dễ hiểu).

### I3. Điều khiển bằng cử chỉ, không chạm màn hình

**Ý tưởng.** Vẫy tay để tắt cuộc gọi, xoay ngón để chỉnh âm lượng, giơ tay để chấp nhận. Mục tiêu: **giảm nhìn xuống màn hình**, tức giảm chính nguyên nhân gây mất tập trung.

**Hướng giải quyết.** Dùng demo `dynamic_gesture` làm nền, giới hạn ở 4 đến 5 cử chỉ lớn, tránh trùng cử chỉ tự nhiên khi lái (chạm mặt, gãi, chỉnh gương); tay đang trên vô-lăng thì không nhận. Dùng chính luật bàn tay–mặt ở file 4 để loại các cử chỉ trùng vùng điện thoại.

**Công sức:** M. **Wow:** trung bình đến cao. Có thể kết hợp với I2 (nhìn vùng + cử chỉ).

### I4. Cảnh báo có điều kiện theo ánh nhìn của tài xế (driver-aware hazard)

**Ý tưởng.** Hệ thống chỉ cảnh báo nguy hiểm bên ngoài khi **tài xế chưa nhìn thấy nó**. Ví dụ: bật xi-nhan trái, có xe trong điểm mù trái, và đã hơn 3 giây tài xế không liếc gương trái thì cảnh báo; nếu đã liếc thì im lặng. Kết quả: ít báo nhầm hơn so với hệ thống điểm mù thông thường, và biết "tài xế chú ý ở đâu" mới là thứ thực sự mới.

**Hướng giải quyết.**
- Camera người lái (cảm biến mắt/đầu) + 1 đến 2 camera ngoài, **cùng một K230** (brief cho 3 cổng MIPI CSI). Phát hiện phương tiện/người bằng `person_detect` hoặc mô hình YOLO nhỏ khác; khoảng cách ước lượng từ kích thước khung như `person_distance`.
- **Camera 360 thật cần ít nhất bốn camera và phép ghép ảnh**, vượt khả năng một K230. Hướng thực tế cho đồ án: dùng **hai camera (phía sau, điểm mù)** trên K230, hoặc lấy dữ liệu từ mô phỏng.
- **Mô phỏng bằng [CARLA](https://github.com/carla-simulator/carla)** (MIT, đang được duy trì, khoảng 14,5 nghìn sao): chạy xe trong thế giới ảo, có sẵn camera vòng quanh và xe lân cận. Người lái ngồi trước webcam thật, điều khiển bằng bàn phím hoặc vô-lăng, còn DriveFocus nhận ảnh khuôn mặt thật và dữ liệu cảnh từ CARLA. **Demo không cần xe thật**, trình diễn được ở lớp. Cần kiểm tra yêu cầu GPU và phiên bản CARLA phù hợp máy.
- Đánh giá: kịch bản có kịch bản (scripted) lặp lại nhiều lần; đo số cảnh báo thừa so với hệ thống điểm mù thuần, thời gian tới phản ứng, số lần bỏ sót.

**Công sức:** L. **Wow:** rất cao. Đây là ý tưởng "khác biệt" nhất, vì nối **trạng thái người lái với trạng thái môi trường**.

### I5. Giao thức khi tài xế mất khả năng lái, tự dừng xe an toàn và gọi cứu hộ

**Ý tưởng.** Mức 4 kéo dài (mắt nhắm ≥ 3 s, đầu gục) mà tài xế không phản hồi sau một lời hỏi "Anh có ổn không?" thì xe: bật đèn khẩn cấp, giảm tốc, tấp vào lề, **gửi SOS kèm vị trí và đoạn đường** tới người thân.

**Hướng giải quyết.**
- Thang leo thang sau mức 4: hỏi bằng giọng nói, chờ phản hồi 5 đến 10 s (giọng nói, cử chỉ, hoặc chạm vô-lăng), rồi mới sang bước kế.
- Tấp xe là **can thiệp động lực học (bậc 3)** nên ngoài phạm vi xe thật. Trong **CARLA** có thể chuyển xe sang chế độ tự lái và dừng lại để minh họa; đây là phần dễ làm và rất trực quan.
- SOS: sự kiện đi qua luồng đã thiết kế (file 5), đám mây gửi thông báo cho số liên hệ khẩn cấp; Tile38 có thể tìm cơ sở y tế gần nhất nếu nạp dữ liệu điểm quan tâm từ OSM (I6).
- Phân biệt với ngủ gật thường: thêm điều kiện đầu gục lâu và không có chuyển động, và yêu cầu hỏi xác nhận trước khi hành động.

**Công sức:** M (với CARLA). **Wow:** rất cao, ý nghĩa xã hội rõ.

### I6. Gợi ý trạm nghỉ và tuyến an toàn hơn

**Ý tưởng.** Khi mệt, trợ lý đề xuất chỗ dừng nghỉ **phía trước trên đường đang đi**, và khi lập tuyến thì né các đoạn đường hay xảy ra buồn ngủ vào giờ này.

**Hướng giải quyết (tận dụng hạ tầng đã có).**
- **Điểm nghỉ:** lấy các điểm quan tâm từ OSM (trạm xăng, bãi dừng nghỉ, quán cà phê, bãi đậu xe) nạp vào **Tile38**; truy vấn lân cận dọc theo tuyến phía trước. Traffic-SM đã có công cụ nạp dữ liệu hình học vào Tile38 (`graph-edge-importer`), có thể làm tương tự cho điểm quan tâm.
- **Tuyến an toàn:** cấu hình GraphHopper của bạn đã dùng **custom model** (`profiles` trỏ tới `car.json`, `motorcycle.json`), nên hướng khả thi là sinh các **vùng đa giác (`areas`)** quanh các đoạn có rủi ro cao theo giờ (từ bảng `df.risk_segment_hour` ở file 5) và đặt hệ số ưu tiên thấp hơn cho vùng đó. Cần kiểm tra cú pháp `areas` và phiên bản GraphHopper trong fork của bạn.
- Hạn chế: bản đồ rủi ro cần dữ liệu đủ nhiều mới có ý nghĩa; với đồ án, dùng dữ liệu mô phỏng và nói rõ như vậy.

**Công sức:** M. **Wow:** trung bình đến cao, **gắn chặt hai nửa của đồ án** (thiết bị và Big Data).

### I7. Dự đoán buồn ngủ trước khi xảy ra

**Ý tưởng.** Thay vì chờ tới khi nhắm mắt, mô hình dự đoán xác suất tài xế sẽ ở mức ≥ 3 trong 15 phút tới, rồi nhắc nghỉ sớm.

**Hướng giải quyết.** Đặc trưng: thời gian lái liên tục, giờ trong ngày (giờ buồn ngủ sinh học thường rơi vào đêm khuya và đầu giờ chiều), tốc độ tăng của PERCLOS, số lần ngáp, thời lượng chớp. Mô hình: hồi quy logistic hoặc cây tăng cường; đánh giá bằng AUC và thời gian báo trước. Spark MLlib cho phần huấn luyện theo lô, suy luận đơn giản đưa xuống thiết bị.

**Rủi ro lớn nhất:** cần nhiều chuyến thật có nhãn. Với đồ án, ghi rõ giới hạn và dùng dữ liệu NTHU-DDD, video tự quay và dữ liệu sinh giả có kiểm soát.

**Công sức:** M. **Wow:** trung bình; **giá trị học thuật cao** vì thêm một thành phần học máy có kiểm chứng ở đúng chỗ.

### I8. Cảnh báo cộng đồng theo vùng địa lý (crowd-sourced hazard)

**Ý tưởng.** Một xe phát hiện phanh gấp liên tiếp, xe dừng giữa đường, hay nhiều tài xế mức 3 trên một đoạn, thì các xe đang tiến tới đoạn đó nhận cảnh báo sớm hơn.

**Hướng giải quyết.** Điểm nguy hiểm ghi vào Tile38 với thời hạn sống ngắn (khoảng 30 phút); mỗi chuyến đăng ký một **vùng địa lý (geofence)** phía trước; khi điểm nguy hiểm lọt vào vùng thì `context-publisher` (file 6) đẩy ngữ cảnh xuống thiết bị. Nguồn tín hiệu: gia tốc từ IMU (phanh gấp), tốc độ về 0 trên đường đang thông thoáng theo `traffic.congestion`, mật độ sự kiện mức 3.

**Công sức:** M. **Wow:** cao với người xem Big Data. Khai thác trực tiếp Tile38 đang chạy sẵn trong Traffic-SM.

### I9. Phát hiện trẻ em hoặc thú cưng bị bỏ quên trong xe

**Hướng giải quyết.** Camera cabin góc rộng (hoặc camera thứ hai) dùng `person_detect` ở hàng ghế sau khi tắt máy; nếu còn người ở lại quá N phút thì gửi thông báo tới điện thoại. Có thể bổ sung `falldown_detect`. Sản phẩm thật thường dùng radar trong cabin; camera đủ cho prototype.

**Rủi ro:** thiết bị phải còn nguồn khi đỗ (tiêu thụ điện), và camera cần nhìn thấy hàng ghế sau. Trong đồ án có thể mô phỏng bằng video.

**Công sức:** S đến M. **Wow:** trung bình, giá trị xã hội cao, **độc lập với phần còn lại** nên dễ thêm.

### I10. Cá nhân hóa theo người lái (tùy chọn, bật khi đồng ý)

**Ý tưởng.** Nhận ra chủ xe và người thân để nạp hồ sơ: ngưỡng EAR đã hiệu chỉnh, tư thế đầu trung tính, cài đặt nhiệt độ và ghế (trong bản mô phỏng). Người lạ ngồi vào lái thì báo chủ xe.

**Hướng giải quyết.** Dùng `face_verification`, so khuôn mặt trong thiết bị với vectơ đã đăng ký; **vectơ không rời thiết bị**. Hiệu chỉnh theo người giúp cải thiện chính các ngưỡng ở file 4.

**Lưu ý.** Điều này đi ngược quyết định trước đây "không nhận diện danh tính" (file 10, D10); nếu làm thì phải là **tùy chọn đăng ký (opt-in) và xử lý hoàn toàn cục bộ**, và cần cập nhật nhật ký quyết định. Dữ liệu sinh trắc nhạy cảm về pháp lý.

**Công sức:** S đến M. **Wow:** trung bình.

### I11. Huấn luyện viên cuối chuyến (báo cáo bằng ngôn ngữ tự nhiên)

**Ý tưởng.** Sau mỗi chuyến hoặc mỗi tuần, trợ lý viết bản tóm tắt tiếng Việt: "Hôm nay anh lái 3 giờ, ngáp 4 lần sau giờ thứ hai trên QL1; lần mệt nhất vào khoảng 14h. Nên nghỉ sau 2 giờ."

**Hướng giải quyết.** Truy vấn ClickHouse lấy số liệu tổng hợp theo chuyến, rồi đưa **chỉ số tổng hợp (không gửi tọa độ thô)** cho một mô hình ngôn ngữ ở đám mây để viết lời; có thể dùng bất kỳ dịch vụ LLM nào. Hiển thị trên trang cá nhân (FR11).

**Công sức:** S. **Wow:** trung bình, rẻ, trình diễn đẹp.

### I12. Tín hiệu bổ sung (mức nghiên cứu, rủi ro cao)

| Ý | Mô tả | Đánh giá |
|---|---|---|
| Hợp nhất tín hiệu từ xe | Độ lệch làn (dùng `yolop_lane_seg` hoặc dữ liệu CARLA) kết hợp với mắt để xác nhận buồn ngủ; xác thực chéo hai nguồn độc lập làm giảm báo nhầm | Khả thi trong CARLA; cần camera phía trước ở xe thật |
| Nhịp tim từ video (rPPG) | Ước lượng nhịp tim từ thay đổi màu da trên mặt, ví dụ dựa trên [rPPG-Toolbox](https://github.com/ubicomplab/rPPG-Toolbox) (GitHub không khai báo giấy phép rõ ràng, cần kiểm tra) | Rất "wow" nhưng **kém ổn định trong xe** (ánh sáng đổi, rung); chỉ nên làm dạng thử nghiệm so sánh có đánh giá, không đưa vào quyết định |
| Nhận diện cảm xúc | `face_emotion` để chỉnh giọng điệu trợ lý (nhẹ nhàng hơn khi căng thẳng) | Cơ sở khoa học của suy ra cảm xúc từ nét mặt còn tranh cãi; nếu dùng thì chỉ để điều chỉnh phong cách giao tiếp, không để kết luận về trạng thái tâm lý |

## 12.4 So sánh nhanh

| Ý tưởng | Wow | Khả thi trong đồ án | Cần phần cứng thêm | Dùng K230 | Dùng Big Data / Traffic-SM |
|---|---|---|---|---|---|
| I1 Copilot chủ động có rào chắn | Cao | Cao | Không (bảng cabin ảo) | Có (trạng thái người lái) | Có (ngữ cảnh, gợi ý nghỉ) |
| I2 Lệnh theo ánh nhìn | Rất cao | Trung bình | Micro | **Có (gaze, từ khóa)** | Không |
| I3 Cử chỉ | Trung bình đến cao | Trung bình | Không | **Có** | Không |
| I4 Cảnh báo theo ánh nhìn | Rất cao | Thấp đến trung bình | Camera ngoài / CARLA | **Có (3 camera)** | Ít |
| I5 Mất khả năng lái → SOS | Rất cao | Cao (với CARLA) | CARLA | Có | Có (SOS, điểm y tế) |
| I6 Trạm nghỉ, tuyến an toàn | Trung bình đến cao | Cao | Không | Gián tiếp | **Có (Tile38, GraphHopper, risk map)** |
| I7 Dự đoán buồn ngủ | Trung bình | Trung bình | Không | Gián tiếp | **Có (Spark ML)** |
| I8 Cảnh báo cộng đồng | Cao | Cao | Không | Gián tiếp | **Có (Tile38 geofence)** |
| I9 Trẻ bỏ quên | Trung bình | Cao | Camera hàng sau | Có | Ít |
| I10 Cá nhân hóa | Trung bình | Cao | Không | Có | Ít |
| I11 Báo cáo cuối chuyến | Trung bình | Rất cao | Không | Không | Có (ClickHouse) |
| I12 rPPG, cảm xúc | Cao (rủi ro) | Thấp | Không | Có | Không |

## 12.5 Đề xuất gói cho đồ án 3

Ba phương án, từ ít đến nhiều rủi ro. Mỗi phương án đều giữ phần lõi (file 4) làm nền.

| Phương án | Gồm | Vì sao | Rủi ro |
|---|---|---|---|
| **Gọn** | Lõi cảnh báo + **I1** + **I6** + **I11** | Hoàn toàn khả thi, bám sát hai repo hiện có, có câu chuyện Big Data rõ | Ít "wow" thị giác |
| **Cân bằng (đề xuất)** | Lõi + **I1** (ngắn) + **I2** (gaze + giọng nói) + **I5** (trong CARLA) + **I6** | Có "wow" ở trình diễn: nhìn cửa kính nói lệnh; nhắm mắt thì xe tự tấp lề; gợi ý trạm nghỉ từ dữ liệu thật | Cần CARLA, GPU phù hợp; nhận dạng giọng tiếng Việt cần đo |
| **Tham vọng** | Thêm **I4** (cảnh báo theo ánh nhìn) và **I8** | Điểm khác biệt học thuật mạnh nhất | Dễ quá tải thời gian; mỗi ý đều là một dự án con |

Thứ tự gợi ý nếu chọn "Cân bằng": lõi cảnh báo (P1) → **I2** (không phụ thuộc phần cứng, thử trên webcam) → **I5** trong CARLA → **I6** với Tile38 và GraphHopper → I1 làm lớp keo và chính sách.

## 12.6 Cách "code thử" nhanh cho từng ý (1 đến 3 ngày mỗi ý)

| Ý | Thử nghiệm nhỏ nhất | Thành công khi |
|---|---|---|
| I2 | Webcam + MediaPipe: hiệu chỉnh 6 vùng nhìn, phân loại vùng theo thời gian thực, in vùng ra màn hình; ghép với gõ phím thay cho giọng nói | Phân loại đúng vùng ≥ 85% trên 6 vùng ở một người |
| I5 | CARLA chạy xe tự lái; script nhận cờ "mức 4" từ lõi cảnh báo, chuyển xe sang tự lái và dừng lề | Nhắm mắt 3 s thật trước webcam thì xe ảo dừng |
| I6 | Nạp ~200 điểm OSM vào Tile38, truy vấn lân cận dọc một tuyến GraphHopper; thử thêm một `areas` phạt vào custom model và so sánh hai tuyến | Tuyến thay đổi đúng khi thêm vùng phạt |
| I8 | Hai tiến trình giả lập hai xe; xe A ghi điểm nguy hiểm vào Tile38, xe B đăng ký geofence phía trước và nhận thông báo | B nhận cảnh báo trước khi tới điểm |
| I4 | CARLA: kịch bản xe ở điểm mù + xi-nhan; so cảnh báo có và không điều kiện ánh nhìn | Số cảnh báo thừa giảm mà không bỏ sót |
| I7 | Sinh dữ liệu chuyến giả có kiểm soát, huấn luyện logistic regression, vẽ ROC | AUC hợp lý trên dữ liệu giả (chỉ để kiểm quy trình) |

## 12.7 Lưu ý

- **Thông tin từ nơi bạn làm việc.** Đồ án nên dùng công nghệ và dữ liệu công khai. Không đưa thông tin nội bộ hoặc bảo mật của công ty vào đồ án (tài liệu, mã, dữ liệu); nếu có thỏa thuận bảo mật với công ty thì kiểm tra trước. Các điểm "tích hợp xe" trong tài liệu này đều dùng bản mô phỏng.
- **Mọi hành động điều khiển xe thật** (ngoài tiện nghi) cần đánh giá an toàn chức năng riêng. Đồ án chỉ mô phỏng, nêu rõ như vậy.
- **Dữ liệu sinh trắc** (I10) và **hình ảnh hàng ghế sau** (I9) phải xử lý cục bộ, có đồng ý.
- **Giọng nói tiếng Việt:** từ khóa tiếng Việt cho K230 và nhận dạng câu lệnh trong cabin ồn là hai bài toán riêng, cần thu mẫu và đo; không giả định sẽ ổn ngay.
- Mọi ý tưởng đều ghi **chưa chạy thử**; mục 12.6 là cách để biết nhanh ý nào đáng đầu tư trước khi cam kết vào báo cáo.
