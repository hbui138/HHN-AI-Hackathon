# 🎤 Presentation Notes — Boie AI Product Matching

> Ghi chú để làm slide và thuyết trình. Số liệu lấy từ 200 query **test chưa từng dùng để train** (seed 42 + seed 2026, 100 mẫu mỗi seed), lần chạy ngày 2026-09-19. Trước khi lên slide: chạy lại 1000 mẫu để chốt số (xem "Việc cần làm trước demo").

---

## 1. Thông điệp chính (1 câu)

> **"Chúng tôi biến 25.000 đơn hàng Boie đã xử lý thành một hệ thống tự động chốt ~60% yêu cầu báo giá với độ chính xác ~91% (≈94% nếu tính biến thể tương đương khách không chỉ định) — phần còn lại chuyển cho nhân viên kèm Top-3 gợi ý."**

Ba từ khóa lặp lại xuyên suốt: **Học từ lịch sử đơn hàng của Boie** · **Giải thích được từng quyết định** · **Con người quyết định khi AI không chắc**.

---

## 2. Use cases

### Use case 1 — Tự động hóa đơn hàng / báo giá (trọng tâm demo)
*   **Input:** file CSV/email với các dòng mô tả tự do, vd. `Positionsfuss Form B SW13x10 M8 02041-208010 NORELEM`.
*   **Output:** mỗi dòng → Top-3 sản phẩm Boie + confidence + lý do; dòng xanh = tự động chốt, dòng vàng = Manual Review.
*   **Giá trị:** nhân viên chỉ xử lý ~37% dòng, và với những dòng đó vẫn có sẵn gợi ý.

### Use case 2 — Thay SOLR trên shop
*   Khách gõ mã sai chính tả / mã đối thủ / tên hãng khác → vẫn ra đúng hàng Boie.
*   Cùng một engine; chỉ khác UI (danh sách xếp hạng thay vì quyết định chốt đơn).

### Use case phụ (nói ở phần Market Value)
*   **Cross-reference đối thủ:** khách mang mã Norelem / FAG / INA / KOYO → Boie trả lời ngay bằng hàng mình (Kipp, SKF). Đây là **cơ hội bán hàng**, không chỉ là tìm kiếm.
*   **Phân tích catalog:** phát hiện dữ liệu bẩn (mã `nan`, file trùng lặp, mô tả thiếu mã) — hệ thống đã tìm ra khi build.

---

## 3. Số liệu cho slide

### 3.1 Trước / sau (cùng 100 mẫu test)

| | Baseline | Hiện tại |
|---|---|---|
| Top-1 (đúng ngay kết quả đầu) | 40% | **70–75%** |
| Top-3 (đáp án nằm trong 3 gợi ý) | 49% | **77–81%** |
| Tự động hóa | ~18% | **~62–64%** |
| Auto-match đúng nhãn | ~70% | **~89–94%** |
| Auto-match đúng nhãn **hoặc biến thể tương đương khách không chỉ định** (kiểm tra tay) | – | **≈ 94%** |

Biểu đồ gợi ý: cột Top-1 qua từng giai đoạn (bảng 5.1 trong `challenge2.md`) — kể câu chuyện "mỗi bước sửa một nguyên nhân gốc".

### 3.2 Theo nhóm hàng (200 mẫu)

| Nhóm | n | Top-1 | Top-3 | Tự động hóa | Auto-match đúng nhãn |
|---|---|---|---|---|---|
| Standard parts (Kipp, Ganter) | 118 | 75% | 79% | 64% | **96%** |
| Bearings (SKF) | 68 | 66% | 79% | 60% | 83% |
| Pneumatics | 14 | 64% | 71% | 71% | 90% (n nhỏ) |

→ Bearings thấp hơn vì rất nhiều biến thể gần giống nhau (`6007-2Z` / `6007-2Z/C3`), và hệ thống còn bỏ sót chi tiết khách **có** ghi (`C3`, `NR`, mã hàng Boie) — xem `challenge2.md` Mục 5.3.

---

## 4. Trade-off (slide "Boie chọn điểm vận hành")

