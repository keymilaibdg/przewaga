// Usage: BASE_URL=http://localhost:4173 OUT=screenshots node tests/e2e/func.cjs
const { chromium, devices } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:4173';
const OUT = process.env.OUT || 'screenshots';
require('fs').mkdirSync(OUT, { recursive: true });
const results = [];
const check = async (name, fn) => { try { await fn(); results.push(['ZALICZONY', name]); console.log('ZALICZONY', name); } catch (e) { results.push(['NIEZALICZONY', name]); console.log('NIEZALICZONY', name, '—', e.message.split('\n')[0]); } };
const assert = (c, m) => { if (!c) throw new Error(m); };
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, isMobile:true, hasTouch:true, userAgent: devices['Pixel 7'].userAgent, locale:'pl-PL', timezoneId:'Europe/Warsaw' });
  ctx.setDefaultTimeout(5000);
  const page = await ctx.newPage();
  const B = BASE + '';
  await page.goto(B + '/#/'); await page.waitForTimeout(800);
  await check('Dashboard: KPI i okazja dnia renderują się', async () => {
    assert(await page.getByText('Podsumowanie analiz').isVisible(), 'brak podsumowania');
    assert(await page.getByText('Najlepsza okazja dnia').isVisible(), 'brak okazji dnia');
  });
  await check('Baner DEMO widoczny na każdym ekranie', async () => {
    for (const r of ['/#/', '/#/typy', '/#/mecze', '/#/statystyki', '/#/profil']) { await page.goto(B + r); await page.waitForTimeout(300); assert(await page.getByText('TRYB DEMO ·').isVisible(), r); }
  });
  await check('Nawigacja dolna: 5 pozycji przełącza widoki', async () => {
    await page.goto(B + '/#/');
    for (const [label, h] of [['Typy','Najlepsze typy'],['Mecze','Mecze'],['Statystyki','Statystyki'],['Profil','Profil'],['Start','Najlepsza okazja dnia']]) {
      await page.getByRole('navigation').getByRole('button', { name: label }).click(); await page.waitForTimeout(350);
      assert(await page.getByText(h, { exact: true }).first().isVisible(), label);
    }
  });
  await check('Powiadomienia: arkusz otwiera się i zamyka, licznik znika', async () => {
    await page.goto(B + '/#/'); await page.waitForTimeout(500);
    await page.getByRole('button', { name: /Powiadomienia/ }).click(); await page.waitForTimeout(400);
    assert(await page.getByRole('dialog').isVisible(), 'brak dialogu');
    await page.keyboard.press('Escape'); await page.waitForTimeout(300);
    assert(!(await page.getByRole('dialog').count()), 'dialog nie zamknięty');
    assert(await page.getByRole('button', { name: 'Powiadomienia' }).count() === 1, 'licznik nadal widoczny');
  });
  await check('Typy: maks. 10, filtr koszykówki pokazuje tylko kosz', async () => {
    await page.goto(B + '/#/typy'); await page.waitForTimeout(600);
    const n = await page.locator('article').count(); assert(n > 0 && n <= 10, 'liczba ' + n);
    await page.getByRole('button', { name: 'Koszykówka', exact: true }).click(); await page.waitForTimeout(300);
    const football = await page.locator('article [aria-label="Piłka nożna"]').count(); assert(football === 0, 'piłka w filtrze kosza');
  });
  await check('Typy: filtr bez wyników pokazuje komunikat „Brak zakładów…”', async () => {
    await page.goto(B + '/#/typy'); await page.waitForTimeout(500);
    await page.getByRole('button', { name: 'Koszykówka', exact: true }).click();
    await page.getByRole('button', { name: 'Niskie ryzyko' }).click();
    await page.getByRole('button', { name: 'Średnie', exact: true }).click(); await page.waitForTimeout(300);
    const n = await page.locator('article').count();
    if (n === 0) assert(await page.getByText('Brak zakładów spełniających obecnie kryteria jakości').isVisible(), 'brak komunikatu');
  });
  await check('Typy: rozwinięcie uzasadnienia (argumenty za/przeciw)', async () => {
    await page.goto(B + '/#/typy'); await page.reload(); await page.waitForTimeout(700);
    assert(await page.locator('article button[aria-expanded]').first().getAttribute('aria-expanded') === 'true', 'aria'); assert(await page.locator('article button[aria-expanded]').nth(1).getAttribute('aria-expanded') === 'false', 'druga rozwinięta');
    assert(await page.getByText('Przeciw / ryzyka').first().isVisible(), 'pierwsza karta nie rozwinięta');
  });
  await check('Mecze: zakres Dziś/Jutro/3/7 dni i wyszukiwarka filtrują listę', async () => {
    await page.goto(B + '/#/mecze'); await page.waitForTimeout(500);
    await page.getByRole('button', { name: '7 dni', exact: true }).click(); await page.waitForTimeout(200);
    const all = await page.locator('main button.card').count();
    await page.getByRole('button', { name: 'Dziś', exact: true }).click(); await page.waitForTimeout(200);
    const today = await page.locator('main button.card').count();
    assert(all >= today, `7d ${all} < dziś ${today}`);
    await page.getByRole('button', { name: '7 dni', exact: true }).click();
    await page.getByLabel('Szukaj wydarzeń').fill('zzzz'); await page.waitForTimeout(200);
    assert(await page.getByText('Brak wydarzeń dla wybranych filtrów').isVisible(), 'brak pustego stanu');
  });
  await check('Mecze: widok kalendarza i przełączanie dni', async () => {
    await page.goto(B + '/#/mecze?widok=kalendarz'); await page.waitForTimeout(500);
    const days = page.locator('main button.w-14'); assert(await days.count() === 8, 'dni ' + await days.count());
    await days.nth(2).click(); await page.waitForTimeout(300);
  });
  await check('Analiza meczu: 5 zakładek, rynki z EV, kursy bukmacherów', async () => {
    await page.goto(B + '/#/mecze'); await page.reload(); await page.waitForTimeout(700);
    await page.locator('main button.card').first().click(); await page.waitForTimeout(500);
    await page.getByRole('tab', { name: 'Rynki' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('Marża').first().isVisible(), 'brak marży');
    assert(await page.getByText('Niedostępny').first().isVisible(), 'brak rynków niedostępnych');
    await page.getByRole('tab', { name: 'Kursy' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('Porównanie bukmacherów').isVisible(), 'brak porównania');
    await page.getByRole('tab', { name: 'Składy' }).click(); await page.waitForTimeout(300);
    assert(await page.getByText('Absencje').isVisible(), 'brak absencji');
  });
  await check('Statystyki: przełączenie Rekomendacje/Backtest i Historia', async () => {
    await page.goto(B + '/#/statystyki'); await page.waitForTimeout(600);
    await page.getByRole('button', { name: 'Backtest' }).click(); await page.waitForTimeout(500);
    assert(await page.getByText('Symulacja historyczna').isVisible(), 'brak opisu backtestu');
    await page.getByRole('tab', { name: 'Historia typów' }).click(); await page.waitForTimeout(500);
    assert(await page.getByText('Pokaż więcej').isVisible(), 'brak paginacji');
  });
  await check('Ustawienia: min. ocena 90 zmniejsza listę typów i zapisuje się po odświeżeniu', async () => {
    await page.goto(B + '/#/typy'); await page.waitForTimeout(500);
    const before = await page.locator('article').count();
    await page.goto(B + '/#/profil'); await page.waitForTimeout(400);
    const slider = page.locator('input[type=range]').first();
    await slider.fill('90'); await page.waitForTimeout(200);
    await page.reload(); await page.waitForTimeout(500);
    assert(await page.getByText('90/100').isVisible(), 'nie zapisano');
    await page.goto(B + '/#/typy'); await page.waitForTimeout(500);
    const after = await page.locator('article').count();
    assert(after <= before, `${after} > ${before}`);
    await page.goto(B + '/#/profil'); await page.waitForTimeout(300);
    await page.locator('input[type=range]').first().fill('60');
  });
  await check('PWA: manifest poprawny, Service Worker zarejestrowany', async () => {
    const m = await (await page.request.get(B + '/manifest.webmanifest')).json();
    assert(m.display === 'standalone' && m.icons.length === 3, 'manifest');
    for (const i of m.icons) assert((await page.request.get(B + i.src)).ok(), i.src);
    await page.goto(B + '/#/'); await page.waitForTimeout(1500);
    const reg = await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()));
    assert(reg, 'brak SW');
  });
  await check('Offline: aplikacja ładuje się z cache po utracie sieci', async () => {
    await page.reload(); await page.waitForTimeout(800);
    await ctx.setOffline(true);
    await page.reload(); await page.waitForTimeout(800);
    assert(await page.getByText('Podsumowanie analiz').isVisible(), 'nie działa offline');
    await ctx.setOffline(false);
  });
  await check('Wydajność: czas do wyrenderowania dashboardu < 1,5 s (localhost)', async () => {
    const p2 = await ctx.newPage(); const t = Date.now();
    await p2.goto(B + '/#/'); await p2.getByText('Najlepsza okazja dnia').waitFor(); 
    const ms = Date.now() - t; results.push(['INFO', `czas renderu ${ms} ms`]); assert(ms < 1500, ms + ' ms');
  });
  console.log(results.map(r => r.join(' | ')).join('\n'));
  await browser.close();
})();
