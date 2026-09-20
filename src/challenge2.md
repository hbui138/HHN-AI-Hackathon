# 🚀 Project Status & Technical Challenges: AI-Driven Product Matching (Boie)

> **Trạng thái hiện tại (2026-09-20, 2.000 query test chưa từng train — 1.000 mẫu × seed 42 + seed 2026):**
> Top-1 **76.0%** · Top-3 **81.8%** · Tự động hóa **59.2%** · Auto-match đúng nhãn **95.4%** (sai 54/1.185)
> Phân loại lỗi tự động: 59% biến thể khách để ngỏ · 15% biến thể khách có ghi rõ · 26% sản phẩm khác.
> (Baseline ban đầu: Top-1 40%, Top-3 49%, precision ~70%.) Báo cáo đầy đủ: `results/evaluation_summary.md` · Ghi chú thuyết trình: `presentation_notes.md`.

## 1. Bối cảnh & Mục tiêu dự án (Context & Objectives)
**Nhiệm vụ cốt lõi:** *From description to article* - Khách hàng đặt hàng hoặc yêu cầu báo giá bằng các đoạn text tự do (free-text) chứa mã phụ tùng, tên hãng và các thuộc tính. AI cần nhận diện và đối chiếu chính xác với cơ sở dữ liệu để tạo ra một danh sách kết quả được xếp hạng theo độ liên quan (relevance-ranked list).

*   **Use case 1 (Order Automation):** Đề xuất bằng AI giúp cải thiện đáng kể tốc độ và hiệu quả của việc khớp mã sản phẩm cho các đơn hàng và yêu cầu báo giá.
*   **Use case 2 (Shop Search):** Danh sách kết quả do AI tạo ra sẽ thay thế chức năng tìm kiếm SOLR hiện tại trên trang thương mại điện tử (Boie shop).

**Tiêu chí đánh giá của Ban giám khảo (Judging Criteria):**
1. Functionality (Tính năng hoạt động tốt)
2. Innovative (Tính đổi mới, sáng tạo)
3. Feasibility (Tính khả thi triển khai thực tế)
4. Market Value (Giá trị mang lại cho thị trường/doanh nghiệp)
5. Pitching (Khả năng trình bày thuyết phục)

---

## 2. Luồng nghiệp vụ cốt lõi (Business Logic & Routing)
Hệ thống không cố gắng thay thế con người 100% (rất dễ gây hậu quả nghiêm trọng trong B2B), mà hoạt động theo mô hình **Human-in-the-Loop**:
1. Đọc yêu cầu (inquiries) từ khách hàng.
2. AI phân tích và tìm kiếm sản phẩm.
3. **Auto-Match (Automation):** Nếu điểm tin cậy (Confidence) đủ cao (vượt ngưỡng Threshold và chênh lệch Delta an toàn), hệ thống sẽ tự động chốt đơn và chuyển thẳng xuống xưởng đóng gói (straight to packaging).
4. **Manual Review (Fallback):** Nếu điểm tin cậy thấp hoặc có sự mơ hồ, hệ thống sẽ gắn cờ (Flag) và chuyển danh sách Top 3 Gợi ý ra giao diện UI để nhân viên kiểm tra và chọn thủ công.

**[Cập nhật] Quyết định từ Boie:** nhiều sản phẩm tương đương nhau; nếu sản phẩm được chọn **đáp ứng đúng yêu cầu khách** (vd. khách ghi `6007 2Z`, giao `6007-2Z` dù nhãn là `6007-2Z/C3`) thì chấp nhận được → không cần routing đặc biệt cho biến thể.

---

## 3. Các vấn đề & Thách thức (Bottlenecks) — kèm trạng thái

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | Mơ hồ biến thể | ✅ Đủ dùng (Boie chấp nhận biến thể tương đương) |
| 2 | Top-1 thấp (~36–40%) | ✅ **70–73%** — nguyên nhân chính là bug dữ liệu + CE lật kết quả |
| 3 | Từ lóng / lệch từ vựng | 🟡 Học được một phần từ dữ liệu (luật thuộc tính, brand model, Norelem→Kipp) |
| 4 | Chấm điểm quá khắt khe | ✅ Tự động hóa 18% → **62–64%** |

