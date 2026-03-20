# Bao cao audit cap nhat du an JavS

## 1. Thong tin chung

- Thoi diem audit cap nhat: 2026-03-20
- Pham vi: toan bo repo hien co trong worktree, bao gom tai lieu `.md`, ma nguon Python, test suite, script ho tro, va tinh trang quality gate hien tai
- Nguyen tac thuc hien: ban 2026-03-16 la dot doi chieu tai lieu; ban cap nhat 2026-03-17 tong hop ket qua sau dot sua code, them regression tests, va dong bo lai tai lieu/runtime
- Boi canh worktree: dirty; bao cao nay phan anh dung trang thai dang lam viec hien tai, khong mac dinh la mot commit sach

## 2. Ngu canh du an hien tai

### 2.1 Muc tieu san pham

Theo `README.md`, `CONTEXT.md`, va `docs/USAGE.md`, JavS la mot CLI Python bat dong bo de:

- Quet thu muc video JAV
- Trich xuat movie ID tu filename
- Goi nhieu scraper de lay metadata
- Tong hop metadata theo thu tu uu tien
- Tao NFO, tai poster/thumb/trailer
- Sap xep va doi ten thu vien media

### 2.2 Kien truc va phan lop

Kien truc tong the van duoc tach lop ro rang:

- `javs/config`: model cau hinh, loader, updater
- `javs/core`: orchestration, scanner, aggregator, organizer, NFO
- `javs/scrapers`: base scraper, registry, scraper cu the
- `javs/services`: HTTP, image, translation, Emby
- `javs/utils`: helper logging, HTML, string
- `javs/models`: model du lieu file va movie
- `tests`: unit tests va scraper fixtures
- `docs`, `README.md`, `CONTEXT.md`: tai lieu, huong dan, va architecture notes
- `scripts`: script debug/thuc nghiem

### 2.3 Danh gia tong quan ve architecture

Diem tot:

- Async architecture la lua chon dung cho bai toan scrape batch
- `ScraperRegistry` giup mo rong nguon scrape kha de dang
- Pydantic models giu config va data model kha gon
- Core flow `scan -> scrape -> aggregate -> organize` de theo doi

Diem ton dong:

- Benchmark hieu nang scrape that truoc/sau van chua co day du cho moi scraper/policy
- Template config van can tiep tuc giu ky luat secret hygiene

## 3. Tai lieu `.md` va muc do khop voi code

### 3.1 Cac file `.md` da giup hieu du an ra sao

Bo ba `README.md`, `CONTEXT.md`, va `docs/USAGE.md` van cho ngu canh dung ve:

- Tam nhin san pham
- Package layout
- Dinh huong async CLI + scraper plugin
- Vai tro cua config, proxy, Cloudflare, va sorting pipeline

### 3.2 Diem lech giua tai lieu va runtime hien tai

Sau dot cap nhat 2026-03-17, cac diem lech ro rang nhat da duoc dong bo lai:

- `README.md`, `docs/USAGE.md`, va `CONTEXT.md` khong con claim cu ve `100% coverage`, `mypy`, hay `129 passing tests`
- `./venv/bin/javs config --help` da hien `sync`
- Tai lieu Cloudflare/Javlibrary auth da thu gon ve cac field runtime that su consume

Phan debt tai lieu con lai khong con o muc "claim sai ro rang", ma chu yeu la:

- can tiep tuc giu docs cap nhat khi coverage/test count thay doi
- `CONTEXT.md` va docs van nen duoc ra soat lai neu co them refactor lon o P2

### 3.3 Ket luan ve tai lieu

Tai lieu hien tai da tro lai gan hon voi runtime:

- Dung de hieu tam nhin: tot
- Dung de tin vao hanh vi runtime hien tai: kha hon ro rang
- Dung de troubleshooting: kha, nhung van can tiep tuc cap nhat neu co thay doi P2

## 4. Verification snapshot