| Threshold | Delta | Tự động hóa | Đúng nhãn |
|---|---|---|---|
| 0.80 | 0.02 | 70% | 92% |
| **0.90** | **0.02** | **63%** | **91%** ← mặc định |
| 0.90 | 0.05 | 48% | 95% |
| 0.94 | 0.05 | 44% | 95% |

**Cách kể:**
*   "Tự động hóa và độ an toàn là **một núm vặn**, không phải con số cố định. Boie chọn: muốn an toàn tối đa → 44% tự động, 95% đúng nhãn; muốn năng suất → 70% tự động."
*   "Khoảng một nửa số ca 'sai' là biến thể khách không chỉ định: khách ghi `6007 2Z`, chúng tôi giao `6007-2Z`, nhân viên lúc đó chọn `6007-2Z/C3`." (Đừng dùng ví dụ `6010 2Z` — khách đã ghi kèm mã hàng Boie của bản `/C3`, đó là lỗi thật.)
*   Nhận xét của Boie: sản phẩm tương đương đúng yêu cầu khách là chấp nhận được.

**Trade-off kỹ thuật khác (cho phần Q&A):**

| Lựa chọn | Được | Mất |
|---|---|---|
| Mã quyết định (55%), Cross-Encoder chỉ 10% | Không bị model ngôn ngữ lật exact match | Query không có mã (chỉ mô tả) yếu hơn |
| Brand model học từ dữ liệu thay vì "sai hãng = 0" | Xử lý đúng FAG→SKF, NORELEM→Kipp | Nếu Boie đổi chính sách hãng phải học lại (tự động, chạy lại script) |
| Luật thuộc tính học từ dữ liệu | Không cần viết từ điển; tự phủ vật liệu, `C3`, Form | Từ hiếm có thể nhiễu → lọc bằng Wilson + lift |
| LLM chỉ để trích Hãng/Mã, có cache | Rẻ, lặp lại được, dữ liệu có thể chạy offline sau này | Vẫn phụ thuộc API ở lần đầu (có thể thay bằng model local) |
| Luật viết tay (hậu tố vòng bi, tiền tố nhà cung cấp) | Chính xác, dễ kiểm tra | Phải bảo trì → chuyển ra file cấu hình |

---

## 5. Phân tích / phát hiện đáng kể (slide "Chúng tôi học được gì từ dữ liệu Boie")

1.  **Bug dữ liệu quan trọng hơn model:** 45% mã trong bảng tra cứu không bao giờ khớp được do chuẩn hóa không nhất quán (`71802 CD/P4DBA`). Sửa → nền tảng cho mọi cải thiện sau.
2.  **Boie luôn giao SKF cho vòng bi** — kể cả khi khách ghi FAG (576/576 đơn), INA (369/369), KOYO (193/193). → Luật "sai hãng = phạt" sẽ sai. Hệ thống **tự học** điều này.
3.  **Khách dùng mã đối thủ:** ghi Norelem `03089-4004` → Boie giao Kipp `K0338.4004` (chung hậu tố kích thước). Hệ thống học 380 cặp series Norelem → Kipp từ lịch sử đơn → standard parts Top-1 tăng ~18 điểm.
4.  **Mã nội bộ nhà cung cấp:** FAG `2026219-2Z` thực ra là `6219-2Z` (Boie gắn tiền tố `202`), INA `101…`, GLYCO `109…`.
5.  **Model ngôn ngữ bị đánh lừa bởi dữ liệu:** mô tả biến thể có chứa mã (`1006208-2RS1N`), mô tả sản phẩm gốc thì không → Cross-Encoder chọn biến thể. Sửa bằng cách đưa `hãng + mã` vào mọi văn bản → Top-1 +7–10 điểm, tự động hóa 42% → 63%.
6.  **Hệ thống tự học thuật ngữ:** `edelstahl` / `VA` / `A2` / `inox` → `rostfreier Stahl`; `C3` → `radiale Lagerluft C3`; `2Z` → `Deckscheibe` — không ai viết từ điển này.
7.  **271.035 ảnh sản phẩm** đã được gắn vào kết quả → UI Manual Review hiển thị ảnh để nhân viên chọn nhanh.

---

