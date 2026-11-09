// Slide bảo vệ DriveFocus. Số liệu đọc từ report/results/*.json.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/Administrator/.claude/skills/synced/dbe77007-127d-4b91-a0e3-e928c7d3afaf_454ea1c5-c548-4cfd-9b1c-8402712b1e51/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "figs");
const RES = path.join(ROOT, "results");
const OUT = path.join(ROOT, "DriveFocus_Slide_DoAn3.pptx");
const J = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));
const sf = J("sf_analysis.json"), cl = J("closure.json"), bench = J("bench.json");
const vn = (x, nd = 1) => x.toFixed(nd).replace(".", ",");
const pc = (a, b, nd = 1) => vn((100 * a) / b, nd) + "%";

// ---- theme
const THEME = {
  name: "DriveFocus",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A41", lt1: "FFFFFF", dk2: "0F2A43", lt2: "EEF2F7",
    accent1: "1B998B", accent2: "F28F3B", accent3: "C8283C", accent4: "3D5A80", accent5: "4C9F70", accent6: "F2C94C",
    hlink: "1B998B", folHlink: "3D5A80",
  },
};
const HEX = { grid: "D9DEE7", axis: "55606E", face: "C8283C", pose: "1B998B", teal: "1B998B", orange: "F28F3B", navy: "3D5A80" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "DriveFocus: giám sát tài xế mất tập trung";
pres.author = "Trần Gia Huy";
const C = pres.SchemeColor;

// ---- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: "0F2A43" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.35, w: 4.9, h: 1.0, fontSize: 48, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.45, w: 4.9, h: 1.0, fontSize: 18, color: C.background2, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "TITLE_ONLY",
  background: { color: "FFFFFF" },
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent4, align: "right" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.8, fontSize: 28, bold: true, color: C.text1, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "DriveFocus  •  Đồ án 3", options: { x: 0.5, y: 5.2, w: 4, h: 0.3, fontSize: 10, color: C.accent4, margin: 0 } } },
  ],
});
pres.defineSlideMaster({
  title: "DARK_END",
  background: { color: "0F2A43" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.5, w: 8.8, h: 0.8, fontSize: 34, bold: true, color: C.background1, margin: 0, valign: "middle", align: "left" }, text: "" } },
  ],
});

const notes = (s, t) => s.addNotes(t);
const card = (s, x, y, w, h, name, fill = C.background2) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: 0.08, objectName: name });
const stat = (s, x, y, w, big, label, color = C.accent1, name = "stat") => {
  card(s, x, y, w, 1.15, name + "-card");
  s.addText(big, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.6, fontSize: 30, bold: true, color, margin: 0, isTextBox: true, objectName: name + "-value", fontFace: THEME.headFontFace });
  s.addText(label, { x: x + 0.15, y: y + 0.68, w: w - 0.3, h: 0.42, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: name + "-label" });
};
const chip = (s, x, y, n, color) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color, width: 0 }, objectName: `chip-${n}` });
  s.addText(String(n), { x, y, w: 0.42, h: 0.42, align: "center", valign: "middle", fontSize: 14, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: `chip-${n}-n` });
};
const bullets = (s, items, x, y, w, h, fontSize = 14, name = "bullets") =>
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
    { x, y, w, h, fontSize, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: name });
const img = (s, file, x, y, w, name) => {
  const p = path.join(FIG, file);
  // đọc kích thước PNG/JPG để giữ tỉ lệ
  const buf = fs.readFileSync(p);
  let iw, ih;
  if (buf.readUInt32BE(0) === 0x89504e47) { iw = buf.readUInt32BE(16); ih = buf.readUInt32BE(20); }
  else { let o = 2; while (o < buf.length) { const m = buf.readUInt16BE(o); const l = buf.readUInt16BE(o + 2); if (m >= 0xffc0 && m <= 0xffcf && m !== 0xffc4 && m !== 0xffc8 && m !== 0xffcc) { ih = buf.readUInt16BE(o + 5); iw = buf.readUInt16BE(o + 7); break; } o += 2 + l; } }
  const h = (w * ih) / iw;
  s.addImage({ path: p, x, y, w, h, objectName: name, altText: name });
  return h;
};
const title = (s, t) => s.addText(t, { placeholder: "title" });

