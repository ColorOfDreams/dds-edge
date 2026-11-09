"""Nội dung báo cáo DriveFocus. Số liệu đọc từ report/results/*.json; mã nguồn trích bằng inspect."""
from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "report" / "results"
FIG = ROOT / "report" / "figs"
DDS_FIGS = ROOT.parent / "dds-edge" / "reports" / "cv" / "figs"
sys.path.insert(0, str(ROOT / "edge" / "src"))
sys.path.insert(0, str(ROOT / "cloud" / "src"))


def vn(x: float, nd: int = 1) -> str:
    """Số kiểu Việt: dấu phẩy thập phân."""
    return f"{x:.{nd}f}".replace(".", ",")


def pct(a: int, b: int, nd: int = 1) -> str:
    return vn(100.0 * a / b, nd) + "%"


def thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _strip_comments(lines):
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("#"):
            continue
        ln = re.sub(r"\s{2,}#.*$", "", ln)
        out.append(ln)
    return out


def src(obj, strip_doc=False, max_lines=None) -> str:
    s = inspect.getsource(obj)
    s = inspect.cleandoc(s) if False else s
    lines = s.rstrip("\n").split("\n")
    # bỏ thụt đầu dòng chung
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    lines = [l[indent:] for l in lines]
    if strip_doc:
        text = "\n".join(lines)
        text = re.sub(r'\n    """.*?"""\n', "\n", text, flags=re.S)
        lines = text.split("\n")
    lines = _strip_comments(lines)
    if max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