### Vấn đề 1: Sự mơ hồ về biến thể (Variant Ambiguity)
*   **Mô tả:** Cơ sở dữ liệu có rất nhiều sản phẩm có mã gốc giống nhau nhưng khác hậu tố (ví dụ: `6019` là loại nắp sắt, `6019 J2` là biến thể nắp cao su/thông số khác).
*   **Lỗi ban đầu:** Exact Match cứng nhắc vồ lấy mã gốc và chốt đơn, bỏ qua biến thể đúng.
*   **[Cập nhật] Đã làm:** dict `code → [ids]` (không ghi đè biến thể); prefix match trừ điểm theo ký tự thừa (`678` = 0.95, `678/A` = 0.93); bearings tách mã gốc + hậu tố và trừ điểm biến thể đặc biệt (`6008-2RS1` > `6008-2RS1/VP233F7`).
*   **[Cập nhật] Kết luận:** khoảng **một nửa** (4–5/11) ca auto-match sai là *biến thể khách không chỉ định* — Boie chấp nhận; nửa còn lại là lỗi thật (khách **có** chỉ định: `C3`, `NR`, mã hàng Boie — xem Mục 5.3). Tăng Delta không giải được (các ca này có Delta lớn).

### Vấn đề 2: Độ chính xác Top-1 còn thấp (Low Top-1 Accuracy ~36%)
*   **Giả thuyết ban đầu:** Vector search "mù" với mã SKU; gộp mọi cột vào `combined_text` gây nhiễu.
*   **[Cập nhật] Nguyên nhân thực sự lớn hơn là bug, đã sửa:**
    *   45% mã trong exact dict (84.799/186.413) **không bao giờ khớp được** (dict chỉ bỏ dấu cách/`-`, search bỏ mọi ký tự đặc biệt) → `normalize_code()` dùng chung.
    *   Key `"nan"` trong dict (159 sản phẩm) → loại.
    *   Standard-parts không được lọc category (`standard-parts` ≠ `standard_parts`) → `normalize_category()`.
    *   Boie gắn tiền tố nội bộ vào mã: FAG `202`, INA `101`/`102`, GLYCO `109` (`2026219-2Z` = `6219-2Z`) → alias không tiền tố.
    *   Chỉ tin 1 `Part_Number` từ LLM → trích thêm mã bằng regex trực tiếp từ query.
    *   **Cross-Encoder lật kết quả:** CE (`ms-marco`, tiếng Anh) chiếm 50% trọng số và chấm sản phẩm đúng mã = 0.0 vì mô tả của nó không chứa mã, trong khi biến thể có mô tả `1006208-2RS1N ...` được 0.96 → sửa công thức (mã quyết định) + luôn ghép `hãng + mã` vào văn bản đưa cho CE.

### Vấn đề 3: Bất đồng ngôn ngữ kỹ thuật (Domain Slang & Vocabulary Mismatch)
*   **Ví dụ:** khách ghi `VA` / `A2` / `Edelstahl`, DB ghi `rostfreier Stahl`; khách ghi `M5x12`, DB ghi `D=M05 L=12`.
*   **[Cập nhật] Mã đối thủ (Competitor Cross-Reference):** khách ghi mã **Norelem** (`03089-4004`), Boie bán **Kipp** tương đương (`K0338.4004`, chung hậu tố). Học bảng series Norelem → Kipp (380 series) **chỉ từ tập train**. Standard-parts Top-1: 41% → 59% (lúc áp dụng).
*   **[Cập nhật] Hãng thay thế:** Boie **luôn giao SKF cho bearings** kể cả khi khách ghi FAG (576/576), INA (369/369), KOYO (193/193); NORELEM → Kipp (99.7%), ELESA → Ganter (100%) → brand model học từ dữ liệu (Mục 5.2).
*   **[Cập nhật] Luật thuộc tính học từ dữ liệu** (`attribute_rules.py`): hệ thống tự tìm ra `edelstahl` / `va` / `a2` / `inox` → `Lagerwerkstoff = rostfreier Stahl`, `c3` → `radiale Lagerluft = C3`, `2z` → `Deckscheibe`, `form_b` → `Form = B`. Tác động lên số liệu tổng trên 200 mẫu **chưa có ý nghĩa thống kê** (±1–2 ca; chỉ ~6% query nhắc thuộc tính) — cần đánh giá có mục tiêu (Mục 5.6).
*   **Còn lại:** hậu tố vòng bi tương đương (`2RS1`/`2RSH`/`2RSR`, `ZZ`/`2Z`, `69xx`=`619xx`) và regex từ lóng (`VA → edelstahl`) vẫn là luật viết tay (Mục 5.4).

