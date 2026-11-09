"""Bộ dựng thân tài liệu Word bằng XML, dùng đúng các kiểu của báo cáo mẫu (Nidung, Mcln, Tiumc,
Heading1, Tiu, Caption, ListParagraph). Số hình, số bảng tự đánh bằng trường STYLEREF/SEQ như mẫu,
nên Word cập nhật được mục lục và danh mục hình.
"""
from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

W_TEXT = 8788           # chiều rộng vùng chữ (twips): 11907 - 1985 - 1134
EMU_PER_CM = 360000


def esc(s: str) -> str:
    return escape(s)


def run(text: str, bold=False, italic=False, size=None, mono=False) -> str:
    rpr = ""
    if mono:
        rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas" w:eastAsia="Consolas"/>'
    if bold:
        rpr += "<w:b/><w:bCs/>"
    if italic:
        rpr += "<w:i/><w:iCs/>"
    if size:
        rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def rich(text: str, size=None, mono=False) -> str:
    """Hỗ trợ **đậm** và *nghiêng* trong một đoạn."""
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("`"):
            out.append(run(part[1:-1], size=size, mono=True))
        elif part.startswith("**"):
            out.append(run(part[2:-2], bold=True, size=size, mono=mono))
        else:
            out.append(run(part, size=size, mono=mono))
    return "".join(out)


