# Ke hoach cap nhat sau audit lai du an JavS

## 1. Muc tieu

Ke hoach nay khong lap lai audit cu mot cach may moc. Muc tieu la:

- Ghi nhan muc nao da duoc xu ly that su
- Dong cac viec con mo theo thu tu uu tien moi
- Tap trung vao phan con rui ro that, khong tiep tuc "fix lai" nhung muc da on

Ke hoach duoi day duoc cap nhat theo trang thai code hien tai den 2026-03-22.

## 2. Trang thai tong quan cua roadmap cu

| Hang muc cu | Trang thai moi | Ghi chu |
| --- | --- | --- |
| Lifecycle `HttpClient` trong engine | Xong | Da co regression test cho `find_one()` va batch `sort_path()` |
| Proxy routing HTTP/SOCKS per scraper | Xong | Da co test cho tach session direct/proxy |
| `config sync` + schema alignment | Xong | Custom path, help text, va template schema da khop runtime |
| Lint clean baseline | Xong | `ruff` da xanh |
| Cloudflare config wiring | Xong | Public auth surface da thu gon va da co regression test |
| Javlibrary direct-match URL | Xong | Khong con fallback `_detail_`, direct-match EN/JA/ZH da co test |
| Subtitle matching | Xong | Da co regression test cho subtitle theo stem video |
| SSL policy/global-off | Da dong | `verify_ssl` da map dung nghia sang `aiohttp ssl` va da co regression test |
| Docs/runtime alignment | Xong | README, USAGE, CONTEXT, va CLI help da duoc dong bo |
| Dead config surface | Xong | Da wire `required_fields` va loai bo/deprecate cac section placeholder con lai khoi template cong khai |
| Javlibrary interactive recovery | Xong | Da co prompt `cf_clearance`, reuse `browser_user_agent`, desktop notification best-effort, va retry trong run hien tai |
| In-place metadata refresh | Xong | Da co `javs update` de refresh NFO/sidecars trong thu vien da sort ma khong move video |

## 3. Nguyen tac trien khai tiep theo

- Khong refactor rong khi chua co regression test cho cac fix vua co
- Muc nao da xu ly o muc implementation thi uu tien dong no bang test va docs, khong mo them pham vi sua khong can thiet
- Uu tien "fix nghia/contract" truoc "them feature"
- Moi thay doi tren config hoac networking deu phai co verification ro rang

## 4. P0 da dong nhung can hardening

### P0.1 Hardening lifecycle `HttpClient` trong `JavsEngine`

- Status: Da dong
- Goal: khoa chat fix hien tai de khong bi vo lai
- Files/Subsystems affected:
  - `javs/core/engine.py`
  - tests cho engine
- Fix approach:
  - Giu nguyen thiet ke `find()` la internal flow su dung session da mo
  - Giu `find_one()` la public entrypoint cho luong standalone
  - Khong refactor them engine truoc khi co test bao ve lifecycle
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - Test xac nhan `find_one()` mo/dong session dung mot lan
  - Test xac nhan `sort_path()` giu session mo den het batch
- Risk:
  - Neu tiep tuc sua engine khi chua co test, bug cu co the quay lai rat nhanh
- Definition of done:
  - Da dat

### P0.2 Hardening routing proxy HTTP/SOCKS

- Status: Da dong
- Goal: khoa chat mo hinh dual-session hien tai
- Files/Subsystems affected:
  - `javs/services/http.py`
  - tests proxy/integration
- Fix approach:
  - Giu `_session_direct` va `_session_proxy`
  - Ghi ro contract: SOCKS route theo session, HTTP proxy route theo per-request kwargs
  - Khong doi lai networking layer neu chua co ly do ro rang
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - Test cho `use_proxy=False` khong dung proxy session
  - Test cho `use_proxy=True` dung proxy session
- Risk:
  - Refactor networking khong co test se de vo logic route vua moi sua xong