// ======================================================================= 1. Bìa
pres.addSection({ title: "Mở đầu" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Mở đầu" });
s.addText("DriveFocus", { placeholder: "title" });
s.addText("Giám sát tài xế buồn ngủ và mất tập trung bằng điểm mốc khuôn mặt", { placeholder: "body" });
s.addText([
  { text: "Đồ án 3  •  Môn Thị giác máy tính", options: { breakLine: true, bold: true } },
  { text: "Sinh viên: Trần Gia Huy  •  MSSV 10123169  •  Lớp 12423TN", options: { breakLine: true } },
  { text: "Giảng viên hướng dẫn: TS. Lê Trung Hiếu", options: { breakLine: true } },
  { text: "Trường Đại học Sư phạm Kỹ thuật Hưng Yên, 2026" },
], { x: 0.6, y: 3.75, w: 5.2, h: 1.3, fontSize: 13, color: C.background2, margin: 0, valign: "top", isTextBox: true, objectName: "author-block" });
img(s, "title_osd.png", 5.75, 1.15, 3.7, "ảnh giao diện chế độ riêng tư, mức 4");
s.addText("Mức 4: nhắm mắt liên tục 3 giây", { x: 5.75, y: 3.95, w: 3.7, h: 0.3, fontSize: 12, italic: true, color: C.accent6, margin: 0, isTextBox: true, objectName: "caption-title-img" });
notes(s, "Chào thầy cô. Đề tài DriveFocus là hệ thống giám sát tài xế chạy trên thiết bị biên: cảnh báo ngay trên xe, không cần mạng, không gửi video đi đâu. Ảnh bên phải là giao diện ở chế độ riêng tư: chỉ vẽ các điểm mốc khuôn mặt trên nền đen, đang ở mức báo động 4.");

// ======================================================================= 2. Bài toán
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Mở đầu" });
title(s, "Bài toán và mục tiêu");
bullets(s, [
  "Camera trong cabin theo dõi tài xế; cảnh báo ngay trên thiết bị, chỉ khi xe đang chạy.",
  "Bốn mức cảnh báo. Chỉ mức 4 là báo động khẩn cấp, ví dụ nhắm mắt liên tục từ 3 giây.",
  "Quyết định do thuật toán tự thiết kế; mạng nơ-ron chỉ là cảm biến phổ thông.",
  "Sự kiện ẩn danh được gửi lên và ghép với Traffic-SM để biết nguy hiểm xảy ra ở đoạn đường nào.",
], 0.5, 1.35, 5.1, 3.4, 15, "problem-bullets");
stat(s, 6.0, 1.35, 3.5, "4 mức", "cảnh báo, từ nhắc nhẹ đến báo động", C.accent2, "stat-levels");
stat(s, 6.0, 2.65, 3.5, "3 giây", "nhắm mắt liên tục là mức 4", C.accent3, "stat-3s");
stat(s, 6.0, 3.95, 3.5, "0 video", "rời thiết bị; chỉ gửi số đo và sự kiện", C.accent1, "stat-privacy");
notes(s, "Bốn khó khăn chính: báo nhầm làm hỏng sản phẩm, không nhìn thấy mắt không được coi là nhắm mắt, dữ liệu công khai khác miền triển khai, và thiết bị biên hạn chế tài nguyên.");

// ======================================================================= 3. Ý tưởng cốt lõi
pres.addSection({ title: "Phương pháp" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Cảm biến có sẵn, quyết định tự viết");
const stages = [["Camera", "IR / webcam", C.accent4], ["Cảm biến", "mặt, điểm mốc, tay", C.accent1], ["Số đo", "EAR, MAR, góc đầu", C.accent1], ["Thuật toán", "tự viết, 4 mức", C.accent2], ["Cảnh báo", "còi, LED, sự kiện", C.accent3]];
stages.forEach(([a, b, col], i) => {
  const x = 0.5 + i * 1.82;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.45, w: 1.55, h: 1.15, fill: { color: col }, line: { color: col, width: 0 }, rectRadius: 0.08, objectName: `stage-${i}` });
  s.addText([{ text: a, options: { bold: true, fontSize: 15, breakLine: true } }, { text: b, options: { fontSize: 11 } }], { x, y: 1.45, w: 1.55, h: 1.15, align: "center", valign: "middle", color: C.background1, margin: 4, isTextBox: true, objectName: `stage-${i}-text` });
  if (i < 4) s.addText("→", { x: x + 1.55, y: 1.8, w: 0.27, h: 0.4, align: "center", fontSize: 18, color: C.accent4, margin: 0, isTextBox: true, objectName: `arrow-${i}` });
});
card(s, 0.5, 2.95, 4.3, 2.0, "col-sensor");
s.addText("Cảm biến (mạng nơ-ron có sẵn)", { x: 0.7, y: 3.05, w: 3.9, h: 0.35, fontSize: 15, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "col-sensor-h" });
bullets(s, ["MediaPipe Face, Hand, Pose Landmarker trên PC", "Thay bằng mô hình SDK Kendryte K230 trên chip", "Chỉ cho ra tọa độ và góc"], 0.7, 3.45, 3.9, 1.4, 13, "col-sensor-b");
card(s, 5.2, 2.95, 4.3, 2.0, "col-decision");
s.addText("Quyết định (tự thiết kế)", { x: 5.4, y: 3.05, w: 3.9, h: 0.35, fontSize: 15, bold: true, color: C.accent2, margin: 0, isTextBox: true, objectName: "col-decision-h" });
bullets(s, ["EAR, PERCLOS, ngân sách chú ý, cổng chuyển động", `Chỉ khoảng ${vn(bench.engine_only_ms, 2)} ms mỗi khung`, "Giải thích được, chỉnh ngưỡng bằng một tệp YAML"], 5.4, 3.45, 3.9, 1.4, 13, "col-decision-b");
notes(s, "Lý do không dùng bộ phân loại hành vi: State Farm không có lớp nhắm mắt hay ngáp, quyết định cần giải thích được, và phần quyết định rất nhẹ nên chạy được trên chip K230.");

// ======================================================================= 4. Kiến trúc
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Kiến trúc hệ thống");
img(s, "arch.png", 0.4, 1.2, 5.9, "sơ đồ kiến trúc");
[["DF-Edge", "Trên xe: tự quyết định, hoạt động khi mất mạng.", C.accent2], ["DF-Cloud", "Gateway ẩn danh hóa: mã tài xế thành mã chuyến đi.", C.accent4], ["Traffic-SM", "Nhận GPS, map matching, mức tắc nghẽn; dùng nguyên vẹn.", C.accent1]].forEach(([h, t, col], i) => {
  const y = 1.3 + i * 1.2;
  card(s, 6.55, y, 3.0, 1.05, `arch-card-${i}`);
  s.addText([{ text: h, options: { bold: true, fontSize: 14, color: col, breakLine: true } }, { text: t, options: { fontSize: 12, color: C.text1 } }], { x: 6.7, y: y + 0.05, w: 2.75, h: 0.95, margin: 0, valign: "middle", isTextBox: true, objectName: `arch-card-${i}-text` });
});
notes(s, "Video không bao giờ rời thiết bị. Gateway bỏ mã thiết bị trước khi chuyển GPS sang Traffic-SM; ánh xạ chuyến-thiết bị nằm riêng trong một kho hạn chế.");

// ======================================================================= 5. Các số đo
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Các số đo hình học");
img(s, "ear.png", 0.4, 1.3, 4.7, "công thức EAR");
s.addText("EAR chuẩn hóa theo mắt mở của từng tài xế; nhắm khi EAR chuẩn hóa dưới 0,5.", { x: 0.5, y: 3.25, w: 4.5, h: 0.6, fontSize: 12, italic: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "ear-note" });
[["PERCLOS", "Tỉ lệ thời gian nhắm trong 60 s, tính theo thời gian, loại khoảng không biết.", C.accent1],
 ["MAR", "Độ mở miệng; ngáp khi vượt ngưỡng liên tục từ 1,5 s.", C.accent2],
 ["Tư thế đầu", "Ma trận biến đổi MediaPipe; pitch dương là cúi xuống.", C.accent4],
 ["Tay – đầu", "Khoảng cách tay tới tai và miệng, chuẩn hóa theo cỡ đầu.", C.accent3]].forEach(([h, t, col], i) => {
  const y = 1.3 + i * 0.95;
  chip(s, 5.35, y + 0.1, i + 1, col);
  s.addText([{ text: h, options: { bold: true, fontSize: 14, breakLine: true } }, { text: t, options: { fontSize: 12 } }], { x: 5.95, y, w: 3.6, h: 0.85, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `metric-${i}` });
});
card(s, 0.5, 3.95, 4.5, 1.0, "unknown-card");
s.addText("Quan sát ba trạng thái: không nhìn thấy mắt thì là KHÔNG BIẾT, tuyệt đối không suy ra nhắm mắt.", { x: 0.65, y: 4.0, w: 4.2, h: 0.9, fontSize: 13, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "unknown-text" });
notes(s, "EAR tính trên toạ độ điểm ảnh chứ không dùng toạ độ chuẩn hoá vì toạ độ chuẩn hoá làm méo tỉ lệ khung hình. Ý tưởng PERCLOS theo thời gian lấy từ dự án mã nguồn mở driver-state-detection.");

// ======================================================================= 6. Bốn mức
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Bốn mức cảnh báo");
img(s, "fsm.png", 0.4, 1.3, 5.0, "máy trạng thái");
const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent4 }, align: "center", fontSize: 12 } });
const row = (a, b, c, col) => [{ text: a, options: { bold: true, align: "center", color: C.background1, fill: { color: col }, fontSize: 12 } }, { text: b, options: { align: "center", fontSize: 12, color: C.text1 } }, { text: c, options: { fontSize: 11, color: C.text1 } }];
s.addTable([[hdr("Mức"), hdr("Nhắm liên tục"), hdr("Đầu ra")],
  row("1", "≥ 0,5 s", "LED vàng, một tiếng bíp", C.accent6),
  row("2", "≥ 1,0 s", "LED cam, lời nhắc", C.accent2),
  row("3", "≥ 2,0 s", "LED đỏ, chuông ngắt quãng", C.accent3),
  row("4", "≥ 3,0 s", "Còi liên tục: báo động", C.text2)],
  { x: 5.6, y: 1.35, w: 3.9, colW: [0.7, 1.2, 2.0], border: { type: "solid", pt: 0.5, color: "D9DEE7" }, rowH: 0.42, valign: "middle", objectName: "levels-table" });
