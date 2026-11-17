// APK-mode checks (build with NATIVE=1): no silent DEMO fallback, offline copy of the last data.
// Usage: BASE_URL=http://localhost:4176 node tests/e2e/native.cjs   (serve the NATIVE build; put data/ next to it for step 2)
const { chromium, devices } = require('playwright');
const fs = require('fs');
const path = require('path');
const BASE = process.env.BASE_URL || 'http://localhost:4176';
const ROOT = process.env.NATIVE_ROOT || '/tmp/native';
const DATA = process.env.DATA_SRC || '/tmp/live/data';
const results = [];
const check = async (name, fn) => { try { await fn(); results.push('ZALICZONY | ' + name); } catch (e) { results.push('NIEZALICZONY | ' + name + ' — ' + e.message.split('\n')[0]); } };
const assert = (c, m) => { if (!c) throw new Error(m); };
(async () => {
  fs.rmSync(path.join(ROOT, 'data'), { recursive: true, force: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, userAgent: devices['Pixel 7'].userAgent });
  ctx.setDefaultTimeout(6000);
  const page = await ctx.newPage();
  await check('Brak danych: ekran informacyjny zamiast cichego DEMO', async () => {
    await page.goto(BASE + '/#/'); await page.waitForTimeout(800);
    assert(await page.getByText('Brak danych do wyświetlenia').isVisible(), 'brak ekranu');
    await page.getByRole('button', { name: /Pokaż wersję DEMO/ }).click(); await page.waitForTimeout(500);
    assert(await page.getByText('TRYB DEMO').isVisible(), 'demo po kliknięciu');
  });
  fs.cpSync(DATA, path.join(ROOT, 'data'), { recursive: true });
  await check('Dane opublikowane: tryb live po „Spróbuj ponownie”/starcie', async () => {
    await page.goto(BASE + '/#/'); await page.reload(); await page.waitForTimeout(1000);
    assert(await page.getByText(/Aktualizacja ·/).isVisible(), 'brak trybu live');
    assert(!(await page.getByText('TRYB DEMO').count()), 'DEMO w trybie live');
  });
  await check('Bez Service Workera w buildzie APK', async () => {
    const reg = await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()));
    assert(!reg, 'SW zarejestrowany');
  });
  await check('Offline: ostatnie dane z pamięci urządzenia + oznaczenie „Offline”', async () => {
    fs.rmSync(path.join(ROOT, 'data'), { recursive: true, force: true }); // simulate network failure for data
    await page.reload(); await page.waitForTimeout(1000);
    assert(await page.getByText(/Offline ·/).isVisible(), 'brak oznaczenia offline');
    await page.goto(BASE + '/#/typy'); await page.waitForTimeout(600);
    assert((await page.locator('article').count()) > 0, 'brak typów z pamięci');
  });
  await check('Profil: wersja aplikacji Android', async () => {
    await page.goto(BASE + '/#/profil'); await page.waitForTimeout(600);
    assert(await page.getByText(/v0\.3\.1 · Android/).isVisible(), 'wersja');
    assert(await page.getByText('Wersja aplikacji').isVisible(), 'karta aktualizacji');
  });
  console.log(results.join('\n'));
  await browser.close();
})();