- Definition of done:
  - Da dat

### P0.3 Hardening `config sync` va schema alignment

- Status: Da dong
- Goal: chot config contract cho dung ca runtime lan CLI
- Files/Subsystems affected:
  - `javs/config/updater.py`
  - `javs/data/default_config.yaml`
  - `javs/cli.py`
  - docs config
- Fix approach:
  - Giu template schema hien tai la nguon su that
  - Khong mo rong them top-level keys moi neu chua duoc model hoa
  - Chinh help text va docs de phan anh dung `sync`
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - Test cho `javs config --help`
  - Test CLI cho `javs config sync --config ...`
  - `./venv/bin/javs config --help`
- Risk:
  - Neu help/docs khong doi theo code, van se tiep tuc gay nham lan cho user
- Definition of done:
  - Da dat

### P0.4 Lint baseline

- Status: Da dong
- Goal: giu repo o trang thai lint clean
- Files/Subsystems affected:
  - Toan repo Python
- Fix approach:
  - Khong merge thay doi moi neu `ruff` do
  - Can nhac dua `ruff check` vao CI gate
- Verification:
  - `./venv/bin/python -m ruff check javs tests`
- Risk:
  - Thap
- Definition of done:
  - `ruff` la bat buoc trong local/CI workflow

## 5. P1: muc vua dong va muc dang mo

### P1.1 Sua nghia va contract cua `verify_ssl`

- Status: Da dong trong dot 2026-03-17
- Goal: bien ten, comment, va hanh vi cua `HttpClient` phai cung mot nghia
- Files/Subsystems affected:
  - `javs/services/http.py`
  - `javs/core/engine.py`
  - `javs/services/emby.py`
  - `javs/core/organizer.py`
  - `javs/scrapers/base.py`
  - `scripts/real_scrape_test.py`
- Fix approach:
  - Da sua logic request de `verify_ssl=True` thi truyen `ssl=True`, `verify_ssl=False` thi truyen `ssl=False`
  - Da audit nhanh cac callsite `HttpClient()` hien co; engine van explicit `verify_ssl=False` nhu mot trade-off runtime, cac callsite con lai van giu default strict
  - Da them test khoa contract nay truoc khi tiep tuc sua networking
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - `./venv/bin/python -m pytest tests/test_proxy.py tests/test_engine.py -q`
  - `./venv/bin/python -m ruff check javs tests`
  - Test moi xac nhan `verify_ssl=True/False` map dung sang request `ssl=True/False`
  - Test moi xac nhan `JavsEngine` van khoi tao `HttpClient(verify_ssl=False)` mot cach co y
- Risk:
  - Contract da duoc chot, nhung neu sau nay mo rong them callsite can quyet dinh ro la giu strict SSL hay explicit opt-out
- Definition of done:
  - Da dat

### P1.2 Chot lai Cloudflare/Javlibrary auth surface

- Status: Da dong
- Goal: chi giu nhung field auth co tac dung that trong app flow
- Files/Subsystems affected:
  - `javs/config/models.py`
  - `javs/core/engine.py`
  - `javs/services/http.py`
  - docs config
- Fix approach:
  - Da giu lai surface runtime toi thieu: `cookie_cf_clearance` va `browser_user_agent`
  - Da bo/deprecate `cookie_cf_bm`, `cookie_session`, `cookie_userid`
  - Da bo tri lai message/manual path theo section `javlibrary`
  - Da them `javs config javlibrary-cookie` va `javs config javlibrary-test`
  - Da them interactive recovery flow khi `javlibrary` bi Cloudflare block trong `find`/`sort`
  - Da toi gian prompt: chi bat buoc nhap `cf_clearance`; `browser_user_agent` chi hoi neu config dang trong
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - Test cho config -> engine -> `HttpClient`
  - Test cho manual-cookie path cua `get_cf()`
- Risk:
  - Neu giu qua nhieu field mo ho, debt se tiep tuc phinh ra
