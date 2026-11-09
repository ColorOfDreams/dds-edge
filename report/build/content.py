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
def _find_dds(root):
    """dds-edge nằm cạnh drivefocus/ (bản làm việc) hoặc chính là thư mục cha (nhánh drive-focus của repo dds-edge)."""
    for cand in (root.parent / "dds-edge", root.parent):
        if (cand / "src" / "dds_edge").is_dir():
            return cand
    return root.parent / "dds-edge"


DDS_FIGS = _find_dds(ROOT) / "reports" / "cv" / "figs"
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
    b = bench
    t_edge = sum(v for k, v in tc.items() if k != "cloud")

    from drivefocus import estimators, geometry, motion
    from drivefocus_cloud import gateway

    # ======================================================================= CHƯƠNG 1
    B.h1("TỔNG QUAN BÀI TOÁN")
    B.h2("Bài toán")
    B.p("Buồn ngủ và mất tập trung khi lái xe là hai nguyên nhân thường gặp trong các vụ tai nạn giao thông. Nếu đặt một camera trong xe hướng "
        "về phía tài xế thì có thể dùng thị giác máy tính để nhận ra sớm các dấu hiệu này và nhắc tài xế ngay lúc đó. Đề tài DriveFocus xây dựng "
        "một hệ thống như vậy, gồm hai phần. Phần đặt trên xe (DF-Edge) xử lý ảnh và tự đưa ra cảnh báo, không cần kết nối mạng. Phần máy chủ "
        "(DF-Cloud) nhận các sự kiện đã ẩn danh và chuyển dữ liệu GPS sang hệ thống phân tích giao thông Traffic-SM mà nhóm đã làm trước đó.")
    B.p("Đầu vào của hệ thống là ảnh từ camera trong cabin và tốc độ xe lấy từ GPS. Đầu ra gồm:")
    B.bullets(["Mức cảnh báo từ 0 đến 4, cập nhật theo từng khung hình. Mức 4 là báo động, dùng cho trường hợp nguy hiểm nhất như nhắm mắt liên tục từ 3 giây trở lên.",
               "Các sự kiện: loại sự kiện (nhắm mắt, buồn ngủ, nhìn lệch, dùng điện thoại...), mức cao nhất, thời lượng và quãng đường xe đã đi trong lúc xảy ra sự kiện.",
               "Hệ thống chỉ cảnh báo khi xe đang chạy. Khi xe dừng đèn đỏ thì không cảnh báo."])
    B.p("Trong đề tài này, em không dùng mạng nơ-ron để phân loại trực tiếp hành vi tài xế. Các mô hình có sẵn của MediaPipe chỉ được dùng để tìm "
        "khuôn mặt, các điểm mốc trên mặt, bàn tay và tư thế cơ thể. Từ các điểm này em tính ra độ mở mắt, độ mở miệng, góc quay đầu và vị trí tay so với đầu, "
        "sau đó dùng các quy tắc có ngưỡng và thời lượng để quyết định mức cảnh báo. Em chọn cách này vì bộ dữ liệu State Farm không có nhãn nhắm mắt "
        "hay ngáp, vì các quy tắc dễ giải thích và dễ chỉnh ngưỡng, và vì phần quyết định chạy rất nhanh (khoảng 0,13 ms cho mỗi khung hình), phù hợp "
        "để đưa lên thiết bị nhúng như chip Kendryte K230.")
    B.p("Một số khó khăn của bài toán:")
    B.bullets(["Hệ thống phải hạn chế báo nhầm. Chớp mắt, liếc gương, đeo kính râm hay dừng đèn đỏ đều không phải tình huống nguy hiểm.",
               "Khi không nhìn rõ mắt (kính râm, thiếu sáng, quay mặt đi) thì không được coi là tài xế đang nhắm mắt.",
               "Dữ liệu công khai khác với điều kiện thực tế: ảnh State Farm được chụp từ phía ghế phụ nên tài xế bị nhìn nghiêng, trong khi các thuật toán dựa trên mắt cần ảnh mặt nhìn thẳng.",
               "Thiết bị đặt trên xe có bộ nhớ và năng lực tính toán hạn chế."])

    B.h2("Trình bày dữ liệu bài toán")
    B.p("Đề tài sử dụng một số nguồn dữ liệu khác nhau, mỗi nguồn dùng cho một phần của hệ thống ({tbl:sources}).")
    B.table("sources", "Các nguồn dữ liệu và vai trò", ["Nguồn", "Nội dung", "Quy mô", "Vai trò trong đề tài"],
            [["State Farm Distracted Driver", "Ảnh 640×480, 10 lớp hành vi, camera đặt phía ghế phụ, ban ngày", "22.424 ảnh, 26 tài xế",
              "Đánh giá luật bàn tay gần đầu; đo tỉ lệ phát hiện của các mô hình"],
             ["Ảnh chân dung mẫu của MediaPipe", "Một ảnh mặt nhìn thẳng, mắt mở", "1 ảnh",
              "Kiểm thử phần cảm biến; giả lập mắt nhắm bằng cách phủ màu da lên vùng mắt"],
             ["fake_gps.csv của Traffic-SM", "GPS mô phỏng trên đường thật ở TP.HCM, gồm ô tô và xe máy", "36.941 dòng, 30 tài xế",
              "Cung cấp tốc độ và lộ trình khi chạy thử với Traffic-SM"],
             ["NTHU-DDD, YawDD, DMD", "Video buồn ngủ, ngáp, mất tập trung", "Chưa tải",
              "Dự kiến dùng để chỉnh ngưỡng; phải đăng ký mới tải được"]],
            [2000, 2700, 1800, 2288], ["left", "left", "center", "left"])
    B.p("Bộ State Farm Distracted Driver Detection là dữ liệu của một cuộc thi trên Kaggle năm 2016, gồm ảnh của 26 tài xế thực hiện mười hành vi "
        "từ c0 đến c9. Em dùng lại cách chia dữ liệu theo tài xế của bài tập lớn trước (cùng tệp manifest) để mỗi tài xế chỉ thuộc một tập: "
        f"18 tài xế cho tập huấn luyện, 4 tài xế cho tập kiểm định (val, {thousands(nval)} ảnh) và 4 tài xế cho tập kiểm tra (test, {thousands(ntest)} ảnh). "
        "Do đề tài không huấn luyện mô hình nên tập huấn luyện không được dùng. Tập val dùng để chọn ngưỡng, tập test dùng để báo cáo kết quả.")
    B.p("Mười lớp hành vi của bộ dữ liệu:")
    B.bullets(["c0: lái xe an toàn.", "c1, c3: nhắn tin bằng tay phải, bằng tay trái; c2, c4: gọi điện bằng tay phải, bằng tay trái.",
               "c5: chỉnh radio; c6: uống nước.", "c7: với ra phía sau; c8: chải tóc hoặc trang điểm; c9: nói chuyện với người ngồi bên cạnh."])
    B.p("Dữ liệu GPS lấy từ tệp fake_gps.csv do bộ mô phỏng của Traffic-SM sinh ra. Mỗi dòng gồm mã tài xế, thời điểm, vĩ độ, kinh độ, hướng đi, tốc độ "
        "(m/s), độ chính xác và loại phương tiện. Em lấy lộ trình của một tài xế ô tô làm nguồn tốc độ cho thiết bị giả lập, sau đó gửi ngược dữ liệu "
        "này vào cổng nhận dữ liệu của Traffic-SM để kiểm tra luồng xử lý.")

    B.h2("Tiền xử lý dữ liệu")
    B.bullets([
        "Ảnh được đọc bằng OpenCV ở dạng BGR và chuyển sang RGB trước khi đưa vào MediaPipe. Các khoảng cách đều tính theo toạ độ điểm ảnh, "
        "vì toạ độ chuẩn hoá (0 đến 1) làm sai tỉ lệ khi chiều rộng và chiều cao ảnh khác nhau.",
        "Các bộ đếm thời gian dùng thời điểm thực của khung hình thay vì đếm số khung, nên kết quả không bị ảnh hưởng khi tốc độ khung hình thay đổi.",
        "Mỗi số đo có ba trạng thái: mở, nhắm hoặc không xác định (khi mất khuôn mặt hoặc vùng mắt quá tối). Trạng thái không xác định không làm "
        "tăng hay giảm bộ đếm và không được tính vào PERCLOS.",
        "Hiệu chỉnh theo từng người: độ mở mắt bình thường lấy bằng trung vị EAR trong khoảng đầu chuyến đi; tư thế đầu khi nhìn thẳng lấy bằng "
        "trung vị các góc khi xe chạy từ 30 km/h trở lên.",
        "Dữ liệu GPS được đổi sang định dạng của Traffic-SM: trường time theo múi giờ UTC+7, trường t_timestamp có dạng phút:giây và mã tài xế "
        "được thay bằng mã chuyến đi.",
        "Với State Farm, em dùng ảnh gốc 640×480 của tập val và tập test, không thu nhỏ, để các mô hình có đủ độ phân giải."])

    B.h2("Trực quan dữ liệu")
    B.p("{fig:classes} là mười lớp hành vi của cùng một tài xế. Do camera đặt phía ghế phụ nên tài xế luôn bị nhìn nghiêng, chỉ thấy được một bên mặt "
        "và một bên tai, bàn tay phía xa thường bị che khuất.")
    B.fig("classes", DDS_FIGS / "classes.jpg", "Mười lớp hành vi c0 đến c9 của cùng một tài xế trong bộ State Farm", 14.5)
    B.p(f"Em chạy hai mô hình của MediaPipe trên {thousands(ntest)} ảnh của tập test và thống kê tỉ lệ phát hiện theo từng lớp ({{fig:detection}}). "
        f"Face Landmarker chỉ tìm thấy khuôn mặt trong {thousands(DT['face'])} ảnh ({pct(DT['face'], DT['n'])}). Lớp c9 có tỉ lệ cao nhất "
        f"({pct(D['c9']['face'], D['c9']['n'])}) vì tài xế quay mặt về phía camera khi nói chuyện, còn lớp c0 chỉ đạt {pct(D['c0']['face'], D['c0']['n'])}. "
        f"Trong các ảnh tìm thấy mặt, chỉ có {DT['eyes']} ảnh nhìn rõ mắt để tính EAR. Pose Landmarker (mô hình tư thế cơ thể) cho kết quả tốt hơn, "
        f"tìm được tư thế trong {pct(DT['pose'], DT['n'])} số ảnh.")
    B.fig("detection", FIG / "sf_detection.png", "Tỉ lệ ảnh phát hiện được theo từng lớp trên tập test của State Farm", 14.5)
    B.p("Như vậy không thể đánh giá các thuật toán dựa trên mắt (EAR, PERCLOS) bằng bộ dữ liệu này. Em chỉ dùng State Farm để đánh giá luật bàn tay gần đầu, "
        "với mô hình tư thế cơ thể thay cho mô hình khuôn mặt.")

    # ======================================================================= CHƯƠNG 2
    B.h1("CƠ SỞ LÝ THUYẾT")
    B.h2("Thị giác máy tính và giám sát tài xế")
    B.h3("Giới thiệu về thị giác máy tính")
    B.p("Thị giác máy tính là lĩnh vực nghiên cứu cách để máy tính thu nhận, xử lý và hiểu nội dung của ảnh và video. Các bài toán thường gặp gồm phân loại ảnh, "
        "phát hiện đối tượng, ước lượng tư thế và theo dõi chuyển động. Trong bài toán giám sát tài xế, các kỹ thuật này được dùng để biết tài xế đang nhìn về đâu, "
        "mắt đang mở hay nhắm và tay đang làm gì.")
    B.h3("Các dấu hiệu buồn ngủ và mất tập trung")
    B.bullets(["Nhắm mắt lâu và tỉ lệ thời gian nhắm mắt cao (PERCLOS) là các dấu hiệu buồn ngủ hay được sử dụng.",
               "Ngáp và gục đầu là dấu hiệu phụ, thường xuất hiện khi mệt.",
               "Đầu hoặc mắt hướng ra khỏi mặt đường trong thời gian dài là dấu hiệu mất tập trung.",
               "Tay đưa lên gần tai hoặc miệng có thể là gọi điện, uống nước, ăn uống hoặc hút thuốc; cúi đầu nhìn xuống lâu có thể là nhắn tin."])
    B.p("Các dấu hiệu trên chỉ có ý nghĩa khi kéo dài đủ lâu. Một lần chớp mắt thường ngắn hơn nửa giây, một lần liếc gương thường ngắn hơn một giây. "
        "Vì vậy các quy tắc trong đề tài đều có thêm điều kiện về thời lượng.")
    B.h3("Trí tuệ nhân tạo trên thiết bị biên và chip K230")
    B.p("Khi xử lý ngay trên thiết bị đặt trong xe, cảnh báo không phải chờ đường truyền, video quay khuôn mặt tài xế không phải gửi đi nơi khác và hệ thống vẫn "
        "chạy khi mất sóng. Chip Kendryte K230 có hai lõi RISC-V (một lõi 1,6 GHz có tập lệnh vector chạy hệ điều hành thời gian thực, một lõi 800 MHz chạy Linux), "
        "bộ tăng tốc suy luận KPU hỗ trợ INT8 và INT16 (theo nhà sản xuất là khoảng 6 TOPS), ba cổng camera MIPI CSI và bộ xử lý ảnh hỗ trợ cảm biến RGB-IR. "
        "Bộ SDK của K230 có sẵn các ví dụ nhận diện khuôn mặt, điểm mốc, tư thế đầu, hướng nhìn và phát hiện bàn tay, có thể dùng thay MediaPipe khi chuyển "
        "từ máy tính sang chip. Trong phạm vi đồ án này em chưa chạy được trên chip K230, các số đo trong báo cáo đều đo trên CPU máy tính.")

    B.h2("OpenCV và MediaPipe")
    B.h3("Giới thiệu về OpenCV")
    B.p("OpenCV là thư viện mã nguồn mở cho thị giác máy tính, hỗ trợ đọc ghi ảnh và video, xử lý ảnh, vẽ lên ảnh và giải các bài toán hình học như PnP. "
        "Trong đề tài, OpenCV được dùng để đọc camera và video, vẽ thông tin lên khung hình và tính tư thế đầu.")
    B.h3("MediaPipe")
    B.p("MediaPipe là bộ công cụ mã nguồn mở của Google dành cho các ứng dụng thị giác chạy thời gian thực. Đề tài sử dụng ba mô hình thông qua Tasks API:")
    B.bullets(["Face Landmarker: tìm khuôn mặt và 478 điểm mốc (có cả mống mắt), đồng thời trả về ma trận biến đổi 4×4 mô tả tư thế đầu.",
               "Hand Landmarker: trả về 21 điểm mốc cho mỗi bàn tay.",
               "Pose Landmarker: trả về 33 điểm mốc trên cơ thể như mũi, tai, miệng, vai và cổ tay. Mô hình này được dùng cho ảnh chụp nghiêng khi Face Landmarker không tìm thấy mặt."])
    B.p("Các mô hình được dùng nguyên bản, không huấn luyện lại. Phiên bản MediaPipe trong đề tài là 1.2.2.")
    B.h3("Cài đặt")
    B.bullets(["Cài thư viện bằng pip: pip install mediapipe opencv-python numpy pyyaml.", "Tải các tệp mô hình (.task) bằng script scripts/download_models.py.",
               "Phiên bản Python sử dụng là 3.11."])

    B.h2("Các đại lượng hình học trên khuôn mặt")
    B.h3("Tỉ số mở mắt EAR")
    B.p("Tỉ số mở mắt EAR (Eye Aspect Ratio) do Soukupová và Čech đề xuất, được tính từ sáu điểm quanh mắt ({fig:ear}):")
    B.p("EAR = (‖p2 − p6‖ + ‖p3 − p5‖) / (2 · ‖p1 − p4‖)")
    B.p("Trong đó p1 và p4 là hai khoé mắt, hai cặp (p2, p6) và (p3, p5) nằm trên mi trên và mi dưới. Khi mắt mở EAR thường vào khoảng 0,2 đến 0,35, "
        "khi mắt nhắm EAR gần bằng 0. Vì độ mở mắt khác nhau giữa từng người và phụ thuộc vào góc camera, em chia EAR cho EAR lúc mắt mở của chính tài xế "
        "đó và coi là mắt nhắm khi giá trị này nhỏ hơn 0,5.")
    B.fig("ear", FIG / "ear.png", "Sáu điểm quanh mắt và công thức EAR", 12.0)
    B.h3("PERCLOS")
    B.p("PERCLOS là tỉ lệ thời gian mắt nhắm trong một khoảng thời gian, thường là một phút. Em tính PERCLOS theo thời gian thực (cộng độ dài các khoảng mắt nhắm "
        "thay vì đếm số khung), bỏ các khoảng không xác định ra khỏi mẫu số và chỉ sử dụng kết quả khi cửa sổ đã đủ dài và phần quan sát được chiếm ít nhất 80%. "
        "Cách tính này em tham khảo từ dự án mã nguồn mở driver-state-detection.")
    B.h3("Tỉ số mở miệng MAR")
    B.p("MAR (Mouth Aspect Ratio) bằng khoảng cách giữa môi trên và môi dưới chia cho chiều rộng miệng. Một lần ngáp được tính khi MAR lớn hơn ngưỡng "
        "liên tục từ 1,5 giây trở lên. Số lần ngáp trong 10 phút được dùng làm dấu hiệu mệt mỏi.")
    B.h3("Tư thế đầu")
    B.p("Tư thế đầu được mô tả bằng ba góc: yaw (quay trái phải), pitch (cúi, ngửa) và roll (nghiêng). Em lấy ba góc này từ ma trận biến đổi 4×4 mà Face Landmarker "
        "tính được khi khớp toàn bộ 468 điểm với mô hình mặt chuẩn. Ngoài ra em cũng thử giải bài toán PnP (Perspective-n-Point) từ sáu điểm. Trên ảnh mẫu nhìn thẳng, "
        "ma trận của MediaPipe cho góc pitch khoảng 4 độ, còn cách PnP sáu điểm cho khoảng 18 độ do bị ảnh hưởng bởi hình dạng khuôn mặt của từng người. Sai lệch "
        "cố định có thể loại bỏ khi hiệu chỉnh tư thế nhìn thẳng, nhưng độ nhiễu thì không, nên em chọn dùng ma trận của MediaPipe. Trong đề tài, pitch dương nghĩa là cúi xuống.")

    B.h2("Luật bàn tay gần đầu")
    B.p("Khi gọi điện, uống nước, ăn hoặc hút thuốc, tài xế đều đưa tay lên gần đầu. Luật này đo khoảng cách từ tâm bàn tay đến tai và đến miệng, rồi chia cho kích thước đầu "
        "để kết quả không phụ thuộc vào khoảng cách từ người tới camera. Nếu khoảng cách nhỏ hơn ngưỡng k và kéo dài đủ lâu thì luật đánh dấu sự kiện. Ý tưởng này em "
        "tham khảo từ ví dụ dms_system trong SDK của K230 và có hai thay đổi. Thứ nhất, khoảng cách được chia cho một độ dài (chiều rộng mặt hoặc khoảng cách mũi - tai) "
        "thay vì diện tích khuôn mặt như trong ví dụ gốc, vì độ dài tỉ lệ với căn bậc hai của diện tích. Thứ hai, trường hợp bàn tay ở gần mắt hơn tai và miệng được bỏ qua "
        "để không nhầm với dụi mắt. Riêng việc nhắn tin không đưa tay lên mặt nên được phát hiện qua việc cúi đầu kéo dài.")

    B.h2("Ngân sách chú ý và máy trạng thái")
    B.p("Nếu bộ đếm thời gian nhìn lệch quay về 0 mỗi khi tài xế liếc lên đường, thì người vừa lái vừa nhắn tin và thỉnh thoảng nhìn lên sẽ không bao giờ bị cảnh báo. "
        "Dự án openpilot giải quyết vấn đề này bằng một đại lượng mức độ chú ý giảm dần khi tài xế mất tập trung và tăng dần khi tài xế chú ý trở lại. Em áp dụng ý tưởng "
        "tương tự: ngân sách A nằm trong khoảng từ 0 đến 1. Khi mất tập trung, A giảm với tốc độ w/T, trong đó T = 6 giây và w là trọng số theo nguyên nhân. Khi tài xế "
        "nhìn lại đường, A tăng với hệ số từ 1,25 đến 5 lần, tăng nhanh hơn khi A đang thấp. Mức cảnh báo được xác định theo các ngưỡng 0,75; 0,58 và 0,33, còn A bằng 0 "
        "ứng với mức 4. Với w = 1, các mức lần lượt đạt sau 1,5; 2,5; 4,0 và 6,0 giây mất tập trung liên tục.")
    B.p("Mức cảnh báo hiển thị cho tài xế được đưa qua một máy trạng thái: mức tăng ngay khi điều kiện xảy ra, nhưng chỉ giảm từng bậc sau khi điều kiện đã hết một "
        "khoảng thời gian, để cảnh báo không bị nhấp nháy.")

    B.h2("Hạ tầng dữ liệu của Traffic-SM")
    B.p("Traffic-SM nhận GPS của nhiều tài xế, khớp các điểm vào bản đồ đường thật bằng GraphHopper rồi tính mức tắc nghẽn. Dữ liệu đi qua Kafka theo các topic gps.raw, "
        "gps.traces và gps.matched. Spark Structured Streaming gom dữ liệu theo cửa sổ 10 giây (watermark 30 giây) cho từng đoạn đường, so sánh tốc độ trung vị với tốc độ "
        "chuẩn để gán mức FREE, SLOW hoặc CONGESTED. Kết quả được lưu trong ClickHouse và hiển thị bằng Grafana. Dữ liệu vào hệ thống qua cổng POST /v1/ingest, nhận một "
        "bản ghi hoặc một mảng tối đa 5.000 bản ghi. DriveFocus không sửa Traffic-SM: mỗi xe chỉ là thêm một nguồn GPS, với mã tài xế được thay bằng mã chuyến đi.")

    B.h2("Chỉ số đánh giá")
    B.bullets(["Precision, recall và F1 cho từng luật. Precision là tỉ lệ ảnh bị đánh dấu đúng trong số ảnh bị đánh dấu, recall là tỉ lệ ảnh cần đánh dấu đã được đánh dấu, "
               "F1 là trung bình điều hoà của hai chỉ số này.",
               "AUC: xác suất để một ảnh thuộc lớp dương có điểm cao hơn một ảnh thuộc lớp âm, không phụ thuộc vào ngưỡng.",
               "Độ trễ cảnh báo: thời gian từ lúc bắt đầu nhắm mắt đến lúc đạt từng mức.",
               "Thời gian xử lý mỗi khung hình và số khung hình mỗi giây trên CPU."])

    # ======================================================================= CHƯƠNG 3
    B.h1("NỘI DUNG THỰC HIỆN VÀ KẾT QUẢ")
    B.h2("Kiến trúc hệ thống")
    B.p("Hệ thống gồm ba khối ({fig:arch}). Trên xe, DF-Edge nhận ảnh từ camera và tốc độ từ GPS. Phần cảm biến tính các số đo hình học, phần quyết định đưa ra mức cảnh báo "
        "và lưu sự kiện vào hàng đợi. Sự kiện và GPS được gửi lên device-gateway. Gateway thay mã tài xế bằng mã chuyến đi, chuyển GPS sang Traffic-SM và lưu sự kiện vào "
        "ClickHouse. Video không được gửi ra khỏi thiết bị.")
    B.fig("arch", FIG / "arch.png", "Kiến trúc hệ thống DriveFocus", 14.5)
    B.p("{fig:fsm} là máy trạng thái của mức cảnh báo. Có 4 mức: nhắc nhẹ, cảnh báo, nguy hiểm và báo động. Với trường hợp nhắm mắt liên tục, các mức tương ứng với "
        "thời gian 0,5; 1; 2 và 3 giây.")
    B.fig("fsm", FIG / "fsm.png", "Máy trạng thái hiển thị mức cảnh báo", 14.0)

    core_lines = sum(len((ROOT / "edge" / "src" / "drivefocus" / f).read_text(encoding="utf-8").splitlines())
                     for f in ("config.py", "types.py", "geometry.py", "motion.py", "estimators.py", "engine.py"))
    core_lines = int(round(core_lines, -1))
    B.h2("Mã nguồn các bộ đo")
    B.p(f"Phần quyết định nằm trong gói drivefocus, khoảng {core_lines} dòng Python, chỉ cần numpy và pyyaml. OpenCV và MediaPipe chỉ dùng ở phần cảm biến. "
        "Tất cả các ngưỡng được đặt trong một tệp cấu hình YAML để dễ thay đổi.")
    B.h3("Tỉ số mở mắt")
    B.p("Hàm tính EAR cho một mắt nhận sáu điểm theo thứ tự: hai khoé mắt, cặp điểm thứ nhất và cặp điểm thứ hai ({fig:code_ear}). Nếu chiều rộng mắt bằng 0 thì hàm trả về None, "
        "tương ứng với trạng thái không xác định.")
    B.code("code_ear", "Mã nguồn tính EAR từ sáu điểm theo toạ độ điểm ảnh", src(geometry.eye_aspect_ratio, strip_doc=True))
    B.h3("Thời gian nhắm mắt liên tục")
    B.p("Mức 4 được quyết định dựa vào thời gian nhắm mắt liên tục ({fig:code_run}). Nếu có một vài khung hình mắt mở xen vào nhưng tổng cộng không quá 0,2 giây "
        "(thường do điểm mốc bị nhiễu) thì bộ đếm vẫn giữ nguyên. Khoảng không xác định ngắn cũng không làm thay đổi bộ đếm, nhưng nếu kéo dài quá 1 giây thì bộ đếm "
        "được đặt lại về 0.")
    B.code("code_run", "Mã nguồn cập nhật thời gian nhắm mắt liên tục", src(estimators.EyeEstimator._update_run))
    B.h3("Xác định xe đang chạy")
    B.p("Hệ thống chỉ cảnh báo khi xe đang chạy ({fig:code_gate}). Xe được coi là đang chạy khi tốc độ từ 10 km/h trở lên liên tục trong 3 giây, và được coi là dừng khi "
        "tốc độ dưới 3 km/h liên tục trong 5 giây. Hai ngưỡng khác nhau giúp trạng thái không bị bật tắt liên tục khi xe đi chậm trong lúc kẹt xe. Khi mất GPS, hệ thống "
        "giữ trạng thái cũ tối đa 30 giây rồi chuyển sang dùng cảm biến gia tốc (IMU). Nếu không có IMU thì trạng thái là chưa xác định, khi đó chỉ giữ lại cảnh báo mức 4 "
        "khi nhắm mắt.")
    B.code("code_gate", "Mã nguồn xác định trạng thái chuyển động của xe", src(motion.MovementGate.update))
    B.h3("Ngân sách chú ý")
    B.p("{fig:code_budget} là phần cài đặt ngân sách chú ý. Mỗi nguyên nhân có một trọng số: nhìn lệch là 1,0, dùng điện thoại là 1,5 và uống nước hoặc ăn là 0,7.")
    B.code("code_budget", "Mã nguồn ngân sách chú ý", src(estimators.AttentionBudget.update))

    B.h2("Thực nghiệm và kết quả")
    B.h3("Kiểm thử tự động")
    B.p(f"Em viết {t_edge} bài kiểm thử cho phần thiết bị và {tc['cloud']} bài cho gateway, tất cả đều chạy đạt ({{tbl:tests}}). Ngoài các bài kiểm thử đơn vị, em dùng "
        "thêm một kịch bản kiểm thử ghi sẵn (golden trace) dài khoảng 60 giây gồm chớp mắt, nhắm mắt, nhìn lệch, dùng điện thoại và dừng xe. Kịch bản này được ghi ra "
        "tệp JSON Lines và phát lại, danh sách sự kiện đầu ra phải giống với tệp kết quả đã lưu. Khi chuyển chương trình sang chip K230, có thể dùng lại kịch bản này "
        "để kiểm tra phiên bản mới cho kết quả giống phiên bản trên máy tính.")
    B.table("tests", "Các nhóm kiểm thử tự động", ["Nhóm", "Số bài", "Nội dung chính"],
            [["Hình học", str(tc.get("test_geometry", 0)), "EAR, MAR, tư thế đầu và quy ước dấu của góc pitch"],
             ["Bộ đo", str(tc.get("test_estimators", 0)), "Trạng thái chuyển động, nhắm mắt, PERCLOS, ngáp, tư thế, bàn tay, ngân sách chú ý"],
             ["Quyết định", str(tc.get("test_engine", 0)), "Kịch bản đầy đủ: mức 4 sau đúng 3 giây, chớp mắt, kính râm, xe dừng, mất mặt"],
             ["Kịch bản ghi sẵn", str(tc.get("test_golden", 0)), "Phát lại kịch bản và so sánh sự kiện"],
             ["Cảm biến", str(tc.get("test_perception", 0)), "Ảnh thật qua MediaPipe: EAR hợp lý, mắt nhắm vẫn quan sát được, vùng mắt tối thì không"],
             ["Gateway", str(tc["cloud"]), "Định dạng dữ liệu, ẩn danh, loại trùng, hàng đợi khi mất mạng"]],
            [2000, 1100, 5688], ["left", "center", "left"])

    B.h3("Thời gian nhắm mắt và mức cảnh báo")
    B.p(f"Do không có webcam và dữ liệu video nhắm mắt có nhãn, em dùng một ảnh chân dung thật và tạo thêm phiên bản mắt nhắm bằng cách phủ màu da lên vùng mắt. "
        f"Hai ảnh này đi qua MediaPipe để lấy số đo thật: EAR khi mở mắt là {vn(cl['ear_open'], 3)}, khi nhắm là {vn(cl['ear_closed'], 3)} "
        f"(bằng {vn(cl['ear_closed'] / cl['ear_open'], 2)} lần). Từ hai bộ số đo này em tạo các chuỗi 15 khung/giây với thời gian nhắm mắt khác nhau rồi chạy "
        "phần quyết định. Thí nghiệm này chỉ dùng ảnh của một người nên chủ yếu kiểm tra logic ngưỡng và độ trễ ({tbl:closure}).")
    rows = []
    for r in cl["rows"]:
        f = r["first_s"]
        g = lambda L: (vn(f[str(L)], 2) + " s") if str(L) in f else "–"
        rows.append([vn(r["closed_s"], 1), str(r["max_level"]), g(1), g(2), g(3), g(4)])
    B.table("closure", "Mức cảnh báo theo thời gian nhắm mắt (xe chạy 50 km/h)",
            ["Nhắm mắt (s)", "Mức cao nhất", "Đạt mức 1", "Đạt mức 2", "Đạt mức 3", "Đạt mức 4"], rows, [1500, 1400, 1470, 1470, 1470, 1478])
    B.p("Kết quả đúng với thiết kế: mức 4 đạt tại thời điểm 3,00 giây, các mức 1, 2, 3 đạt tại khoảng 0,5; 1,0 và 2,0 giây ({fig:closure}). Do có khoảng dung sai 0,2 giây "
        "nên khi nhắm khoảng 2,9 giây hệ thống vẫn lên mức 4, và nhắm 0,4 giây đã lên mức 1. {fig:signals} là các tín hiệu khi chạy với video thử gồm 14 giây mở mắt và "
        "4 giây nhắm mắt: EAR giảm xuống dưới ngưỡng, thời gian nhắm tăng đều và mức cảnh báo tăng dần từng bậc.")
    B.fig("closure", FIG / "closure.png", "Mức đạt được và độ trễ cảnh báo theo thời gian nhắm mắt", 14.5)
    B.fig("signals", FIG / "signals.png", "EAR, thời gian nhắm liên tục và mức cảnh báo trên video thử", 14.5)
    rb = {r["closed_s"]: r for r in cl["robust"]}
    B.p(f"Để kiểm tra độ ổn định, em thêm nhiễu Gauss với độ lệch chuẩn 0,02 vào EAR và làm mất khuôn mặt ngẫu nhiên ở 3% số khung, mỗi trường hợp chạy 20 lần. "
        f"Khi nhắm 0,3 giây, hệ thống không lần nào cảnh báo. Khi nhắm 1,0 giây, cả {rb[1.0]['runs']} lần đều lên mức 2. Khi nhắm 3,5 giây, "
        f"{rb[3.5]['level4_runs']}/{rb[3.5]['runs']} lần lên mức 4. Khi xe dừng và tài xế nhắm mắt 10 giây thì không có sự kiện nào.")
    sc = {(r["speed"], r["closed_s"]): r for r in cl["scaling"]}
    B.p("Em cũng thử thêm hệ số theo tốc độ (mặc định tắt): ngưỡng thời gian được rút ngắn khi xe chạy nhanh, vì cùng một giây nhắm mắt thì xe đi được quãng đường xa hơn. "
        f"Ở 50 km/h kết quả không đổi. Ở 100 km/h, nhắm mắt 1,5 giây chỉ lên mức {sc[(100.0, 1.5)]['off']['max_level']} khi tắt hệ số, nhưng lên mức 4 sau "
        f"{vn(sc[(100.0, 1.5)]['on']['t_l4'], 2)} giây khi bật.")

    B.h3("Ngân sách chú ý")
    B.p("{fig:budget} so sánh hai trường hợp. Bên trái là tài xế nhìn lệch liên tục, ngân sách về 0 sau đúng 6 giây. Bên phải là tài xế nhắn tin, cứ khoảng 2 giây lại liếc "
        "lên đường 0,3 giây. Ngân sách chỉ hồi lại một phần nên vẫn giảm dần, trong khi nếu đặt lại bộ đếm mỗi lần liếc đường thì trường hợp này sẽ không bao giờ bị cảnh báo. "
        "Bài kiểm thử tương ứng cũng cho thấy liếc gương dưới 1 giây không gây cảnh báo.")
    B.fig("budget", FIG / "budget.png", "Ngân sách chú ý khi nhìn lệch liên tục và khi nhắn tin xen kẽ liếc đường", 14.5)

    B.h3("Đánh giá luật bàn tay gần đầu trên State Farm")
    B.p("Vì ảnh State Farm chụp nghiêng, em dùng mô hình tư thế cơ thể để lấy vị trí tai, miệng và bàn tay. Tâm bàn tay là trung bình của cổ tay, ngón trỏ, ngón út và ngón cái. "
        "Khoảng cách từ tâm bàn tay đến tai (phía gần camera) và đến miệng được chia cho khoảng cách mũi - tai. Ngưỡng k được chọn trên tập val sao cho F1 lớn nhất, "
        "sau đó giữ nguyên để đánh giá trên tập test gồm các tài xế khác. Với luật tai, lớp dương là c2 và c4 (gọi điện); với luật miệng, lớp dương là c6 (uống nước); "
        "các lớp còn lại là lớp âm.")
    B.table("rules", "Kết quả hai luật trên State Farm",
            ["Luật", "k*", "Val P / R / F1", "Test P / R / F1", "AUC val / test"],
            [["Gọi điện (tay - tai)", vn(ph["best_k"], 2), f"{vn(ph['val_best']['precision'], 2)} / {vn(ph['val_best']['recall'], 2)} / {vn(ph['val_best']['f1'], 2)}",
              f"{vn(ph['test_at_best']['precision'], 2)} / {vn(ph['test_at_best']['recall'], 2)} / {vn(ph['test_at_best']['f1'], 2)}",
              f"{vn(ph['auc_val'], 2)} / {vn(ph['auc_test'], 2)}"],
             ["Uống nước (tay - miệng)", vn(dr["best_k"], 2), f"{vn(dr['val_best']['precision'], 2)} / {vn(dr['val_best']['recall'], 2)} / {vn(dr['val_best']['f1'], 2)}",
              f"{vn(dr['test_at_best']['precision'], 2)} / {vn(dr['test_at_best']['recall'], 2)} / {vn(dr['test_at_best']['f1'], 2)}",
              f"{vn(dr['auc_val'], 2)} / {vn(dr['auc_test'], 2)}"]],
            [2400, 700, 1900, 1900, 1888])
    B.p(f"Kết quả chưa tốt: F1 trên tập test là {vn(ph['test_at_best']['f1'], 2)} với luật gọi điện và {vn(dr['test_at_best']['f1'], 2)} với luật uống nước, thấp hơn "
        "nhiều so với tập val vì tài xế ở tập test khác tài xế ở tập val. {fig:curves} cho thấy ngưỡng tốt nhất nằm ở khoảng giữa của dải ngưỡng đã thử. Em thấy có hai "
        "nguyên nhân chính. Khi gọi điện bằng tay trái (c4), tay nằm ở phía tai xa camera nên bị đầu che. Ngoài ra, khoảng cách mũi - tai trong ảnh chỉ khoảng 22 đến 41 "
        "điểm ảnh (trung vị theo lớp), quá nhỏ nên phép chuẩn hoá bị nhiễu.")
    B.fig("curves", FIG / "sf_curves.png", "Precision, recall và F1 theo ngưỡng k trên tập val", 14.5)
    B.p(f"Nếu xem luật như một bộ phát hiện chung cho việc đưa tay lên đầu thì kết quả khả quan hơn ({{fig:flagged}}). Lớp c0 (lái xe an toàn) chỉ bị đánh dấu "
        f"{pct(near['c0']['flagged'], near['c0']['n'])}, gần bằng các lớp c3 và c9 vốn không đưa tay lên đầu. Trong khi đó các lớp có đưa tay lên đầu bị đánh dấu nhiều hơn hẳn: "
        f"c4 {pct(near['c4']['flagged'], near['c4']['n'])}, c8 {pct(near['c8']['flagged'], near['c8']['n'])}, c2 {pct(near['c2']['flagged'], near['c2']['n'])} và "
        f"c6 {pct(near['c6']['flagged'], near['c6']['n'])}. Tuy vậy luật không phân biệt được gọi điện, uống nước và chải tóc vì đều là đưa tay lên đầu, và gần như không "
        "phát hiện được nhắn tin (c1, c3 dưới 5%) vì khi nhắn tin tay không đưa lên mặt.")
    B.fig("flagged", FIG / "sf_flagged.png", "Tỉ lệ ảnh bị đánh dấu theo từng lớp trên tập test", 14.5)
    B.fig("samples", FIG / "sf_samples.png", "Một số kết quả: tai (vuông xanh), miệng (tam giác hồng), bàn tay (tròn vàng) và kết luận của luật", 14.5)
    B.p("Trong bài tập lớn trước, mô hình EfficientNet-Lite0 với cùng cách chia tài xế đạt macro-F1 khoảng 0,82 cho bài toán sáu nhóm hành vi. Hai kết quả không so sánh "
        "trực tiếp được vì bài toán khác nhau, nhưng có thể thấy luật hình học đơn giản kém hơn nhiều so với một mô hình được huấn luyện trên chính bộ dữ liệu này. Bù lại, "
        "luật không cần dữ liệu huấn luyện, dễ giải thích và có thể dùng cho camera đặt ở góc khác chỉ bằng cách chỉnh lại ngưỡng, còn mô hình huấn luyện trên State Farm "
        "sẽ không còn chính xác khi đổi góc camera.")

    B.h3("Hiệu năng")
    B.p(f"Em đo thời gian xử lý trên CPU {b['machine']['cpu']}, Python {b['machine']['python']}, MediaPipe {b['machine']['mediapipe']}, với video có khung hình "
        f"{b['frame_size'][0]}×{b['frame_size'][1]}, tổng cộng {b['frames']} khung (bỏ 10 khung đầu). Phần cảm biến (khuôn mặt và bàn tay) mất trung bình "
        f"{vn(b['sensor_ms']['mean'], 1)} ms mỗi khung (p95 là {vn(b['sensor_ms']['p95'], 1)} ms), phần quyết định chỉ mất {vn(b['engine_only_ms'], 2)} ms. "
        f"Cả hệ thống đạt khoảng {vn(b['pipeline_fps'], 0)} khung/giây ({{fig:bench}}). Như vậy phần quyết định không ảnh hưởng đến tốc độ chung. Hiệu năng trên chip "
        "K230 em chưa đo được.")
    B.fig("bench", FIG / "bench.png", "Thời gian xử lý mỗi khung trên CPU", 12.5)
    B.table("bench", "Hiệu năng đo trên CPU", ["Hạng mục", "Giá trị"],
            [["Cảm biến khuôn mặt và bàn tay, trung bình mỗi khung", f"{vn(b['sensor_ms']['mean'], 1)} ms"],
             ["Cảm biến, p95", f"{vn(b['sensor_ms']['p95'], 1)} ms"],
             ["Phần quyết định, mỗi khung", f"{vn(b['engine_only_ms'], 2)} ms"],
             ["Toàn hệ thống", f"khoảng {vn(b['pipeline_fps'], 0)} khung/giây"],
             ["Gateway chuyển đổi GPS", f"khoảng {thousands(int(round(b['gateway_points_per_s'], -3)))} điểm/giây"]],
            [5400, 3388], ["left", "center"])

    B.h2("Phần máy chủ và kết nối với Traffic-SM")
    B.p("Device-gateway nhận GPS từ thiết bị ở dạng rút gọn (thời điểm, vĩ độ, kinh độ, tốc độ) và chuyển sang định dạng mà cổng nhận dữ liệu của Traffic-SM yêu cầu. "
        "Cổng này kiểm tra khá chặt: phải có đủ mười một trường số, trường time theo giờ UTC+7, phút trong t_timestamp phải trùng với phút trong time, và vehicle_type chỉ "
        "nhận car hoặc bike. Để kiểm tra phần chuyển đổi, em chạy lại trên 200 dòng thật của fake_gps.csv: với cùng một thời điểm, gateway tạo ra đúng giá trị time và "
        "t_timestamp giống như Traffic-SM ({fig:code_gw}).")
    B.code("code_gw", "Mã nguồn chuyển một điểm GPS của thiết bị sang bản ghi của Traffic-SM", src(gateway.to_ingest_payload, strip_doc=True, max_lines=46))
    B.p("Trước khi chuyển dữ liệu đi, gateway bỏ mã thiết bị. Traffic-SM và bảng sự kiện chỉ thấy mã chuyến đi, còn bảng ghép chuyến đi với thiết bị được lưu riêng trong "
        "SQLite. Sự kiện được loại trùng theo mã sự kiện nên khi thiết bị gửi lại thì không bị ghi hai lần. Khi mất mạng, thiết bị ghi dữ liệu vào tệp outbox và gửi lại "
        "ở lần chạy sau.")
    B.table("e2e", "Kết quả chạy thử toàn bộ luồng: video, thiết bị, gateway, máy chủ nhận dữ liệu giả lập",
            ["Hạng mục", "Kết quả"],
            [["Điểm GPS gửi qua gateway", "49 điểm của 3 chuyến, nhận 49, từ chối 0"],
             ["Sự kiện được lưu", "6 sự kiện, không có mã thiết bị, không trùng"],
             ["Gửi lại từ outbox khi gateway chạy lại", "7 bản ghi gửi thành công, outbox còn 0"],
             ["Mã tài xế phía Traffic-SM nhận được", "là mã chuyến đi (3 mã khác nhau)"],
             ["Chạy với Traffic-SM thật", "chưa chạy (máy chưa chạy Docker, thiếu dữ liệu bản đồ OSM)"]],
            [3800, 4988], ["left", "left"])
    B.p("Phía nhận dữ liệu trong lần chạy thử là một máy chủ giả lập do em viết, kiểm tra dữ liệu theo đúng các quy tắc trong hàm gps.Canonicalize của Traffic-SM "
        "(viết bằng Go). Các phần còn lại của Traffic-SM như map matching, Spark, ClickHouse và Grafana chưa được chạy lại trong đồ án này.")

    B.h2("Sản phẩm")
    B.p("Chương trình demo chạy trên máy tính với webcam hoặc tệp video ({fig:osd}). Cửa sổ hiển thị mức cảnh báo bằng thanh màu ở phía trên, các số đo EAR, PERCLOS, "
        "tư thế đầu, ngân sách chú ý, trạng thái chuyển động của xe và các cờ báo chất lượng. Ảnh trong báo cáo được vẽ ở chế độ riêng tư, chỉ có các điểm mốc trên nền đen. "
        "Chương trình phát âm thanh bằng winsound trên Windows, mỗi mức có một kiểu âm báo riêng. Các phím tắt: w và s để tăng giảm tốc độ giả lập, phím cách để cho xe "
        "dừng hoặc chạy, c để hiệu chỉnh nhanh, m để tắt âm thanh và q để thoát.")
    B.fig("osd", FIG / "osd_levels.png", "Giao diện demo ở chế độ riêng tư tại mức 0, mức 2 và mức 4", 14.5)
    B.p("Cách chạy: lệnh python -m drivefocus.demo --quick để chạy với webcam; thêm --source clip.mp4 --no-window để chạy với tệp video; thêm --route-csv và --gateway "
        "để gửi dữ liệu qua gateway; lệnh python -m drivefocus.replay trace.jsonl để phát lại kịch bản đã ghi.")

    # ======================================================================= KẾT LUẬN
    B.h1("KẾT LUẬN", numbered=False)
    B.p("Trong đồ án 3, em đã xây dựng hệ thống giám sát tài xế DriveFocus và đạt được một số kết quả sau:")
    B.bullets([
        "Xây dựng phần quyết định cảnh báo bằng thuật toán, không dùng mô hình phân loại hành vi: EAR chuẩn hoá theo từng người, PERCLOS tính theo thời gian, "
        "tư thế đầu từ ma trận biến đổi, luật bàn tay gần đầu, ngân sách chú ý, xác định xe đang chạy và máy trạng thái bốn mức.",
        "Khi nhắm mắt liên tục 3 giây, hệ thống lên mức 4 đúng tại thời điểm 3,00 giây; không cảnh báo khi chỉ chớp mắt, vẫn ổn định khi có nhiễu và mất khuôn mặt "
        "ngẫu nhiên, và không cảnh báo khi xe dừng.",
        f"Viết {t_edge + tc['cloud']} bài kiểm thử tự động (đều đạt) và một kịch bản ghi sẵn để kiểm tra khi chuyển sang thiết bị khác.",
        f"Phần quyết định chỉ mất khoảng {vn(b['engine_only_ms'], 2)} ms mỗi khung; cả hệ thống chạy khoảng {vn(b['pipeline_fps'], 0)} khung/giây trên CPU máy tính.",
        "Xây dựng phần máy chủ tối thiểu: ẩn danh dữ liệu, chuyển GPS sang định dạng của Traffic-SM (đã kiểm tra với 200 dòng dữ liệu thật), loại trùng sự kiện và gửi lại khi mất mạng.",
        "Đánh giá trên State Farm: mô hình khuôn mặt chỉ tìm được mặt ở khoảng 28% số ảnh do góc chụp nghiêng; luật bàn tay gần đầu đạt F1 0,34 với gọi điện và 0,19 với uống nước."])
    B.p("Đồ án vẫn còn một số hạn chế:")
    B.bullets([
        "Chưa thử với webcam và người lái thật. Thí nghiệm nhắm mắt mới dùng ảnh của một người, vùng mắt nhắm được tạo bằng cách phủ màu da. Các ngưỡng hiện tại mới là giá trị ban đầu.",
        "Chưa có dữ liệu mặt nhìn thẳng có nhãn (NTHU-DDD, YawDD, DMD) nên chưa đánh giá được EAR, PERCLOS và ngáp trên nhiều người, chưa đo được số lần báo nhầm khi lái xe bình thường.",
        "Luật bàn tay gần đầu còn yếu: chưa phân biệt được các hành vi đưa tay lên đầu và không phát hiện được nhắn tin.",
        "Chưa chạy trên chip K230 nên hiệu năng và độ chính xác trên chip vẫn chỉ là ước lượng.",
        "Chưa chạy với Traffic-SM thật, mới thử với máy chủ giả lập, và chưa có phần bảo mật (mã hoá, xác thực thiết bị)."])
    B.p("Trong thời gian tới, em dự định tải và đánh giá trên các bộ NTHU-DDD, YawDD và DMD để chỉnh lại ngưỡng, quay thêm video ở đúng vị trí đặt camera trên xe, "
        "chuyển phần cảm biến sang các mô hình trong SDK của K230, kết nối với Traffic-SM thật để làm bản đồ rủi ro theo đoạn đường, và bổ sung phần bảo mật "
        "(mTLS, phân quyền, cập nhật có chữ ký).")

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