### 4.1 Lenh da chay

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q
./venv/bin/python -m ruff check javs tests
./venv/bin/javs config --help
./venv/bin/python scripts/benchmark_sort_batch.py --files 8 --throttle-limit 4 --sleep 2 --scrape-delay 0.05 --organize-delay 0.01 --compare-zero-sleep
./venv/bin/python scripts/benchmark_real_scrape.py --help
```

### 4.2 Ket qua hien tai

| Hang muc | Ket qua | Nhan xet |
| --- | --- | --- |
| Test suite | `248 passed in 2.31s` | Tang tiep nho Javlibrary interactive recovery, credential helper tests, va hardening output/runtime cho Cloudflare flow |
| Ruff | `All checks passed!` | Da sach lint, day la cai thien ro rang so voi audit truoc |
| Coverage | `79%` tong | Da vuot them moc `75%`, va long-tail coverage gap chinh cua P2.2 da duoc dong |
| CLI help | `config sync` da hien trong help | Help/runtime da duoc dong bo va co test CLI bao ve |
| Real benchmark | `dmm`/`r18dev` da co snapshot dau tien | Da co so request/latency thuc te, khong con chi dua vao synthetic harness |

### 4.3 Coverage theo module quan trong

| Module | Coverage | Danh gia |
| --- | ---: | --- |
| `javs/cli.py` | 64% | Da cover them `find`, `sort`, `scrapers`, `config path/edit/unknown` |
| `javs/scrapers/dmm.py` | 86% | Da co test cho search fallback, scrape, SPA redirect, actress thumb, va trailer parse |
| `javs/services/emby.py` | 100% | Da cover ca success va failure path |
| `javs/services/image.py` | 95% | Da co test crop thanh cong va error tolerance |
| `javs/core/engine.py` | 69% | Da co them test pacing regression: scrape slot khong bi giu trong organizer work |
| `javs/core/organizer.py` | 71% | Da co them test preview, NFO, download helper, screenshot naming, va move guard |
| `javs/services/http.py` | 75% | Da co them test nested parent, partial cleanup, request failure, va no-hang close quanh `download()` |
| `javs/services/translator.py` | 93% | Da khoa disabled path, keep-original description, va success/failure path cho `googletrans`/`deepl` |
| `javs/scrapers/registry.py` | 100% | Da cover register/get/list/proxy routing/warning/import-failure path |
| `javs/scrapers/base.py` | 98% | Da cover `normalize_id()` va `search_and_scrape()` cho success/no-result/error |
| `javs/config/updater.py` | 84% | Da co test custom-path sync va deprecation cleanup |
| `javs/scrapers/javlibrary.py` | 67% | Da co test direct-match EN/JA/ZH cho canonical va non-canonical path |
| `javs/scrapers/mgstage.py` | 81% | La diem tang truong chat luong ro rang cua dot nay |

### 4.4 Y nghia cua snapshot moi

So voi audit truoc, codebase da co tien trien that:

- Da dong lai baseline lint
- Da tang test count
- Da tang coverage tong
- Da xu ly mot so bug integration quan trong

Tuy vay, repo van chua o muc "audit clean" vi:

- Benchmark scrape that da co snapshot dau tien, nhung moi o muc ban dau va chua mo rong qua nhieu repeat/scraper
- Policy rate-limit theo scraper van chua duoc tach rieng; global `sleep=2` moi la diem can bang tam thoi

## 5. Thay doi noi bat ke tu audit truoc

### 5.1 Cac van de da duoc xu ly ro rang

1. Lifecycle `HttpClient` trong `JavsEngine` da duoc tach hop ly hon.
2. Routing proxy SOCKS da duoc sua theo mo hinh hai session direct/proxy.
3. `config sync` da ton trong custom path.
4. `default_config.yaml` da duoc viet lai de map vao `JavsConfig`.
5. Lint da xanh.
6. Logic move subtitle da duoc thu hep theo stem video.
7. Contract `verify_ssl` da duoc sua dung nghia va da co regression tests.
8. Docs, CLI help, va config sync help/runtime da duoc dong bo lai.
9. Cloudflare/Javlibrary auth surface da thu gon ve cac field runtime that su consume.
10. Javlibrary interactive recovery da chay duoc trong terminal that, voi prompt `cf_clearance`, reuse `browser_user_agent`, va desktop notification best-effort.
10. Javlibrary direct-match da khong con fallback `_detail_`.
11. DMM/Emby/Image/CLI/Organizer da duoc bo sung test va day coverage len muc thuc dung.
12. Dead config surface da duoc don tiep: `scrapers.options`, `tag_csv`, `javdb`, va mot nhom location/format placeholder da duoc loai khoi template cong khai.
13. Long-tail coverage cho `translator`, `registry`, va `scrapers/base` da duoc dong.
14. Da them `scripts/benchmark_real_scrape.py` de do request/latency tren luong scrape that ma khong tron voi synthetic benchmark.
15. `HttpClient.download()` da duoc harden bang temp-file `.part`, atomic replace, cleanup khi stream/request loi, va async file write bang `aiofiles`.

### 5.2 Cac van de chi moi duoc xu ly mot phan

1. Hieu nang da co cai thien do duoc trong synthetic benchmark, nhung chua co benchmark tren scrape thuc du cho moi policy/scraper.
2. Rate-limit behavior cua `r18dev` va `javlibrary` van can tiep tuc theo doi neu sau nay toi uu them pacing.

### 5.3 Cai thien moi duoc ghi nhan

- `mgstage.py` khong con o trang thai gan nhu stub; scraper nay da co implementation va test rieng (`tests/scrapers/test_mgstage.py`)
- `tests/test_config_sync.py` moi da bao ve schema template va custom-path sync
- `tests/test_engine.py` va bo test SSL moi trong `tests/test_proxy.py` da khoa bug contract cua `HttpClient`
- `tests/test_cli.py`, regression tests moi cho subtitle matching, Cloudflare wiring, dual-session proxy, va Javlibrary direct-match da duoc them
- `tests/test_emby.py`, `tests/test_image.py`, va `tests/scrapers/test_dmm.py` moi da bao phu cac module truoc day `0%`
- Template config va sync cleanup hien tai da loai bo them `scrapers.options`, `tag_csv`, `javdb`, va mot nhom location/format flags khong noi runtime
- `sort_path()` da duoc doi pacing strategy de khong giu scrape slot trong luc organizer dang chay; benchmark synthetic cho thay `sleep=3` giam tu `6.1355s` xuong `3.1189s` tren harness hien tai
- `tests/test_translator.py`, `tests/scrapers/test_registry.py`, va `tests/scrapers/test_base.py` moi da dong nhom coverage long-tail truoc day con mo
- `tests/test_proxy.py` da khoa them nested parent, cleanup partial file, request setup failure, no-hang close, va async-file write quanh `download()`
- `scripts/benchmark_real_scrape.py` va `tests/test_benchmark_real_scrape.py` moi da chuan hoa luong do request/latency cho benchmark manual that
- `javs/services/javlibrary_auth.py` moi da them helper prompt/test/save cho `cf_clearance` va `browser_user_agent`, cung voi output guidance de doc hon
- Snapshot live dau tien da cho thay:
  - `find` voi `dmm`, `4` ID, `sleep=2`: `34.7462s`, `4/4 found`
  - `sort` voi `dmm`, `4` ID: `sleep=2` -> `27.9004s`, `sleep=0` -> `21.0701s`, overhead ~ `1.32x`
  - `find` voi `r18dev`, `ABP-420`, `sleep=2`: `1.5990s`
- Benchmark matrix mo rong da bo sung them:
  - `dmm` `find` `repeat=3`: movie median `5.8837s`, request median `1.3553s`, fail `0`
  - `dmm` `sort` `repeat=3`: `sleep=2` mean `26.0813s`, median `26.3468s`; `sleep=0` mean `19.4442s`, median `19.1805s`
  - `r18dev` `find` `repeat=3`: `8 found`, `4 no_result`, da thay `429 Too Many Requests`
  - `mgstageja` `find` `repeat=3` tren `FSDSS-198`: movie median `8.9190s`, request median `3.2818s`, fail `0`
  - `javlibrary` `find` `repeat=3` tren `ABP-420`: snapshot ban dau `3/3 no_result` do Cloudflare `403`
- Benchmark script `sort` da duoc sua mapping de uu tien `original_filename`, tranh danh dau nham `skipped` khi scraper canonicalize ID nhu `ABP-420DOD`
- Tu 2026-03-20, Javlibrary da co interactive recovery thuc te:
  - prompt hien dung trong terminal khi Cloudflare block
  - chi can nhap `cf_clearance`; `browser_user_agent` duoc tai su dung neu da co trong config
  - output Cloudflare guidance da duoc rut gon trong log va render thanh block de doc hon trong terminal
  - benchmark that voi cookie hop le cho thay Javlibrary van co the gap `429`, nhung `sleep=2` on dinh hon `sleep=0`

## 6. Finding chi tiet cap nhat

Moi finding duoi day co:

- `Status`
- `Severity`
- `Evidence`
- `Impact`
- `Recommended fix`
- `Tests to add`

---

### Finding F1: Lifecycle `HttpClient` trong `JavsEngine`

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/core/engine.py:68-132` cho thay `find()` khong con tu mo/dong `async with self.http`
  - `javs/core/engine.py:134-146` them `find_one()` de quan ly session cho luong goi doc lap
  - `javs/core/engine.py:199-201` `sort_path()` mo session mot lan o muc batch
  - `javs/cli.py:97-99` da chuyen sang goi `engine.find_one(...)`