s.addText("Chỉ khi xe chạy: từ 10 km/h liên tục 3 s; dừng khi dưới 3 km/h liên tục 5 s.", { x: 5.6, y: 3.65, w: 3.9, h: 0.6, fontSize: 12, color: C.text1, margin: 0, isTextBox: true, objectName: "gate-note" });
s.addText("Cùng cơ chế áp dụng cho nhìn lệch, điện thoại, ngáp, gục đầu, mất mặt.", { x: 5.6, y: 4.3, w: 3.9, h: 0.6, fontSize: 12, italic: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "other-note" });
notes(s, "Mức 4 là báo động duy nhất. Các mức thấp chỉ nhắc để tài xế tự điều chỉnh, giảm báo nhầm gây khó chịu. Ngưỡng 10 và 3 km/h có hysteresis để không nhấp nháy khi kẹt xe; 10 km/h cũng là ngưỡng openpilot dùng.");

// ======================================================================= 7. Ngân sách chú ý
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Ngân sách chú ý: bắt người nhắn tin xen kẽ");
img(s, "budget.png", 0.5, 1.25, 7.0, "đồ thị ngân sách chú ý");
card(s, 7.7, 1.3, 1.85, 2.1, "budget-card");
s.addText([{ text: "Giảm đều khi mất tập trung, hồi phục dần khi nhìn đường.", options: { breakLine: true } }, { text: " ", options: { breakLine: true, fontSize: 6 } }, { text: "Liếc đường 0,3 s không đủ để xóa.", options: { bold: true } }], { x: 7.82, y: 1.4, w: 1.65, h: 1.9, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "budget-text" });
s.addText("Ý tưởng lấy từ openpilot; nếu đặt lại bộ đếm mỗi lần liếc đường thì người nhắn tin sẽ không bao giờ bị cảnh báo.", { x: 0.5, y: 4.4, w: 9.0, h: 0.6, fontSize: 13, color: C.text1, margin: 0, isTextBox: true, objectName: "budget-foot" });
notes(s, "Nhìn lệch w = 1, điện thoại w = 1,5. Với nhìn lệch liên tục các mức đạt sau 1,5; 2,5; 4,0 và 6,0 giây. Bài kiểm thử cũng xác nhận liếc gương dưới 1 giây không gây cảnh báo.");

