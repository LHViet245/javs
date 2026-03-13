# Ke hoach xu ly audit du an JavS

## 1. Muc tieu

Muc tieu cua roadmap nay la dua codebase tu trang thai "kien truc tot nhung van con bug integration va docs lech" len trang thai:

- config/runtime/doc dong bo
- network va proxy behavior co the du doan duoc
- flow `find`/`sort` on dinh hon
- security posture ro rang hon
- test gate bao ve duoc cac vung rui ro nhat

Ke hoach duoc chia theo `P0`, `P1`, `P2`. Moi pha duoi day la decision-complete, co the giao thang cho nguoi trien khai.

## 2. Nguyen tac trien khai

- Khong tron fix code va cap nhat docs mot cach tuy tien; moi pha phai co verification ro rang
- Moi bug P0/P1 deu phai co regression test di kem
- Tai lieu chi duoc cap nhat sau khi implementation va verification da xong
- Muc tieu la loai bo "config/doc promise" sai lech truoc khi them feature moi

## 3. P0 - On dinh core runtime va config

### P0.1 Sua lifecycle `HttpClient` trong `JavsEngine`

- Goal: dam bao session HTTP duoc mo/dong dung mot cho, khong bi close som giua cac task
- Files/Subsystems affected:
  - `javs/core/engine.py`
  - neu can, `javs/services/http.py`
  - test moi cho engine
- Fix approach:
  - Chon mo hinh session lifecycle duy nhat
  - Khuyen nghi: `find()` khong tu quan ly `async with self.http`; `sort_path()` quan ly batch-level context, con `find()` gia dinh session da co san
  - Neu `find()` duoc goi doc lap tu CLI, can co wrapper public hoac context management ro rang o entrypoint
  - Dam bao `close()` chi goi sau khi toan bo batch sort hoan tat
- Verification:
  - Tao test cho `find()` standalone
  - Tao test cho `sort_path()` nhieu file, `throttle_limit > 1`
  - Xac nhan khong co loi session closed trong batch concurrency
- Risk:
  - Neu sua khong ky, co the gay resource leak hoac request song song dung session chua khoi tao

### P0.2 Sua routing proxy HTTP/SOCKS dung per-scraper

- Goal: `config.scrapers.use_proxy` phai co tac dung dung voi ca HTTP proxy va SOCKS proxy
- Files/Subsystems affected:
  - `javs/services/http.py`
  - `javs/core/engine.py`
  - `javs/scrapers/registry.py`
  - tests proxy/integration
- Fix approach:
  - Bo session global duy nhat khi dung SOCKS neu khong the route per-request
  - Su dung hai client/session rieng: co proxy va khong proxy; scraper nhan dung client theo config
  - Hoac abstract network layer de route tai muc client thay vi muc request
  - Dong bo log message va docs de phan biet HTTP-proxy route va SOCKS route
- Verification:
  - Test `use_proxy=False` voi SOCKS khong di qua proxy
  - Test `use_proxy=True` voi SOCKS co di qua proxy
  - Test HTTP proxy van giu duoc hanh vi cu
- Risk:
  - Doi networking layer co the cham vao nhieu scraper cung luc

### P0.3 Dong bo schema giua `default_config.yaml`, `JavsConfig`, va `config sync`

- Goal: nguoi dung tao/sync config nao thi runtime doc dung config do
- Files/Subsystems affected:
  - `javs/config/models.py`
  - `javs/config/loader.py`
  - `javs/config/updater.py`
  - `javs/data/default_config.yaml`
  - CLI config command
- Fix approach:
  - Quy dinh `JavsConfig` la schema nguon su that
  - Viet lai `default_config.yaml` theo schema nay
  - Cho `sync_user_config()` nhan `path` tu CLI thay vi hardcode default path
  - Xac dinh ro chinh sach voi unknown key:
    - neu muon strict, dung validation chong key la
    - neu muon mềm, it nhat phai canh bao khi gap key khong map runtime
  - Dam bao `create_default_config()` va `config sync` tao ra cung mot schema
- Verification:
  - Test `create_default_config()`
  - Test `sync_user_config(custom_path)`
  - Test load template sau sync cho ra gia tri dung nhu mong doi
- Risk:
  - Anh huong truc tiep den config cu cua nguoi dung; can co migration strategy ro

### P0.4 Lam sach toolchain chat luong toi thieu