- Impact:
  - Rui ro dong shared session giua cac task trong `sort` da giam rat manh
  - Batch scrape hien tai co architecture hop ly hon audit truoc
  - Regression-risk chinh cua finding nay da duoc khoa bang test
- Recommended fix:
  - Giu nguyen mo hinh `find()` + `find_one()` hien tai
  - Bo sung regression tests cho session lifecycle truoc khi tiep tuc refactor engine
- Tests to add:
  - Da them test `find_one()` mo/dong session dung mot lan
  - Da them test `sort_path()` giu session mo cho batch

---

### Finding F2: Routing proxy SOCKS va `use_proxy`

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/services/http.py:108-109` tach `_session_direct` va `_session_proxy`
  - `javs/services/http.py:137-164` `_get_session(use_proxy=...)` tra ve session phu hop
  - `javs/services/http.py:166-178` chi truyen `proxy=` per-request voi HTTP proxy; SOCKS duoc route qua connector cua session proxy
- Impact:
  - Loi cu "SOCKS connector ap len toan session" da duoc giai quyet tren implementation hien tai
  - Hanh vi route direct/proxy da duoc khoa bang test cho ca SOCKS va HTTP proxy
- Recommended fix:
  - Giu mo hinh dual-session hien tai
  - Them integration-style tests cho direct/proxy session selection
- Tests to add:
  - Da them test `use_proxy=False`/`use_proxy=True` cho route direct/proxy

---

### Finding F3: `config sync`, schema template, va custom path

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/config/updater.py:22-43` `sync_user_config(config_path: Path | None = None)` da nhan custom path
  - `javs/cli.py:146-149` CLI da truyen `config_path=path`
  - `tests/test_config_sync.py:17-72` xac nhan template load duoc vao `JavsConfig` va khong con unknown top-level keys
  - `tests/test_config_sync.py:78-113` xac nhan sync tao file moi va giu override cua user
  - `javs/data/default_config.yaml:1` da duoc viet lai theo schema runtime
