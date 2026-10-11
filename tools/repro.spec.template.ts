// Throwaway repro for ONE ticket. Copy lives in evidence/<id>/; never commit it, never put it in the repo's own test folders.
import { test, expect } from '@playwright/test';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { guard } = require('../../tools/guard.js');

const TEST_HOST = process.env.TEST_HOST || '';          // the ONLY host where state-changing requests are allowed
const SHOTS = __dirname + '/shots';

test('repro', async ({ page, context }) => {
  if (!TEST_HOST) throw new Error('TEST_HOST not set: refusing to run without a test environment');
  const blocked: string[] = await guard(context, { testHost: TEST_HOST, actionWords: process.env.GUARD_ACTION_WORDS });

  // 1. STEPS FROM THE TICKET (on the TEST environment only)
  await page.goto('/');                                  // baseURL = TEST_BASE_URL
  // ... follow the ticket's repro steps here ...

  // 2. EVIDENCE: always capture a "before" screenshot + the facts you rely on
  await page.screenshot({ path: `${SHOTS}/before.png`, fullPage: false });
  // const facts = await page.evaluate(() => ({ /* DOM / state values proving the bug */ }));
  // console.log('FACTS', JSON.stringify(facts));

  // 3. ASSERT THE BUG: this test should PASS when the bug is reproduced (assert the wrong behaviour).
  // expect(facts.something).toBe('wrong value');

  console.log('GUARD-LOG', JSON.stringify(blocked));
});
