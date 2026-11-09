"""Lắp báo cáo: lấy file Word của bạn làm nền, thay bìa và toàn bộ phần thân, thêm ảnh.

Chạy bằng python của venv edge:  python assemble.py
Sau đó chạy update_fields.ps1 để Word cập nhật mục lục và danh mục hình, rồi xuất PDF kiểm tra.
"""
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[1]
def _find_dds(root):
    """dds-edge nằm cạnh drivefocus/ (bản làm việc) hoặc chính là thư mục cha (nhánh drive-focus của repo dds-edge)."""
    for cand in (root.parent / "dds-edge", root.parent):
        if (cand / "src" / "dds_edge").is_dir():
            return cand
    return root.parent / "dds-edge"


BASE = _find_dds(ROOT) / "reports" / "BaoCao_ThiGiacMayTinh_TranGiaHuy.docx"
OUT = ROOT / "report" / "build" / "stage1.docx"

import content  # noqa: E402
from docx_lib import Builder  # noqa: E402


def replace_text(xml: str, old: str, new: str, count: int = 0) -> str:
    n = xml.count(f">{old}<")
    if n == 0:
        raise SystemExit(f"không tìm thấy nút văn bản: {old!r}")
    return xml.replace(f">{old}<", f">{new}<", count or n)


def main() -> None:
    zin = zipfile.ZipFile(BASE)
    xml = zin.read("word/document.xml").decode("utf-8")

    # --- thân tài liệu: hai lượt để tham chiếu "Hình x.y" biết số
    B1 = Builder(ROOT / "report" / "figs")
    content.build(B1)
    B2 = Builder(ROOT / "report" / "figs")
    B2.known = dict(B1.labels)
    content.build(B2)
    missing = [k for k in B1.labels if B2.labels.get(k) != B1.labels[k]]
    assert not missing, missing
    body = B2.xml()
    assert "?" not in re.sub(r"<[^>]+>", "", " ".join(re.findall(r"Hình \?|Bảng \?", body))), "còn tham chiếu chưa giải"

    # --- vị trí thay thân: từ đoạn Heading1 đầu tiên đến sectPr cuối
    first_h1 = xml.index('<w:pStyle w:val="Heading1"/>')
    i = xml.rfind("<w:p ", 0, first_h1)
    j = xml.rindex("<w:sectPr")
    front, tail = xml[:i], xml[j:]

    # --- bìa và phần đầu
    front = replace_text(front, "BÀI TẬP LỚN", "ĐỒ ÁN 3")
    front = replace_text(front, "MÔN: THỊ GIÁC MÁY TÍNH", "DRIVEFOCUS")
    front = replace_text(front, "NHẬN DIỆN HÀNH VI TÀI XẾ MẤT TẬP TRUNG", "GIÁM SÁT TÀI XẾ BUỒN NGỦ VÀ MẤT TẬP TRUNG")
    front = replace_text(front, "TRƯỜNG ĐẠI HỌC SƯ PHẠM KỸ THUẬT HƯNG YÊN", "TRƯỜNG ĐẠI HỌC CÔNG NGHỆ KỸ THUẬT HƯNG YÊN")
    front = replace_text(front, "TS. LÊ TRUNG HIẾU", "PGS.TS. NGUYỄN MINH TIẾN")
    front = front.replace("bài tập lớn môn Thị giác máy tính", "đồ án 3")
    front = front.replace("TS. Lê Trung Hiếu", "PGS.TS. Nguyễn Minh Tiến").replace("thầy Lê Trung Hiếu", "thầy Nguyễn Minh Tiến")
    front = front.replace("Trường Đại học Sư phạm Kỹ thuật Hưng Yên", "Trường Đại học Công nghệ Kỹ thuật Hưng Yên")
    front = front.replace("bài tập lớn", "đồ án").replace("Bài tập lớn", "Đồ án")
    for old in ("Lê Trung Hiếu", "LÊ TRUNG HIẾU", "Sư phạm", "SƯ PHẠM", "THỊ GIÁC MÁY TÍNH"):
        leftovers = [m for m in re.findall(r"<w:t[^>]*>([^<]*)</w:t>", front) if old in m and "TOC" not in m]
        assert not leftovers, (old, leftovers)
    front = front.replace("28 tháng 10 năm 2026", "9 tháng 11 năm 2026")
    new_xml = front + body + tail

    # --- quan hệ và ảnh
    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    add = ""
    media = {}
    for rid, path in B2.images:
        target = f"media/df_{path.stem}_{rid}{path.suffix}"
        add += f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{target}"/>'
        media["word/" + target] = path.read_bytes()
    rels = rels.replace("</Relationships>", add + "</Relationships>")

    # dọn quan hệ ảnh cũ không còn được tham chiếu
    used = set(re.findall(r'r:(?:embed|id|link)="(rId\d+)"', new_xml))
    drop_media = []

    def prune(m):
        rid, target = m.group(1), m.group(2)
        if "/image" in m.group(0) and rid not in used:
            drop_media.append("word/" + target)
            return ""
        return m.group(0)

    rels = re.sub(r'<Relationship Id="(rId\d+)"[^>]*Target="(media/[^"]+)"[^>]*/>', prune, rels)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in drop_media:
                continue
            data = zin.read(item.filename)
            if re.fullmatch(r"word/header\d+\.xml", item.filename):
                s = data.decode("utf-8")
                s = s.replace("Bài tập lớn: Nhận diện hành vi tài xế mất tập trung", "Đồ án 3: DriveFocus giám sát tài xế")
                s = s.replace("Nhận diện hành vi tài xế mất tập trung", "DriveFocus giám sát tài xế")
                data = s.encode("utf-8")
            elif item.filename == "word/styles.xml":
                s = data.decode("utf-8")
                s = re.sub(r'(<w:style [^>]*w:styleId="TableofFigures".*?<w:rPr>).*?(</w:rPr></w:style>)',
                           r'\1<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/>\2', s, flags=re.S)
                data = s.encode("utf-8")
            if item.filename == "word/document.xml":
                data = new_xml.encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            zout.writestr(item, data)
        for name, data in media.items():
            zout.writestr(name, data)
    print(f"đã ghi {OUT} | ảnh mới {len(media)} | đã bỏ ảnh cũ {len(drop_media)} | nhãn hình/bảng {len(B2.labels)}")
    print({k: v for k, v in B2.labels.items()})


if __name__ == "__main__":
    main()