- Impact:
  - Loi nghiem trong nhat cua pipeline config da duoc xu ly
  - Config tao ra hien tai map duoc vao runtime that
  - Help text va CLI-level custom-path flow da co test bao ve
- Recommended fix:
  - Giu current contract
  - Can nhac strict hon voi unknown keys o `load_config()` neu muon tranh drift tai tuong lai
- Tests to add:
  - Da them test CLI cho `javs config sync --config /tmp/custom.yaml`
  - Da them test help text cho command `config`

---

### Finding F4: Cloudflare manual config trong app flow

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/core/engine.py` da truyen `cf_clearance` va `browser_user_agent` vao `HttpClient`
  - `javs/services/http.py` da dung `cf_clearance` neu co va da co test cho manual-cookie path
  - `javs/config/models.py` va `default_config.yaml` da bo cac cookie fields khong duoc runtime consume
  - `javs/cli.py` va `javs/services/javlibrary_auth.py` da them flow `javs config javlibrary-cookie`, `javs config javlibrary-test`, va interactive recovery trong `find`/`sort`
- Impact:
  - Public auth surface da gon hon va de hieu
  - Engine -> HttpClient wiring va manual-cookie path da duoc bao ve bang test
  - Javlibrary khong con o trang thai "bi block la dung tay sua YAML"; user co the refresh credential ngay trong luc scrape
- Recommended fix:
  - Giu current public schema toi thieu cho Cloudflare/Javlibrary auth
  - Neu mo rong them auth field trong tuong lai, phai wire runtime va test cung luc
- Tests to add:
  - Da them test `JavsEngine` khoi tao `HttpClient` voi `cookie_cf_clearance` va `browser_user_agent`
  - Da them test manual cookie path cua `get_cf()`
  - Da them test cho prompt/reuse `browser_user_agent`, credential validation, va Cloudflare guidance output

---

### Finding F5: Javlibrary direct-match URL fallback `_detail_`

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/scrapers/javlibrary.py` khong con fallback `_detail_`
  - Direct-match khong co canonical se tra ve search URL co the fetch lai
  - Da co test direct-match EN/JA/ZH cho ca canonical va non-canonical path
