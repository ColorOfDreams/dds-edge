// Slide bảo vệ DriveFocus (bản 2). Số liệu đọc từ report/results/*.json.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("C:/Users/Administrator/.claude/skills/synced/dbe77007-127d-4b91-a0e3-e928c7d3afaf_454ea1c5-c548-4cfd-9b1c-8402712b1e51/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "figs");
const RES = path.join(ROOT, "results");
const OUT = path.join(ROOT, "DriveFocus_Slide_DoAn3.pptx");
const J = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));
const sf = J("sf_analysis.json"), cl = J("closure.json"), bench = J("bench.json"), tests = J("tests.json"), bud = J("budget_series.json");
const vn = (x, nd = 1) => x.toFixed(nd).replace(".", ",");
const pc = (a, b, nd = 1) => vn((100 * a) / b, nd) + "%";

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
// màu chỉ nhận mã hex (biểu đồ, viền bảng)
const HEX = { grid: "D9DEE7", axis: "55606E", teal: "1B998B", orange: "F28F3B", red: "C8283C", navy: "3D5A80", grey: "9AA5B1", green: "4C9F70" };

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "DriveFocus: giám sát tài xế mất tập trung";
pres.author = "Trần Gia Huy";
const C = pres.SchemeColor;
const LEVEL_COLS = [C.accent5, C.accent6, C.accent2, C.accent3, C.text2];

// dải 5 chấm theo màu của 5 mức cảnh báo: dấu hiệu nhận diện của deck
const dots = (x, y, h, dark) => [{ image: { x, y, w: h * (5 * 120 + 4 * 50) / 120, h, path: path.join(FIG, dark ? "dots_dark.png" : "dots_light.png") } }];

pres.defineSlideMaster({
  title: "DARK",
  background: { color: "0F2A43" },
  objects: [
    ...dots(0.6, 2.42, 0.22, true),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.2, w: 5.0, h: 1.0, fontSize: 48, bold: true, color: C.background1, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.85, w: 4.9, h: 0.9, fontSize: 18, color: C.background2, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "TITLE_ONLY",
  background: { color: "FFFFFF" },
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent4, align: "right" },
  objects: [
    ...dots(8.55, 0.62, 0.14, false),
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 7.9, h: 0.8, fontSize: 28, bold: true, color: C.text1, margin: 0, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "DriveFocus  •  Đồ án 3", options: { x: 0.5, y: 5.2, w: 4, h: 0.3, fontSize: 10, color: C.accent4, margin: 0 } } },
  ],
});
pres.defineSlideMaster({
  title: "DARK_END",
  background: { color: "0F2A43" },
  objects: [
    ...dots(8.55, 0.62, 0.14, true),
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 7.5, h: 0.8, fontSize: 34, bold: true, color: C.background1, margin: 0, valign: "middle", align: "left" }, text: "" } },
  ],
});

const notes = (s, t) => s.addNotes(t);
const card = (s, x, y, w, h, name, fill = C.background2) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: 0.08, objectName: name });
const stat = (s, x, y, w, big, label, color = C.accent1, name = "stat", h = 1.15) => {
  card(s, x, y, w, h, name + "-card");
  s.addText(big, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.6, fontSize: 30, bold: true, color, margin: 0, isTextBox: true, objectName: name + "-value", fontFace: THEME.headFontFace });
  s.addText(label, { x: x + 0.15, y: y + 0.68, w: w - 0.3, h: h - 0.73, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: name + "-label" });
};
const chip = (s, x, y, n, color, d = 0.42) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 }, objectName: `chip-${n}` });
  s.addText(String(n), { x, y, w: d, h: d, align: "center", valign: "middle", fontSize: 14, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: `chip-${n}-n` });
};
const bullets = (s, items, x, y, w, h, fontSize = 14, name = "bullets") =>
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8 } })),
    { x, y, w, h, fontSize, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: name });
