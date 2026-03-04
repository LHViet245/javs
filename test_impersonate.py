import asyncio
import time
from curl_cffi.requests import AsyncSession

async def test_impersonate(browser_name, url):
    try:
        async with AsyncSession(impersonate=browser_name) as s:
            t0 = time.time()
            # print to console
            print(f'Testing {browser_name}...', end=' ', flush=True)
            # also write to file
            with open('test_impersonate.log', 'a') as f:
                f.write(f'Testing {browser_name}...\n')
                
            resp = await s.get(url, timeout=10)
            html = resp.text
            t1 = time.time()
            if 'video_id' in html or ('Just a moment' not in html and 'videothumbs' in html):
                res = f'✅ PASSED in {t1-t0:.2f}s'
            else:
                res = f'❌ FAILED (Blocked by CF) in {t1-t0:.2f}s'
    except Exception as e:
        if '403' in str(e):
            res = '❌ FAILED (HTTP 403 Forbidden)'
        else:
            res = f'❌ ERROR ({str(e)})'
            
    print(res, flush=True)
    with open('test_impersonate.log', 'a') as f:
        f.write(f'{res}\n')
    return 'PASSED' in res

async def main():
    url = 'https://www.javlibrary.com/en/vl_searchbyid.php?keyword=HNTRZ-015'
    impersonates = [
        'chrome', 'chrome110', 'chrome116', 'chrome120', 'chrome124',
        'safari', 'safari_ios', 'safari15_5', 'safari17_0',
        'edge', 'edge101', 'edge114'
    ]
    with open('test_impersonate.log', 'w') as f:
        f.write(f'Starting test for {url}\n\n')
    
    success_count = 0
    for imp in impersonates:
        # add wrapper to prevent total hang
        try:
            success = await asyncio.wait_for(test_impersonate(imp, url), timeout=15)
            if success:
                success_count += 1
        except asyncio.TimeoutError:
            print(f'❌ TIMEOUT for {imp}', flush=True)
            with open('test_impersonate.log', 'a') as f:
                f.write(f'❌ TIMEOUT for {imp}\n')
        await asyncio.sleep(2)
        
    print(f'\nTotal Success: {success_count}/{len(impersonates)}')
    with open('test_impersonate.log', 'a') as f:
        f.write(f'\nTotal Success: {success_count}/{len(impersonates)}\n')

if __name__ == '__main__':
    asyncio.run(main())
