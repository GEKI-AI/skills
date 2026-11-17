import { test, expect } from '@playwright/test';

test('create order', async ({ page }) => {
  await page.goto('https://shop-admin.example.com/login');
  await page.fill('div.form > div:nth-child(1) > input', 'admin');
  await page.fill('div.form > div:nth-child(2) > input', 'Winter-2026!');
  await page.click('div.form > button');
  await page.waitForTimeout(3000);

  await page.goto('https://shop-admin.example.com/orders/new');
  await page.selectOption('#customer', 'Alder Dental Practice');
  await page.fill('#item', 'Desk lamp');
  await page.fill('#quantity', '1');
  await page.click('text=Save');
  await page.waitForTimeout(5000);
  await expect(page.locator('.toast')).toHaveText('Order saved');
});

test('cancel order', async ({ page }) => {
  await page.goto('https://shop-admin.example.com/login');
  await page.fill('div.form > div:nth-child(1) > input', 'admin');
  await page.fill('div.form > div:nth-child(2) > input', 'Winter-2026!');
  await page.click('div.form > button');
  await page.waitForTimeout(3000);

  await page.goto('https://shop-admin.example.com/orders');
  await page.click('table tr:nth-child(2) >> text=Cancel');
  await page.waitForTimeout(5000);
  await expect(page.locator('.toast')).toHaveText('Order cancelled');
});