### Vấn đề 4: Hệ thống chấm điểm quá khắt khe (Over-penalization)
*   **Ban đầu:** phạt nặng khi thiếu tên hãng, khóa trần vector 0.85 → tự động hóa ~18%.
*   **[Cập nhật]** Công thức mới + brand model học từ dữ liệu → tự động hóa **62–64%**. Luật "sai hãng = 0" trong Notes bị bỏ vì dữ liệu cho thấy Boie thường giao hãng khác hãng khách ghi.

---

## 4. Hướng giải quyết đề xuất ban đầu → đã làm thế nào

| Đề xuất ban đầu | Thực tế đã làm |
|---|---|
| LLM Parser thành "Data Normalizer" | Không cần: dịch từ lóng được **học từ dữ liệu** (luật thuộc tính, brand model) thay vì nhét vào prompt; LLM chỉ còn trích Hãng/Mã, có cache |
| Hybrid BM25 + Vector + CE | Thay BM25 bằng **bộ sinh ứng viên theo mã** (exact / prefix / fuzzy / regex / bearing / Norelem) + Vector; CE chỉ làm trọng tài |
| Weighted Scoring, `Delta >= 2%` | ✅ `0.55·Mã + 0.20·Hãng + 0.10·Text + 0.15·Thuộc tính`; Threshold 0.90, Delta 0.02 |

---

## 5. Tiến độ & phân tích (2026-09-19)

### 5.1 Kết quả qua từng giai đoạn (100 mẫu test, seed 42 trừ khi ghi khác)

| Giai đoạn | Top-1 | Top-3 | Tự động hóa | Auto-match đúng nhãn |
|---|---|---|---|---|
| Baseline | 40% | 49% | – | ~70% (1000 mẫu) |
| Sửa bug chuẩn hóa mã / dict / category | 42% | 50% | 22% | 90.9% |
| + Regex trích mã + Norelem→Kipp | 53% | 61% | 34% | 94.1% |
| + Bearings (tiền tố nhà cung cấp, mã gốc + hậu tố) | 52% | 62% | 34% | 91.2% |
| + Công thức mới + Brand model | 64% | 74% | 42% | 90.5% |
| + Sửa bias Cross-Encoder | 71% | 79% | 63% | 88.9% |
| ↳ Chống overfit: **seed 2026** (100 mẫu khác) | 75% | 81% | 64% | 93.8% |
| + Luật thuộc tính học từ dữ liệu — seed 42 / 2026 | 71% / 75% | 78% / 81% | 61% / 65% | 90.2% / 92.3% |
| Lần chạy `20260919_202234` / `_201912` (phiên song song) — seed 42 / 2026 | 70% / 73% | 77% / 80% | 62% / 64% | 88.7% / 93.8% |
| **1.000 mẫu** — seed 42 / seed 2026 | **74.3% / 77.7%** | **81.1% / 82.4%** | **58.1% / 60.4%** | **95.0% / 95.9%** |
| **+ Tra mã hàng Boie trong câu khách** (`20260919_204920` / `_204556`) — seed 42 / 2026 | **72% / 76%** | **79% / 81%** | **62% / 65%** | **90.3% / 93.8%** |

**Tra mã hàng Boie:** số 6–10 chữ số đứng riêng trong câu mà trùng đúng một mã hàng trong catalog → `S_code = 1.0`, mọi ứng viên khác bị giới hạn 0.90. Sửa được `6010 2Z / 10004423` (→ `6010-2Z/C3`) và `3206-BD-XL-2HRS-TVH / 10003946` (mã FAG + mã hàng Boie → đúng hàng SKF). Lỗi `W 6001-2RS1` ở lần chạy song song **không tái hiện** với code hiện tại.

⚠️ Hai lần chạy mới nhất được tạo trong lúc có một phiên khác đang sửa code song song (cơ chế `ABLATE`, tự phát hiện tiền tố) → số lệch 1–2 điểm so với dòng phía trên. Cần chạy lại khi code ổn định.

### 5.2 Công thức chấm điểm (`search_engine.py`)
*   **Ứng viên có bằng chứng mã:** `Final = 0.55·S_code + 0.20·S_brand + 0.10·S_text + 0.15·S_attr`.
*   **Ứng viên chỉ từ vector:** `Final = 0.85·S_text·(0.7·S_brand + 0.3)·(0.7 + 0.3·S_attr)` — luôn thấp hơn mã khớp thật.
*   `S_brand` = xác suất Boie giao hãng đó, học từ train (floor 0.3 khi khách ghi hãng, 0.5 khi không ghi).
*   `S_attr` = mức khớp với luật thuộc tính đã học; 1.0 khi query không yêu cầu thuộc tính; chấm tương đối (ứng viên khớp nhất = 1.0).
*   `S_text` = Cross-Encoder trên `hãng + mã + combined_text`.
*   Routing: Top-1 ≥ 0.90 **và** Top-1 − Top-2 ≥ 0.02 → Auto-Match.