const img = (s, file, x, y, w, name) => {
  const p = path.join(FIG, file);
  const buf = fs.readFileSync(p);
  let iw, ih;
  if (buf.readUInt32BE(0) === 0x89504e47) { iw = buf.readUInt32BE(16); ih = buf.readUInt32BE(20); }
  else { let o = 2; while (o < buf.length) { const m = buf.readUInt16BE(o); const l = buf.readUInt16BE(o + 2); if (m >= 0xffc0 && m <= 0xffcf && m !== 0xffc4 && m !== 0xffc8 && m !== 0xffcc) { ih = buf.readUInt16BE(o + 5); iw = buf.readUInt16BE(o + 7); break; } o += 2 + l; } }
  const h = (w * ih) / iw;
  s.addImage({ path: p, x, y, w, h, objectName: name, altText: name });
  return h;
};
const title = (s, t) => s.addText(t, { placeholder: "title" });
const chartBase = () => ({
  titleFontSize: 12, titleColor: HEX.axis, titleFontFace: "+mn-lt",
  legendFontSize: 11, legendColor: HEX.axis, legendFontFace: "+mn-lt",
  catAxisLabelColor: HEX.axis, catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt",
  valAxisLabelColor: HEX.axis, valAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt",
  dataLabelColor: HEX.axis, dataLabelFontSize: 10, dataLabelFontFace: "+mn-lt",
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" },
});
const th = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent4 }, align: "center", fontSize: 12 } });
const td = (t, a = "center", extra = {}) => ({ text: t, options: { align: a, fontSize: 12, color: C.text1, ...extra } });
const tableBorder = () => ({ type: "solid", pt: 0.5, color: HEX.grid });