- Impact:
  - Placeholder URL `_detail_` da bi loai bo khoi flow direct-match
  - Truong hop thieu canonical van con URL scrape duoc thong qua search URL
  - Bug user-facing anh huong `find` va `sort` da duoc dong
- Recommended fix:
  - Giu current fallback an toan bang search URL co the tai su dung
  - Neu sau nay `HttpClient` expose duoc final URL, co the can nhac doi tu search URL sang final URL that
- Tests to add:
  - Da them test `search()` direct-match cho EN/JA/ZH
  - Da them test truong hop co canonical va khong co canonical

---

### Finding F6: Subtitle move scope

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `javs/core/organizer.py:306-327` chi move subtitle neu `sub_stem.startswith(video_stem)`
- Impact:
  - Loi integrity cu "move tat ca subtitle trong thu muc" da duoc thu hep ro rang
  - Behavior hien tai da hop ly hon cho cac case `ABC-123.srt`, `ABC-123.chi.srt`, `ABC-123.eng.ass`
  - Regression-risk cua logic nay da giam nhieu nho test moi
- Recommended fix:
  - Giu logic match hien tai, sau do bo sung test cho subtitle matching
  - Danh gia them cac pattern multipart truoc khi mo rong tiep
- Tests to add:
  - Da them test subtitle lien quan duoc move, subtitle khong lien quan khong bi move

---

### Finding F7: TLS/SSL posture trong `HttpClient`

- Status: Da dong trong dot 2026-03-17
- Severity: Da dong
- Evidence:
  - `javs/services/http.py` da truyen `ssl=self._verify_ssl` trong `get()`, `get_json()`, va `download()`
  - `tests/test_proxy.py` da co test moi cho `verify_ssl=True -> ssl=True` va `verify_ssl=False -> ssl=False`
  - `tests/test_engine.py` da co test xac nhan `JavsEngine` van explicit `HttpClient(verify_ssl=False)` nhu mot trade-off runtime
- Impact:
  - Contract cua `HttpClient` da tro lai ro rang va khong con tinh trang "dung vi vo tinh"
  - Engine van giu duoc explicit trade-off SSL cho scraping sites, trong khi cac callsite mac dinh khac van strict theo default
  - Rui ro maintainability cua bien `verify_ssl` da giam ro rang
- Recommended fix:
  - Giu nguyen semantics hien tai
  - Neu sau nay them callsite moi, quyet dinh ro giua strict SSL va explicit opt-out thay vi dua vao "accidental behavior"
