import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const mockups = path.join(__dirname, '../mockups/generate.html');
const outDir = path.join(__dirname, '../screenshots');
const screens = ['home', 'write', 'sort', 'ask', 'entries'];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
await page.goto(`file://${mockups}`);

for (const id of screens) {
  const el = page.locator(`#${id}`);
  await el.screenshot({
    path: path.join(outDir, `${id}.png`),
    type: 'png',
  });
  console.log(`wrote ${id}.png`);
}

await browser.close();