// ======================================================================= 8. Kết quả nhắm mắt
pres.addSection({ title: "Kết quả" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Kết quả: thời lượng nhắm mắt và mức cảnh báo");
img(s, "closure.png", 0.4, 1.3, 5.6, "mức đạt theo thời lượng nhắm");
const rb = Object.fromEntries(cl.robust.map((r) => [r.closed_s, r]));
stat(s, 6.25, 1.3, 3.3, "3,00 s", "đạt mức 4, đúng yêu cầu", C.accent3, "stat-l4");
stat(s, 6.25, 2.55, 3.3, `${rb[3.5].level4_runs}/${rb[3.5].runs}`, "lần đạt mức 4 khi nhắm 3,5 s (có nhiễu, mất mặt 3%)", C.accent1, "stat-robust");
stat(s, 6.25, 3.8, 3.3, `${rb[0.3].level4_runs}/${rb[0.3].runs}`, "lần báo khi chỉ chớp mắt 0,3 s", C.accent2, "stat-blink");
s.addText("Xe dừng, nhắm mắt 10 s: không có sự kiện nào.", { x: 0.5, y: 4.55, w: 5.5, h: 0.4, fontSize: 13, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: "stopped-note" });
notes(s, `Thí nghiệm tổng hợp: hai ảnh thật đi qua MediaPipe (EAR mở ${vn(cl.ear_open, 3)}, EAR nhắm ${vn(cl.ear_closed, 3)}) rồi dựng chuỗi 15 khung/giây. Lưu ý dung sai 0,2 giây khiến nhắm khoảng 2,9 giây vẫn chạm mức 4 và nhắm 0,4 giây đã chạm mức 1. Đây là kiểm tra logic, không phải độ chính xác ngoài đời.`);

// ======================================================================= 9. Tín hiệu & giao diện
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Tín hiệu và giao diện demo");
img(s, "signals.png", 0.4, 1.2, 5.0, "chuỗi tín hiệu EAR, bộ đếm, mức");
img(s, "osd_levels.png", 5.55, 1.3, 4.0, "giao diện demo ở mức 0, 2, 4");
s.addText("Giao diện ở chế độ riêng tư: chỉ vẽ điểm mốc trên nền đen.", { x: 5.55, y: 2.95, w: 4.0, h: 0.5, fontSize: 12, italic: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "osd-note" });
bullets(s, ["EAR tụt dưới ngưỡng, bộ đếm tăng đều", "Mức leo từng bậc, xuống chậm sau khi hết", "Còi khác nhau theo mức"], 5.55, 3.5, 4.0, 1.4, 13, "signals-bullets");
notes(s, "Ngưỡng nhắm là 0,15 trước khi hiệu chỉnh xong và 0,5 lần EAR mắt mở sau khi hiệu chỉnh, nên đường ngưỡng đỏ tụt xuống ở giây thứ 11.");

// ======================================================================= 10. State Farm
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "State Farm: khoảng cách miền dữ liệu");
const classes = Object.keys(sf.detection);
const DT = sf.detection_total;
s.addChart(pres.charts.BAR, [
  { name: "Thấy mặt (Face Landmarker)", labels: classes, values: classes.map((c) => +(100 * sf.detection[c].face / sf.detection[c].n).toFixed(1)) },
  { name: "Có tư thế cơ thể (Pose Landmarker)", labels: classes, values: classes.map((c) => +(100 * sf.detection[c].pose / sf.detection[c].n).toFixed(1)) },
], {
  x: 0.4, y: 1.2, w: 5.9, h: 3.7, barDir: "col", barGrouping: "clustered", chartColors: [HEX.face, HEX.pose],
  showTitle: true, title: "% ảnh phát hiện được theo lớp (tập test)", titleFontSize: 12, titleColor: HEX.axis, titleFontFace: "+mn-lt",
  showLegend: true, legendPos: "b", legendFontSize: 10, legendColor: HEX.axis, legendFontFace: "+mn-lt",
  catAxisLabelColor: HEX.axis, catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt",
  valAxisLabelColor: HEX.axis, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt", valAxisMaxVal: 100, valAxisMinVal: 0,
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" }, objectName: "chart-detection",
});
stat(s, 6.5, 1.3, 3.0, pc(DT.face, DT.n), `ảnh thấy mặt (${DT.face}/${DT.n})`, C.accent3, "stat-face");
stat(s, 6.5, 2.6, 3.0, pc(DT.pose, DT.n), "ảnh có tư thế cơ thể", C.accent1, "stat-pose");
stat(s, 6.5, 3.9, 3.0, String(DT.eyes), "ảnh có mắt đủ rõ để đo EAR", C.accent2, "stat-eyes");
notes(s, "Camera ghế phụ nhìn tài xế nghiêng gần 90 độ nên thuật toán dựa trên mắt không đánh giá được trên bộ này. Lớp c9, nói chuyện với hành khách, quay mặt về camera nên thấy mặt tới 84%. State Farm chỉ dùng được cho luật tay–đầu với mô hình tư thế cơ thể.");

// ======================================================================= 11. Luật tay-đầu
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Luật tay – đầu trên State Farm");
img(s, "sf_samples.png", 0.4, 1.25, 5.3, "mẫu kết quả luật tay-đầu");
const ph = sf.rules.phone, dr = sf.rules.drink, nr = sf.any_hand_near_head;
const th = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent4 }, align: "center", fontSize: 11 } });
const td = (t, a = "center") => ({ text: t, options: { align: a, fontSize: 11, color: C.text1 } });
const f = (r) => `${vn(r.precision, 2)} / ${vn(r.recall, 2)} / ${vn(r.f1, 2)}`;
s.addTable([[th("Luật"), th("Test P / R / F1"), th("AUC test")],
  [td("Gọi điện", "left"), td(f(ph.test_at_best)), td(vn(ph.auc_test, 2))],
  [td("Uống nước", "left"), td(f(dr.test_at_best)), td(vn(dr.auc_test, 2))]],
  { x: 5.9, y: 1.3, w: 3.65, colW: [1.1, 1.75, 0.8], border: { type: "solid", pt: 0.5, color: "D9DEE7" }, rowH: 0.38, valign: "middle", objectName: "rules-table" });