### 5.3 Phân tích đánh đổi (200 mẫu, lần chạy mới nhất)

| Threshold | Delta | Tự động hóa | Đúng nhãn |
|---|---|---|---|
| 0.80 | 0.02 | 70.0% | 92.1% |
| **0.90** | **0.02** | **63.0%** | **91.3%** |
| 0.90 | 0.05 | 47.5% | 94.7% |
| 0.94 | 0.05 | 43.5% | 95.4% |

*   **Kiểm tra tay 11 ca auto-match sai (cấu hình 0.90 / 0.02):**
    *   **Chấp nhận được** — khách không chỉ định biến thể, giao đúng thứ khách ghi (4–5 ca): `653-M5-20` (nhãn `-NI`), `6007 2Z` (nhãn `/C3`), `SKF 30302` (nhãn `J2`), `K0122.3081X30` (khách ghi đúng 3081, nhãn 3082 — nhiễu nhãn), có thể cả `6201` (khách chỉ ghi kích thước).
    *   **Lỗi thật** (6–7 ca): `6010 2Z / 10004423` — **khách ghi kèm mã hàng Boie 10004423 = `6010-2Z/C3`**, hệ thống bỏ qua; `NR6205-2Z` bỏ mất `NR`; `6308-Z C3` bỏ mất `C3`; `6001-2RS1` → chọn nhầm bản inox `W 6001-2RS1` (**hồi quy** do alias bỏ tiền tố chữ + luật thuộc tính); `Alternative zum …`; `252.24/1`.
    *   → Precision "đúng nhãn hoặc biến thể tương đương" ≈ **94%** (119/126). *Con số ≈ 98% ghi trước đó đã sai*: phép kiểm tra tự động "mã xuất hiện trong câu khách" quá lỏng (vd. `62052z` nằm trong `NR6205-2Z`).
*   **Mã hàng Boie trong câu khách:** 2.5% query test (158/6287) chứa sẵn một mã hàng Boie hợp lệ (8 chữ số), và 92% trong số đó chính là nhãn (train: 97.8%) → ✅ đã thêm tra cứu trực tiếp.
*   **Sau khi thêm tra mã hàng Boie:** 10 ca auto-match sai / 127 — 4 chấp nhận được (`653-M5-20` → `-NI`, `6007 2Z` → `/C3`, `30302` → `J2`, `K0122.3081` nhãn nhiễu), 6 lỗi thật (`NR6205-2Z` bỏ `NR`, `6308-Z C3` bỏ `C3`, `6304-2RS A2` bỏ inox, `6201` chọn `6201 NR`, `Alternative zum …`, `252.24/1`).
*   **Khi khách ghi đúng một mã có trong DB (bearings, train):** nhãn = đúng mã đó 65%, = biến thể dài hơn 28% (chủ yếu khách chỉ ghi mã gốc `6010` → nhãn `6010-2Z`), khác 7.5%. Luật "ưu tiên mã trơn" đúng trong đa số trường hợp; có thể học thêm "variant prior" theo từng mã giống brand model.
*   **Top-3 trong nhóm tự động chốt:** 119/126 (94.4%) so với Top-1 91.3% — chỉ thêm 3 điểm, vì 7/11 ca sai có nhãn **nằm ngoài** Top-3.
*   Theo nhóm hàng: standard parts auto-match đúng **96%**; bearings chỉ **83%** (nhiều biến thể `/C3`, `NR`); pneumatics 90% (n nhỏ).
*   Manual Review (37% đơn): đáp án nằm trong Top-3 chỉ ở **51%** → điểm yếu lớn nhất hiện tại; 43/200 query không có đáp án trong Top-3.

### 5.4 Nguồn tri thức: học từ dữ liệu vs. luật viết tay