- Goal: dua repo ve trang thai co the lint sach o branch dang lam
- Files/Subsystems affected:
  - `javs/config/updater.py`
  - `javs/core/scanner.py`
  - `javs/cli.py`
  - bat ky file lien quan den loi ruff hien tai
- Fix approach:
  - Sua cac loi ruff hien tai
  - Dat baseline lint clean truoc khi tiep tuc fix sau
- Verification:
  - `./venv/bin/python -m ruff check javs tests`
- Risk:
  - Thap; mostly hygiene

### Definition of done cho P0

- `pytest` xanh
- `ruff` xanh
- `config sync` ton trong custom path
- Template config map dung schema runtime
- Routing proxy dung voi ca HTTP va SOCKS
- Batch sort khong con bug session lifecycle

## 4. P1 - Sua bug tich hop va nang posture bao mat

### P1.1 Wire Cloudflare/Javlibrary auth vao flow thuc te

- Goal: bo cau hinh manual Cloudflare co the su dung duoc trong app, khong chi trong script thu nghiem
- Files/Subsystems affected:
  - `javs/config/models.py`
  - `javs/core/engine.py`
  - `javs/services/http.py`
  - co the `javs/scrapers/javlibrary.py`
  - docs config
- Fix approach:
  - Chon duy nhat mot noi luu config CF/Javlibrary auth
  - Truyen du lieu do vao `HttpClient`
  - Bo thong diep huong dan sai schema trong exception text
  - Danh gia co nen xoa `scripts/real_scrape_test.py` hoac bien no thanh script debug noi bo
- Verification:
  - Test load config -> engine -> `HttpClient` co `cf_clearance` va `cf_user_agent`
  - Test search Javlibrary khi bat manual config
- Risk:
  - Neu schema chon sai se tiep tuc gay lech docs/runtime

### P1.2 Sua direct-match URL logic cho Javlibrary EN/JA/ZH

- Goal: `search()` cua Javlibrary luon tra URL that co the scrape duoc
- Files/Subsystems affected:
  - `javs/scrapers/javlibrary.py`
  - tests scraper
- Fix approach:
  - Lay canonical URL neu co
  - Neu response da la detail page, su dung URL thuc te thay vi placeholder `_detail_`
  - Giu language path dung cho JA/ZH
- Verification:
  - Test direct-match EN
  - Test direct-match JA
  - Test direct-match ZH
- Risk:
  - Thap; localised trong scraper

### P1.3 Sua matching subtitle theo movie thay vi theo thu muc

- Goal: khong di chuyen subtitle khong lien quan
- Files/Subsystems affected:
  - `javs/core/organizer.py`
  - tests organizer
- Fix approach:
  - Match subtitle theo basename/stem va movie id
  - Ho tro multi-part logic
  - Khong move subtitle neu khong co match ro rang
- Verification:
  - Test 2 video + 2 subtitle rieng
  - Test part-specific subtitle
  - Test subtitle khong lien quan khong bi move
- Risk:
  - Trung binh; can can bang giua strict va flexible matching

### P1.4 Thu hep pham vi `ssl=False`

- Goal: giam be mat tan cong, giu lai kha nang scrape o nhung host thuc su can
- Files/Subsystems affected:
  - `javs/services/http.py`
  - scraper config/doc
- Fix approach:
  - Mac dinh verify SSL
  - Cho phep bypass theo host/scraper/config flag
  - Ghi ro trade-off trong docs
- Verification:
  - Test request default co verify SSL
  - Test scraper/host whitelist van bypass duoc neu can
- Risk:
  - Co the lam mot so site scraping fail tam thoi neu site dang co SSL issue

### Definition of done cho P1

- Cloudflare manual config dung duoc trong app flow
- Javlibrary `search()` direct-match khong tra URL gia
- Subtitle matching khong con move nham
- SSL policy khong con global-off

## 5. P2 - Nâng test maturity, hieu nang, va docs governance

### P2.1 Tang coverage cho cac module "0%/thap"

- Goal: test phai bao ve cac path rui ro nhat thay vi chi parser unit
- Files/Subsystems affected:
  - `javs/cli.py`
  - `javs/core/engine.py`
  - `javs/services/http.py`
  - `javs/scrapers/dmm.py`
  - `javs/config/updater.py`
  - `javs/services/image.py`
  - `javs/services/emby.py`