- Definition of done:
  - Da dat

### P1.3 Dong hoan toan bug direct-match cua Javlibrary

- Status: Da dong
- Goal: khong con tra ve URL gia `_detail_`
- Files/Subsystems affected:
  - `javs/scrapers/javlibrary.py`
  - tests scraper
- Fix approach:
  - Da bo fallback `_detail_`
  - Direct-match khong co canonical se tra ve search URL co the tai su dung
  - Da giu dung language path cho EN/JA/ZH
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - Test moi cho direct-match EN/JA/ZH
- Risk:
  - Thap; localized trong scraper
- Definition of done:
  - Da dat

### P1.4 Dong bo docs va CLI help voi implementation hien tai

- Status: Da dong
- Goal: docs va help phai tro lai thanh nguon su that
- Files/Subsystems affected:
  - `README.md`
  - `CONTEXT.md`
  - `docs/USAGE.md`
  - `javs/cli.py`
- Fix approach:
  - Sua help text `config` de hien `sync`
  - Sua lai claim ve `100% coverage`, `mypy`, `129 tests`, `per-request proxy routing`
  - Chi giu claim nao co bang chung hien tai
- Verification:
  - `./venv/bin/javs config --help`
  - Doc review chong cheo docs/runtime
  - Test CLI cho help text
- Risk:
  - Neu cap nhat docs truoc khi chot contract SSL/Cloudflare, se phai sua lai them mot lan nua
- Definition of done:
  - Da dat

### P1.5 Bo sung regression tests cho cac fix vua xong

- Status: Da dong
- Goal: chuyen cac fix hien tai tu "co ve dung" thanh "duoc khoa bang test"
- Files/Subsystems affected:
  - `tests/`
  - `javs/core/engine.py`
  - `javs/services/http.py`
  - `javs/core/organizer.py`
  - `javs/scrapers/javlibrary.py`
- Fix approach:
  - Da them test cho:
    - engine lifecycle
    - proxy dual-session
    - subtitle matching
    - Cloudflare wiring
    - Javlibrary direct-match
    - config sync custom path va deprecation cleanup
    - CLI help/config sync
- Verification:
  - `./venv/bin/python -m pytest tests -q`
  - `./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q`
- Risk:
  - Neu bo qua buoc nay, nhung muc "da xu ly" van de bi hoi quy
- Definition of done:
  - Da dat

## 6. P2: clean-up va nang maturity

### P2.1 Ra soat va giam dead config surface

- Status: Da dong trong dot 2026-03-17
- Goal: config public chi chua field co nghia
- Files/Subsystems affected:
  - `javs/config/models.py`
  - `javs/data/default_config.yaml`
  - docs config
- Fix approach:
  - Da wire `required_fields` vao runtime sort
  - Da deprecate/xoa khoi template cong khai:
    - `rename_folder_in_place`
    - `check_updates`
    - cookie fields cu cua `javlibrary`
    - `scrapers.options`
    - `sort.metadata.tag_csv`
    - `sort.format.output_folder`
    - `sort.format.group_actress`
    - `locations.uncensor_csv`
    - `locations.history_csv`
    - `locations.tag_csv`
    - `javdb`
- Verification:
  - Test config parsing
  - Test behavior/warning cua cac field duoc giu lai
- Risk:
  - Co the cham vao compatibility config cua user hien tai
- Definition of done:
  - Moi field public deu co chu nghia runtime ro
  - Trang thai hien tai:
    - `required_fields` da duoc wire vao `sort_path()`
    - Cac placeholder section chinh da duoc prune khoi `default_config.yaml`
    - `load_config()` va `sync_user_config()` da co test cleanup cho cac key deprecated
    - Da dat cho pham vi audit config hien tai

### P2.2 Tang coverage vao cac module rui ro cao