def test_counts() -> dict[str, int]:
    out = subprocess.run([str(ROOT / "edge" / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "--collect-only", "-q", "tests"],
                         cwd=ROOT / "edge", capture_output=True, text=True, encoding="utf-8").stdout
    c: dict[str, int] = {}
    for m in re.finditer(r"tests[\/](test_\w+)\.py::", out):
        c[m.group(1)] = c.get(m.group(1), 0) + 1
    out2 = subprocess.run([str(ROOT / "edge" / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "--collect-only", "-q", "tests"],
                          cwd=ROOT / "cloud", capture_output=True, text=True, encoding="utf-8").stdout
    c["cloud"] = len(re.findall(r"tests[\/]test_gateway\.py::", out2))
    return c


def build(B) -> None:
    sf = json.loads((RES / "sf_analysis.json").read_text(encoding="utf-8"))
    cl = json.loads((RES / "closure.json").read_text(encoding="utf-8"))
    bench = json.loads((RES / "bench.json").read_text(encoding="utf-8"))
    tc = test_counts()
    D = sf["detection"]
    DT = sf["detection_total"]
    ntest, nval = sf["n"]["test"], sf["n"]["val"]
    ph, dr = sf["rules"]["phone"], sf["rules"]["drink"]
    near = sf["any_hand_near_head"]

    from drivefocus import estimators, geometry, motion
    from drivefocus_cloud import gateway

    # ======================================================================= CHƯƠNG 1
    B.h1("TỔNG QUAN BÀI TOÁN")
    B.h2("Bài toán")
    B.p("Buồn ngủ và mất tập trung khi lái xe là hai nguyên nhân phổ biến gây tai nạn giao thông. Một camera đặt trong xe hướng về tài xế "
        "kết hợp với thị giác máy tính có thể phát hiện sớm các dấu hiệu này và nhắc tài xế ngay tại chỗ. Đề tài DriveFocus xây dựng một "
        "hệ thống giám sát tài xế gồm hai phần: phần trên xe (DF-Edge) tự quyết định cảnh báo mà không cần mạng, và phần đám mây (DF-Cloud) "
        "nhận sự kiện đã ẩn danh, ghép với hệ thống phân tích giao thông Traffic-SM của nhóm để biết sự kiện nguy hiểm xảy ra ở đoạn đường nào.")
    B.p("Đề tài thuộc lĩnh vực thị giác máy tính, cụ thể là bài toán giám sát tài xế (Driver Monitoring System). Hệ thống nhận vào luồng ảnh từ "
        "camera trong cabin và tốc độ xe từ GPS, rồi trả ra:")
    B.bullets(["Mức cảnh báo từ 0 đến 4 theo thời gian thực. Chỉ mức 4 là báo động khẩn cấp, ví dụ nhắm mắt liên tục từ 3 giây trở lên.",
               "Sự kiện cho từng đoạn bất thường: loại (nhắm mắt, buồn ngủ, nhìn lệch, điện thoại…), mức cao nhất, thời lượng, quãng đường xe đã đi trong sự kiện.",
               "Chỉ hoạt động khi xe đang chạy: xe dừng đèn đỏ thì không cảnh báo."])
    B.p("Điểm đặc biệt của đề tài là **mọi quyết định cảnh báo do thuật toán tự thiết kế đưa ra**, không dùng một mạng phân loại hành vi huấn luyện sẵn. "
        "Mạng nơ-ron chỉ đóng vai cảm biến phổ thông (tìm mặt, điểm mốc khuôn mặt, bàn tay, tư thế cơ thể); các số đo hình học tính từ đó "
        "(độ mở mắt, độ mở miệng, góc đầu, vị trí tay so với đầu) được đưa qua một bộ quy tắc có ngưỡng và thời lượng. Cách làm này có ba lý do: "
        "bộ dữ liệu công khai phổ biến (State Farm) không có lớp nhắm mắt hay ngáp; quyết định giải thích được và chỉnh được ngưỡng; và phần quyết định "
        "rất nhẹ (khoảng 0,13 ms mỗi khung) nên chạy được trên thiết bị biên như chip Kendryte K230.")
    B.p("Bài toán có bốn khó khăn chính:")
    B.bullets(["Báo nhầm làm hỏng sản phẩm: chớp mắt, liếc gương, đeo kính râm hay dừng đèn đỏ đều không phải nguy hiểm.",
               "Không nhìn thấy mắt (kính râm, thiếu sáng, quay mặt) không được coi là nhắm mắt.",
               "Dữ liệu công khai khác miền triển khai: ảnh State Farm quay từ ghế phụ, nhìn nghiêng gần 90 độ, trong khi thuật toán cần mặt nhìn thẳng.",
               "Thiết bị biên có bộ nhớ, năng lượng tính toán và điện năng hạn chế."])

    B.h2("Trình bày dữ liệu bài toán")
    B.p("Đề tài dùng nhiều nguồn dữ liệu, mỗi nguồn phục vụ một phần của hệ thống ({tbl:sources}). Không có nguồn nào đủ cho toàn bộ bài toán, "
        "và điều này được ghi nhận như một hạn chế ở phần kết luận.")
    B.table("sources", "Các nguồn dữ liệu và vai trò", ["Nguồn", "Nội dung", "Quy mô", "Vai trò trong đề tài"],
            [["State Farm Distracted Driver", "Ảnh 640×480, 10 lớp hành vi, camera ghế phụ, ban ngày", "22.424 ảnh, 26 tài xế",
              "Đánh giá luật hình học tay–đầu; đo tỉ lệ phát hiện của cảm biến"],
             ["Ảnh chân dung mẫu của MediaPipe", "Một ảnh mặt nhìn thẳng, mắt mở", "1 ảnh",
              "Kiểm thử cảm biến; mô phỏng mắt nhắm bằng phủ màu da lên vùng mắt"],
             ["fake_gps.csv của Traffic-SM", "GPS mô phỏng trên đường thật ở TP.HCM, ô tô và xe máy", "36.941 dòng, 30 tài xế",
              "Nguồn tốc độ và tuyến cho thử nghiệm ghép với Traffic-SM"],
             ["NTHU-DDD, YawDD, DMD", "Video buồn ngủ, ngáp, phân tâm", "Chưa tải",
              "Dự kiến dùng để chỉnh ngưỡng; chưa có vì cần đăng ký truy cập"]],
            [2000, 2700, 1800, 2288], ["left", "left", "center", "left"])
    B.p("Bộ State Farm Distracted Driver Detection là cuộc thi Kaggle năm 2016, gồm ảnh của 26 tài xế thực hiện mười hành vi c0 đến c9. "
        "Đề tài dùng lại đúng cách chia theo tài xế của báo cáo trước về học sâu (cùng một tệp manifest), để mỗi tài xế chỉ nằm ở một tập: "
        f"18 tài xế huấn luyện, 4 tài xế kiểm định (val, {thousands(nval)} ảnh) và 4 tài xế kiểm tra (test, {thousands(ntest)} ảnh). "
        "Vì đề tài này không huấn luyện mô hình, tập huấn luyện không được dùng; tập val dùng để chọn ngưỡng và tập test dùng để báo cáo, "
        "nên không có tài xế nào xuất hiện ở cả hai bước.")
    B.p("Các lớp hành vi theo đúng nhãn của bộ dữ liệu:")
    B.bullets(["c0: lái xe an toàn.", "c1, c3: nhắn tin bằng tay phải, bằng tay trái; c2, c4: gọi điện bằng tay phải, bằng tay trái.",
               "c5: thao tác radio; c6: uống nước.", "c7: với ra phía sau; c8: chải tóc hoặc trang điểm; c9: nói chuyện với hành khách."])
    B.p("Dữ liệu GPS lấy từ tệp fake_gps.csv của Traffic-SM do bộ mô phỏng sinh ra: mỗi dòng gồm mã tài xế, thời điểm, vĩ độ, kinh độ, hướng, tốc độ (m/s), "
        "độ chính xác và loại phương tiện. Đề tài đọc một tài xế ô tô làm tuyến và tốc độ cho thiết bị giả lập, rồi đẩy lại vào Traffic-SM qua cổng "
        "ingest để kiểm tra đường ống.")

    B.h2("Tiền xử lý dữ liệu")
    B.bullets([
        "Ảnh: đọc BGR bằng OpenCV, đổi sang RGB trước khi đưa vào MediaPipe. Mọi khoảng cách tính trên **toạ độ điểm ảnh** chứ không trên toạ độ chuẩn hoá, "
        "vì toạ độ chuẩn hoá làm méo tỉ lệ khung hình (đã có bài kiểm thử cho điều này).",
        "Thời gian: mọi bộ đếm dùng mốc thời gian thực của khung hình, không đếm số khung, để kết quả không đổi khi tốc độ khung thay đổi.",
        "Quan sát ba trạng thái: mỗi số đo có thể là đóng/mở hoặc KHÔNG BIẾT (mất mặt, mắt quá tối). KHÔNG BIẾT không cộng và không làm suy giảm bộ đếm, "
        "và bị loại khỏi mẫu số của PERCLOS.",
        "Hiệu chỉnh theo người: độ mở mắt bình thường lấy từ trung vị EAR trong khoảng đầu chuyến khi xe chạy ổn định; tư thế đầu trung tính lấy từ trung vị góc "
        "khi xe chạy từ 30 km/h.",
        "GPS: đổi tốc độ, toạ độ về định dạng ingest của Traffic-SM; `time` theo múi giờ UTC+7, `t_timestamp` dạng MM:SS.s (cắt, không làm tròn); "
        "mã tài xế thay bằng mã chuyến đi ẩn danh.",
        "Ảnh State Farm: dùng ảnh gốc 640×480 của tập val và test, không thu nhỏ, để cảm biến có đủ độ phân giải."])

    B.h2("Trực quan dữ liệu")
    B.p("{fig:classes} cho thấy mười lớp hành vi của cùng một tài xế. Điểm đáng chú ý là camera đặt ở ghế phụ nên **tài xế luôn được nhìn nghiêng**: "
        "chỉ thấy một bên mặt, một bên tai, và một tay thường bị che.")
    B.fig("classes", DDS_FIGS / "classes.jpg", "Mười lớp hành vi c0 đến c9 của cùng một tài xế trong bộ State Farm", 14.5)
    B.p(f"Hệ quả được đo ở {{fig:detection}} trên tập test ({thousands(ntest)} ảnh). Bộ Face Landmarker của MediaPipe chỉ tìm thấy mặt trong "
        f"{thousands(DT['face'])} ảnh ({pct(DT['face'], DT['n'])}); riêng lớp c9 (nói chuyện với hành khách, tài xế quay mặt về phía camera) là "
        f"{pct(D['c9']['face'], D['c9']['n'])}, còn lái xe an toàn c0 chỉ {pct(D['c0']['face'], D['c0']['n'])}. Trong số ảnh tìm thấy mặt, chỉ "
        f"{DT['eyes']} ảnh có mắt đủ rõ để đo EAR. Ngược lại, Pose Landmarker (mô hình tư thế cơ thể) tìm thấy tư thế trong {pct(DT['pose'], DT['n'])} ảnh.")
    B.fig("detection", FIG / "sf_detection.png", "Tỉ lệ ảnh phát hiện được theo từng lớp trên tập test của State Farm", 14.5)
    B.p("Vì vậy các thuật toán dựa trên mắt (EAR, PERCLOS) **không đánh giá được trên State Farm**; bộ dữ liệu này chỉ dùng để đánh giá luật hình học tay–đầu, "
        "với mô hình tư thế cơ thể thay cho mô hình khuôn mặt.")

    # ======================================================================= CHƯƠNG 2
    B.h1("CƠ SỞ LÝ THUYẾT")
    B.h2("Thị giác máy tính và giám sát tài xế")
    B.h3("Giới thiệu về thị giác máy tính")
    B.p("Thị giác máy tính là lĩnh vực nghiên cứu cách để máy tính thu nhận, xử lý và hiểu nội dung của ảnh và video. Các bài toán tiêu biểu gồm phân loại ảnh, "
        "phát hiện đối tượng, ước lượng tư thế và theo dõi chuyển động. Trong giám sát tài xế, các bài toán này được dùng để biết tài xế đang nhìn đâu, "
        "mắt đang mở hay nhắm, và tay đang làm gì.")
    B.h3("Các dấu hiệu buồn ngủ và mất tập trung")
    B.bullets(["Mắt nhắm kéo dài và tỉ lệ thời gian nhắm mắt cao (PERCLOS) là dấu hiệu buồn ngủ được dùng rộng rãi.",
               "Ngáp và gục đầu là dấu hiệu phụ, thường đi cùng mệt mỏi.",
               "Hướng đầu và hướng nhìn lệch khỏi mặt đường kéo dài là dấu hiệu mất tập trung.",
               "Tay đưa lên tai hoặc miệng gợi ý gọi điện, uống nước, ăn uống hoặc hút thuốc; nhìn xuống kéo dài gợi ý nhắn tin."])
    B.p("Mỗi dấu hiệu chỉ có ý nghĩa khi kéo dài đủ lâu: một lần chớp mắt thường dưới nửa giây, một lần liếc gương dưới một giây. Vì vậy mọi quy tắc "
        "trong đề tài đều có điều kiện thời lượng.")
    B.h3("Trí tuệ nhân tạo trên thiết bị biên và chip K230")
    B.p("Chạy trên thiết bị biên có ba lợi thế: cảnh báo không phải chờ đường truyền, video có khuôn mặt tài xế không phải gửi đi đâu, và hệ thống vẫn hoạt động "
        "khi mất sóng. Chip Kendryte K230 có hai lõi RISC-V (một lõi 1,6 GHz có vector chạy RTOS và một lõi 800 MHz chạy Linux), bộ tăng tốc suy luận KPU hỗ trợ INT8 và INT16 "
        "(nhà sản xuất ghi khoảng 6 TOPS), ba cổng camera MIPI CSI và bộ ISP hỗ trợ mẫu RGB-IR. SDK của K230 có sẵn các demo nhận diện mặt, điểm mốc, tư thế đầu, "
        "hướng nhìn và phát hiện lòng bàn tay, là nền cho tầng cảm biến khi chuyển từ máy tính sang chip. Đề tài này chưa chạy trên chip K230 thật; mọi số đo "
        "trong báo cáo là trên CPU máy tính.")

    B.h2("OpenCV và MediaPipe")
    B.h3("Giới thiệu về OpenCV")
    B.p("OpenCV là thư viện mã nguồn mở phổ biến nhất cho thị giác máy tính, hỗ trợ đọc ghi ảnh và video, xử lý ảnh, vẽ và giải bài toán hình học như PnP. "
        "Đề tài dùng OpenCV để đọc camera và video, vẽ lớp thông tin lên khung hình và phép biến đổi hình học.")
    B.h3("MediaPipe")
    B.p("MediaPipe là bộ công cụ mã nguồn mở của Google cho các ứng dụng thị giác thời gian thực. Đề tài dùng ba mô hình qua giao diện Tasks API:")
    B.bullets(["Face Landmarker: tìm mặt và 478 điểm mốc (có cả mống mắt), kèm ma trận biến đổi 4×4 mô tả tư thế đầu.",
               "Hand Landmarker: 21 điểm mốc cho mỗi bàn tay.",
               "Pose Landmarker: 33 điểm mốc cơ thể, gồm mũi, tai, miệng, vai và cổ tay; dùng cho ảnh nhìn nghiêng khi Face Landmarker không tìm thấy mặt."])
    B.p("Các mô hình này được dùng như cảm biến có sẵn, không huấn luyện lại. Phiên bản MediaPipe dùng là 1.2.2.")
    B.h3("Cài đặt")
    B.bullets(["Pip: `pip install mediapipe opencv-python numpy pyyaml`.", "Tải các tệp mô hình `.task` bằng `scripts/download_models.py`.",
               "Phiên bản Python dùng là 3.11."])

    B.h2("Các đại lượng hình học trên khuôn mặt")
    B.h3("Tỉ số mở mắt EAR")
    B.p("Tỉ số mở mắt EAR (Eye Aspect Ratio) của Soukupová và Čech được tính từ sáu điểm quanh mắt ({fig:ear}):")
    B.p("EAR = (‖p2 − p6‖ + ‖p3 − p5‖) / (2 · ‖p1 − p4‖)")
    B.p("trong đó p1 và p4 là hai khóe mắt, các cặp (p2, p6) và (p3, p5) là mi trên và mi dưới. Mắt mở cho EAR khoảng 0,2 đến 0,35; mắt nhắm cho EAR gần 0. "
        "Tọa độ phải là điểm ảnh. Để khác biệt giữa các người và góc camera không ảnh hưởng, đề tài chuẩn hoá EAR bằng EAR mắt mở của chính tài xế và coi mắt nhắm khi EAR "
        "chuẩn hoá dưới 0,5.")
    B.fig("ear", FIG / "ear.png", "Sáu điểm quanh mắt và công thức EAR", 12.0)
    B.h3("PERCLOS")
    B.p("PERCLOS là tỉ lệ thời gian mắt nhắm trong một cửa sổ, thường là một phút. Đề tài tính PERCLOS theo thời gian (tích phân giữa các mẫu chứ không đếm khung), "
        "loại các khoảng KHÔNG BIẾT khỏi mẫu số, và chỉ coi là hợp lệ khi cửa sổ đã đầy và phần quan sát được chiếm ít nhất 80%. Cách làm này lấy ý tưởng từ "
        "dự án mã nguồn mở driver-state-detection.")
    B.h3("Tỉ số mở miệng MAR")
    B.p("MAR (Mouth Aspect Ratio) bằng khoảng cách giữa môi trên và môi dưới (điểm trong) chia chiều rộng miệng. Ngáp được tính khi MAR vượt ngưỡng "
        "liên tục từ 1,5 giây trở lên; số lần ngáp trong 10 phút là dấu hiệu mệt mỏi.")
    B.h3("Tư thế đầu")
    B.p("Tư thế đầu gồm ba góc yaw (quay trái phải), pitch (gật, cúi) và roll (nghiêng). Đề tài lấy từ ma trận biến đổi 4×4 mà Face Landmarker khớp từ cả 468 điểm "
        "với mô hình mặt chuẩn. Một phương án dự phòng là giải bài toán PnP (Perspective-n-Point) từ sáu điểm với mô hình 3D mặt chuẩn. Trên ảnh mẫu nhìn thẳng, "
        "ma trận cho pitch khoảng +4 độ còn PnP sáu điểm cho +18 độ, vì PnP nhạy với đặc điểm khuôn mặt từng người; lệch hằng số này bước hiệu chỉnh trung tính "
        "loại bỏ được, nhưng độ nhiễu thì không, nên ma trận được chọn làm mặc định. Quy ước: pitch dương là cúi xuống.")

    B.h2("Luật hình học bàn tay–đầu")
    B.p("Gọi điện, uống nước, ăn uống hoặc hút thuốc đều đưa tay lên gần đầu. Luật đo khoảng cách từ tâm bàn tay đến tai và đến miệng, chia cho một đơn vị cỡ đầu "
        "để không phụ thuộc khoảng cách tới camera. Khi khoảng cách nhỏ hơn ngưỡng k và kéo dài đủ lâu, luật gắn cờ. Ý tưởng lấy từ demo dms_system của SDK K230, có hai sửa đổi: "
        "chuẩn hoá theo độ dài (chiều rộng mặt hoặc khoảng cách mũi–tai) thay vì theo diện tích, vì độ dài tỉ lệ với căn bậc hai của diện tích; và loại trường hợp "
        "bàn tay gần mắt hơn tai và miệng để không nhầm với dụi mắt. Nhắn tin không đưa tay lên mặt nên được bắt bằng việc cúi đầu kéo dài.")

    B.h2("Ngân sách chú ý và máy trạng thái")
    B.p("Nếu mỗi lần tài xế liếc lên đường là bộ đếm quay về 0, người nhắn tin xen kẽ liếc đường sẽ không bao giờ bị cảnh báo. Dự án mã nguồn mở openpilot giải quyết bằng một "
        "đại lượng chú ý giảm đều khi mất tập trung và hồi phục có điều kiện. Đề tài dùng cùng ý tưởng: ngân sách A trong [0, 1]; khi mất tập trung, "
        "A giảm với tốc độ w/T (T = 6 giây, w là trọng số theo nguyên nhân); khi chú ý trở lại, A tăng với hệ số hồi phục từ 1,25 đến 5 lần, nhanh hơn khi A đang thấp. "
        "Mức cảnh báo là số ngưỡng 0,75, 0,58 và 0,33 mà A đã vượt xuống, và A = 0 là mức 4. Với w = 1, các mức đạt lần lượt sau 1,5; 2,5; 4,0 và 6,0 giây mất tập trung liên tục.")
    B.p("Mức cảnh báo hiển thị đi qua một máy trạng thái: lên ngay khi điều kiện đạt, xuống từng bậc sau khi điều kiện hết đủ lâu, để tránh nhấp nháy.")

    B.h2("Hạ tầng dữ liệu của Traffic-SM")
    B.p("Traffic-SM nhận GPS của nhiều tài xế, khớp vào đường thật bằng GraphHopper và tính mức tắc nghẽn. Luồng xử lý đi qua Kafka theo các topic gps.raw, gps.traces và gps.matched; "
        "Spark Structured Streaming gom theo cửa sổ 10 giây (watermark 30 giây) cho từng đoạn đường, so tốc độ trung vị với tốc độ chuẩn để gán mức FREE, SLOW hoặc CONGESTED; kết quả "
        "lưu ở ClickHouse và hiển thị bằng Grafana. Cổng vào là `POST /v1/ingest`, nhận một bản ghi hoặc một mảng tối đa 5.000 bản ghi. DriveFocus tận dụng nguyên vẹn hệ thống "
        "này: xe DriveFocus chỉ là một nguồn GPS nữa, với mã tài xế thay bằng mã chuyến đi ẩn danh.")

    B.h2("Chỉ số đánh giá")
    B.bullets(["Precision, recall và F1 cho từng luật: precision là tỉ lệ ảnh gắn cờ đúng, recall là tỉ lệ ảnh cần gắn cờ được gắn cờ, F1 là trung bình điều hoà của hai chỉ số.",
               "AUC: xác suất một ảnh dương có điểm số cao hơn một ảnh âm bất kỳ, không phụ thuộc ngưỡng.",
               "Độ trễ cảnh báo: thời gian từ lúc bắt đầu nhắm mắt đến lúc đạt từng mức.",
               "Thời gian xử lý mỗi khung và số khung mỗi giây trên CPU."])

    # ======================================================================= CHƯƠNG 3
    B.h1("NỘI DUNG THỰC HIỆN VÀ KẾT QUẢ")
    B.h2("Kiến trúc hệ thống")
    B.p("Hệ thống gồm ba khối ({fig:arch}). Trên xe, DF-Edge nhận ảnh camera và tốc độ GPS; tầng cảm biến tính các số đo hình học, tầng quyết định đưa ra mức cảnh báo và "
        "ghi sự kiện vào hàng đợi. Sự kiện và GPS được gửi lên device-gateway; gateway ẩn danh hóa (mã tài xế thành mã chuyến đi), chuyển GPS sang Traffic-SM "
        "và lưu sự kiện vào ClickHouse. Video không bao giờ rời thiết bị.")
    B.fig("arch", FIG / "arch.png", "Kiến trúc hệ thống DriveFocus", 14.5)
    B.p("{fig:fsm} là máy trạng thái hiển thị. Cảnh báo có 4 mức: nhắc nhẹ, cảnh báo, nguy hiểm và báo động khẩn cấp. Điều kiện nhắm mắt liên tục lần lượt là "
        "0,5; 1; 2 và 3 giây; mức 4 chỉ do các điều kiện nguy cấp nhất kích hoạt.")
    B.fig("fsm", FIG / "fsm.png", "Máy trạng thái hiển thị mức cảnh báo", 14.0)

    B.h2("Mã nguồn các bộ đo")
    core_lines = sum(len((ROOT / "edge" / "src" / "drivefocus" / f).read_text(encoding="utf-8").splitlines()) for f in ("config.py", "types.py", "geometry.py", "motion.py", "estimators.py", "engine.py"))
    core_lines = int(round(core_lines, -1))
    B.p(f"Phần quyết định nằm trong gói drivefocus, gồm khoảng {core_lines} dòng Python thuần, chỉ phụ thuộc numpy và pyyaml; OpenCV và MediaPipe chỉ cần ở tầng cảm biến. "
        "Các hằng số đều nằm trong một tệp cấu hình YAML có chú thích.")
    B.h3("Tỉ số mở mắt")
    B.p("Hàm tính EAR cho một mắt từ sáu điểm theo thứ tự hai khóe mắt, cặp điểm thứ nhất, cặp điểm thứ hai ({fig:code_ear}). Mắt bị co về bề rộng bằng 0 thì trả về None, "
        "tức KHÔNG BIẾT.")
    B.code("code_ear", "Mã nguồn tính EAR từ sáu điểm theo toạ độ điểm ảnh", src(geometry.eye_aspect_ratio, strip_doc=True))
    B.h3("Đoạn nhắm mắt liên tục")
    B.p("Đại lượng quyết định cho mức 4 là thời gian nhắm mắt liên tục ({fig:code_run}). Một lỗ hổng \"mở mắt\" dài tối đa 0,2 giây (nhiễu điểm mốc một hai khung) "
        "không làm bộ đếm quay về 0; khoảng KHÔNG BIẾT ngắn giữ nguyên bộ đếm, và khi KHÔNG BIẾT kéo dài quá 1 giây thì bộ đếm được đặt lại.")
    B.code("code_run", "Mã nguồn cập nhật đoạn nhắm mắt liên tục", src(estimators.EyeEstimator._update_run))
    B.h3("Cổng chuyển động")
    B.p("Cổng chuyển động chỉ cho phép cảnh báo khi xe chạy ({fig:code_gate}). Vào trạng thái MOVING khi tốc độ từ 10 km/h liên tục 3 giây; ra khi dưới 3 km/h liên tục 5 giây. "
        "Khoảng cách giữa hai ngưỡng và thời gian giữ là hysteresis, chống nhấp nháy khi kẹt xe. Mất GPS thì giữ trạng thái cũ tối đa 30 giây, sau đó dùng cảm biến chuyển động (IMU); "
        "không có IMU thì chuyển sang UNKNOWN, khi đó chỉ giữ báo động nhắm mắt mức 4.")
    B.code("code_gate", "Mã nguồn cổng chuyển động với hysteresis", src(motion.MovementGate.update))
    B.h3("Ngân sách chú ý")
    B.p("{fig:code_budget} là cài đặt ngân sách chú ý. Nguyên nhân gây mất tập trung có trọng số khác nhau: nhìn lệch 1,0, điện thoại 1,5 và uống hoặc ăn 0,7.")
    B.code("code_budget", "Mã nguồn ngân sách chú ý", src(estimators.AttentionBudget.update))

    B.h2("Thực nghiệm và kết quả")
    B.h3("Kiểm thử tự động")
    t_edge = sum(v for k, v in tc.items() if k != "cloud")
    B.p(f"Toàn bộ mã được phủ bằng {t_edge} bài kiểm thử cho phần thiết bị và {tc['cloud']} bài cho gateway, tất cả đều đạt ({{tbl:tests}}). "
        "Ngoài kiểm thử đơn vị, đề tài dùng golden trace: một kịch bản dài khoảng 60 giây gồm chớp mắt, nhắm mắt, nhìn lệch, điện thoại và dừng xe được phát lại qua tệp JSON Lines; "
        "chuỗi sự kiện ra phải trùng tệp mong đợi. Cùng cơ chế sẽ dùng để kiểm bản cài đặt C++ trên K230.")
    B.table("tests", "Các nhóm kiểm thử tự động", ["Nhóm", "Số bài", "Nội dung chính"],
            [["Hình học", str(tc.get("test_geometry", 0)), "EAR, MAR, tư thế đầu và quy ước dấu pitch"],
             ["Bộ đo", str(tc.get("test_estimators", 0)), "Cổng chuyển động, nhắm mắt, PERCLOS, ngáp, tư thế, tay–mặt, ngân sách chú ý"],
             ["Quyết định", str(tc.get("test_engine", 0)), "Kịch bản đầu cuối: mức 4 sau đúng 3 giây, chớp mắt, kính râm, xe dừng, mất mặt"],
             ["Golden trace", str(tc.get("test_golden", 0)), "Phát lại kịch bản và so sánh sự kiện"],
             ["Cảm biến", str(tc.get("test_perception", 0)), "Ảnh thật qua MediaPipe: EAR hợp lý, mắt nhắm vẫn quan sát được, kính tối thì không"],
             ["Gateway", str(tc["cloud"]), "Định dạng ingest, ẩn danh hóa, loại trùng, hàng đợi khi mất mạng"]],
            [2000, 1100, 5688], ["left", "center", "left"])

    B.h3("Thời lượng nhắm mắt và mức cảnh báo")
    B.p(f"Thí nghiệm dùng hai ảnh thật đi qua MediaPipe: ảnh mắt mở (EAR {vn(cl['ear_open'], 3)}) và cùng ảnh với vùng mắt phủ màu da (EAR {vn(cl['ear_closed'], 3)}, "
        f"tỉ lệ {vn(cl['ear_closed'] / cl['ear_open'], 2)}). Từ hai bộ số đo thật này dựng chuỗi theo thời gian ở 15 khung/giây cho nhiều thời lượng nhắm, rồi chạy bộ quyết định. "
        "Đây là thí nghiệm tổng hợp trên một người, nó kiểm tra logic ngưỡng và độ trễ chứ không phải độ chính xác ngoài đời ({tbl:closure}).")
    rows = []
    for r in cl["rows"]:
        f = r["first_s"]
        g = lambda L: (vn(f[str(L)], 2) + " s") if str(L) in f else "–"
        rows.append([vn(r["closed_s"], 1), str(r["max_level"]), g(1), g(2), g(3), g(4)])
    B.table("closure", "Mức cảnh báo theo thời lượng nhắm mắt (xe chạy 50 km/h)",
            ["Nhắm mắt (s)", "Mức cao nhất", "Đạt mức 1", "Đạt mức 2", "Đạt mức 3", "Đạt mức 4"], rows, [1500, 1400, 1470, 1470, 1470, 1478])
    B.p("Kết quả khớp thiết kế: mức 4 đạt đúng lúc 3,00 giây, các mức thấp hơn đạt ở 0,5; 1,0 và 2,0 giây ({fig:closure}). Có hai hệ quả của dung sai 0,2 giây "
        "cần ghi nhận: nhắm khoảng 2,9 giây vẫn chạm mức 4 và nhắm 0,4 giây đã chạm mức 1. {fig:signals} là chuỗi tín hiệu của video thật gồm 14 giây mắt mở rồi 4 giây mắt nhắm: "
        "EAR tụt xuống dưới ngưỡng, bộ đếm tăng đều và mức cảnh báo leo từng bậc.")
    B.fig("closure", FIG / "closure.png", "Mức đạt được và độ trễ cảnh báo theo thời lượng nhắm mắt", 14.5)
    B.fig("signals", FIG / "signals.png", "EAR, thời gian nhắm liên tục và mức cảnh báo trên video thử", 14.5)
    rb = {r["closed_s"]: r for r in cl["robust"]}
    B.p(f"Độ bền: thêm nhiễu Gauss σ = 0,02 vào EAR và làm mất mặt ngẫu nhiên 3% số khung, chạy 20 hạt giống cho mỗi thời lượng. Nhắm 0,3 giây: mức cao nhất trung bình "
        f"{vn(rb[0.3]['mean_max_level'], 1)} (không báo nhầm). Nhắm 1,0 giây: đạt mức 2 trong {rb[1.0]['runs']}/{rb[1.0]['runs']} lần. Nhắm 3,5 giây: đạt mức 4 trong "
        f"{rb[3.5]['level4_runs']}/{rb[3.5]['runs']} lần. Xe dừng và nhắm mắt 10 giây: mức cao nhất {cl['stopped']['max_level']}, không có sự kiện nào.")
    sc = {(r["speed"], r["closed_s"]): r for r in cl["scaling"]}
    B.p("Hệ số tốc độ là một thí nghiệm tùy chọn, mặc định tắt: ngưỡng thời gian co lại khi xe chạy nhanh vì cùng một giây nhắm mắt xe đi xa hơn. Ở 50 km/h kết quả giống hệt "
        f"khi tắt; ở 100 km/h, nhắm 1,5 giây chỉ đạt mức {sc[(100.0, 1.5)]['off']['max_level']} khi tắt nhưng đạt mức 4 sau {vn(sc[(100.0, 1.5)]['on']['t_l4'], 2)} giây khi bật.")

    B.h3("Ngân sách chú ý")
    B.p("{fig:budget} so sánh hai trường hợp. Bên trái, nhìn lệch liên tục làm ngân sách cạn đúng sau 6 giây. Bên phải, tài xế nhắn tin rồi liếc đường 0,3 giây sau mỗi 2 giây: "
        "ngân sách chỉ hồi một phần nên vẫn cạn dần, trong khi cách đặt lại bộ đếm mỗi lần liếc đường sẽ không bao giờ cảnh báo. Bài kiểm thử tương ứng cũng xác nhận liếc gương "
        "dưới 1 giây không gây cảnh báo.")
    B.fig("budget", FIG / "budget.png", "Ngân sách chú ý khi nhìn lệch liên tục và khi nhắn tin xen kẽ liếc đường", 14.5)

    B.h3("Đánh giá luật tay–đầu trên State Farm")
    B.p("Luật được đánh giá trên ảnh nhìn nghiêng bằng mô hình tư thế cơ thể: khoảng cách từ tâm bàn tay (trung bình cổ tay, ngón trỏ, ngón út, ngón cái) đến tai quay về camera và đến miệng, "
        "chia cho khoảng cách mũi–tai. Ngưỡng k chọn trên tập val để F1 lớn nhất, sau đó giữ nguyên và báo cáo trên tập test (khác tài xế). Lớp dương của luật tai là c2 và c4 (gọi điện); "
        "của luật miệng là c6 (uống nước); các lớp còn lại là âm.")
    B.table("rules", "Kết quả hai luật hình học trên State Farm",
            ["Luật", "k*", "Val P / R / F1", "Test P / R / F1", "AUC val / test"],
            [["Gọi điện (d tay–tai)", vn(ph["best_k"], 2), f"{vn(ph['val_best']['precision'], 2)} / {vn(ph['val_best']['recall'], 2)} / {vn(ph['val_best']['f1'], 2)}",
              f"{vn(ph['test_at_best']['precision'], 2)} / {vn(ph['test_at_best']['recall'], 2)} / {vn(ph['test_at_best']['f1'], 2)}",
              f"{vn(ph['auc_val'], 2)} / {vn(ph['auc_test'], 2)}"],
             ["Uống nước (d tay–miệng)", vn(dr["best_k"], 2), f"{vn(dr['val_best']['precision'], 2)} / {vn(dr['val_best']['recall'], 2)} / {vn(dr['val_best']['f1'], 2)}",
              f"{vn(dr['test_at_best']['precision'], 2)} / {vn(dr['test_at_best']['recall'], 2)} / {vn(dr['test_at_best']['f1'], 2)}",
              f"{vn(dr['auc_val'], 2)} / {vn(dr['auc_test'], 2)}"]],
            [2400, 700, 1900, 1900, 1888])
    B.p(f"Kết quả khiêm tốn: F1 trên test là {vn(ph['test_at_best']['f1'], 2)} cho luật gọi điện và {vn(dr['test_at_best']['f1'], 2)} cho luật uống nước, thấp hơn rõ so với val vì tập test có tài xế khác. "
        "{fig:curves} cho thấy ngưỡng tốt nhất nằm ở giữa dải quét chứ không ở mép. Hai nguyên nhân chính được quan sát: tay trái gọi điện (c4) nằm phía tai xa camera nên bị đầu che; "
        "và khoảng cách mũi–tai chỉ vào khoảng 22 đến 41 điểm ảnh (trung vị theo lớp) nên đơn vị chuẩn hoá nhiễu.")
    B.fig("curves", FIG / "sf_curves.png", "Precision, recall và F1 theo ngưỡng k trên tập val", 14.5)
    B.p(f"Luật có giá trị hơn khi coi là bộ phát hiện \"tay gần đầu\" chung ({{fig:flagged}}): lái xe an toàn c0 chỉ bị gắn cờ {pct(near['c0']['flagged'], near['c0']['n'])} "
        f"(ngang mức của c3 và c9, các lớp không đưa tay lên đầu), trong khi các lớp tay lên đầu bị gắn cờ nhiều hơn rõ rệt: c4 {pct(near['c4']['flagged'], near['c4']['n'])}, c8 {pct(near['c8']['flagged'], near['c8']['n'])}, "
        f"c2 {pct(near['c2']['flagged'], near['c2']['n'])}, c6 {pct(near['c6']['flagged'], near['c6']['n'])}. Tuy nhiên luật hình học không phân biệt được gọi điện, uống nước và chải tóc "
        "(đều là tay lên đầu), và hoàn toàn không phát hiện nhắn tin (c1, c3 gắn cờ dưới 5%), vì nhắn tin không đưa tay lên mặt.")
    B.fig("flagged", FIG / "sf_flagged.png", "Tỉ lệ ảnh bị gắn cờ theo từng lớp trên tập test", 14.5)
    B.fig("samples", FIG / "sf_samples.png", "Mẫu kết quả: tai (vuông xanh), miệng (tam giác hồng), bàn tay (tròn vàng) và quyết định của luật", 14.5)
    B.p("Để so sánh: báo cáo học sâu trước đây trên cùng cách chia tài xế đạt macro-F1 khoảng 0,82 cho bài toán sáu nhóm hành vi bằng EfficientNet-Lite0. Hai con số không so trực tiếp được "
        "vì bài toán khác nhau, nhưng cho thấy luật hình học đơn giản kém hẳn một bộ phân loại học trên đúng dữ liệu này. Đổi lại luật không cần dữ liệu huấn luyện, giải thích được, "
        "và dùng được ở camera đặt khác góc nếu chỉ chỉnh ngưỡng; còn bộ phân loại huấn luyện trên State Farm sẽ mất giá trị khi đổi góc camera.")

    B.h3("Hiệu năng")
    b = bench
    B.p(f"Đo trên CPU {b['machine']['cpu']}, Python {b['machine']['python']}, MediaPipe {b['machine']['mediapipe']}, khung hình {b['frame_size'][0]}×{b['frame_size'][1]}, "
        f"{b['frames']} khung (bỏ 10 khung khởi động). Tầng cảm biến (mặt và tay) mất trung bình {vn(b['sensor_ms']['mean'], 1)} ms mỗi khung (p95 {vn(b['sensor_ms']['p95'], 1)} ms); "
        f"tầng quyết định chỉ {vn(b['engine_only_ms'], 2)} ms. Toàn đường ống đạt khoảng {vn(b['pipeline_fps'], 0)} khung/giây ({{fig:bench}}). Con số này chỉ cho biết phần "
        "quyết định không phải là điểm nghẽn; hiệu năng trên chip K230 chưa được đo.")
    B.fig("bench", FIG / "bench.png", "Thời gian xử lý mỗi khung trên CPU", 12.5)
    B.table("bench", "Hiệu năng đo trên CPU máy phát triển", ["Hạng mục", "Giá trị"],
            [["Cảm biến mặt + tay, trung bình mỗi khung", f"{vn(b['sensor_ms']['mean'], 1)} ms"],
             ["Cảm biến, p95", f"{vn(b['sensor_ms']['p95'], 1)} ms"],
             ["Thuật toán quyết định, mỗi khung", f"{vn(b['engine_only_ms'], 2)} ms"],
             ["Toàn đường ống", f"khoảng {vn(b['pipeline_fps'], 0)} khung/giây"],
             ["Gateway đổi GPS sang định dạng ingest", f"khoảng {thousands(int(round(b['gateway_points_per_s'], -3)))} điểm/giây"]],
            [5400, 3388], ["left", "center"])

    B.h2("Đám mây và tích hợp Traffic-SM")
    B.p("Device-gateway nhận GPS dưới dạng gọn (thời điểm, vĩ độ, kinh độ, tốc độ) và đổi sang định dạng rất chặt của cổng ingest Traffic-SM: đủ mười một trường số, `time` theo UTC+7, "
        "`t_timestamp` có phút trùng với `time`, `vehicle_type` chỉ nhận car hoặc bike. Bản chuyển đổi được kiểm tra bằng cách chạy lại trên 200 dòng thật của fake_gps.csv: "
        "với cùng một thời điểm, nó tái tạo đúng `time` và `t_timestamp` do chính Traffic-SM sinh ra ({fig:code_gw}).")
    B.code("code_gw", "Mã nguồn đổi một điểm GPS của thiết bị sang bản ghi ingest, với driver_id là mã chuyến", src(gateway.to_ingest_payload, strip_doc=True, max_lines=46))
    B.p("Gateway bỏ mã thiết bị trước khi chuyển tiếp: Traffic-SM và bảng sự kiện chỉ thấy mã chuyến đi; ánh xạ chuyến–thiết bị nằm riêng trong một kho SQLite. Sự kiện được loại trùng theo "
        "mã sự kiện nên gửi lại không nhân đôi. Khi mất mạng, thiết bị ghi vào tệp outbox và gửi bù ở lần chạy sau.")
    B.table("e2e", "Kết quả chạy thử đầu cuối: video, thiết bị, gateway, ingest giả lập",
            ["Hạng mục", "Kết quả"],
            [["Điểm GPS gửi qua gateway", "49 điểm, 3 chuyến, được chấp nhận 49, từ chối 0"],
             ["Sự kiện lưu", "6 sự kiện, không có mã thiết bị, 0 trùng"],
             ["Gửi bù từ outbox sau khi gateway chưa chạy", "7 bản ghi gửi bù thành công, outbox về 0"],
             ["Mã tài xế phía ingest", "chính là mã chuyến đi (3 mã khác nhau)"],
             ["Kiểm tra xem Traffic-SM thật có nhận không", "chưa chạy (Docker không chạy, thiếu dữ liệu OSM)"]],
            [3800, 4988], ["left", "left"])
    B.p("Cần nói rõ: phía nhận là một máy chủ giả lập tái hiện đúng quy tắc kiểm tra `gps.Canonicalize` đọc từ mã nguồn Go của Traffic-SM, không phải Traffic-SM thật. "
        "Phần còn lại của luồng (map matching, Spark, ClickHouse, Grafana) giữ nguyên và chưa được chạy lại trong đề tài này.")

    B.h2("Sản phẩm")
    B.p("Ứng dụng demo chạy trên máy tính với webcam hoặc video ({fig:osd}). Cửa sổ hiển thị mức cảnh báo bằng thanh màu, các số đo (EAR, PERCLOS, tư thế, ngân sách chú ý), "
        "trạng thái chuyển động và cờ chất lượng. Để giữ nguyên tắc video không rời thiết bị, ảnh minh hoạ trong báo cáo dùng chế độ riêng tư: chỉ vẽ các điểm mốc trên nền đen. Còi dùng "
        "winsound trên Windows, mỗi mức một mẫu âm riêng. Phím tắt: `w`/`s` đổi tốc độ giả lập, `space` dừng hoặc chạy, `c` hiệu chỉnh nhanh, `m` tắt còi, `q` thoát.")
    B.fig("osd", FIG / "osd_levels.png", "Giao diện demo ở chế độ riêng tư (chỉ điểm mốc) tại mức 0, mức 2 và mức 4", 14.5)
    B.p("Lệnh chạy: `python -m drivefocus.demo --quick` cho webcam; `--source clip.mp4 --no-window` cho video; `--route-csv` và `--gateway` để nối với Traffic-SM qua gateway; "
        "`python -m drivefocus.replay trace.jsonl` để phát lại golden trace.")

    # ======================================================================= KẾT LUẬN
    B.h1("KẾT LUẬN", numbered=False)
    B.p("Đồ án 3 đã xây dựng hệ thống giám sát tài xế DriveFocus với các kết quả chính sau:")
    B.bullets([
        "Thuật toán quyết định tự thiết kế, không dùng mô hình phân loại hành vi: EAR chuẩn hoá theo người, PERCLOS theo thời gian có loại khoảng không biết, tư thế đầu từ ma trận biến đổi, "
        "luật tay–đầu chuẩn hoá theo độ dài, ngân sách chú ý, cổng chuyển động có hysteresis và máy trạng thái bốn mức.",
        "Nhắm mắt liên tục 3 giây là báo động mức 4: đo được đạt đúng lúc 3,00 giây, không báo nhầm với chớp mắt, bền với nhiễu và mất mặt ngẫu nhiên, và không báo khi xe dừng.",
        f"{t_edge + tc['cloud']} bài kiểm thử tự động đạt, cùng cơ chế golden trace để kiểm bản cài đặt trên chip khác.",
        f"Phần quyết định chỉ mất khoảng {vn(b['engine_only_ms'], 2)} ms mỗi khung; toàn đường ống trên CPU máy tính đạt khoảng {vn(b['pipeline_fps'], 0)} khung/giây.",
        "Đường ống đám mây tối thiểu: ẩn danh hóa, chuyển GPS sang định dạng của Traffic-SM (đối chiếu 200 dòng thật), loại trùng sự kiện, gửi bù khi mất mạng.",
        "Đánh giá trung thực trên State Farm: cảm biến khuôn mặt chỉ tìm thấy mặt ở khoảng 28% ảnh vì góc nhìn nghiêng, và luật tay–đầu đạt F1 0,34 (gọi điện) và 0,19 (uống nước)."])
    B.p("Hạn chế cần nêu rõ:")
    B.bullets([
        "Chưa thử với webcam thật và chưa thử trên người lái thật. Thí nghiệm nhắm mắt dùng ảnh một người với vùng mắt được phủ màu da; toàn bộ ngưỡng là giá trị khởi điểm.",
        "Chưa có dữ liệu mặt nhìn thẳng có nhãn (NTHU-DDD, YawDD, DMD) nên chưa đánh giá được EAR, PERCLOS và ngáp ở quy mô lớn, chưa đo được tỉ lệ báo nhầm trên giờ lái bình thường.",
        "Luật tay–đầu yếu: không phân biệt được các hành vi đưa tay lên đầu và không phát hiện nhắn tin; ngưỡng cần chỉnh theo camera thật.",
        "Chưa chạy trên chip K230; hiệu năng và độ chính xác trên chip còn là ước tính.",
        "Chưa chạy với Traffic-SM thật, mới thử với máy chủ giả lập; chưa có bảo mật (mã hoá, xác thực thiết bị)."])
    B.p("Hướng phát triển: tải và đánh giá trên NTHU-DDD, YawDD, DMD để chỉnh ngưỡng; thu video tự quay có đồng ý đúng góc lắp; chuyển tầng cảm biến sang mô hình trong SDK K230 và so golden trace; "
        "ghép với Traffic-SM thật để tạo bản đồ rủi ro theo đoạn đường và phản hồi ngữ cảnh đường về thiết bị; cuối cùng là bảo mật (mTLS, ACL, cập nhật có chữ ký).")

    # ======================================================================= TÀI LIỆU THAM KHẢO
    B.h1("TÀI LIỆU THAM KHẢO", numbered=False, style="Tiu")
    B.refs([
        "T. Soukupová, J. Čech, “Real-Time Eye Blink Detection using Facial Landmarks”, Computer Vision Winter Workshop, 2016.",
        "D. F. Dinges, R. Grace, “PERCLOS: A Valid Psychophysiological Measure of Alertness as Assessed by Psychomotor Vigilance”, FHWA-MCRT-98-006, 1998.",
        "C. Lugaresi và cộng sự, “MediaPipe: A Framework for Building Perception Pipelines”, arXiv:1906.08172, 2019.",
        "Y. Kartynnik và cộng sự, “Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs”, CVPR Workshops, 2019.",
        "F. Zhang và cộng sự, “MediaPipe Hands: On-device Real-time Hand Tracking”, arXiv:2006.10214, 2020.",
        "V. Bazarevsky và cộng sự, “BlazePose: On-device Real-time Body Pose tracking”, arXiv:2006.10204, 2020.",
        "V. Lepetit, F. Moreno-Noguer, P. Fua, “EPnP: An Accurate O(n) Solution to the PnP Problem”, International Journal of Computer Vision, 2009.",
        "G. Bradski, “The OpenCV Library”, Dr. Dobb’s Journal of Software Tools, 2000.",
        "J. Kreps, N. Narkhede, J. Rao, “Kafka: a Distributed Messaging System for Log Processing”, NetDB, 2011.",
        "M. Zaharia và cộng sự, “Apache Spark: A Unified Engine for Big Data Processing”, Communications of the ACM, 2016.",
        "State Farm Distracted Driver Detection, Kaggle, 2016: https://www.kaggle.com/c/state-farm-distracted-driver-detection",
        "Dự án openpilot (comma.ai), mô-đun giám sát tài xế: https://github.com/commaai/openpilot",
        "Dự án driver-state-detection (e-candeloro): https://github.com/e-candeloro/driver-state-detection",
        "Kendryte K230 SDK và nncase: https://github.com/kendryte/k230_sdk, https://github.com/kendryte/nncase",
        "Tài liệu MediaPipe: https://ai.google.dev/edge/mediapipe",
        "Báo cáo bài tập lớn môn Thị giác máy tính: Nhận diện hành vi tài xế mất tập trung (dds-edge), 2026.",
        "Traffic-SM: hệ thống phân tích tắc nghẽn giao thông từ GPS (Kafka, Spark, ClickHouse, GraphHopper), 2026."])