- Tests to add:
  - Da them test cho `verify_ssl=True/False`
  - Da them test cho engine wiring

---

### Finding F8: Tai lieu, tooling, va runtime van chua dong bo hoan toan

- Status: Da dong
- Severity: Da dong
- Evidence:
  - `README.md`, `CONTEXT.md`, `docs/USAGE.md` da duoc cap nhat lai theo runtime hien tai
  - `./venv/bin/javs config --help` da hien `sync`
  - Da co test CLI bao ve help text va custom-path sync
- Impact:
  - Rui ro lech ky vong giua docs va runtime da giam ro rang
  - Chi phi support tu cac claim cu da giam
- Recommended fix:
  - Giu current nguyen tac: chi de claim nao co bang chung tu test/tooling hien tai
- Tests to add:
  - Da them test help text cho `javs config`
  - Co the can nhac them checklist docs-runtime alignment vao CI sau nay

---

### Finding F9: Dead config surface va feature flags chua noi vao flow

- Status: Da dong trong dot 2026-03-17
- Severity: P2
- Evidence:
  - `required_fields` da duoc wire vao `sort_path()`
  - `rename_folder_in_place`, `check_updates`, cookie fields cu cua `javlibrary`, `scrapers.options`, `sort.metadata.tag_csv`, `sort.format.output_folder`, `sort.format.group_actress`, `locations.uncensor_csv`, `locations.history_csv`, `locations.tag_csv`, va `javdb` da duoc remove/deprecate khoi public template
  - `load_config()` va `sync_user_config()` da co logic ignore/prune deprecated keys
- Impact:
  - Be mat config public da gon hon va sat runtime hon
  - Debt maintainability cua schema da giam ro rang
- Recommended fix:
  - Giu current nguyen tac: field cong khai nao khong co runtime contract thi khong de trong template
  - Neu tiep tuc deprecate them, giu pattern `warn + prune + test` nhu hien tai
- Tests to add:
  - Da them test sync cleanup cho deprecated keys chinh
  - Da them test template khong con advertize cac section placeholder

---

### Finding F10: Test maturity van chua theo kip cac fix moi

- Status: Da xu ly mot phan
- Severity: P2
- Evidence:
  - `javs/core/engine.py` da len `61%`
  - `javs/core/engine.py` sau dot pacing da len `69%`
  - `javs/services/http.py` da len `75%`
  - `javs/scrapers/javlibrary.py` da len `67%`
  - `javs/cli.py`: `64%`
  - `javs/core/organizer.py`: `71%`
  - `javs/scrapers/dmm.py`: `86%`
  - `javs/services/emby.py`: `100%`
  - `javs/services/image.py`: `95%`
  - `javs/services/translator.py`: `93%`
  - `javs/scrapers/registry.py`: `100%`
  - `javs/scrapers/base.py`: `98%`
- Impact:
  - Nhieu fix quan trong nay da an toan hon khi refactor
  - Muc tieu coverage P2 da dat ro hon; phan con lai chu yeu la benchmark va hardening dai han
- Recommended fix:
  - Chuyen uu tien tu long-tail coverage sang benchmark scrape that va quyet dinh cho async file I/O strategy
  - Khong can tri hoan feature nho chi vi muc `>=65%` nua, vi target nay da vuot ro
- Tests to add:
  - Da them translator/registry/base tests va benchmark-script helper tests
  - Da them dual-session proxy test
  - Da them subtitle matching test
  - Da them Javlibrary direct-match test
  - Da them Cloudflare config wiring test
  - Da them DMM/Emby/Image/CLI/Organizer regression tests
  - Con mo chu yeu cho benchmark scrape that va quyet dinh async file I/O strategy cua `download()`

## 7. Bao mat

### 7.1 Diem tot hien tai

- Password trong proxy URL van duoc mask khi log
- `InvalidProxyAuthError` va `ProxyConnectionFailedError` tach ro hon
- SSL posture thuc te cua engine hien tai khong con o trang thai "global-off" nhu audit truoc

### 7.2 Rui ro bao mat hien tai