- Status: Da dong trong dot 2026-03-17
- Goal: nang maturity cua test suite len muc bao ve vung integration quan trong
- Files/Subsystems affected:
  - `javs/cli.py`
  - `javs/core/engine.py`
  - `javs/services/http.py`
  - `javs/scrapers/dmm.py`
  - `javs/services/emby.py`
  - `javs/services/image.py`
- Fix approach:
  - Uu tien module dang `0%` hoac rat thap
  - Dat target thuc te:
    - tong coverage >= 65% o pha dau
    - module quan trong >= 50%
- Verification:
  - `./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q`
- Risk:
  - Co the ton effort neu thieu fixtures/fakes cho HTTP-heavy modules
  - Definition of done:
  - Coverage tong va coverage module quan trong tang len muc de phong hoi quy
  - Trang thai hien tai:
    - Coverage tong: `79%`
    - `javs/cli.py`: `64%`
    - `javs/core/organizer.py`: `71%`
    - `javs/core/engine.py`: `69%`
    - `javs/services/http.py`: `75%`
    - `javs/services/emby.py`: `100%`
    - `javs/services/image.py`: `95%`
    - `javs/services/translator.py`: `93%`
    - `javs/scrapers/registry.py`: `100%`
    - `javs/scrapers/base.py`: `98%`
    - `javs/scrapers/dmm.py`: `86%`
    - `javs/scrapers/javlibrary.py`: `67%`
    - Muc tieu `>= 65%` tong va `>= 50%` cho module quan trong da dat

### P2.3 Cai thien hieu nang va I/O strategy

- Status: Da dat cho pha synthetic benchmark trong dot 2026-03-18
- Goal: giam latency va bottleneck o batch sort
- Files/Subsystems affected:
  - `javs/services/http.py`
  - `javs/scrapers/dmm.py`
  - `javs/core/engine.py`
  - co the `javs/services/image.py`
- Fix approach:
  - Ra soat `sleep` mac dinh va chinh sach rate-limit
  - Can nhac cache nho cho lookup lap lai
  - Can nhac offload file write khoi event loop neu can
- Verification:
  - Benchmark batch nho truoc/sau
  - So sanh request count neu co cache
- Risk:
  - Doi hieu nang co the tang complexity neu lam som hon muc can thiet