| Loại | Thành phần |
|---|---|
| ✅ Học từ dữ liệu train | Luật thuộc tính (`attribute_rules.json`), brand model (`brand_model.json`), series Norelem → Kipp (`norelem_kipp_series.json`), model vector fine-tune |
| ✅ Học từ catalog | **Tiền tố nhà cung cấp** (`supplier_prefixes.json`) — mới chuyển từ luật viết tay sang, xem 5.7 |
| ⚙️ Tham số thống kê | Trọng số, Threshold/Delta, ngưỡng Wilson/lift; bỏ thuộc tính dạng số |
| ⚠️ Luật viết tay | Hậu tố vòng bi tương đương, `69xx = 619xx`, regex `VA → edelstahl` / `M5x12`, danh sách hãng đối thủ, `DIN/ISO`, mẫu mã Norelem |

*   Quan điểm team: **luật viết tay chấp nhận được nếu mở rộng được** → hướng đi: chuyển ra file cấu hình (`domain_rules.json`) để chuyên gia Boie tự bổ sung, giống `synonyms.txt` của SOLR.
*   Cơ chế đo giá trị từng luật: `feature_flags.py`, bật/tắt bằng biến môi trường `ABLATE=supplier_prefix,suffix_equivalents,...` (**chưa chạy ablation** — xem 5.6).

### 5.5 Thay đổi code

| File | Nội dung |
|---|---|
| `normalization.py` (mới) | `normalize_code`, `normalize_category`, `strip_supplier_prefix` — dùng chung cho build DB và search; **`detect_supplier_prefixes()` + `load_supplier_prefixes()`** học tiền tố từ catalog (5.7) |
| `bearing_codes.py` (mới) | Tách mã vòng bi (mã gốc + hậu tố), hậu tố tương đương, chấm điểm biến thể |
| `build_crossref.py` (mới) | Học Norelem → Kipp series + brand model từ tập train |
| `attribute_rules.py` (mới) | Học luật "từ trong query → thuộc tính sản phẩm" (đối chứng với biến thể, lift so với baseline, cận dưới Wilson) |
| `feature_flags.py` (mới) | Bật/tắt từng luật viết tay để đo ablation |
| `summarize_results.py` (mới) | Kết quả JSON → báo cáo markdown: chỉ số, theo nhóm hàng, bảng đánh đổi, **tự phân loại lỗi** |
| `app.py` (mới) | UI Streamlit 4 tab: **Order automation** (UC1 — lấy ngẫu nhiên n dòng test *ngoài* 1.000 dòng của lần đánh giá seed 2026, chạy trực tiếp, bảng quyết định + tỷ lệ tự động, đẩy dòng không chắc sang nhân viên), **Shop search** (UC2 — khớp real-time khi khách gõ, `streamlit-keyup`, nút gửi inquiry), **Clerk inbox** (phân biệt nguồn shop / mail; xanh: khớp rõ → Accept · cam: Top-3 → mở rộng Top-10 · xám: chỉ liên quan; luôn cho nhập mã tay), **Results** (2.000 query đã đánh giá). Quyết định ghi vào `results/clerk_decisions.jsonl` |
| `search_engine.py` | `generate_code_candidates()`; công thức mới; brand model; `S_attr`; CE dùng `hãng + mã + text`; bearing alias bỏ tiền tố chữ (`W 61802` ← `61802`, trừ 0.1) |
| `llm_parser.py` | Cache kết quả parse (`llm_parse_cache.json`) |
| `create_database.py` | Dict `code → [ids]` + alias không tiền tố; bỏ mã `nan`; lưu thông tin sản phẩm đầy đủ; `--dict-only` / `--skip-vectors` |
| `preprocess_json.py` / `preprocess_csv.py` | Thêm `description`, `longtext`, `attributes`, `images`, `link` |
| `run_pipeline.py` | `--seed`; kết quả **JSON** (metrics tổng + theo category, sản phẩm nhãn + Top-3 đầy đủ, luật thuộc tính đã bật) |

**Dữ liệu:** 162.269 sản phẩm; **271.035 ảnh** (98.4% bearings, 99.9% standard parts có ảnh; pneumatics không có media); đã loại 11 file trùng lặp cũ (backup ở `_backup/`).

**Bố cục thư mục (2026-09-20):** code tìm dữ liệu ở **gốc repo**, không phải trong thư mục tải về. Đúng layout là:
`<repo>/catalogdata_bearings/`, `<repo>/catalogdata_standard_parts/`, `<repo>/customerinquiry/`, `<repo>/articledata_pneumatics/articledata_pneumatics.csv`.
Nếu vừa giải nén bản tải về thì tất cả đang nằm lồng trong `articledata_pneumatics/` → phải chuyển lên gốc, nếu không `preprocess_json.py` báo "No JSON files found" và `build_crossref.py` crash vì danh sách inquiry rỗng. Các thư mục này đã được thêm vào `.gitignore` (commit `c20771c`).