stat(s, 5.9, 2.7, 1.75, pc(nr.c0.flagged, nr.c0.n), "báo nhầm ở c0 (lái an toàn)", C.accent1, "stat-c0");
stat(s, 7.8, 2.7, 1.75, pc(nr.c4.flagged, nr.c4.n), "gắn cờ ở c4 (gọi điện)", C.accent3, "stat-c4");
s.addText("Khiêm tốn: không phân biệt được gọi điện, uống nước, chải tóc và không bắt được nhắn tin (dưới 5%).", { x: 5.9, y: 4.0, w: 3.65, h: 0.9, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "rules-note" });
notes(s, "Ngưỡng chọn trên tập val (4 tài xế) và giữ nguyên khi đánh giá trên tập test (4 tài xế khác). F1 giảm so với val vì tài xế khác. Báo cáo học sâu trước đây đạt macro-F1 khoảng 0,82 cho bài toán 6 nhóm; hai con số không so trực tiếp nhưng cho thấy luật hình học kém hơn nhiều một bộ phân loại học trên đúng dữ liệu này. Đổi lại luật không cần dữ liệu huấn luyện và giải thích được.");

// ======================================================================= 12. Đám mây
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Đám mây và tích hợp Traffic-SM");
[["Thiết bị", "GPS gọn + sự kiện", C.accent2], ["device-gateway", "ẩn danh, đổi định dạng", C.accent4], ["Traffic-SM", "gps.raw → matched", C.accent1]].forEach(([a, b, col], i) => {
  const x = 0.5 + i * 3.1;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.5, h: 0.95, fill: { color: col }, line: { color: col, width: 0 }, rectRadius: 0.08, objectName: `cloud-${i}` });
  s.addText([{ text: a, options: { bold: true, fontSize: 14, breakLine: true } }, { text: b, options: { fontSize: 11 } }], { x, y: 1.3, w: 2.5, h: 0.95, align: "center", valign: "middle", color: C.background1, margin: 4, isTextBox: true, objectName: `cloud-${i}-text` });
  if (i < 2) s.addText("→", { x: x + 2.5, y: 1.5, w: 0.6, h: 0.5, align: "center", fontSize: 22, color: C.accent4, margin: 0, isTextBox: true, objectName: `cloud-arrow-${i}` });
});
s.addTable([
  [th("Kiểm tra chạy thử đầu cuối"), th("Kết quả")],
  [td("Điểm GPS qua gateway", "left"), td("49 điểm, 3 chuyến: nhận 49, từ chối 0", "left")],
  [td("Mã tài xế phía ingest", "left"), td("là mã chuyến đi, không có mã thiết bị", "left")],
  [td("Sự kiện lưu", "left"), td("6 sự kiện, 0 trùng, không có mã thiết bị", "left")],
  [td("Mất mạng rồi có lại", "left"), td("7 bản ghi gửi bù, outbox về 0", "left")],
  [td("Định dạng so với 200 dòng thật", "left"), td("time và t_timestamp khớp 200/200", "left")]],
  { x: 0.5, y: 2.55, w: 9.0, colW: [3.6, 5.4], border: { type: "solid", pt: 0.5, color: "D9DEE7" }, rowH: 0.36, valign: "middle", objectName: "e2e-table" });
