// Live-mode smoke test: app must switch to published /data/*.json and never show DEMO markers.
// Usage: BASE_URL=http://localhost:4174 OUT=screenshots node tests/e2e/live.cjs
const { chromium, devices } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:4174';
const OUT = process.env.OUT || 'screenshots';
require('fs').mkdirSync(OUT, { recursive: true });
const results = [];
const check = async (name, fn) => { try { await fn(); results.push('ZALICZONY | ' + name); } catch (e) { results.push('NIEZALICZONY | ' + name + ' — ' + e.message.split('\n')[0]); } };
const assert = (c, m) => { if (!c) throw new Error(m); };
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: devices['Pixel 7'].userAgent, locale: 'pl-PL', timezoneId: 'Europe/Warsaw' });
  ctx.setDefaultTimeout(6000);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().includes('Failed to load resource')) errors.push(m.text()); });
  await page.goto(BASE + '/#/'); await page.waitForTimeout(1200);
  await check('Tryb live: brak banera DEMO i znaczników DEMO', async () => {
    assert(!(await page.getByText('TRYB DEMO').count()), 'baner DEMO');
    assert(!(await page.locator('text=DEMO').count()), 'znacznik DEMO');
    assert(await page.getByText(/Aktualizacja ·/).isVisible(), 'status aktualizacji');
  });
  await page.screenshot({ path: `${OUT}/live-start.png`, fullPage: true });
  await check('Typy: rekomendacje z danych pipeline', async () => {
    await page.goto(BASE + '/#/typy'); await page.waitForTimeout(700);
    assert((await page.locator('article').count()) > 0, 'brak typów');
  });
  await page.screenshot({ path: `${OUT}/live-typy.png`, fullPage: true });
  await check('Analiza meczu: rynki, kursy bukmacherów, brak xG oznaczony', async () => {
    await page.goto(BASE + '/#/mecze'); await page.reload(); await page.waitForTimeout(700);
    await page.locator('main button.card').first().click(); await page.waitForTimeout(500);
    await page.screenshot({ path: `${OUT}/live-mecz.png`, fullPage: true });
    await page.getByRole('tab', { name: 'Kursy' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('Porównanie bukmacherów').isVisible(), 'kursy');
    await page.getByRole('tab', { name: 'Rynki' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('nie jest pobierany w darmowym planie').first().isVisible(), 'rynki niedostępne');
  });
  await check('Statystyki: historia z rozliczonymi typami, backtest niedostępny', async () => {
    await page.goto(BASE + '/#/statystyki'); await page.reload(); await page.waitForTimeout(800);
    assert(await page.getByText('Zysk (stawka 1 j.)').isVisible(), 'brak zysku');
    await page.screenshot({ path: `${OUT}/live-statystyki.png`, fullPage: true });
    await page.getByRole('button', { name: 'Backtest' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('Backtest nie jest jeszcze dostępny').isVisible(), 'backtest');
    await page.getByRole('button', { name: 'Rekomendacje' }).click();
    await page.getByRole('tab', { name: 'Historia typów' }).click(); await page.waitForTimeout(400);
    assert((await page.getByText(/Wygrany|Przegrany|Wycofany|Oczekuje/).count()) > 0, 'brak historii');
  });
  await check('Profil: stan źródeł i bukmacherzy z danych', async () => {
    await page.goto(BASE + '/#/profil'); await page.waitForTimeout(600);
    assert(await page.getByText('Połączono').first().isVisible(), 'źródła');
    assert(await page.getByText('Pinnacle').isVisible(), 'bukmacherzy');
    await page.screenshot({ path: `${OUT}/live-profil.png`, fullPage: true });
  });
  await check('Wykluczenie bukmachera ukrywa jego typy', async () => {
    await page.goto(BASE + '/#/typy'); await page.waitForTimeout(500);
    const before = await page.locator('article').count();
    await page.goto(BASE + '/#/profil'); await page.waitForTimeout(400);
    await page.locator('label', { hasText: 'Pinnacle' }).getByRole('switch').click();
    await page.goto(BASE + '/#/typy'); await page.waitForTimeout(500);
    const after = await page.locator('article').count();
    assert(after <= before, `${after} > ${before}`);
    assert(!(await page.locator('article', { hasText: 'Pinnacle' }).count()), 'typ Pinnacle nadal widoczny');
    await page.goto(BASE + '/#/profil'); await page.waitForTimeout(300);
    await page.locator('label', { hasText: 'Pinnacle' }).getByRole('switch').click();
  });
  await check('Brak błędów JS w konsoli', async () => assert(errors.length === 0, errors.join(' | ')));
  console.log(results.join('\n'));
  await browser.close();
})();