**Chạy lại:**
```bash
python preprocess_json.py && python preprocess_csv.py && python clean_json.py
python create_database.py --skip-vectors   # bỏ cờ nếu combined_text thay đổi (embed lại Chroma)
python build_crossref.py                   # Norelem->Kipp + brand model
python attribute_rules.py                  # luật thuộc tính
python run_pipeline.py 100 --seed 2026     # -> results/pipeline_results_<timestamp>.json
ABLATE=suffix_equivalents python run_pipeline.py 100   # tắt 1 luật viết tay để so sánh
```

### 5.6 Đánh giá 2.000 query (chốt số, 2026-09-20)

Sinh bằng `python summarize_results.py` → `results/evaluation_summary.md`.

| Nhóm | n | Top-1 | Top-3 | Tự động hóa | Auto-match đúng nhãn |
|---|---|---|---|---|---|
| bearings | 702 | 78.6% | 86.9% | 60.4% | 92.0% |
| standard_parts | 1.136 | 76.1% | 79.8% | 58.9% | **98.1%** |
| pneumatics | 162 | 64.2% | 72.8% | 56.8% | 92.4% |

**Phân loại 54 ca auto-match sai (máy tự phân loại theo mã, không xem tay):** 32 ca (59%) cùng sản phẩm, biến thể khách để ngỏ; 8 ca (15%) cùng sản phẩm nhưng khách **có** ghi chi tiết (`C3`, `NR`, inox); 14 ca (26%) sản phẩm khác. Lưu ý: "cùng sản phẩm" không đồng nghĩa "chấp nhận được" (giao bản inox khi khách không yêu cầu vẫn là sai), nên 98.1% chỉ là cận trên.

**Đánh đổi (2.000 query):**

| Threshold | Delta | Tự động hóa | Đúng nhãn |
|---|---|---|---|
| 0.80 | 0.02 | 68.3% | 93.6% |
| **0.90** | **0.02** | **59.2%** | **95.4%** |
| 0.94 | 0.05 | 39.1% | 97.8% |
| 0.96 | 0.05 | 36.2% | 98.1% |

Manual Review: 815 dòng, đáp án nằm trong Top-3 ở **59%** (trước đây 51%).

**Quy tắc quan trọng trong UI:** inquiry đến từ **shop** (khách đã xem gợi ý và vẫn bấm gửi) **không bao giờ được tô xanh** — lựa chọn của khách là bằng chứng phủ định mạnh hơn điểm của model; các mã khách đã thấy được đánh dấu "customer saw this". Inquiry đến từ **mail/CSV** (khách chưa thấy gợi ý nào) vẫn được tự động chốt như bình thường.

**Latency** (laptop CPU, đo 2026-09-20): tìm kiếm **0.4–1.5 s/query** cho top-10; LLM parser thêm 0.7–1.8 s nếu chưa cache; nạp model 1 lần ~60 s.

### 5.7 Việc tiếp theo
1.  ✅ **Ổn định code:** đã xong (2026-09-20) — `detect_supplier_prefixes` / `SUPPLIER_PREFIX_PATH` đã được viết trong `normalization.py`, pipeline chạy thông tới `build_crossref.py`. Chi tiết ở 5.7.
2.  **Ablation** từng luật viết tay (2 seed, không tốn API vì đã cache) → biết luật nào đáng giữ / chuyển sang cấu hình.
3.  **Đánh giá có mục tiêu cho luật thuộc tính:** chỉ các query có từ khớp luật, bật/tắt `S_attr`.
4.  **Cải thiện Manual Review:** chỉ 51% có đáp án trong Top-3 → tăng recall ứng viên (vd. biến thể `W`/`NR` bị cắt khỏi 25 ứng viên đầu).
5.  Ý định "Alternative zu / baugleich / Ersatz für" → không auto-match.
6.  Chạy 1000 mẫu để chốt số cho pitching; đo latency / query.

---

## 6. Tiền tố nhà cung cấp: từ luật viết tay sang học từ catalog (2026-09-20)

**Vấn đề:** Boie gắn tiền tố nội bộ vào mã của một số nhà cung cấp (`2026219-2Z` thực ra là FAG `6219-2Z`). Trước đây ba nhà cung cấp này được **gõ tay** trong `normalization.py`, nên mỗi lần Boie thêm nhà cung cấp mới lại phải sửa code.

