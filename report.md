# Bao cao audit toan dien du an JavS

## 1. Thong tin chung

- Thoi diem audit: 2026-03-12
- Pham vi: toan bo repo hien co trong worktree, bao gom tai lieu, ma nguon, test suite, script ho tro, cau truc thu muc, va tinh trang hygiene hien tai
- Nguyen tac thuc hien: chi doc/phan tich, khong sua source code; ket qua duoc tong hop tu tai lieu `.md`, code Python, test, lint, va coverage
- Tinh trang worktree: dirty; co file da sua chua commit va mot so file/fixture untracked, vi vay bao cao nay phan anh dung hien trang dang lam viec, khong phai nhat thiet la trang thai commit sach

## 2. Ngu canh du an hien tai

### 2.1 Muc tieu san pham

Theo `README.md`, `CONTEXT.md`, va `docs/USAGE.md`, JavS la mot CLI Python bat dong bo de:

- Quet thu muc video JAV
- Trich xuat movie ID tu filename
- Scrape metadata tu nhieu nguon
- Tong hop metadata theo priority
- Tao NFO/anh poster/thumb/trailer
- Sap xep va doi ten thu vien media

Du an duoc dinh vi la ban viet lai hien dai cua Javinizer bang Python, tap trung vao:

- `asyncio` + `aiohttp`
- Typer/Rich cho CLI
- Pydantic cho config/model
- Plugin-based scraper
- Proxy va Cloudflare handling

### 2.2 Kien truc va phan lop

Kien truc du an nhin chung duoc tach lop kha ro:

- `javs/config`: model config, load/save config, sync template
- `javs/core`: orchestration, scan, aggregate, tao NFO, organizer
- `javs/scrapers`: base scraper, registry, scraper cu the
- `javs/services`: HTTP, image, translation, Emby
- `javs/utils`: logging, string/html helper
- `javs/models`: movie model, file model
- `tests`: unit test parser, config, scanner, proxy, organizer, nfo
- `docs`, `README.md`, `CONTEXT.md`: tai lieu huong dan va mo ta nguyen tac
- `scripts`: cac script thu nghiem thuc te/thu Cloudflare

### 2.3 Quy mo code hien tai

Theo thong ke tu repo hien tai:

- Khoang 4,780 dong Python trong package `javs/`
- Khoang 1,291 dong test Python trong `tests/`
- 30+ module Python chinh
- 3 file `.md` chinh trong repo de dinh nghia nguc canh: `README.md`, `CONTEXT.md`, `docs/USAGE.md`

### 2.4 Nhan xet tong quan ve architecture

Mat tich cuc:

- Tach lop ro theo domain
- Core business flow de theo doi
- Model du lieu co type hint va Pydantic
- Scraper registry giup mo rong du an de dang
- Logging co chu y masking proxy credential

Mat ton dong:

- Tai lieu va implementation dang lech nhau o nhieu diem
- Cac duong I/O thuc te (CLI, engine, DMM, config sync, image, Emby) chua duoc bao phu test tot
- Co cac dead config fields va dead config schema
- Co mot so bug logic nghiem trong o lifecycle HTTP, routing proxy, va config sync

## 3. Tai lieu `.md` va muc do khop voi code

### 3.1 `README.md`

Tai lieu nay mo ta du an dung huong va de hieu, nhung dang co nhieu claim vuot qua hien trang thuc te:

- Quang ba `javs config sync` nhu mot tinh nang da o trang thai san sang
- Noi test suite co "100% mocked coverage for API resiliency"
- Nhan manh type safety va strict quality

Van de:

- `javs config --help` hien tai khong hien action `sync`
- Coverage thuc te chi 50%, khong phai 100%
- `pyproject.toml` khong co `mypy` du `README.md` va `CONTEXT.md` de cap den strict typing voi mypy

### 3.2 `CONTEXT.md`

`CONTEXT.md` la file huu ich nhat de hieu tham vong kien truc, vi no:

- Mo ta package layout
- Liet ke tinh nang da "hoan thanh"
- Ghi ro coding guideline
- Ghi ro security trade-off `ssl=False`

Van de:

- Nhieu muc trong "Completed Features" hien khong phan anh dung implementation thuc te
- Claim "Per-Request Proxy Routing" khong dung voi SOCKS proxy
- Claim "Configuration Upgrader" dang qua lac quan so voi implementation hien tai
- Claim "129 passing tests" dung ve so luong test nhung khong phan anh coverage gap

### 3.3 `docs/USAGE.md`

`docs/USAGE.md` giup hieu luong su dung CLI, nhung dang co khoang cach voi implementation:

- Huong dan `javs config sync` duoc viet nhu mot command on dinh
- Noi test suite "covering 100% of the core paths"
- Mo ta `sort` nhu quy trinh hoan chinh, trong khi mot so path I/O/edge case chua duoc bao phu test

### 3.4 Ket luan ve tai lieu

Tai lieu hien tai tot o muc "truyen thong tam nhin" nhung chua tot o muc "nguon su that van hanh". Tinh trang phu hop hien tai:

- Dung cho onboarding tong quan: tot
- Dung lam nguon su that de tin tuong implement/van hanh: chua tot
- Dung lam tai lieu troubleshooting cho bug hien tai: chua du

## 4. Verification snapshot