## 6. Kiến trúc (1 slide)

```
Câu khách viết
   │
   ├─► LLM (trích Hãng / Mã, có cache) ─┐
   │                                     ▼
   ├─► Bộ sinh ứng viên theo MÃ:  exact · prefix · fuzzy · regex từ query
   │                              · vòng bi (mã gốc + hậu tố) · Norelem → Kipp
   ├─► Vector search (MiniLM fine-tune trên đơn Boie) cho câu không có mã
   ▼
Chấm điểm:  0.55·Mã + 0.20·Hãng + 0.10·Text (Cross-Encoder) + 0.15·Thuộc tính
                       ▲ brand model          ▲ luật thuộc tính
                       └──── học từ 25.000 đơn hàng Boie ────┘
   ▼
Routing:  Top-1 ≥ 0.90 và cách Top-2 ≥ 0.02  →  🟢 Tự động chốt
          ngược lại                            →  🟡 Manual Review + Top-3 + ảnh + lý do
                                                     │
                                                     └─► lựa chọn của nhân viên = dữ liệu train mới
```

---

## 7. Kịch bản thuyết trình 3 phút

**Phút 1 — Nỗi đau**
*   Chiếu 3 dòng thật: `KUGELLAGER 61907-ZZ SKF`, `Positionsfuss Form B SW13x10 M8 02041-208010 NORELEM`, `Edelstahl-Passschraube ISO 7379-8-M6-20-NI Hersteller Ganter`.
*   "Mã sai định dạng, mã của đối thủ, tên hãng khác hàng Boie bán. SOLR không tìm ra. Nhân viên phải tra tay từng dòng."

**Phút 2 — Demo**
*   Upload file → bảng xanh/vàng. Click một dòng xanh: hiện sản phẩm + ảnh + **lý do** (mã khớp, hãng học được, thuộc tính khớp).
*   Click một dòng vàng: Top-3 kèm ảnh, nhân viên chọn 1 click.
*   Chuyển tab Shop Search: gõ mã Norelem → ra hàng Kipp.

**Phút 3 — Vì sao tin được**
*   Slide trade-off: "~60% tự động với ~91% đúng nhãn, hoặc ~45% tự động với ~95%; Boie tự chọn mức an toàn."
*   Slide "học từ lịch sử đơn": FAG→SKF, Norelem→Kipp, VA→inox — tri thức riêng của Boie mà ChatGPT không có.
*   Chốt: "Mỗi lựa chọn của nhân viên ở màn Manual Review trở thành dữ liệu học → hệ thống càng dùng càng giỏi."

---

## 8. Ca demo đã xác minh đúng (từ kết quả test)

| Câu khách viết | Kết quả | Điểm nhấn |
|---|---|---|
| `Positionsfuss Form B SW13x10 M8 02041-208010 NORELEM` | Kipp `K0299.208010` (0.968, tự động) | Mã đối thủ → hàng Boie; luật `form=b` bật |
| `Auflagebolzen d16x5 02010-08 NORELEM` | Kipp `K0292.08` (0.97, tự động) | Norelem → Kipp |
| `Zylinderkopfschraube m.Ansatz M8 d10x4012,9 07534-10X40 NORELEM` | Kipp `K0705.10X40` (0.971, tự động) | Norelem → Kipp |
| `ISO 73796M530NI, Hersteller: Elesa/Ganter` | Ganter `7379-6-M5-30-NI` (0.99, tự động) | Mã viết liền không dấu → vẫn khớp; ELESA → Ganter |
| `436.447 Pendelrollenlager 22216EK nach Zng.-Nr.: 34-1642-000 SKF oder …` | SKF `22216 EK` (0.989, tự động) | Mã lẫn trong câu dài, nhiều số nhiễu |
| `6004-2Z/C3` | SKF `6004-2Z/C3` (1.0, tự động) | Luật `C3` + `Deckscheibe` bật |
| `Edelstahl-Passschraube ISO 7379-8-M6-20-NI Hersteller Ganter Otto GmbH` | Ganter `7379-8-M6-20-NI` (1.0, tự động) | |
| `Rillenkugellager d=15 D=24 B=5 Edelstahl geschlossen 15x24x5` | SKF `W 61802-2RS1` | Không có mã! Luật học được `edelstahl → rostfreier Stahl` chọn đúng bản inox — **kiểm tra lại trước demo** |
| `Rillenkugellager 6308 NR 2RS 40/90x23 DIN625-1` | SKF `6308-2RS1NR` (Manual, đúng Top-1) | Ví dụ dòng vàng: đúng nhưng hệ thống vẫn cẩn thận |