- Definition of done:
  - Co it nhat mot cai thien do duoc tren batch sort mau
  - Trang thai hien tai:
    - Da bo mot lan `sleep` du thua cho item cuoi trong batch
    - Da offload ghi NFO sang thread de giam block event loop
    - Da chuyen `HttpClient.download()` sang `aiofiles` de tranh sync file write trong coroutine, trong khi van giu `.part` + atomic replace + cleanup contract
    - Da them `scripts/benchmark_sort_batch.py` de do synthetic batch sort voi fake scrape/organize delay
    - Da doi pacing strategy trong `sort_path()`:
      - throttle/cooldown ap vao pha `find()`
      - khong giu scrape slot trong luc organizer dang chay
      - chi cooldown khi van con task dang doi scrape slot
    - Benchmark mau (`8` files, `throttle_limit=4`, `scrape_delay=0.05`, `organize_delay=0.01`) cho thay:
      - truoc redesign: `sleep=3` -> `6.1355s`
      - sau redesign: `sleep=3` -> `3.1189s`
      - sau khi giam default: `sleep=2` -> `2.1176s`
      - `sleep=0` -> `0.1130s`
      - cai thien ~ `49%` so voi pacing cu trong cung harness
      - slowdown cua `sleep=2` so voi `sleep=0` hien con ~ `18.74x`
    - Benchmark scrape that ban dau da co snapshot:
      - `find` voi `dmm`, `4` ID, `sleep=2` -> `34.7462s`, `4/4 found`
      - `sort` voi `dmm`, `4` ID, `sleep=2` -> `27.9004s`
      - `sort` voi `dmm`, `4` ID, `sleep=0` -> `21.0701s`
      - overhead thuc te cua `sleep=2` tren batch nay ~ `1.32x`, nhe hon dang ke so voi synthetic harness
      - `find` voi `r18dev`, `ABP-420`, `sleep=2` -> `1.5990s`
    - Benchmark matrix mo rong (`repeat=3`) cho thay:
      - `find` voi `dmm`, `4` ID, `sleep=2`: movie median `5.8837s`, request median `1.3553s`, fail `0`
      - `find` voi `r18dev`, `4` ID, `sleep=2`: `8 found`, `4 no_result`, da bat dau gap `429 Too Many Requests`
      - `find` voi `mgstageja`, `FSDSS-198`, `sleep=2`: movie median `8.9190s`, request median `3.2818s`, fail `0`
      - `find` voi `javlibrary`, `ABP-420`, `repeat=3`: ban dau `3/3 no_result` do Cloudflare `403`; tu 2026-03-20 da co interactive recovery bang `cf_clearance` + `browser_user_agent` de tiep tuc scrape khi cookie het han
      - `find` voi `javlibrary`, `4` ID, `repeat=3`, voi cookie hop le: `7 found`, `5 no_result`, movie median `2.1589s`, request median `1.1258s`, da xuat hien `429` o mot so repeat
      - `sort` voi `javlibrary`, `4` ID, `repeat=3`, `sleep=2`: `9 processed`, `3 skipped`, batch mean `13.5586s`, median `13.4464s`, request fail `0`
      - `sort` voi `javlibrary`, `4` ID, `repeat=3`, `sleep=0`: `6 processed`, `6 skipped`, batch mean `9.0043s`, median `8.9272s`, request fail `3`
      - `sort` voi `dmm`, `4` ID, `repeat=3`: `sleep=2` mean `26.0813s`, median `26.3468s`; `sleep=0` mean `19.4442s`, median `19.1805s`
      - slowdown thuc te cua `sleep=2` tren batch `dmm` nay ~ `1.34x` theo mean, ~ `1.37x` theo median
    - Ket luan hien tai: giu global `sleep=2`. Benchmark that cho thay overhead co that nhung chua den muc can ha tiep; `r18dev` va `javlibrary` deu da co dau hieu rate-limit khi lap lai benchmark, va voi `javlibrary` thi `sleep=2` doi lai duoc ty le thanh cong tot hon `sleep=0`

## 7. Thu tu uu tien cap nhat

1. Neu muon theo duoi policy theo scraper, thiet ke support cooldown rieng cho scraper co dau hieu rate-limit nhu `r18dev`, khong ha global `sleep` them nua o giai doan nay
2. Neu can toi uu them cho `javlibrary`, tap trung vao policy benchmark/rate-limit va cach dung proxy/IP, khong ha global `sleep` chi de dua theo raw throughput
3. Tiep tuc giu docs snapshot khop test count / coverage va ket qua benchmark manual khi co thay doi them

Ly do sap xep:

- Cac bug contract P0/P1 da duoc dong
- P2.1 va P2.2 da dat muc tieu chinh; long-tail coverage cho `translator`, `registry`, va `base` da duoc dong bang test
- Benchmark scrape that da du de giu `sleep=2`; Javlibrary interactive recovery va benchmark co cookie hop le da dong; `HttpClient.download()` cung da duoc chuyen sang async file write. Da bo sung them `javs update` de cap nhat metadata/NFO tai cho cho thu vien da sort. Phan con lai chu yeu la policy rieng cho scraper rate-limited

## 8. Lenh verification bat buoc sau moi pha

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q
./venv/bin/javs config --help
```

## 9. Tieu chi hoan thanh chung

Ke hoach nay duoc xem la dat muc tieu khi:

- Khong con bug contract mo o `HttpClient`
- Cac fix P0/P1 quan trong deu co regression test
- Docs, help text, va runtime khop nhau
- Surface config cong khai duoc don dep hoac giai thich ro
- Coverage tang len muc phu hop hon voi vung rui ro thuc te