### 4.1 Lenh da chay

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q
./venv/bin/javs config --help
```

### 4.2 Ket qua

| Hang muc | Ket qua | Nhan xet |
| --- | --- | --- |
| Test suite | `129 passed in 0.80s` | Test unit/parser dang xanh |
| Ruff | fail, `22` loi | Lint khong clean, chu yeu o file moi/chua format va scanner |
| Coverage | `50%` tong | Bao phu test thap hon rat nhieu so voi tai lieu |
| CLI help | `config sync` khong hien trong help | Tai lieu va help runtime lech nhau |

### 4.3 Coverage theo module quan trong

| Module | Coverage | Danh gia |
| --- | ---: | --- |
| `javs/cli.py` | 0% | Khong co test cho CLI |
| `javs/config/updater.py` | 0% | Tinh nang config sync chua duoc test |
| `javs/scrapers/dmm.py` | 0% | Mot scraper lon nhung khong duoc test |
| `javs/services/emby.py` | 0% | Khong co test |
| `javs/services/image.py` | 0% | Khong co test |
| `javs/core/engine.py` | 23% | Orchestration thuc te gan nhu khong duoc test |
| `javs/core/organizer.py` | 31% | I/O path quan trong chua duoc test du |
| `javs/services/http.py` | 41% | Chi test helper logic, chua test request flow thuc |
| `javs/core/aggregator.py` | 67% | Tam on, nhung CSV path/filter/tagline con lo hong |
| `javs/core/scanner.py` | 65% | Cover format co ban, chua phu edge case regrression moi |

### 4.4 Danh gia verification

Ket luan verification:

- Repo khong o trang thai "clean"
- Test dang xanh nhung chua bao ve nhung khu vuc rui ro nhat
- Lint dang fail nen kho noi codebase dang "clean"
- Coverage thuc te khong khop claim trong tai lieu

## 5. Danh gia cau truc thu muc

### 5.1 Diem tot

- Cau truc package ro va de tim code
- Separation of concerns hop ly
- `tests/` duoc tach rieng, co `scrapers/` subfolder rieng
- Co `docs/` va `CONTEXT.md`, tot cho onboarding

### 5.2 Diem can cai thien

- `scripts/` dang chua script thu nghiem chen voi repo chinh, mot so script doc secret tu file tracked
- `default_config.yaml` vua la template vua co dau hieu duoc dung nhu noi luu secret trong script thu nghiem
- Worktree dirty va co fixture/test data untracked lam giam tinh tin cay cua repo hygiene
- Nhieu field config/feature placeholder ton tai nhung chua duoc noi vao flow chinh

### 5.3 Danh gia tong the

Cau truc thu muc dat muc kha, nhung governance cua configuration, script thu nghiem, va test artifact chua that su gon sach.

## 6. Danh gia code cleanliness

### 6.1 Diem tot

- Dat ten module/ham/lop nhin chung de hieu
- Type hints duoc dung kha nhieu
- Co docstring tot o nhieu module
- Regex/scanner duoc viet co chu thich
- Core flow `scan -> scrape -> aggregate -> organize` ro rang

### 6.2 Diem ton dong

- Ruff dang fail 22 loi, bao gom import ordering, line too long, blank whitespace, trailing whitespace
- Pattern `except Exception` xuat hien rong, trai voi guideline trong `CONTEXT.md`
- Co nhieu config field duoc khai bao nhung khong duoc dung
- Docs, default template, runtime config, va helper script khong dong bo
- `config sync` va `default_config.yaml` chua dat muc "production-ready"

### 6.3 Danh gia

Codebase co nen tang tot, nhung chua dat muc "clean code" o nghia van hanh duoc an tam. Chat luong hien tai nam o muc:

- Kien truc: kha
- Hygiene: trung binh-yeu
- Dong bo docs/runtime: yeu
- Readability: kha
- Regression safety: trung binh

## 7. Finding chi tiet

Moi finding duoi day duoc trinh bay theo 5 truong:

- `Severity`
- `Evidence`
- `Impact`
- `Recommended fix`
- `Tests to add`

---

### Finding F1: `HttpClient` lifecycle khong an toan trong `JavsEngine`

- Severity: P0
- Evidence:
  - `javs/core/engine.py:81` mo `async with self.http` trong `find()`
  - `javs/core/engine.py:180` lai mo `async with self.http` trong `sort_path()`
  - `sort_path()` goi `self.find()` trong tung task song song
- Impact:
  - Cung mot `HttpClient` duoc dung chung cho nhieu task nhung bi dong o nhieu tang context manager
  - Co nguy co mot task dong session trong luc task khac van dang scrape
  - Day la bug logic nghiem trong cho `sort`, dac biet khi `throttle_limit > 1`
  - Hanh vi co the khong de tai hien trong unit test vi `engine.py` gan nhu khong duoc test
- Recommended fix:
  - Chi de mot tang quan ly vong doi `HttpClient`
  - Chon mot trong hai huong:
    - `find()` khong tu quan ly context, chi dung session da mo san
    - hoac `sort_path()` khong mo `async with self.http` va de `find()` tu xu ly
  - Uu tien cach 1 de session duoc dung chung trong batch sort
  - Tach ro phan "session lifecycle" khoi phan "business flow"
- Tests to add:
  - Engine integration test voi fake scraper + fake HttpClient de dam bao `close()` chi duoc goi mot lan
  - Test `sort_path()` voi nhieu file va `throttle_limit > 1`
  - Test regression: khong co request nao fail do session bi close som

---

### Finding F2: Routing proxy SOCKS vo hieu hoa `use_proxy`

- Severity: P0
- Evidence:
  - `javs/services/http.py:121` tao `ProxyConnector` ngay khi co SOCKS proxy
  - `javs/services/http.py:151` tra `{}` cho `use_proxy=False`, nhung connector van global
  - `ScraperRegistry` du kien per-scraper routing thong qua `config.use_proxy`
- Impact:
  - Voi SOCKS proxy, tat ca request deu di qua proxy, ke ca scraper dang dat `use_proxy=False`
  - Claim "per-request proxy routing" trong tai lieu khong con dung
  - Co the lam sai expectation ve bao mat, route, latency, va debugging
- Recommended fix:
  - Tach session/connector cho route co proxy va khong proxy
  - Hoac bo `ProxyConnector` global, thay bang client/session rieng cho request can SOCKS
  - Dong bo docs sau khi sua implementation
- Tests to add:
  - Test integration voi fake connector de xac nhan request `use_proxy=False` khong dung SOCKS
  - Test ca HTTP proxy va SOCKS proxy
  - Test `ScraperRegistry.get_enabled()` + `HttpClient` end-to-end cho routing logic

---

### Finding F3: Pipeline `config sync` dang lech schema va bo qua `--config`

- Severity: P0
- Evidence:
  - `javs/config/updater.py:23` dinh nghia `sync_user_config()` nhung luon su dung `get_default_config_path()`
  - `javs/cli.py:146` goi `sync_user_config()` khong truyen `config_path`
  - `javs/data/default_config.yaml:1` dung top-level keys `movie`, `file`, `translation`, `cloudflare`, `scraper_proxy`
  - `javs/config/models.py:300` root model `JavsConfig` khong co cac top-level keys nay
  - Kiem tra runtime cho thay `JavsConfig(**yaml.safe_load(default_config.yaml))` van load duoc do extra bi ignore, dan den nhieu key trong template khong co tac dung thuc te
- Impact:
  - `javs config sync` co the tao/merge ra file YAML dep nhung nhieu key bi runtime ignore
  - Nguoi dung tuong da config thanh cong trong khi ung dung van dung default model
  - `--config path` se in thong bao thanh cong cho custom path nhung sync thuc te van ghi vao default path
  - Day la bug config rat nguy hiem vi kho nhan ra
- Recommended fix:
  - Cho `sync_user_config()` nhan path tu CLI
  - Dong bo `default_config.yaml` theo `JavsConfig`
  - Neu muon giu template comment-rich, can tao template tu schema dung va kiem tra round-trip
  - Dat `extra='forbid'` hoac co validation ro hon neu muon ngan schema lech
- Tests to add:
  - Test `config sync --config /tmp/custom.yaml`
  - Test round-trip template -> `load_config()` -> expected values
  - Test template co comment nhung van map dung schema

---

### Finding F4: Cloudflare manual config la dead path trong app flow

- Severity: P1
- Evidence:
  - `javs/services/http.py:239` ho tro `cf_clearance` va `cf_user_agent`
  - `scripts/real_scrape_test.py:17` doc section `cloudflare` tu `javs/data/default_config.yaml`
  - `javs/config/models.py:263` chi co `JavlibraryConfig` cookies va `browser_user_agent`
  - `javs/core/engine.py:52` khoi tao `HttpClient` ma khong truyen bat ky gia tri Cloudflare nao
  - `javs/services/http.py:330` con huong dan nguoi dung dien vao `cloudflare:` trong `config.yaml`, nhung model runtime khong ho tro top-level nay
- Impact:
  - Script thu nghiem co duong config rieng, nhung ung dung chinh khong dung duoc
  - Nguoi dung se gap tinh trang docs/sai huong dan khi gap Cloudflare
  - Lam tang chi phi support va debugging
- Recommended fix:
  - Chon mot schema duy nhat cho Cloudflare/Javlibrary auth
  - Wire du lieu do vao `HttpClient` trong engine
  - Xoa script convention khac schema neu khong can
  - Cap nhat thong diep loi trong `HttpClient.get_cf()`
- Tests to add:
  - Test `load_config()` + `JavsEngine()` truyen dung cookie/User-Agent vao `HttpClient`
  - Test search Javlibrary voi manual CF config bat
  - Test message/help khong huong dan sai schema nua

---

### Finding F5: `javlibraryja` va `javlibraryzh` tra ve URL gia `_detail_`

- Severity: P1
- Evidence:
  - `javs/scrapers/javlibrary.py:458` va `javs/scrapers/javlibrary.py:508` tra ve `...?v=_detail_`
  - Duong EN cung co fallback tuong tu o `javs/scrapers/javlibrary.py:84`
  - Test hien tai chi test parser HTML, khong test `search()`
- Impact:
  - Direct-match search co the tra ve URL khong hop le
  - Scrape tiep theo co nguy co fail, hoac scrape nham trang
  - Tac dong truc tiep den manual `find` va pipeline `sort`
- Recommended fix:
  - Su dung canonical URL neu co
  - Neu trang search da la detail page, lay URL thuc te/canonical tu response
  - Khong bao gio tra ve placeholder `_detail_`
- Tests to add:
  - Test `search()` direct-match cho EN/JA/ZH
  - Test fallback khi canonical link ton tai va khi khong ton tai

---

### Finding F6: Organizer di chuyen tat ca subtitle trong thu muc

- Severity: P1
- Evidence:
  - `javs/core/organizer.py:306-315` iterate moi subtitle file trong `file.directory.iterdir()`
  - Khong co bat ky buoc filter nao theo stem, ID, part number, hay basename
- Impact:
  - Neu mot thu muc co nhieu video hoac subtitle khong lien quan, subtitle co the bi move nham sang phim khac
  - Day la bug data integrity thuc te
- Recommended fix:
  - Chi move subtitle neu basename/stem match file video hien tai
  - Ho tro part-aware matching: `pt1`, `pt2`, `cd1`, `A/B`
  - Can xu ly subtitle da co ten dich vu/nhom phu de nhung van match cung movie
- Tests to add:
  - Test thu muc co 2 video + 2 subtitle rieng
  - Test multi-part subtitle
  - Test subtitle khong lien quan khong bi di chuyen

---

### Finding F7: SSL verification bi tat toan cuc

- Severity: P1
- Evidence:
  - `javs/services/http.py:224`
  - `javs/services/http.py:366`
  - `javs/services/http.py:411`
  - `CONTEXT.md:122` co ghi chu day la trade-off co chu y
- Impact:
  - Mo rong be mat tan cong MITM cho toan bo HTTP flow
  - Khong chi scraper kho chiu chung SSL issue ma tat ca request/download deu bi anh huong
  - De lam nhoan ky vong bao mat trong moi truong production
- Recommended fix:
  - Khoanh vung `ssl=False` cho scraper/host can thiet
  - Co config flag ro rang de bat/tat verify SSL
  - Mac dinh nen verify SSL, chi bypass theo whitelist
- Tests to add:
  - Test per-scraper SSL policy
  - Test default path van verify SSL
  - Test host whitelist/bypass hoat dong dung

---

### Finding F8: Tai lieu, tooling va runtime khong dong bo

- Severity: P2
- Evidence:
  - `README.md:20` quang ba `config sync`
  - `README.md:78` noi "100% mocked coverage for API resiliency"
  - `docs/USAGE.md:57` huong dan `javs config sync`
  - `docs/USAGE.md:148` noi test suite cover 100% core paths
  - `CONTEXT.md:9` va `CONTEXT.md:19` de cap `mypy`
  - `pyproject.toml:47-53` khong co `mypy`
  - `./venv/bin/javs config --help` khong hien `sync`
- Impact:
  - Onboarding va trust cua collaborator giam
  - De dan den quyet dinh sai khi debug/van hanh
  - Co the tao expectation khong dung ve muc do chuan bi cua du an
- Recommended fix:
  - Cap nhat lai docs theo implementation thuc te
  - Chi giu claim nao co bang chung tu test/CI
  - Dua lint/type/coverage gate vao CI truoc khi cap nhat docs marketing
- Tests to add:
  - CLI help snapshot test cho `config`
  - CI job cho lint, tests, va coverage threshold

---

### Finding F9: Nhieu field config dang dead hoac chua noi vao flow

- Severity: P2
- Evidence:
  - `javs/config/models.py:156` `required_fields`
  - `javs/config/models.py:166` `rename_folder_in_place`
  - `javs/config/models.py:263` `JavlibraryConfig`
  - `javs/config/models.py:325` `check_updates`
  - Tim kiem usage cho thay cac field nay gan nhu khong duoc consume trong code path chinh
- Impact:
  - Lam model config phinh va gay nham lan
  - Tang chi phi maintain
  - Nguoi dung co the tuong mot setting co tac dung trong khi thuc te vo hieu
- Recommended fix:
  - Lap danh sach field "supported now" va "planned"
  - Hoac implement day du, hoac xoa/tam an khoi schema public
  - Them validation/canh bao neu user dung field chua supported
- Tests to add:
  - Test warning khi dung config field chua supported
  - Test field implemented thuc su co tac dung end-to-end

## 8. Bao mat

### 8.1 Diem tot

- Proxy password duoc mask trong logging
- `InvalidProxyAuthError` duoc tach rieng
- Config proxy co validation protocol

### 8.2 Rui ro chinh

1. `ssl=False` o toan bo request/download path
2. `default_config.yaml` dang tracked du `.gitignore` ghi ro muon ignore vi credential
3. `scripts/real_scrape_test.py` doc cookie Cloudflare tu file tracked
4. Neu nguoi dung dien secret that vao template tracked, nguy co lo secret cao
5. Broad `except Exception` o nhieu noi co the che dau rui ro an ninh va lam mat trace

### 8.3 Muc do danh gia

- Credential masking: kha
- Secret hygiene: yeu
- TLS/SSL posture: yeu
- Overall security posture: trung binh-yeu

## 9. Hieu nang

### 9.1 Diem tot

- Async-native architecture la lua chon dung
- Aggregation/scraping co the chay song song
- HTTP session co connection pool

### 9.2 Nut that hien tai

- DMM scraper co N+1 request de lay actress thumb va trailer
- Khong co cache cho actress/thumb/trailer lap lai
- `sleep=3` mac dinh trong engine giam throughput batch sort
- Download dang dung synchronous file write ben trong coroutine
- Lifecycle session hien tai co the lam mat loi the tai su dung connection

### 9.3 Danh gia

- Kien truc hieu nang: kha
- Hieu nang runtime thuc te: trung binh
- Do on dinh duoi tai/so file lon: chua du bang chung

## 10. Logic nghiep vu

### 10.1 Luong nghiep vu tong the

Luong `scan -> scrape -> aggregate -> organize` de hieu va hop ly.

### 10.2 Van de logic chinh

- Config template lech schema lam logic config thuc te khac logic tai lieu
- Subtitle matching qua rong
- Javlibrary direct-match URL khong an toan
- Proxy routing voi SOCKS trai voi logic `use_proxy`
- Session lifecycle co the pha batch flow

### 10.3 Danh gia

Logic domain co huong dung, nhung co nhieu "integration logic bugs" o vung giua core, config, va service layer.

## 11. Diem manh cua du an

- Architecture phan lop ro
- Scanner va parser unit test kha tot
- Co mindset maintainability va logging structure
- Co test suite hoat dong va pass nhanh
- Core model duoc thiet ke kha de mo rong
- Scraper registry la mot quyet dinh kien truc tot

## 12. Danh gia tong hop

### 12.1 Cham diem tuong doi

| Hang muc | Diem tham chieu | Nhan xet |
| --- | ---: | --- |
| Architecture | 7.5/10 | Nen tang tot, phan lop ro |
| Code cleanliness | 5.5/10 | Co type hints/docstring nhung lint fail va dong bo kem |
| Correctness | 5.0/10 | Co mot so bug logic nghiem trong o path tich hop |
| Security | 4.5/10 | SSL tat toan cuc va hygiene secret chua on |
| Performance | 6.0/10 | Async dung huong nhung co bottleneck va thieu cache |
| Test maturity | 5.0/10 | Test xanh nhung coverage tong thap va lo hong o module quan trong |

### 12.2 Ket luan cuoi

JavS la mot du an co nen tang kien truc tot va co ti le "y tuong dung" cao. Tuy nhien, trang thai hien tai chua the goi la clean hay san sang on dinh cho van hanh nghiem tuc vi:

- Docs khong con la nguon su that tin cay
- Config sync/template dang sai schema
- Proxy SOCKS routing va HTTP lifecycle co bug logic nghiem trong
- Coverage thap o nhung module quan trong nhat
- Security posture bi ha thap boi `ssl=False` va hygiene secret

Neu uu tien dung 3 nhom viec P0/P1 trong `plan.md`, du an co the duoc nang len rat nhanh ve do on dinh.