**Cách phân biệt:** tiền tố nội bộ phủ gần như toàn bộ mã của một hãng, còn tiền tố series thật thì rải rác.

| Hãng | Mã trong catalog | Tiền tố 3 ký tự phổ biến nhất | Kết luận |
|---|---|---|---|
| FAG | 13.550 | `202` = **96.7%** | tiền tố nội bộ |
| GLYCO | 322 | `109` = **99.7%** | tiền tố nội bộ |
| INA | 6.494 | `101` = **68.1%**, `102` = 10.5% | tiền tố nội bộ (cả hai) |
| SKF | 16.792 | `620` = 4.0% | series thật → bỏ qua |
| Ganter | 56.514 | `300` = 5.4% | series thật → bỏ qua |

Ngưỡng: ≥ 100 mã mỗi hãng, tiền tố chính ≥ 50%, tiền tố phụ ≥ 5% (chỉ tính khi đã có tiền tố chính, để bắt được `102` của INA).

**Kết quả:** học ra đúng `{FAG: [202], INA: [101, 102], GLYCO: [109]}` — **trùng khớp danh sách viết tay cũ**, nên hành vi hệ thống không đổi và không cần đo lại metrics. Kết quả tương tự khi chạy với dữ liệu đầy đủ (163.709 sản phẩm) lẫn khi mới giải nén một phần (73.159 sản phẩm).

**Luồng hoạt động:** `create_database.py` gọi `detect_supplier_prefixes()` → ghi `preprocessed_data/supplier_prefixes.json` → những lần import sau, `normalization.py` tự nạp file này thay cho danh sách viết tay. Nếu thiếu file thì quay về danh sách viết tay, không có trạng thái hỏng. Cờ `ABLATE=supplier_prefix` vẫn hoạt động như cũ.

**Bẫy đã gặp:** với ngưỡng 30 mã, hệ thống bắt nhầm `Fluid Concept` (59 mã đều bắt đầu bằng `200` — đó là cách đánh số riêng của họ) và sinh ra 8 alias trùng nhầm sản phẩm khác. Vì vậy ngưỡng được đặt ở 100.

**Lưu ý cho người chạy lại:** chuỗi mô tả của `supplier_prefix` trong `feature_flags.py` vẫn ghi "(normalization.py)" theo nghĩa luật viết tay — chỉ là chú thích, không ảnh hưởng chạy.

---

## 7. Giao diện demo (`src/app.py`, 2026-09-20)

```bash
streamlit run src/app.py
```

Hai chế độ, chọn ở sidebar:

| Chế độ | Nguồn dữ liệu | Cần gì |
|---|---|---|
| **Results** | đọc `results/pipeline_results_*.json` | **chỉ cần `streamlit`** — chạy được trên laptop bất kỳ, dùng khi pitch |
| **Live search** | gọi thẳng `llm_parser.parse_query` + `search_engine.hybrid_search` | model fine-tune, Chroma, `OPENROUTER_API_KEY` |

`search_engine` được import **lazy** trong `load_engine()`, nên chế độ Results vẫn chạy trên máy không có torch. Model chỉ load một lần nhờ `@st.cache_resource`.

### 7.1 Map dữ liệu → giao diện

| Trường JSON | Hiển thị |
|---|---|
| `metrics.*` | 4 ô số lớn: Top-1, Top-3, Automation rate, Auto-match precision |
| `metrics_by_category` | hàng số theo bearings / pneumatics / standard parts |
| `routing` | viền **xanh** Auto-matched / viền **vàng** Manual review |
| `query` | tiêu đề anfrage |
| `parsed_query` | dòng "Extracted from the text — Manufacturer / Part_Number" |
| `confidence_delta` | "Margin over rank 2" — giải thích vì sao được auto hay không |
| `attribute_rules_fired` | chip các luật thuộc tính đã kích hoạt |
| `predictions[].confidence` | số % lớn bên phải thẻ |
| `predictions[].method` | tách thành 4 dòng lý do: Part number / Manufacturer / Description (cross-encoder) / Technical attributes |
| `predictions[].product.images[0].url` | ảnh sản phẩm |
| `predictions[].product.attributes` | dòng thông số |
| `is_label` | ✅ / ✗ — **chỉ có ý nghĩa khi xem kết quả test**, không tồn tại ở chế độ live |

Bộ lọc: All / Auto-matched / Manual review / Errors only, lọc theo warengruppe, và ô tìm trong nội dung anfrage.

### 7.2 Cần để ý

