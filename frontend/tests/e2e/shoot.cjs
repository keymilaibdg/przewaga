// Usage: BASE_URL=http://localhost:4173 OUT=screenshots node tests/e2e/shoot.cjs
const { chromium, devices } = require('playwright');
const BASE = process.env.BASE_URL || 'http://localhost:4173';
const OUT = process.env.OUT || 'screenshots';
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await chromium.launch();
  const results = [];
  for (const vp of [{w:390,h:844,name:'390'},{w:360,h:780,name:'360'},{w:412,h:915,name:'412'}]) {
    const ctx = await browser.newContext({ viewport:{width:vp.w,height:vp.h}, deviceScaleFactor:2, isMobile:true, hasTouch:true, userAgent: devices['Pixel 7'].userAgent, locale:'pl-PL', timezoneId:'Europe/Warsaw' });
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', m => { if (m.type()==='error' || m.type()==='warning') errors.push(m.type()+': '+m.text()); });
    page.on('pageerror', e => errors.push('pageerror: '+e.message));
    const routes = [['start','/#/'],['typy','/#/typy'],['mecze','/#/mecze'],['kalendarz','/#/mecze?widok=kalendarz'],['statystyki','/#/statystyki'],['historia','/#/statystyki?zakladka=historia'],['profil','/#/profil']];
    for (const [name, r] of routes) {
      await page.goto(BASE + r); await page.waitForTimeout(700);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      results.push(`${vp.name} ${name} overflowX=${overflow}`);
      if (vp.name==='390') await page.screenshot({ path:`${OUT}/${vp.name}-${name}.png`, fullPage:true });
      else await page.screenshot({ path:`${OUT}/${vp.name}-${name}.png` });
    }
    // match detail: first event with a tip
    await page.goto(BASE + '/#/typy'); await page.waitForTimeout(600);
    const link = await page.evaluate(() => null);
    await page.goto(BASE + '/#/mecze'); await page.waitForTimeout(600);
    await page.locator('main button.card').first().click(); await page.waitForTimeout(600);
    for (const tab of ['Analiza','Rynki','Kursy','Forma i statystyki','Składy']) {
      await page.getByRole('tab', { name: tab, exact: true }).click(); await page.waitForTimeout(450);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      results.push(`${vp.name} mecz/${tab} overflowX=${overflow}`);
      if (vp.name==='390') await page.screenshot({ path:`${OUT}/${vp.name}-mecz-${tab.split(' ')[0]}.png`, fullPage:true });
    }
    results.push(`${vp.name} errors: ${JSON.stringify(errors)}`);
    await ctx.close();
  }
  console.log(results.join('\n'));
  await browser.close();
})();