s.addText("Phía nhận là máy chủ giả lập tái hiện quy tắc kiểm tra của Traffic-SM (đọc từ mã nguồn Go); chưa chạy với Traffic-SM thật.", { x: 0.5, y: 4.85, w: 9.0, h: 0.4, fontSize: 12, bold: true, color: C.accent3, margin: 0, isTextBox: true, objectName: "e2e-caveat" });
notes(s, "Cổng ingest của Traffic-SM rất chặt: đủ mười một trường số, time theo UTC+7, t_timestamp có phút trùng time, vehicle_type chỉ nhận car hoặc bike. Gateway đã được kiểm tra bằng cách chạy lại trên 200 dòng thật của fake_gps.csv.");

// ======================================================================= 13. Hiệu năng
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Hiệu năng và kiểm thử");
stat(s, 0.5, 1.3, 2.85, vn(bench.sensor_ms.mean, 1) + " ms", "cảm biến mặt + tay mỗi khung", C.accent1, "stat-sensor");
stat(s, 3.55, 1.3, 2.85, vn(bench.engine_only_ms, 2) + " ms", "thuật toán quyết định mỗi khung", C.accent2, "stat-engine");
stat(s, 6.6, 1.3, 2.9, "~" + vn(bench.pipeline_fps, 0), "khung/giây trên CPU", C.accent4, "stat-fps");
s.addChart(pres.charts.BAR, [{ name: "ms mỗi khung", labels: ["Cảm biến (mặt + tay)", "Thuật toán quyết định"], values: [+bench.sensor_ms.mean.toFixed(2), +bench.engine_only_ms.toFixed(2)] }], {
  x: 0.5, y: 2.7, w: 4.7, h: 2.3, barDir: "bar", chartColors: [HEX.teal, HEX.orange], showTitle: true, title: "Thời gian xử lý mỗi khung (ms, CPU)",
  titleFontSize: 12, titleColor: HEX.axis, titleFontFace: "+mn-lt", showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
  dataLabelColor: HEX.axis, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.00",
  catAxisLabelColor: HEX.axis, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
  valAxisLabelColor: HEX.axis, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt", valAxisMaxVal: 40, valAxisMinVal: 0,
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" }, objectName: "chart-bench",
});
card(s, 5.4, 2.7, 4.1, 2.3, "tests-card");
s.addText([{ text: "69 bài kiểm thử đạt", options: { bold: true, fontSize: 16, color: C.accent1, breakLine: true } },
  { text: "50 bài thiết bị, 19 bài gateway", options: { fontSize: 13, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "Golden trace: cùng chuỗi đặc trưng thì cùng chuỗi sự kiện, dùng để kiểm bản cài đặt trên K230.", options: { fontSize: 12 } }],
  { x: 5.55, y: 2.8, w: 3.8, h: 2.1, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "tests-text" });
notes(s, `Đo trên ${bench.machine.cpu}, khung hình ${bench.frame_size[0]}x${bench.frame_size[1]}, Python ${bench.machine.python}, MediaPipe ${bench.machine.mediapipe}. Phần quyết định không phải là điểm nghẽn. Chưa đo trên chip K230.`);

// ======================================================================= 14. Hạn chế
pres.addSection({ title: "Kết luận" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết luận" });
title(s, "Hạn chế và hướng phát triển");
card(s, 0.5, 1.3, 4.4, 3.5, "limits-card");
s.addText("Hạn chế", { x: 0.7, y: 1.4, w: 4.0, h: 0.4, fontSize: 17, bold: true, color: C.accent3, margin: 0, isTextBox: true, objectName: "limits-h" });
bullets(s, ["Chưa thử webcam thật và người lái thật; thí nghiệm nhắm mắt dùng ảnh một người", "Chưa có NTHU-DDD, YawDD, DMD: chưa đo báo nhầm trên giờ lái bình thường", "Luật tay–đầu yếu (F1 0,34 và 0,19)", "Chưa chạy trên K230 và Traffic-SM thật; chưa có bảo mật"], 0.7, 1.9, 4.0, 2.8, 14, "limits-b");
card(s, 5.1, 1.3, 4.4, 3.5, "next-card");
s.addText("Hướng phát triển", { x: 5.3, y: 1.4, w: 4.0, h: 0.4, fontSize: 17, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "next-h" });
bullets(s, ["Đánh giá trên dữ liệu mặt nhìn thẳng, chỉnh ngưỡng; thu video tự quay có đồng ý", "Chuyển cảm biến sang mô hình SDK K230, đối chiếu bằng golden trace", "Ghép Traffic-SM thật: bản đồ rủi ro, ngữ cảnh đường về thiết bị", "Bảo mật: mTLS, ACL, cập nhật có chữ ký"], 5.3, 1.9, 4.0, 2.8, 14, "next-b");
notes(s, "Mọi ngưỡng hiện là giá trị khởi điểm. Điều đáng tin nhất đã làm được là logic quyết định, độ trễ và tính ẩn danh; điều chưa chứng minh được là độ chính xác ngoài đời.");

// ======================================================================= 15. Kết luận
s = pres.addSlide({ masterName: "DARK_END", sectionTitle: "Kết luận" });
s.addText("Kết luận", { placeholder: "title" });
[["Thuật toán tự thiết kế", "EAR, PERCLOS, ngân sách chú ý, cổng chuyển động, 4 mức"], ["Nhắm mắt 3 giây là mức 4", "đạt đúng 3,00 s; không báo nhầm chớp mắt; xe dừng thì im"], ["Nhẹ và kiểm thử được", `${vn(bench.engine_only_ms, 2)} ms mỗi khung; 69 bài kiểm thử; golden trace`], ["Trung thực về giới hạn", "State Farm chỉ thấy mặt ở 27,6% ảnh; luật tay–đầu F1 0,34"]].forEach(([h, t], i) => {
  const y = 1.5 + i * 0.85;
  chip(s, 0.6, y + 0.1, i + 1, [C.accent1, C.accent2, C.accent4, C.accent3][i]);
  s.addText([{ text: h, options: { bold: true, fontSize: 18, color: C.background1, breakLine: true } }, { text: t, options: { fontSize: 13, color: C.background2 } }], { x: 1.25, y, w: 8.2, h: 0.7, margin: 0, valign: "middle", isTextBox: true, objectName: `concl-${i}` });
});
s.addText("Xin cảm ơn thầy cô đã lắng nghe", { x: 0.6, y: 4.85, w: 8.8, h: 0.5, fontSize: 20, bold: true, color: C.accent6, margin: 0, isTextBox: true, objectName: "thanks", fontFace: THEME.headFontFace });
notes(s, "Em xin cảm ơn thầy cô. Em sẵn sàng trả lời câu hỏi.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("đã ghi", OUT);
})();