- Fix approach:
  - Them integration-style unit tests voi mock/fake client
  - Bao phu command CLI, orchestration, config sync, DMM parser/flow
  - Dat target coverage thuc te, vi du >= 75% tong va > 60% cho module quan trong
- Verification:
  - `./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q`
- Risk:
  - Trung binh; can effort kha lon

### P2.2 Ra soat va giam dead config surface

- Goal: schema public chi chua field co tac dung that
- Files/Subsystems affected:
  - `javs/config/models.py`
  - docs config
- Fix approach:
  - Danh dau field dang support / planned / deprecated
  - Implement hoac remove:
    - `required_fields`
    - `rename_folder_in_place`
    - `check_updates`
    - `JavlibraryConfig` cookies neu tiep tuc dung
  - Them warning khi user dung field chua support
- Verification:
  - Test config deprecation warning
  - Test field implemented thuc su co tac dung
- Risk:
  - Thap-trung binh; chu yeu la compatibility

### P2.3 Cai thien hieu nang I/O va scraping

- Goal: giam request lap lai va tang throughput sort
- Files/Subsystems affected:
  - `javs/scrapers/dmm.py`
  - `javs/services/http.py`
  - `javs/core/engine.py`
  - neu can, them cache layer nho
- Fix approach:
  - Cache actress thumb/trailer lookup trong mot batch
  - Ra soat `sleep` strategy de co rate-limit policy ro hon
  - Xem xet offload file write/cpu-bound image sang thread neu can
- Verification:
  - Benchmark don gian cho batch sort nho
  - So sanh so request truoc/sau
- Risk:
  - Co the tang complexity neu lam cache qua som

### P2.4 Dong bo docs voi hien trang thuc te

- Goal: docs tro lai thanh nguon su that
- Files/Subsystems affected:
  - `README.md`
  - `docs/USAGE.md`
  - `CONTEXT.md`
  - neu can, them `CONTRIBUTING.md` hoac CI docs
- Fix approach:
  - Xoa/sua claim "100% coverage"
  - Neu chua dung `mypy`, bo claim hoac them thuc su vao toolchain
  - Dong bo help text `config sync`
  - Ghi ro security trade-off, config schema, va feature dang stub
- Verification:
  - Doc review chong lech docs/runtime
  - CLI help snapshot test
- Risk:
  - Thap

### Definition of done cho P2

- Coverage tang ro rang va bao phu vung rui ro
- Cac dead config field da duoc xu ly ro
- Performance bottleneck chinh da duoc giam
- Docs khop voi runtime/tooling hien tai

## 6. Test va verification bat buoc sau moi pha

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
./venv/bin/python -m pytest tests --cov=javs --cov-report=term-missing -q
```

Them vao test plan khi implement:

- Test regression cho lifecycle session engine
- Test regression cho SOCKS per-scraper routing
- Test `config sync --config`
- Test direct-match Javlibrary EN/JA/ZH
- Test subtitle matching theo stem/movie id/part
- Test wire Cloudflare config vao `HttpClient`

## 7. Thu tu uu tien de xuat

1. P0.3 `config sync` + schema alignment
2. P0.1 lifecycle `HttpClient` trong engine
3. P0.2 proxy routing HTTP/SOCKS
4. P0.4 lint clean baseline
5. P1.2 Javlibrary direct-match URL
6. P1.3 subtitle matching
7. P1.4 SSL scoping
8. P1.1 Cloudflare config wiring
9. Toan bo P2

Ly do:

- Config/schema sai la nguon phat tan nhieu bug va docs sai
- Lifecycle/proxy la rui ro nghiem trong cho correctness
- Lint clean baseline giup de review cac patch tiep theo
- Javlibrary/subtitle la bug huong user ro rang
- Bao mat va docs nen duoc chot sau khi core runtime on dinh

## 8. Rui ro rollout

- Migration config cu co the gay vo cau hinh neu khong co chinh sach ro rang
- Sua networking layer co the anh huong nhieu scraper mot luc
- Thu hep `ssl=False` co the lam lo ra mot so site đang phu thuoc vao bypass
- Tang coverage cho DMM/HTTP co the can mock phuc tap hon test hien tai

## 9. Tieu chi hoan thanh chung

Ke hoach nay duoc xem la hoan thanh khi:

- Runtime, docs, va config schema dong bo
- Khong con P0 open
- Cac bug P1 da co regression test
- Coverage va lint dat nguong toi thieu da thoa thuan
- Repo co the duoc review ma khong con claim sai lech hien trang
