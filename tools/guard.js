// Network guard for replication runs (Playwright). Enforces "look, never touch" in code, not just in prompts.
//   const { guard } = require('<automation dir>/tools/guard.js');
//   await guard(context, { testHost: process.env.TEST_HOST, actionWords: process.env.GUARD_ACTION_WORDS });   // call BEFORE any page.goto
// Rules:
//   - Any request that is not GET/HEAD/OPTIONS is ABORTED unless its host is the test environment or localhost.
//   - A POST to a GraphQL endpoint is allowed anywhere only if its body contains no "mutation" (read-only queries).
//   - An API URL containing a state-changing action word (generic list below + the project's guard_action_words) is aborted on every host
//     that is not the test environment, even for GET.
// Every decision is appended to the returned log; write it next to the evidence for the report.
const SAFE = new Set(['GET', 'HEAD', 'OPTIONS']);
const BASE_ACTIONS = ['cancel', 'delete', 'remove', 'refund', 'charge', 'pay', 'purchase', 'checkout', 'publish', 'unsubscribe'];
function actionRegex(cfg) {
  const extra = Array.isArray(cfg.actionWords) ? cfg.actionWords : String(cfg.actionWords || '').split(',');
  const words = BASE_ACTIONS.concat(extra.map(w => w.trim()).filter(Boolean)).map(w => w.replace(/[^a-z0-9-]/gi, ''));
  return new RegExp('(' + words.join('|') + ')', 'i');
}

function hostOf(u) { try { return new URL(u).hostname.toLowerCase(); } catch (e) { return ''; } }

function isTestHost(host, cfg) {
  if (!host) return false;
  if (host === 'localhost' || host === '127.0.0.1') return true;
  const test = (cfg.testHost || cfg.testShop || '').toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  return !!test && (host === test || host.endsWith('.' + test));
}

// Pure function: easy to unit-test. req = { method, url, postData }
function decide(req, cfg = {}) {
  const method = (req.method || 'GET').toUpperCase();
  const host = hostOf(req.url);
  const test = isTestHost(host, cfg);
  if (test) return { allow: true, why: 'test environment/localhost' };
  if (actionRegex(cfg).test(req.url) && /\/(apps|api|a)\//i.test(req.url) && !/\.(js|css|png|jpe?g|svg|woff2?|gif|webp)(\?|$)/i.test(req.url)) {
    return { allow: false, why: 'state-changing action URL on a non-test host' };
  }
  if (SAFE.has(method)) return { allow: true, why: 'read-only method' };
  if (method === 'POST' && /graphql/i.test(req.url) && req.postData && !/\bmutation\b/i.test(req.postData)) {
    return { allow: true, why: 'graphql query (no mutation)' };
  }
  return { allow: false, why: `${method} to non-test host ${host}` };
}

async function guard(target, cfg = {}) {
  const log = [];
  await target.route('**/*', route => {
    const r = route.request();
    const d = decide({ method: r.method(), url: r.url(), postData: r.postData() }, cfg);
    if (!d.allow) { log.push(`BLOCKED ${r.method()} ${r.url()} (${d.why})`); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  return log;
}

module.exports = { guard, decide, isTestHost };