1. `default_config.yaml` van tracked trong repo, nhung be mat nhap secret da gon hon va hien chu yeu con `javlibrary.cookie_cf_clearance`.
2. Mot so callsite debug/utility van chua explicit ve SSL policy, de de drift neu sau nay co them use case dac biet.
3. Van can giu ky luat khong dua cookie/secret that vao template tracked hoac fixture.

### 7.3 Danh gia muc do

- Credential masking: kha
- Secret hygiene: trung binh
- TLS semantics/maintainability: trung binh
- Tong the security posture: trung binh

## 8. Hieu nang

### 8.1 Diem tot

- Async architecture van la nen tang dung
- Dual-session trong `HttpClient` giup connection reuse hop ly hon cho proxy/direct flow
- MGStage va config sync co tien trien theo huong chat luong tot hon
- Ghi NFO da duoc offload sang thread, giam block event loop o sort path
- DMM khong con la diem mu cua test suite, nen viec toi uu sau nay se de do va danh gia hon
- Da co benchmark harness rieng (`scripts/benchmark_sort_batch.py`) de do orchestration cost ma khong can live network
- Pacing cua `sort_path()` da khong con giu scrape slot trong organizer phase

### 8.2 Nut that con lai

- `sleep: 2` mac dinh trong `default_config.yaml` van la throttle rat thu cong, du da nhe hon truoc
- `javs/services/http.py` da chuyen `download()` sang async file write, nhung van chua co cac toi uu khac nhu cache/request coalescing
- Chua thay co cache cho du lieu lap lai nhu actress/trailer/thumb
- Benchmark synthetic cho thay `sleep=2` van la nut that lon nhat hien tai tren batch nho:
  - `8` files, `throttle_limit=4`, `scrape_delay=0.05`, `organize_delay=0.01`
  - `sleep=2` -> `2.1176s`
  - `sleep=0` -> `0.1130s`
  - slowdown ~ `18.74x`
- Benchmark synthetic lich su cho thay redesign pacing da giam `sleep=3` tu `6.1355s` xuong `3.1189s`
- Benchmark scrape that dau tien cho thay tac dong cua `sleep=2` tren batch `dmm` thuc te nhe hon synthetic:
  - `sort` `dmm`, `4` ID, `sleep=2` -> `27.9004s`
  - `sort` `dmm`, `4` ID, `sleep=0` -> `21.0701s`
  - slowdown ~ `1.32x`
- Request latency thuc te:
  - `dmm` `find`, `4` ID: `17` request `get`, median `1.9792s`, p95 `7.8659s`
  - `r18dev` `find`, `ABP-420`: `2` request `get_json`, median `0.7931s`
- Benchmark matrix mo rong cho thay:
  - `dmm` batch `repeat=3`: slowdown cua `sleep=2` so voi `sleep=0` van quanh `1.34x-1.37x`, khong con o muc qua lon nhu synthetic
  - `r18dev` direct path nhanh, nhung da cham `429` khi lap `repeat=3`, nen bai toan rate-limit cua scraper nay nang hon viec ha global `sleep`
  - `javlibrary` voi cookie hop le:
    - `find`, `4` ID, `repeat=3`, `sleep=2`: `7 found`, `5 no_result`, movie median `2.1589s`, request median `1.1258s`, `2` request fail
    - `sort`, `4` ID, `repeat=3`, `sleep=2`: `9 processed`, `3 skipped`, batch mean `13.5586s`, request fail `0`
    - `sort`, `4` ID, `repeat=3`, `sleep=0`: `6 processed`, `6 skipped`, batch mean `9.0043s`, request fail `3`
    - `sleep=0` nhanh hon khoang `1.5x`, nhung ty le thanh cong thap hon ro rang so voi `sleep=2`
- Quyết định hiện tại hop ly nhat la giu global `sleep=2`, khong ha tiep, va chi can nghien cuu cooldown theo scraper neu sau nay muon harden `r18dev`/`javlibrary`
- Mau benchmark Javlibrary moi cung tiep tuc ung ho quyet dinh giu `sleep=2` neu uu tien do on dinh thay vi raw throughput