⚠️ Chạy lại toàn bộ ca demo ngay trước khi thuyết trình (code còn đang thay đổi).

---

## 9. Chuẩn bị Q&A

| Câu hỏi có thể gặp | Trả lời |
|---|---|
| "90% đúng là đủ cho B2B chưa? 10% giao sai rất đắt." | Khoảng một nửa số ca "sai" là biến thể tương đương khách không chỉ định (≈94% tính theo tiêu chí này, kiểm tra tay). Và ngưỡng là núm vặn: 95% đúng nhãn ở 44–48% tự động. Boie chọn. |
| "Đây có phải chỉ là rule hard-code?" | Tri thức chính (hãng thay thế, Norelem→Kipp, thuật ngữ vật liệu) **học từ 25.000 đơn**, sinh lại tự động khi có đơn mới. Một lớp nhỏ luật ngành (hậu tố vòng bi, DIN/ISO) được giữ tường minh, dễ kiểm tra, sẽ chuyển ra file cấu hình cho chuyên gia Boie — như `synonyms.txt` của SOLR nhưng nhỏ hơn nhiều. |
| "Có overfit không?" | Tách train/test cố định; mọi bảng học chỉ dùng tập train; kiểm tra trên 2 bộ 100 mẫu khác nhau (seed 42 / 2026, trùng 1 dòng) — kết quả tương đương. |
| "Sao không dùng ChatGPT cho tất cả?" | GPT không biết Boie giao SKF thay FAG hay Norelem 02041 = Kipp K0299. Tri thức đó nằm trong lịch sử đơn của Boie. LLM chỉ dùng để trích Hãng/Mã, có cache → chi phí gần 0 và có thể thay bằng model chạy nội bộ. |
| "Bảo trì thế nào?" | Chạy lại `build_crossref.py` + `attribute_rules.py` định kỳ (vài phút). Lựa chọn của nhân viên ở Manual Review = nhãn mới → vòng lặp tự cải thiện. |
| "Latency?" | ⚠️ Chưa đo chính thức — đo trước demo (ước lượng: dưới 1 giây/query khi LLM đã cache). |
| "Query chỉ có mô tả, không có mã?" | Điểm yếu thừa nhận: đi qua vector search + thuộc tính, confidence thấp hơn → thường vào Manual Review (đúng thiết kế). |

---

## 10. Điểm yếu cần nói thật / tránh overclaim
*   Manual Review: chỉ ~51% dòng vàng có đáp án trong Top-3; 43/200 query không có đáp án trong Top-3.
*   Bearings auto-match đúng nhãn 83% (thấp nhất) — nhiều biến thể `/C3`, `NR`.
*   Luật thuộc tính: chưa chứng minh được cải thiện số liệu tổng (±1–2 ca trên 200 mẫu) → trình bày như **năng lực + ví dụ**, không trình bày như "+X%".
*   Số liệu từ 200 mẫu → sai số ±5 điểm; cần chạy 1000 mẫu.
*   Ý định "Alternative zu… / baugleich" (khách muốn hàng thay thế) chưa xử lý.

---

## 11. Việc cần làm trước demo
1.  Ổn định code (đang có sửa đổi song song), chạy lại 1000 mẫu → cập nhật mọi con số ở mục 3–4.
2.  Đo latency / query (có cache và không cache).
3.  Chạy lại các ca demo ở mục 8.
4.  UI (Streamlit): bảng xanh/vàng, ảnh sản phẩm, cột "lý do" từ trường `method` + `attribute_rules_fired` trong file kết quả JSON.
5.  (Tuỳ chọn) Ablation luật viết tay → một dòng trên slide: "bỏ hết luật viết tay chỉ mất X điểm".