*   **Ngôn ngữ:** nhãn giao diện tiếng Anh; **nội dung sản phẩm và câu hỏi của khách giữ nguyên tiếng Đức** vì đó là dữ liệu thật của Boie. Đừng dịch, sẽ làm demo sai lệch.
*   **`is_label` không có ở chế độ live.** Dấu ✅/✗ chỉ so với nhãn của tập test. Khi demo live đừng hứa hệ thống "biết" đáp án đúng.
*   **64% sản phẩm có `link` rỗng**, nên nút "Open in shop" chỉ hiện ở một phần. 92% thẻ có ảnh; pneumatics **không có ảnh nào** (CSV không có media) → hiện chữ "no image".
*   **Giá trị thuộc tính bị đệm 3 chữ số thập phân** (`8.000 mm`). UI tự rút gọn thành `8 mm` khi hiển thị; dữ liệu gốc vẫn vậy.
*   **Bộ lọc "Errors only" trộn hai thứ rất khác nhau** — xem 7.3. Nên tách thành hai bộ lọc riêng trước khi demo.
*   `run.input_file` trong file kết quả ghi đường dẫn kiểu Windows (`preprocessed_data\unseen_test_data.csv`) vì được chạy trên máy Windows. Không ảnh hưởng gì.

### 7.3 Những gì nhìn ra được qua bộ lọc "Errors only" (seed 2026, 1000 mẫu)

223 ca Top-1 sai, chia theo **khách có ghi mã hay không**:

| Nhóm | Số ca | Top-1 đúng | Auto | Auto sai | Precision auto |
|---|---|---|---|---|---|
| **A.** khách ghi **đúng mã nhãn**, hệ thống vẫn trượt | 477 | 95% | 392 | 3 | **99.2%** |
| **B.** khách ghi mã sp được chọn, nhãn là biến thể khác | 29 | 0% | 12 | 12 | 0% |
| **C.** khách không ghi mã khớp nào | 494 | 65% | 200 | 10 | 95.0% |

Ba điều rút ra:

1.  **176/223 ca sai có nhãn nằm ngoài Top-3** → là bài toán *recall*, không phải bài toán xếp hạng. Hiển thị thêm lựa chọn không cứu được.
2.  **Nhóm A còn 22 ca lỗi khó biện minh**: khách gõ đúng mã mà hệ thống chọn biến thể dài hơn. Mẫu lặp rõ nhất: `6006-2Z` (5 lần) → chọn `W 6006-2Z`. Đúng hồi quy đã ghi ở 5.3 do alias bỏ tiền tố chữ. Luật "ưu tiên mã khớp chính xác, chỉ tính cụm dài nhất trong câu" đo trên Top-3 có sẵn: **sửa 4, hỏng 0** (cận dưới, vì chạy thật còn kéo thêm được ứng viên ngoài Top-3).
3.  **Confidence không tách được nhóm C**: trung vị nhóm C là 0.91, 260/494 ca ≥0.90 — gần bằng nhóm A. Và **cả 10 ca C auto sai đều đến từ method `Code`**, không phải Semantic (0 ca auto-match nào thuần semantic). Nghĩa là rò rỉ nằm ở chỗ `S_code` tính **khớp mờ ngang với khớp chính xác**, chứ không nằm ở ngưỡng routing.

Ý tưởng đang cân nhắc — **routing theo loại bằng chứng** thay vì theo điểm số: khớp chính xác → auto; nhiều biến thể cùng mã gốc khớp chính xác → hỏi khách; chỉ khớp mờ hoặc chỉ có mô tả → nhân viên kiểm. Đo thô: cấm hoàn toàn nhóm C auto-match thì automation 60.4% → 39.2%, precision lên ~99%. Cần đo thêm mức trung gian (C vẫn auto nhưng ngưỡng 0.94–0.96) trước khi quyết.

⚠️ Phương án "đưa mọi ứng viên ≥90% cho khách chọn" **đã đo và không nên làm ở dạng thô**: kích hoạt ở 289/1000 anfrage, cứu được 5 ca auto sai nhưng biến 191 ca đang đúng thành câu hỏi thừa (automation 60.4% → 41.0%). Lý do: hầu như mã vòng bi nào cũng có họ biến thể `-Z`/`/C3`/`N`/`NR` cùng đạt trên 90%, nên điều kiện này bắn vào ca bình thường. Chỉ đáng làm khi kết hợp: *không có ứng viên nào khớp chính xác* **và** có nhiều biến thể cùng mã gốc.