// ======================================================================= 1. Bìa
pres.addSection({ title: "Mở đầu" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Mở đầu" });
s.addText("DriveFocus", { placeholder: "title" });
s.addText("Giám sát tài xế buồn ngủ và mất tập trung bằng điểm mốc khuôn mặt", { placeholder: "body" });
s.addText([
  { text: "Đồ án 3", options: { breakLine: true, bold: true } },
  { text: "Sinh viên: Trần Gia Huy  •  MSSV 10123169  •  Lớp 12423TN", options: { breakLine: true } },
  { text: "Giảng viên hướng dẫn: PGS.TS. Nguyễn Minh Tiến", options: { breakLine: true } },
  { text: "Trường Đại học Công nghệ Kỹ thuật Hưng Yên, 2026" },
], { x: 0.6, y: 3.95, w: 5.2, h: 1.2, fontSize: 13, color: C.background2, margin: 0, valign: "top", isTextBox: true, objectName: "author-block" });
const hTitleImg = img(s, "title_osd.png", 5.85, 1.0, 3.6, "giao diện demo ở chế độ riêng tư, mức 4");
s.addText("Giao diện demo, mức 4: nhắm mắt liên tục 3 giây", { x: 5.85, y: 1.0 + hTitleImg + 0.08, w: 3.6, h: 0.3, fontSize: 11, italic: true, color: C.accent6, margin: 0, isTextBox: true, objectName: "caption-title-img" });
notes(s, "Em xin chào thầy cô. Đề tài của em là DriveFocus, một hệ thống giám sát tài xế đặt trên xe. Hệ thống tự cảnh báo ngay trên thiết bị, không cần mạng và không gửi video đi đâu. Hình bên phải là giao diện demo, chỉ vẽ các điểm mốc trên khuôn mặt, đang ở mức báo động 4.");

// ======================================================================= 2. Bài toán
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Mở đầu" });
title(s, "Bài toán và mục tiêu");
bullets(s, [
  "Camera trong xe theo dõi tài xế, cảnh báo ngay trên thiết bị và chỉ khi xe đang chạy.",
  "Bốn mức cảnh báo. Mức 4 là báo động, ví dụ khi nhắm mắt liên tục từ 3 giây.",
  "Quyết định bằng thuật toán; mạng nơ-ron chỉ dùng để lấy điểm mốc.",
  "Sự kiện đã ẩn danh được gửi lên máy chủ và nối với hệ thống giao thông Traffic-SM.",
], 0.5, 1.35, 5.1, 3.6, 16, "problem-bullets");
stat(s, 6.0, 1.35, 3.5, "4 mức", "cảnh báo, từ nhắc nhẹ đến báo động", C.accent2, "stat-levels");
stat(s, 6.0, 2.65, 3.5, "3 giây", "nhắm mắt liên tục là mức 4", C.accent3, "stat-3s");
stat(s, 6.0, 3.95, 3.5, "0 video", "gửi ra khỏi xe, chỉ gửi số đo và sự kiện", C.accent1, "stat-privacy");
notes(s, "Khó nhất của bài toán là tránh báo nhầm: chớp mắt, liếc gương hay dừng đèn đỏ đều không phải nguy hiểm. Ngoài ra khi không nhìn rõ mắt thì hệ thống không được kết luận là đang nhắm mắt.");

// ======================================================================= 3. Ý tưởng chính
pres.addSection({ title: "Phương pháp" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Cảm biến có sẵn, quyết định tự viết");
const stages = [["Camera", "IR / webcam", C.accent4], ["Cảm biến", "mặt, điểm mốc, tay", C.accent1], ["Số đo", "EAR, MAR, góc đầu", C.accent1], ["Thuật toán", "4 mức cảnh báo", C.accent2], ["Cảnh báo", "còi, LED, sự kiện", C.accent3]];
stages.forEach(([a, b2, col], i) => {
  const x = 0.5 + i * 1.82;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.4, w: 1.55, h: 1.15, fill: { color: col }, line: { color: col, width: 0 }, rectRadius: 0.08, objectName: `stage-${i}` });
  s.addText([{ text: a, options: { bold: true, fontSize: 16, breakLine: true } }, { text: b2, options: { fontSize: 12 } }], { x, y: 1.4, w: 1.55, h: 1.15, align: "center", valign: "middle", color: C.background1, margin: 4, isTextBox: true, objectName: `stage-${i}-text` });
  if (i < 4) s.addText("→", { x: x + 1.55, y: 1.75, w: 0.27, h: 0.4, align: "center", fontSize: 18, color: C.accent4, margin: 0, isTextBox: true, objectName: `arrow-${i}` });
});
card(s, 0.5, 2.9, 4.3, 2.1, "col-sensor");
s.addText("Cảm biến (mô hình có sẵn)", { x: 0.7, y: 3.0, w: 3.9, h: 0.4, fontSize: 16, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "col-sensor-h" });
bullets(s, ["MediaPipe Face, Hand, Pose trên máy tính", "Trên chip: mô hình có sẵn trong SDK K230", "Chỉ trả về toạ độ điểm và góc"], 0.7, 3.45, 3.9, 1.5, 14, "col-sensor-b");
card(s, 5.2, 2.9, 4.3, 2.1, "col-decision");
s.addText("Quyết định (tự viết)", { x: 5.4, y: 3.0, w: 3.9, h: 0.4, fontSize: 16, bold: true, color: C.accent2, margin: 0, isTextBox: true, objectName: "col-decision-h" });
bullets(s, ["EAR, PERCLOS, ngân sách chú ý", `Khoảng ${vn(bench.engine_only_ms, 2)} ms mỗi khung hình`, "Ngưỡng nằm trong một tệp YAML"], 5.4, 3.45, 3.9, 1.5, 14, "col-decision-b");
notes(s, "Em không huấn luyện mô hình phân loại hành vi vì bộ State Farm không có nhãn nhắm mắt hay ngáp. Thay vào đó em dùng các mô hình có sẵn để lấy điểm mốc, rồi tự viết phần quyết định. Phần này rất nhẹ nên có thể chạy trên chip K230.");

// ======================================================================= 4. Kiến trúc
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Kiến trúc hệ thống");
img(s, "arch.png", 0.4, 1.2, 5.9, "sơ đồ kiến trúc");
[["DF-Edge", "Trên xe, tự quyết định, chạy được khi mất mạng.", C.accent2], ["DF-Cloud", "Gateway thay mã tài xế bằng mã chuyến đi.", C.accent4], ["Traffic-SM", "Nhận GPS, khớp bản đồ, tính tắc nghẽn.", C.accent1]].forEach(([h, t, col], i) => {
  const y = 1.25 + i * 1.25;
  card(s, 6.55, y, 3.0, 1.1, `arch-card-${i}`);
  s.addText([{ text: h, options: { bold: true, fontSize: 16, color: col, breakLine: true } }, { text: t, options: { fontSize: 13, color: C.text1 } }], { x: 6.7, y: y + 0.05, w: 2.75, h: 1.0, margin: 0, valign: "middle", isTextBox: true, objectName: `arch-card-${i}-text` });
});
notes(s, "Video không bao giờ rời khỏi thiết bị. Gateway bỏ mã thiết bị trước khi chuyển GPS sang Traffic-SM, bảng ghép chuyến đi với thiết bị được lưu riêng.");

// ======================================================================= 5. Số đo
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Các số đo hình học");
img(s, "ear.png", 0.4, 1.3, 4.7, "công thức EAR");
s.addText("Chia EAR cho EAR lúc mở mắt của chính tài xế; mắt nhắm khi kết quả nhỏ hơn 0,5.", { x: 0.5, y: 3.25, w: 4.5, h: 0.6, fontSize: 13, italic: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "ear-note" });
[["PERCLOS", "Tỉ lệ thời gian nhắm mắt trong 60 giây.", C.accent1],
 ["MAR", "Độ mở miệng; ngáp khi há miệng từ 1,5 giây.", C.accent2],
 ["Tư thế đầu", "Ma trận biến đổi của MediaPipe; pitch dương là cúi.", C.accent4],
 ["Tay và đầu", "Khoảng cách tay tới tai, tới miệng.", C.accent3]].forEach(([h, t, col], i) => {
  const y = 1.3 + i * 0.95;
  chip(s, 5.35, y + 0.12, i + 1, col);
  s.addText([{ text: h, options: { bold: true, fontSize: 15, breakLine: true } }, { text: t, options: { fontSize: 13 } }], { x: 5.95, y, w: 3.6, h: 0.85, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: `metric-${i}` });
});
card(s, 0.5, 3.95, 4.5, 1.0, "unknown-card");
s.addText("Không nhìn rõ mắt thì ghi là không xác định, không bao giờ coi là nhắm mắt.", { x: 0.65, y: 4.0, w: 4.2, h: 0.9, fontSize: 14, bold: true, color: C.text1, margin: 0, valign: "middle", isTextBox: true, objectName: "unknown-text" });
notes(s, "EAR tính theo toạ độ điểm ảnh. Cách tính PERCLOS theo thời gian em tham khảo từ dự án driver-state-detection trên GitHub.");

// ======================================================================= 6. Bốn mức
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Bốn mức cảnh báo");
const lv = [["Bình thường", "mức 0"], ["Nhắc nhẹ", "mức 1"], ["Cảnh báo", "mức 2"], ["Nguy hiểm", "mức 3"], ["Báo động", "mức 4"]];
lv.forEach(([a, b2], i) => {
  const x = 0.5 + i * 1.82, col = LEVEL_COLS[i];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 1.55, h: 0.95, fill: { color: col }, line: { color: col, width: 0 }, rectRadius: 0.08, objectName: `level-${i}` });
  s.addText([{ text: a, options: { bold: true, fontSize: 15, breakLine: true } }, { text: b2, options: { fontSize: 12 } }], { x, y: 1.3, w: 1.55, h: 0.95, align: "center", valign: "middle", color: i === 1 ? C.text1 : C.background1, margin: 4, isTextBox: true, objectName: `level-${i}-text` });
  if (i < 4) s.addText("→", { x: x + 1.55, y: 1.55, w: 0.27, h: 0.4, align: "center", fontSize: 18, color: C.accent4, margin: 0, isTextBox: true, objectName: `level-arrow-${i}` });
});
s.addText("Lên mức ngay khi đủ điều kiện, xuống từng bậc sau 1, 1, 2 và 3 giây để không nhấp nháy.", { x: 0.5, y: 2.35, w: 9.0, h: 0.35, fontSize: 13, italic: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "fsm-note" });
const lvRow = (n, a, b2, i) => [{ text: n, options: { bold: true, align: "center", color: i === 1 ? C.text1 : C.background1, fill: { color: LEVEL_COLS[i] }, fontSize: 13 } }, td(a), td(b2, "left")];
s.addTable([[th("Mức"), th("Nhắm mắt liên tục"), th("Đầu ra")],
  lvRow("1", "≥ 0,5 giây", "LED vàng, một tiếng bíp", 1),
  lvRow("2", "≥ 1,0 giây", "LED cam, lời nhắc", 2),
  lvRow("3", "≥ 2,0 giây", "LED đỏ, chuông ngắt quãng", 3),
  lvRow("4", "≥ 3,0 giây", "Còi liên tục: báo động", 4)],
  { x: 0.5, y: 2.85, w: 5.6, colW: [0.8, 1.8, 3.0], border: tableBorder(), rowH: 0.42, valign: "middle", objectName: "levels-table" });