### 8.3 Danh gia

- Kien truc hieu nang: kha
- Hieu nang runtime thuc te: trung binh
- Khả nang do luong/benchmark: con thieu

## 9. Logic nghiep vu

### 9.1 Luong nghiep vu tong the

Luong `scan -> scrape -> aggregate -> organize` van hop ly va de doc.

### 9.2 Danh gia logic hien tai

- Core session lifecycle logic da hop ly hon truoc
- Proxy routing logic da phu hop hon voi `use_proxy`
- Config sync logic da tiệm can schema runtime that
- Subtitle move logic da an toan hon
- Cloudflare va Javlibrary auth/direct-match da duoc don gon va khoa bang test
- SSL semantics da duoc chot dung nghia va khoa bang test

### 9.3 Ket luan logic

So voi audit truoc, bug integration nghiem trong da giam ro rang. Van de lon nhat hien tai khong con la "core flow hong", ma la:

- benchmark da du co baseline, nhung chua co policy cooldown rieng cho scraper rate-limited
- file I/O strategy cua `download()` da duoc xu ly; phan con mo nghieng ve pacing/rate-limit policy theo scraper
- policy throttling theo scraper neu muon toi uu them van con mo, du global `sleep=2` da co co so de giu nguyen

## 10. Diem manh cua du an

- Architecture va package layout ro rang
- Test suite pass nhanh, feedback loop tot
- Lint da sach tro lai
- Config sync va template schema da duoc chinh dung huong
- MGStage la mot vi du tot cho viec nang chat luong thuc chat, khong chi la dọn docs

## 11. Danh gia tong hop

### 11.1 Cham diem tham chieu moi

| Hang muc | Diem tham chieu | Nhan xet |
| --- | ---: | --- |
| Architecture | 7.5/10 | Nen tang van tot va ro rang |
| Code cleanliness | 7.9/10 | Lint da xanh, docs/runtime da khop hon, config surface da duoc don sau hon |
| Correctness | 8.4/10 | Cac bug contract P0/P1 lon da dong, P2.1/P2.2 da dat muc tieu chinh, Javlibrary recovery/runtime prompt da duoc khoa bang test va kiem chung that |
| Security | 6.3/10 | SSL semantics va auth surface da ro rang hon, nhung van can ky luat secret hygiene va explicit SSL policy |
| Performance | 7.6/10 | Da co benchmark synthetic, snapshot scrape that, benchmark Javlibrary co cookie hop le, va `download()` da khong con sync file write; nut that lon nhat con mo la policy rieng cho scraper rate-limited |
| Test maturity | 8.7/10 | Suite da len 248 tests va 79% coverage; long-tail coverage va Javlibrary recovery flow da duoc khoa tot hon |

### 11.2 Ket luan cuoi

JavS dang o trang thai tot hon ro rang so voi audit truoc. Day khong con la repo "co nhieu P0 mo" nua; mot so van de integration quan trong da duoc xu ly that su trong code:

- lifecycle engine da on hon
- proxy SOCKS da route dung hon
- config sync/schema da on dinh hon
- subtitle move da an toan hon
- lint da xanh
- Javlibrary da co recovery flow thuc dung thay vi chi dua vao huong dan sua config thu cong

Tuy vay, repo van chua nen duoc xem la "audit complete" vi:

- benchmark scrape that da co snapshot, nhung van can mo rong them neu muon chot policy rieng cho tung scraper
- benchmark synthetic da xong; default `sleep` da giam xuong `2` va hien nen duoc giu nguyen cho policy global
- Javlibrary da benchmark duoc voi cookie hop le, va ket qua tiep tuc ung ho viec giu `sleep=2` neu uu tien do on dinh thay vi raw speed
- bai toan con mo lon nhat hien nay la policy rate-limit/pacing theo scraper, khong con la file I/O strategy cua `download()`

Huong di hop ly nhat luc nay la dong nhung muc con mo trong `plan.md` truoc khi tiep tuc them feature moi.