class Builder:
    def __init__(self, media_dir: Path, first_rid: int = 200, first_docpr: int = 9000):
        self.parts: list[str] = []
        self.chapter = 0
        self.fig_n = 0
        self.tbl_n = 0
        self.labels: dict[str, str] = {}
        self.known: dict[str, str] = {}      # nhãn đã biết từ lượt trước
        self.images: list[tuple[str, Path]] = []   # (rId, đường dẫn)
        self._rid = first_rid
        self._docpr = first_docpr
        self.media_dir = media_dir

    # ------------------------------------------------------------ tham chiếu
    def ref(self, text: str) -> str:
        return re.sub(r"\{(fig|tbl):([a-z0-9_]+)\}", lambda m: self.known.get(f"{m.group(1)}:{m.group(2)}", "?"), text)

    # ----------------------------------------------------------- tiêu đề
    def h1(self, text: str, numbered=True, style="Heading1") -> None:
        if numbered:
            self.chapter += 1
            self.fig_n = self.tbl_n = 0
        extra = "" if numbered or style != "Heading1" else '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
        self.parts.append(
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{extra}<w:rPr><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr><w:t>{esc(text)}</w:t></w:r></w:p>')

    def h2(self, text: str) -> None:
        self.parts.append(
            '<w:p><w:pPr><w:pStyle w:val="Mcln"/><w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr><w:t>{esc(text)}</w:t></w:r></w:p>')

    def h3(self, text: str) -> None:
        self.parts.append(
            '<w:p><w:pPr><w:pStyle w:val="Tiumc"/><w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr><w:t>{esc(text)}</w:t></w:r></w:p>')

    # -------------------------------------------------------------- văn bản
    def p(self, text: str) -> None:
        self.parts.append(f'<w:p><w:pPr><w:pStyle w:val="Nidung"/></w:pPr>{rich(self.ref(text))}</w:p>')

    def bullets(self, items: list[str]) -> None:
        for it in items:
            self.parts.append('<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/>'
                              f'<w:numId w:val="24"/></w:numPr></w:pPr>{rich(self.ref(it))}</w:p>')

    def refs(self, items: list[str]) -> None:
        for it in items:
            self.parts.append('<w:p><w:pPr><w:pStyle w:val="Nidung"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="4"/></w:numPr>'
                              f'<w:spacing w:before="60" w:line="276" w:lineRule="auto"/></w:pPr>{run(it)}</w:p>')

    # ------------------------------------------------------------- chú thích
    def _caption(self, kind: str, key: str, text: str, keep_next: bool) -> None:
        word, seq = ("Hình", "Hình") if kind == "fig" else ("Bảng", "Bảng")
        n = self.fig_n if kind == "fig" else self.tbl_n
        self.labels[f"{kind}:{key}"] = f"{word} {self.chapter}.{n}"
        kn = "<w:keepNext/>" if keep_next else ""
        spacing = '<w:spacing w:before="160" w:after="80"/>' if keep_next else '<w:spacing w:before="80" w:after="200"/>'
        fld = lambda instr, val: (f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
                                  f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:noProof/></w:rPr><w:t>{val}</w:t></w:r>'
                                  f'<w:r><w:fldChar w:fldCharType="end"/></w:r>')
        part_style = fld("STYLEREF 1 \s", self.chapter)
        part_seq = fld("SEQ " + seq + " \* ARABIC \s 1", n)
        body_text = esc(self.ref(text))
        self.parts.append(
            f'<w:p><w:pPr><w:pStyle w:val="Caption"/>{kn}{spacing}</w:pPr>'
            f'<w:r><w:t xml:space="preserve">{word} </w:t></w:r>{part_style}<w:r><w:t>.</w:t></w:r>'
            f'{part_seq}<w:r><w:t xml:space="preserve">: {body_text}</w:t></w:r></w:p>')

    # --------------------------------------------------------------- hình
    def fig(self, key: str, image: Path, caption: str, width_cm: float = 15.0) -> None:
        self.fig_n += 1
        rid = f"rId{self._rid}"
        self._rid += 1
        self._docpr += 1
        with Image.open(image) as im:
            w, h = im.size
        cx = int(width_cm * EMU_PER_CM)
        cy = int(cx * h / w)
        max_cy = int(15.5 * EMU_PER_CM)
        if cy > max_cy:
            cx, cy = int(cx * max_cy / cy), max_cy
        self.images.append((rid, image))
        name = esc(image.name)
        self.parts.append(
            '<w:p><w:pPr><w:pStyle w:val="Nidung"/><w:keepNext/><w:spacing w:before="160"/><w:ind w:firstLine="0"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:noProof/></w:rPr><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{self._docpr}" name="Picture {self._docpr}" descr="{name}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
        self._caption("fig", key, caption, keep_next=False)

    # ---------------------------------------------------------------- bảng
    def table(self, key: str, caption: str, header: list[str], rows: list[list[str]], widths: list[int],
              aligns: list[str] | None = None, bold_last=False) -> None:
        self.tbl_n += 1
        self._caption("tbl", key, caption, keep_next=True)
        total = sum(widths)
        aligns = aligns or ["left"] + ["center"] * (len(header) - 1)
        border = '<w:{s} w:val="single" w:sz="4" w:space="0" w:color="8C8C8C"/>'
        borders = "".join(border.format(s=s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
               '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
               '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
               "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"]

        def cell(text, w, align, head=False, bold=False, fill=None):
            shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
            rp = "<w:b/><w:bCs/>" if (head or bold) else ""
            return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}<w:vAlign w:val="center"/></w:tcPr>'
                    f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="40" w:after="40" w:line="264" w:lineRule="auto"/><w:ind w:firstLine="0"/>'
                    f'<w:jc w:val="{align}"/></w:pPr><w:r><w:rPr>{rp}<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
                    f'<w:t xml:space="preserve">{esc(self.ref(text))}</w:t></w:r></w:p></w:tc>')

        out.append('<w:tr><w:trPr><w:cantSplit/><w:tblHeader/><w:jc w:val="center"/></w:trPr>' +
                   "".join(cell(h, w, "center", head=True, fill="E8E5DC") for h, w in zip(header, widths)) + "</w:tr>")
        for i, r in enumerate(rows):
            last = bold_last and i == len(rows) - 1
            out.append('<w:tr><w:trPr><w:cantSplit/><w:jc w:val="center"/></w:trPr>' +
                       "".join(cell(c, w, a, bold=last) for c, w, a in zip(r, widths, aligns)) + "</w:tr>")
        out.append("</w:tbl>")
        self.parts.append("".join(out))
        self.parts.append('<w:p><w:pPr><w:pStyle w:val="Nidung"/><w:spacing w:before="0" w:after="0"/></w:pPr></w:p>')

    # ------------------------------------------------------------ mã nguồn
    def code(self, key: str, caption: str, source: str) -> None:
        """Khung mã nguồn một ô, nền xám nhạt, chữ Consolas; chú thích 'Hình' phía dưới như báo cáo mẫu."""
        self.fig_n += 1
        lines = source.rstrip("\n").split("\n")
        paras = []
        for ln in lines:
            ln = ln.replace("\t", "    ")
            paras.append('<w:p><w:pPr><w:keepLines/><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/>'
                         f'<w:jc w:val="left"/></w:pPr>{run(ln if ln else " ", size=17, mono=True)}</w:p>')
        border = '<w:{s} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
        borders = "".join(border.format(s=s) for s in ("top", "left", "bottom", "right"))
        self.parts.append(
            f'<w:tbl><w:tblPr><w:tblW w:w="{W_TEXT}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
            '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            f'<w:tblGrid><w:gridCol w:w="{W_TEXT}"/></w:tblGrid><w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="{W_TEXT}" w:type="dxa"/>'
            '<w:shd w:val="clear" w:color="auto" w:fill="F5F5F5"/></w:tcPr>' + "".join(paras) + "</w:tc></w:tr></w:tbl>")
        self._caption("fig", key, caption, keep_next=False)

    def xml(self) -> str:
        return "".join(self.parts)