card(s, 6.35, 2.85, 3.15, 2.1, "gate-card");
s.addText([{ text: "Chỉ khi xe chạy", options: { bold: true, fontSize: 15, color: C.accent1, breakLine: true } },
  { text: "Chạy: từ 10 km/h trong 3 giây", options: { fontSize: 13, breakLine: true } },
  { text: "Dừng: dưới 3 km/h trong 5 giây", options: { fontSize: 13, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "Nhìn lệch, điện thoại, ngáp, gục đầu cũng dùng 4 mức này.", options: { fontSize: 12, italic: true } }],
  { x: 6.5, y: 2.95, w: 2.9, h: 1.9, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "gate-text" });
notes(s, "Chỉ mức 4 là báo động, các mức thấp hơn chỉ nhắc nhở để tài xế tự điều chỉnh. Hai ngưỡng tốc độ khác nhau giúp hệ thống không bật tắt liên tục khi xe đi chậm lúc kẹt xe.");

// ======================================================================= 7. Ngân sách chú ý
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Phương pháp" });
title(s, "Ngân sách chú ý");
s.addChart(pres.charts.LINE, [
  { name: "Nhìn lệch liên tục", labels: bud.t.map((x) => String(x).replace(".", ",")), values: bud.look },
  { name: "Nhắn tin, 2 giây lại liếc đường 0,3 giây", labels: bud.t.map((x) => String(x).replace(".", ",")), values: bud.text },
], {
  ...chartBase(), x: 0.4, y: 1.2, w: 6.1, h: 3.85, chartColors: [HEX.navy, HEX.orange], lineSize: 2, lineDataSymbol: "none",
  showTitle: true, title: "Ngân sách chú ý A theo thời gian (giây)", showLegend: true, legendPos: "b",
  valAxisMinVal: 0, valAxisMaxVal: 1, valAxisMajorUnit: 0.25, catAxisLabelFrequency: 20, objectName: "chart-budget",
});
card(s, 6.75, 1.3, 2.8, 3.7, "budget-card");
s.addText([{ text: "Cách hoạt động", options: { bold: true, fontSize: 15, color: C.accent2, breakLine: true } },
  { text: "Mất tập trung thì A giảm dần, nhìn lại đường thì A tăng dần.", options: { fontSize: 13, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "A dưới 0,75; 0,58; 0,33 là mức 1, 2, 3. A về 0 là mức 4.", options: { fontSize: 13, breakLine: true } },
  { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "Liếc đường 0,3 giây không đủ để hồi lại, nên vẫn cảnh báo người nhắn tin.", options: { fontSize: 13, bold: true } }],
  { x: 6.9, y: 1.4, w: 2.5, h: 3.5, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "budget-text" });
notes(s, "Ý tưởng này em lấy từ dự án openpilot. Nếu mỗi lần liếc đường lại đặt bộ đếm về 0 thì người vừa lái vừa nhắn tin sẽ không bao giờ bị cảnh báo. Đường màu xanh là nhìn lệch liên tục, về 0 sau đúng 6 giây.");

// ======================================================================= 8. Kết quả nhắm mắt
pres.addSection({ title: "Kết quả" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Thời gian nhắm mắt và mức cảnh báo");
s.addChart(pres.charts.BAR, [{ name: "Mức cao nhất", labels: cl.rows.map((r) => vn(r.closed_s, 1)), values: cl.rows.map((r) => r.max_level) }], {
  ...chartBase(), x: 0.4, y: 1.2, w: 5.8, h: 3.4, barDir: "col", chartColors: [HEX.teal], showLegend: false,
  showTitle: true, title: "Mức cao nhất theo thời gian nhắm mắt (giây)", showValue: true, dataLabelPosition: "outEnd",
  valAxisMinVal: 0, valAxisMaxVal: 4, valAxisMajorUnit: 1, objectName: "chart-closure",
});
const rb = Object.fromEntries(cl.robust.map((r) => [r.closed_s, r]));
stat(s, 6.45, 1.25, 3.1, "3,00 s", "lên mức 4, đúng yêu cầu", C.accent3, "stat-l4");
stat(s, 6.45, 2.5, 3.1, `${rb[3.5].level4_runs}/${rb[3.5].runs}`, "lần lên mức 4 khi nhắm 3,5 s, có nhiễu", C.accent1, "stat-robust");
stat(s, 6.45, 3.75, 3.1, `${rb[0.3].level4_runs}/${rb[0.3].runs}`, "lần cảnh báo khi chỉ chớp mắt 0,3 s", C.accent2, "stat-blink");
s.addText("Xe dừng, nhắm mắt 10 giây: không có cảnh báo nào.", { x: 0.5, y: 4.7, w: 5.7, h: 0.4, fontSize: 14, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: "stopped-note" });
notes(s, `Em dùng một ảnh thật và tạo ảnh mắt nhắm bằng cách phủ màu da lên vùng mắt (EAR mở ${vn(cl.ear_open, 3)}, EAR nhắm ${vn(cl.ear_closed, 3)}). Từ đó tạo chuỗi 15 khung/giây với nhiều thời gian nhắm khác nhau. Vì có dung sai 0,2 giây nên nhắm khoảng 2,9 giây vẫn lên mức 4. Thí nghiệm này chủ yếu kiểm tra logic, chưa phải độ chính xác ngoài thực tế.`);

// ======================================================================= 9. Tín hiệu & giao diện
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Tín hiệu và giao diện demo");
img(s, "signals.png", 0.4, 1.2, 5.0, "chuỗi tín hiệu EAR, thời gian nhắm, mức cảnh báo");
img(s, "osd_levels.png", 5.6, 1.3, 3.95, "giao diện demo ở mức 0, 2, 4");
bullets(s, ["EAR giảm dưới ngưỡng khi nhắm mắt", "Thời gian nhắm tăng đều, mức tăng từng bậc", "Mở mắt thì mức giảm dần, không tắt ngay", "Mỗi mức có một kiểu âm báo"], 5.6, 3.05, 3.95, 1.95, 14, "signals-bullets");
notes(s, "Đây là video thử gồm 14 giây mở mắt rồi 4 giây nhắm. Giao diện bên phải chỉ vẽ các điểm mốc trên nền đen, không lưu ảnh khuôn mặt.");

// ======================================================================= 10. State Farm
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Thử trên State Farm: ảnh chụp nghiêng");
const classes = Object.keys(sf.detection);
const DT = sf.detection_total;
s.addChart(pres.charts.BAR, [
  { name: "Tìm thấy mặt", labels: classes, values: classes.map((c) => +(100 * sf.detection[c].face / sf.detection[c].n).toFixed(1)) },
  { name: "Tìm thấy tư thế cơ thể", labels: classes, values: classes.map((c) => +(100 * sf.detection[c].pose / sf.detection[c].n).toFixed(1)) },
], {
  ...chartBase(), x: 0.4, y: 1.2, w: 5.9, h: 3.85, barDir: "col", barGrouping: "clustered", chartColors: [HEX.red, HEX.teal],
  showTitle: true, title: "% ảnh phát hiện được theo lớp (tập test)", showLegend: true, legendPos: "b",
  valAxisMaxVal: 100, valAxisMinVal: 0, objectName: "chart-detection",
});
stat(s, 6.55, 1.25, 3.0, pc(DT.face, DT.n), `ảnh tìm thấy mặt (${DT.face}/${DT.n})`, C.accent3, "stat-face");
stat(s, 6.55, 2.5, 3.0, pc(DT.pose, DT.n), "ảnh tìm thấy tư thế cơ thể", C.accent1, "stat-pose");
stat(s, 6.55, 3.75, 3.0, String(DT.eyes), "ảnh đủ rõ để đo EAR", C.accent2, "stat-eyes");
notes(s, "Camera State Farm đặt phía ghế phụ nên tài xế bị nhìn nghiêng gần 90 độ. Vì vậy em không đánh giá được phần nhắm mắt trên bộ này, chỉ đánh giá được luật tay gần đầu bằng mô hình tư thế cơ thể. Lớp c9 tìm thấy mặt nhiều vì tài xế quay sang nói chuyện, mặt hướng về camera.");

// ======================================================================= 11. Luật tay - đầu
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Luật bàn tay gần đầu trên State Farm");
const nr = sf.any_hand_near_head;
const handUp = new Set(["c2", "c4", "c6", "c8"]);
s.addChart(pres.charts.BAR, [
  { name: "Lớp có đưa tay lên đầu", labels: classes, values: classes.map((c) => handUp.has(c) ? +(100 * nr[c].flagged / nr[c].n).toFixed(1) : 0) },
  { name: "Lớp khác", labels: classes, values: classes.map((c) => handUp.has(c) ? 0 : +(100 * nr[c].flagged / nr[c].n).toFixed(1)) },
], {
  ...chartBase(), x: 0.4, y: 1.2, w: 5.5, h: 3.85, barDir: "col", barGrouping: "stacked", chartColors: [HEX.orange, HEX.grey],
  showTitle: true, title: "% ảnh bị đánh dấu theo lớp (tập test)", showLegend: true, legendPos: "b",
  valAxisMinVal: 0, valAxisMaxVal: 50, valAxisMajorUnit: 10, objectName: "chart-hand",
});
const ph = sf.rules.phone, dr = sf.rules.drink;
const prf = (r) => `${vn(r.precision, 2)} / ${vn(r.recall, 2)} / ${vn(r.f1, 2)}`;
s.addTable([[th("Luật"), th("Test P / R / F1"), th("AUC")],
  [td("Gọi điện", "left"), td(prf(ph.test_at_best)), td(vn(ph.auc_test, 2))],
  [td("Uống nước", "left"), td(prf(dr.test_at_best)), td(vn(dr.auc_test, 2))]],
  { x: 6.1, y: 1.3, w: 3.45, colW: [1.05, 1.75, 0.65], border: tableBorder(), rowH: 0.4, valign: "middle", objectName: "rules-table" });
stat(s, 6.1, 2.65, 1.65, pc(nr.c0.flagged, nr.c0.n), "báo nhầm ở lớp lái an toàn", C.accent1, "stat-c0", 1.25);
stat(s, 7.9, 2.65, 1.65, pc(nr.c4.flagged, nr.c4.n), "đánh dấu đúng ở lớp gọi điện tay trái", C.accent2, "stat-c4", 1.25);
s.addText("Chưa phân biệt được gọi điện, uống nước, chải tóc; không phát hiện được nhắn tin.", { x: 6.1, y: 4.05, w: 3.45, h: 0.95, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "rules-note" });
notes(s, "Ngưỡng được chọn trên tập val rồi giữ nguyên để thử trên tập test với các tài xế khác. Kết quả chưa tốt: F1 chỉ 0,34 với gọi điện và 0,19 với uống nước. Nếu coi là bộ phát hiện chung việc đưa tay lên đầu thì phân biệt được với lái xe bình thường, nhưng không biết đó là gọi điện hay uống nước.");

// ======================================================================= 12. Máy chủ
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Máy chủ và kết nối Traffic-SM");
[["Thiết bị", "GPS rút gọn, sự kiện", C.accent2], ["Gateway", "ẩn danh, đổi định dạng", C.accent4], ["Traffic-SM", "gps.raw → gps.matched", C.accent1]].forEach(([a, b2, col], i) => {
  const x = 0.5 + i * 3.1;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.3, w: 2.5, h: 0.95, fill: { color: col }, line: { color: col, width: 0 }, rectRadius: 0.08, objectName: `cloud-${i}` });
  s.addText([{ text: a, options: { bold: true, fontSize: 16, breakLine: true } }, { text: b2, options: { fontSize: 12 } }], { x, y: 1.3, w: 2.5, h: 0.95, align: "center", valign: "middle", color: C.background1, margin: 4, isTextBox: true, objectName: `cloud-${i}-text` });
  if (i < 2) s.addText("→", { x: x + 2.5, y: 1.5, w: 0.6, h: 0.5, align: "center", fontSize: 22, color: C.accent4, margin: 0, isTextBox: true, objectName: `cloud-arrow-${i}` });
});
s.addTable([
  [th("Nội dung kiểm tra"), th("Kết quả")],
  [td("Điểm GPS gửi qua gateway", "left"), td("49 điểm của 3 chuyến: nhận 49, từ chối 0", "left")],
  [td("Mã tài xế phía Traffic-SM", "left"), td("là mã chuyến đi, không có mã thiết bị", "left")],
  [td("Sự kiện được lưu", "left"), td("6 sự kiện, không trùng, không có mã thiết bị", "left")],
  [td("Mất mạng rồi có lại", "left"), td("7 bản ghi gửi lại thành công", "left")],
  [td("So định dạng với 200 dòng thật", "left"), td("khớp cả 200 dòng", "left")]],
  { x: 0.5, y: 2.55, w: 9.0, colW: [3.6, 5.4], border: tableBorder(), rowH: 0.36, valign: "middle", objectName: "e2e-table" });
s.addText("Lần chạy thử dùng máy chủ giả lập theo đúng quy tắc kiểm tra của Traffic-SM, chưa chạy với Traffic-SM thật.", { x: 0.5, y: 4.8, w: 9.0, h: 0.4, fontSize: 13, bold: true, color: C.accent3, margin: 0, isTextBox: true, objectName: "e2e-caveat" });
notes(s, "Cổng nhận dữ liệu của Traffic-SM kiểm tra khá chặt: đủ 11 trường số, giờ theo UTC+7, loại xe chỉ là car hoặc bike. Em kiểm tra bằng cách chạy lại trên 200 dòng dữ liệu thật của Traffic-SM.");

// ======================================================================= 13. Hiệu năng
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết quả" });
title(s, "Hiệu năng và kiểm thử");
stat(s, 0.5, 1.3, 2.85, vn(bench.sensor_ms.mean, 1) + " ms", "phần cảm biến mỗi khung", C.accent1, "stat-sensor");
stat(s, 3.55, 1.3, 2.85, vn(bench.engine_only_ms, 2) + " ms", "phần quyết định mỗi khung", C.accent2, "stat-engine");
stat(s, 6.6, 1.3, 2.9, "~" + vn(bench.pipeline_fps, 0), "khung hình/giây trên CPU", C.accent4, "stat-fps");
s.addChart(pres.charts.BAR, [{ name: "ms mỗi khung", labels: ["Cảm biến (mặt + tay)", "Quyết định"], values: [+bench.sensor_ms.mean.toFixed(2), +bench.engine_only_ms.toFixed(2)] }], {
  ...chartBase(), x: 0.5, y: 2.7, w: 4.9, h: 2.3, barDir: "bar", chartColors: [HEX.teal], showLegend: false,
  showTitle: true, title: "Thời gian xử lý mỗi khung (ms)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
  catAxisOrientation: "maxMin", valAxisMinVal: 0, valAxisMaxVal: 40, objectName: "chart-bench",
});
card(s, 5.65, 2.7, 3.85, 2.3, "tests-card");
s.addText([{ text: `${tests.total} bài kiểm thử đều đạt`, options: { bold: true, fontSize: 17, color: C.accent1, breakLine: true } },
  { text: `${tests.edge} bài cho thiết bị, ${tests.cloud} bài cho gateway`, options: { fontSize: 14, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
  { text: "Có một kịch bản ghi sẵn để kiểm tra lại khi chuyển chương trình sang chip K230.", options: { fontSize: 13 } }],
  { x: 5.8, y: 2.8, w: 3.55, h: 2.1, color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "tests-text" });
notes(s, `Đo trên ${bench.machine.cpu}, khung hình ${bench.frame_size[0]}x${bench.frame_size[1]}. Phần quyết định gần như không tốn thời gian, phần lâu nhất là MediaPipe. Em chưa đo được trên chip K230.`);

// ======================================================================= 14. Hạn chế
pres.addSection({ title: "Kết luận" });
s = pres.addSlide({ masterName: "TITLE_ONLY", sectionTitle: "Kết luận" });
title(s, "Hạn chế và hướng phát triển");
card(s, 0.5, 1.3, 4.4, 3.7, "limits-card");
s.addText("Hạn chế", { x: 0.7, y: 1.4, w: 4.0, h: 0.4, fontSize: 18, bold: true, color: C.accent3, margin: 0, isTextBox: true, objectName: "limits-h" });
bullets(s, ["Chưa thử với webcam và người lái thật", "Chưa có dữ liệu mặt nhìn thẳng có nhãn (NTHU-DDD, YawDD, DMD)", "Luật tay gần đầu còn yếu (F1 0,34 và 0,19)", "Chưa chạy trên K230 và Traffic-SM thật, chưa có bảo mật"], 0.7, 1.9, 4.0, 3.0, 15, "limits-b");
card(s, 5.1, 1.3, 4.4, 3.7, "next-card");
s.addText("Hướng phát triển", { x: 5.3, y: 1.4, w: 4.0, h: 0.4, fontSize: 18, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: "next-h" });
bullets(s, ["Đánh giá trên NTHU-DDD, YawDD, DMD và video tự quay", "Chuyển phần cảm biến sang mô hình của SDK K230", "Nối với Traffic-SM thật, làm bản đồ rủi ro theo đoạn đường", "Bổ sung bảo mật: mTLS, phân quyền, cập nhật có chữ ký"], 5.3, 1.9, 4.0, 3.0, 15, "next-b");
notes(s, "Các ngưỡng hiện tại mới là giá trị ban đầu. Phần em làm được chắc chắn là logic quyết định, độ trễ và việc ẩn danh dữ liệu. Độ chính xác ngoài thực tế thì em chưa kiểm chứng được.");

// ======================================================================= 15. Kết luận
s = pres.addSlide({ masterName: "DARK_END", sectionTitle: "Kết luận" });
s.addText("Kết luận", { placeholder: "title" });
[["Phần quyết định tự viết", "EAR, PERCLOS, ngân sách chú ý, xác định xe chạy, 4 mức"], ["Nhắm mắt 3 giây là mức 4", "lên đúng 3,00 s; không báo khi chớp mắt hay khi xe dừng"], ["Nhẹ và có kiểm thử", `${vn(bench.engine_only_ms, 2)} ms mỗi khung; ${tests.total} bài kiểm thử`], ["Còn hạn chế về dữ liệu", "State Farm chỉ thấy mặt ở 27,6% ảnh; luật tay gần đầu F1 0,34"]].forEach(([h, t], i) => {
  const y = 1.45 + i * 0.85;
  chip(s, 0.6, y + 0.12, i + 1, [C.accent1, C.accent2, C.accent4, C.accent3][i]);
  s.addText([{ text: h, options: { bold: true, fontSize: 18, color: C.background1, breakLine: true } }, { text: t, options: { fontSize: 14, color: C.background2 } }], { x: 1.25, y, w: 8.2, h: 0.72, margin: 0, valign: "middle", isTextBox: true, objectName: `concl-${i}` });
});
s.addText("Em xin cảm ơn thầy cô đã lắng nghe", { x: 0.6, y: 4.85, w: 8.8, h: 0.5, fontSize: 20, bold: true, color: C.accent6, margin: 0, isTextBox: true, objectName: "thanks", fontFace: THEME.headFontFace });
notes(s, "Em xin cảm ơn thầy cô đã lắng nghe, em xin được nghe câu hỏi và góp ý.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("đã ghi", OUT);
})();
