/**
 * cdp-browser.mjs — Zero-dependency Chrome DevTools Protocol driver for Keelway `/app`.
 */

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function resolvePageWsUrl(cdpHttpUrl) {
  const res = await fetch(`${cdpHttpUrl}/json/list`);
  if (!res.ok) throw new Error(`CDP /json/list failed with HTTP ${res.status}`);
  const targets = await res.json();
  const page =
    targets.find((t) => t.type === "page" && String(t.url || "").includes("/app")) ||
    targets.find((t) => t.type === "page");
  if (!page || !page.webSocketDebuggerUrl) {
    throw new Error("No active /app page target found in headless Chrome.");
  }
  return page.webSocketDebuggerUrl;
}

export async function withCdpPage(inst, fn) {
  const wsUrl = await resolvePageWsUrl(inst.cdpHttpUrl);
  const ws = new WebSocket(wsUrl);
  let seq = 0;
  const pending = new Map();

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("CDP WebSocket connect timeout")), 8000);
    ws.addEventListener("open", () => {
      clearTimeout(timer);
      resolve();
    });
    ws.addEventListener("error", (ev) => {
      clearTimeout(timer);
      reject(new Error(`CDP WebSocket error: ${ev.message || "connection failed"}`));
    });
  });

  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(String(ev.data));
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject, timer } = pending.get(msg.id);
      clearTimeout(timer);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(`CDP ${msg.error.message || JSON.stringify(msg.error)}`));
      else resolve(msg.result);
    }
  });

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`CDP timeout waiting for ${method}`));
      }, 15000);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ id, method, params }));
    });

  const evalJson = async (expression) => {
    const out = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (out.exceptionDetails) {
      throw new Error(`Browser JS exception: ${out.exceptionDetails.text || "evaluation failed"}`);
    }
    return out.result?.value;
  };

  try {
    await send("Page.enable");
    await send("Runtime.enable");
    return await fn({ send, evalJson });
  } finally {
    try {
      ws.close();
    } catch {
      // ignore close errors
    }
  }
}

export async function runBrowserSubcommand(sub, inst, flags, { die, writeOutIfRequested }) {
  if (sub === "click") {
    const name = flags.name;
    if (!name) die("browser click requires --name <accessibleNameOrText>.");
    const role = flags.role ? String(flags.role).toLowerCase() : "";
    const exact = Boolean(flags.exact);
    const index = flags.index ? Number(flags.index) : 0;

    const result = await withCdpPage(inst, async ({ send, evalJson }) => {
      const target = await evalJson(`(() => {
        const roleFilter = ${JSON.stringify(role)};
        const queryName = ${JSON.stringify(String(name))}.trim();
        const queryLower = queryName.toLowerCase();
        const exact = ${JSON.stringify(exact)};
        const pickIndex = ${JSON.stringify(index)};
        const selectorMap = {
          button: 'button, [role="button"], input[type="button"], input[type="submit"]',
          link: 'a[href], [role="link"]',
          tab: '[role="tab"], button',
          checkbox: 'input[type="checkbox"], [role="checkbox"]',
          option: 'option, [role="option"]'
        };
        const sel = roleFilter
          ? (selectorMap[roleFilter] || ('[role="' + roleFilter + '"], ' + roleFilter))
          : 'button, a[href], [role="button"], [role="tab"], [role="link"], input[type="submit"], input[type="checkbox"], summary';
        const getName = (el) =>
          (el.getAttribute('aria-label') || el.innerText || el.textContent || el.getAttribute('title') || el.value || '')
            .replace(/\\s+/g, ' ')
            .trim();
        const visible = [...document.querySelectorAll(sel)].filter((el) => {
          const st = window.getComputedStyle(el);
          const r = el.getBoundingClientRect();
          return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        });
        const exactMatches = visible.filter((el) => getName(el).toLowerCase() === queryLower);
        const subMatches = exact ? [] : visible.filter((el) => getName(el).toLowerCase().includes(queryLower));
        const pool = exactMatches.length > 0 ? exactMatches : subMatches;
        const el = pool[pickIndex];
        if (!el) {
          return { found: false, availableSample: visible.slice(0, 25).map((e) => getName(e)).filter(Boolean) };
        }
        const matchedName = getName(el);
        const isDisabled = Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true';
        const descId = el.getAttribute('aria-describedby');
        const lockReason = descId ? (document.getElementById(descId)?.innerText || '').trim() : '';
        if (isDisabled) {
          return { found: true, disabled: true, matchedName, lockReason };
        }
        el.scrollIntoView({ block: 'center', inline: 'center' });
        const rect = el.getBoundingClientRect();
        return {
          found: true,
          disabled: false,
          matchedName,
          clickOnly: el.getAttribute('data-click-only') === 'true',
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2)
        };
      })()`);

      if (!target?.found) {
        return { ok: false, status: "not_found", role: role || "any", name, availableSample: target?.availableSample || [] };
      }
      if (target.disabled) {
        return { ok: false, status: "disabled", matchedName: target.matchedName, lockReason: target.lockReason };
      }

      await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: target.x, y: target.y, button: "none", buttons: 0 });
      await send("Input.dispatchMouseEvent", {
        type: "mousePressed",
        x: target.x,
        y: target.y,
        button: "left",
        buttons: 1,
        clickCount: 1,
      });
      await send("Input.dispatchMouseEvent", {
        type: "mouseReleased",
        x: target.x,
        y: target.y,
        button: "left",
        buttons: 0,
        clickCount: 1,
      });
      await sleep(300);
      return { ok: true, action: "click", matchedName: target.matchedName, x: target.x, y: target.y, trustedMouse: true };
    });

    if (!result.ok) die(`Click refused (${result.status})`, result, result.status === "disabled" ? 2 : 1);
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  if (sub === "fill" || sub === "select") {
    const label = flags.label;
    const value = flags.value !== undefined ? String(flags.value) : undefined;
    if (!label || value === undefined) die(`browser ${sub} requires --label <label> and --value <value>.`);

    const result = await withCdpPage(inst, async ({ evalJson }) => {
      const res = await evalJson(`(() => {
        const mode = ${JSON.stringify(sub)};
        const query = ${JSON.stringify(String(label))}.trim().toLowerCase();
        const nextVal = ${JSON.stringify(value)};
        const sel = mode === 'select' ? 'select' : 'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), textarea';
        const labelFor = (el) => {
          const aria = el.getAttribute('aria-label') || '';
          const ph = el.getAttribute('placeholder') || '';
          const wrap = el.closest('label')?.innerText || '';
          const id = el.id ? (document.querySelector('label[for="' + CSS.escape(el.id) + '"]')?.innerText || '') : '';
          return [aria, id, wrap, ph].join(' ').replace(/\\s+/g, ' ').trim();
        };
        const candidates = [...document.querySelectorAll(sel)];
        const exactEl = candidates.find((el) => (el.getAttribute('aria-label') || '').trim().toLowerCase() === query);
        const el = exactEl || candidates.find((el) => labelFor(el).toLowerCase().includes(query));
        if (!el) return { ok: false, error: 'Control not found', available: candidates.map((c) => c.getAttribute('aria-label') || c.placeholder || c.name) };
        if (el.disabled || el.getAttribute('aria-disabled') === 'true') return { ok: false, error: 'Control is disabled' };
        if (mode === 'select') {
          const opt = [...el.options].find((o) => o.value === nextVal || o.text.trim().toLowerCase() === nextVal.toLowerCase());
          if (!opt) return { ok: false, error: 'Option not found', options: [...el.options].map((o) => ({ value: o.value, text: o.text.trim() })) };
          const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
          setter.call(el, opt.value);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: true, action: 'select', label: el.getAttribute('aria-label') || query, selectedValue: opt.value, selectedText: opt.text.trim() };
        }
        el.focus();
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
        setter.call(el, nextVal);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        const isSecret = el.type === 'password' || /secret|token|key/i.test(el.getAttribute('aria-label') || '');
        return { ok: true, action: 'fill', label: el.getAttribute('aria-label') || query, valuePreview: isSecret ? '<redacted>' : nextVal };
      })()`);
      await sleep(200);
      return res;
    });

    if (!result?.ok) die(`browser ${sub} failed`, result || {});
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  if (sub === "wait-for") {
    const text = flags.text;
    if (!text) die("browser wait-for requires --text <substring>.");
    const timeoutMs = flags["timeout-ms"] ? Number(flags["timeout-ms"]) : 8000;
    const result = await withCdpPage(inst, async ({ evalJson }) => {
      const deadline = Date.now() + timeoutMs;
      const needle = String(text).toLowerCase();
      while (Date.now() < deadline) {
        const hit = await evalJson(`(() => {
          const body = (document.body?.innerText || '');
          const idx = body.toLowerCase().indexOf(${JSON.stringify(needle)});
          if (idx >= 0) return body.slice(Math.max(0, idx - 40), idx + 120).replace(/\\s+/g, ' ').trim();
          return null;
        })()`);
        if (hit !== null) return { ok: true, matchedSnippet: hit };
        await sleep(200);
      }
      return { ok: false, timeoutMs, expectedText: text };
    });
    if (!result.ok) die(`Timed out waiting for text '${text}'`, result);
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  if (sub === "snapshot") {
    const snap = await withCdpPage(inst, async ({ send, evalJson }) => {
      await send("Accessibility.enable");
      const [{ nodes }, meta] = await Promise.all([
        send("Accessibility.getFullAXTree"),
        evalJson(`({ url: window.location.pathname, title: document.title })`),
      ]);
      const byId = new Map(nodes.map((n) => [n.nodeId, n]));
      const root = nodes[0];
      const lines = [`# ARIA Snapshot — ${meta.title} (${meta.url})`];
      const skipRoles = new Set(["none", "generic", "InlineTextBox", "LineBreak"]);
      const walk = (id, depth) => {
        const n = byId.get(id);
        if (!n) return;
        const role = n.role?.value || "";
        const name = (n.name?.value || "").replace(/\s+/g, " ").trim();
        const val = n.value?.value !== undefined ? String(n.value.value).replace(/\s+/g, " ").trim() : "";
        const props = new Map((n.properties || []).map((p) => [p.name, p.value?.value]));
        const flagsList = [];
        if (props.get("disabled")) flagsList.push("[disabled]");
        if (props.get("selected")) flagsList.push("[selected]");
        if (props.get("checked") === true || props.get("checked") === "true") flagsList.push("[checked]");
        if (props.get("pressed") === true || props.get("pressed") === "true") flagsList.push("[pressed]");
        const meaningful = !n.ignored && (!skipRoles.has(role) || Boolean(name));
        const nextDepth = meaningful ? depth + 1 : depth;
        if (meaningful && role) {
          const indent = "  ".repeat(Math.min(depth, 10));
          const namePart = name ? ` "${name}"` : "";
          const valPart = val && val !== name ? ` value="${val}"` : "";
          const flagPart = flagsList.length ? ` ${flagsList.join(" ")}` : "";
          lines.push(`${indent}- ${role}${namePart}${valPart}${flagPart}`);
        }
        for (const cid of n.childIds || []) walk(cid, nextDepth);
      };
      if (root) walk(root.nodeId, 0);
      return { text: lines.join("\n") + "\n", lineCount: lines.length, title: meta.title, path: meta.url };
    });
    const savedTo = writeOutIfRequested(flags.out, snap.text, false);
    if (!savedTo) process.stdout.write(snap.text);
    else console.log(JSON.stringify({ ok: true, action: "snapshot", lineCount: snap.lineCount, out: savedTo }, null, 2));
    return;
  }

  if (sub === "screenshot") {
    if (!flags.out) die("browser screenshot requires --out <path.png>.");
    const fullPage = Boolean(flags["full-page"]);
    const b64 = await withCdpPage(inst, async ({ send }) => {
      const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: fullPage });
      return shot.data;
    });
    const buf = Buffer.from(b64, "base64");
    const savedTo = writeOutIfRequested(flags.out, buf, true);
    console.log(JSON.stringify({ ok: true, action: "screenshot", bytes: buf.length, out: savedTo }, null, 2));
    return;
  }

  die(`Unknown browser subcommand '${sub}'. Expected: click | fill | select | wait-for | snapshot | screenshot.`);
}
