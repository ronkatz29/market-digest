const app = document.getElementById("app");

// Build DOM nodes without innerHTML: all digest text comes from an LLM and news feeds.
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === false || value == null) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(child));
  }
  return el;
}

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

const pct = (n) => `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
const direction = (n) => (n >= 0 ? "up" : "down");
const longDate = (day) =>
  new Date(`${day}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

function predictionBox(mover, prediction) {
  const p = mover.prediction;
  const status = !prediction || prediction.status === "open"
    ? h("span", { class: "badge" }, "open, scored after 5 trading days")
    : h("span", { class: `badge ${prediction.hit ? "hit" : "miss"}` },
        `${prediction.hit ? "hit" : "miss"}: ${pct(prediction.excess_return_pct)} vs S&P 500`);
  return h("div", { class: "prediction" },
    h("span", { class: "label" }, "Prediction, next 5 trading days"),
    h("strong", {}, `Will ${p.call} the S&P 500 (${p.confidence} confidence)`, status),
    p.reasoning,
    prediction && prediction.retrospective
      ? h("p", {}, h("span", { class: "label" }, "Looking back"), prediction.retrospective)
      : null);
}

function callChip(call, prediction) {
  const arrow = call === "outperform" ? "▲" : "▼";
  if (prediction && prediction.status === "resolved") {
    return h("span", { class: `chip ${prediction.hit ? "hit" : "miss"}` },
      `${arrow} ${call} · ${prediction.hit ? "hit" : "miss"}`);
  }
  return h("span", { class: "chip" }, `${arrow} ${call}`);
}

// Open a mover's story and bring it into view. Not a link: the hash belongs to the router.
function jumpTo(ticker) {
  const row = document.getElementById(`m-${ticker}`);
  if (!row) return;
  row.open = true;
  row.scrollIntoView({ behavior: "smooth", block: "center" });
}

// Colour reaches full strength at this move; bigger moves look the same.
const HEAT_CLAMP_PCT = 3;

function breadthBar(market) {
  const share = Math.round((market.advancers / market.scanned) * 100);
  const segment = (kind, count) =>
    count ? h("span", { class: `seg ${kind}`, style: `flex-grow:${count}`, title: `${count} ${kind}` }) : null;
  return h("div", { class: "breadth" },
    h("div", { class: "breadth-bar", role: "img",
      "aria-label": `${market.advancers} up, ${market.unchanged} unchanged, ${market.decliners} down` },
      segment("up", market.advancers),
      segment("flat", market.unchanged),
      segment("down", market.decliners)),
    h("span", {}, `${share}% of stocks rose`));
}

function sectorBars(sectors) {
  const max = Math.max(...sectors.map((s) => Math.abs(s.change_pct)), 0.01);
  return h("div", { class: "sector-bars" }, sectors.map((s) =>
    h("div", { class: "sector-row", title: `${s.advancers} up, ${s.decliners} down of ${s.count}` },
      h("span", { class: "sector-name" }, s.sector),
      h("span", { class: "track" },
        h("span", { class: `bar ${direction(s.change_pct)}`,
          style: `width:${(Math.abs(s.change_pct) / max) * 50}%` })),
      h("span", { class: "sector-value" }, pct(s.change_pct)))));
}

function heatmap(market, analysed) {
  const byTicker = Object.fromEntries(market.stocks.map((s) => [s.ticker, s]));
  const hint = "Hover or tap a tile to see the stock. Outlined tiles have a story below.";
  const readout = h("p", { class: "readout", "aria-live": "polite" }, hint);
  const stockOf = (e) => byTicker[e.target.dataset && e.target.dataset.t];
  const show = (e) => {
    const s = stockOf(e);
    if (!s) return;
    readout.replaceChildren(
      h("strong", {}, s.ticker), ` · ${s.name} · `,
      h("span", { class: direction(s.change_pct) }, pct(s.change_pct)));
  };

  return h("div", { class: "heatmap" },
    h("div", {
      onpointerover: show,
      onclick: (e) => { show(e); const s = stockOf(e); if (s && analysed.has(s.ticker)) jumpTo(s.ticker); },
    }, market.sectors.map((sector) =>
      h("div", { class: "heat-sector" },
        h("span", { class: "label" }, sector.sector),
        h("div", { class: "tiles" },
          market.stocks
            .filter((s) => s.sector === sector.sector)
            .sort((a, b) => b.change_pct - a.change_pct)
            .map((s) => h("i", {
              class: `tile ${direction(s.change_pct)}${analysed.has(s.ticker) ? " analysed" : ""}`,
              style: `--s:${Math.min(Math.abs(s.change_pct) / HEAT_CLAMP_PCT, 1).toFixed(2)}`,
              "data-t": s.ticker,
            })))))),
    h("div", { class: "heat-legend" },
      `−${HEAT_CLAMP_PCT}%`, h("span", { class: "ramp" }), `+${HEAT_CLAMP_PCT}%`),
    readout);
}

function marketSection(digest) {
  const market = digest.market;
  if (!market || !market.scanned) return [];
  const analysed = new Set(digest.movers.map((m) => m.ticker));
  const b = digest.benchmark;
  const stat = (value, label, cls) =>
    h("div", { class: "stat" }, h("b", { class: cls }, value), h("span", {}, label));
  return [
    h("div", { class: "stats" },
      stat(pct(b.change_pct), "S&P 500 (SPY)", direction(b.change_pct)),
      stat(String(market.advancers), "stocks up"),
      stat(String(market.decliners), "stocks down"),
      stat(pct(market.median_change_pct), "median stock", direction(market.median_change_pct))),
    breadthBar(market),
    h("p", { class: "hint" },
      "The index is weighted by company size, so a few giants can move it while the typical " +
      "stock does something else. Compare the S&P 500 with the median stock."),
    h("div", { class: "market-grid" },
      h("section", {},
        h("h2", {}, "Sectors"),
        h("p", { class: "hint" }, "Average move of the stocks in each sector."),
        sectorBars(market.sectors)),
      h("section", {},
        h("h2", {}, `All ${market.scanned} stocks`),
        heatmap(market, analysed))),
  ];
}

function topTable(title, stocks, analysed) {
  return h("section", {},
    h("h2", {}, title),
    h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {},
          h("th", {}, "Ticker"), h("th", {}, "Company"), h("th", { class: "num" }, "Change"))),
        h("tbody", {}, stocks.map((s) => h("tr", {},
          h("td", {}, analysed.has(s.ticker)
            ? h("button", { class: "jump", title: "Read the story", onclick: () => jumpTo(s.ticker) }, s.ticker)
            : s.ticker),
          h("td", {}, s.name, h("span", { class: "company" }, ` · ${s.sector}`)),
          h("td", { class: `num ${direction(s.change_pct)}` }, pct(s.change_pct))))))));
}

function topMovers(digest, n = 20) {
  const market = digest.market;
  if (!market || !market.scanned) return [];
  const analysed = new Set(digest.movers.map((m) => m.ticker));
  const ranked = [...market.stocks].sort((a, b) => b.change_pct - a.change_pct);
  return h("div", { class: "top-grid" },
    topTable(`Top ${n} up`, ranked.filter((s) => s.change_pct > 0).slice(0, n), analysed),
    topTable(`Top ${n} down`, ranked.filter((s) => s.change_pct < 0).reverse().slice(0, n), analysed));
}

function moverRow(mover, prediction) {
  return h("details", { class: "row", id: `m-${mover.ticker}` },
    h("summary", {},
      h("span", { class: "ticker" }, mover.ticker),
      h("span", { class: `change ${direction(mover.change_pct)}` }, pct(mover.change_pct)),
      h("span", { class: "headline" }, mover.headline || mover.concept.name),
      callChip(mover.prediction.call, prediction)),
    h("div", { class: "detail" },
      h("p", { class: "company" }, `${mover.name} · ${mover.sector} · closed at $${mover.close.toFixed(2)}`),
      h("p", {}, mover.what_happened),
      h("p", {},
        h("span", { class: "label" }, "Why", mover.no_clear_news ? " (no clear news)" : ""),
        mover.why),
      h("div", { class: "concept" },
        h("span", { class: "label" }, "Concept"),
        h("strong", {}, mover.concept.name),
        mover.concept.lesson),
      predictionBox(mover, prediction),
      mover.sources.length
        ? h("ul", { class: "sources" }, mover.sources.map((s) =>
            h("li", {},
              h("a", { href: s.url, target: "_blank", rel: "noopener" }, s.headline),
              h("span", {}, ` (${s.source})`))))
        : null));
}

function moverGroup(title, movers, byId, day) {
  if (!movers.length) return [];
  return [
    h("h2", {}, title),
    h("div", { class: "rows" }, movers.map((m) => moverRow(m, byId[`${day}:${m.ticker}`]))),
  ];
}

async function showDigest(day) {
  const { dates } = await getJSON("data/index.json").catch(() => ({ dates: [] }));
  if (!dates.length) {
    app.replaceChildren(h("p", { class: "empty" }, "No digests yet. The first one appears after the daily job runs."));
    return;
  }
  if (!dates.includes(day)) day = dates[dates.length - 1];
  const [digest, predictions] = await Promise.all([
    getJSON(`data/digests/${day}.json`),
    getJSON("data/predictions.json").catch(() => []),
  ]);
  const byId = Object.fromEntries(predictions.map((p) => [p.id, p]));
  const i = dates.indexOf(day);
  const link = (label, target) =>
    h("a", { href: target ? `#/d/${target}` : "#", "aria-disabled": target ? null : "true" }, label);
  const b = digest.benchmark;

  app.replaceChildren(...[
    h("h1", {}, longDate(day)),
    h("p", { class: "sub" },
      "S&P 500 (SPY) ",
      h("span", { class: direction(b.change_pct) }, pct(b.change_pct)),
      `. The day's biggest S&P 500 movers and the news behind them.`),
    h("div", { class: "daybar" },
      link("← Older", dates[i - 1]),
      h("select", { "aria-label": "Choose a day", onchange: (e) => { location.hash = `#/d/${e.target.value}`; } },
        [...dates].reverse().map((d) => h("option", { value: d, selected: d === day ? "" : null }, d))),
      link("Newer →", dates[i + 1])),
    marketSection(digest),
    digest.movers.length
      ? [
          moverGroup("Gainers", digest.movers.filter((m) => m.change_pct >= 0), byId, day),
          moverGroup("Losers", digest.movers.filter((m) => m.change_pct < 0), byId, day),
          h("p", { class: "hint" }, "Click a stock to see the full story."),
        ]
      : h("p", { class: "empty" }, "No movers were analysed for this day."),
    topMovers(digest),
  ].flat(Infinity));
}

function rate(rows) {
  const hits = rows.filter((p) => p.hit).length;
  return rows.length ? `${Math.round((hits / rows.length) * 100)}%` : "–";
}

function breakdown(title, rows, key) {
  const groups = {};
  for (const p of rows) (groups[p[key]] ||= []).push(p);
  const sorted = Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  return [
    h("h2", {}, title),
    h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {},
          h("th", {}, key), h("th", { class: "num" }, "Scored"),
          h("th", { class: "num" }, "Hits"), h("th", { class: "num" }, "Hit rate"))),
        h("tbody", {}, sorted.map(([name, group]) => h("tr", {},
          h("td", {}, name),
          h("td", { class: "num" }, String(group.length)),
          h("td", { class: "num" }, String(group.filter((p) => p.hit).length)),
          h("td", { class: "num" }, rate(group))))))),
  ];
}

async function showScoreboard() {
  const predictions = await getJSON("data/predictions.json").catch(() => []);
  const resolved = predictions.filter((p) => p.status === "resolved")
    .sort((a, b) => b.resolved_on.localeCompare(a.resolved_on));
  const open = predictions.length - resolved.length;

  const nodes = [
    h("h1", {}, "Scoreboard"),
    h("p", { class: "sub" },
      "Each prediction says whether a stock will beat the S&P 500 over 5 trading days. " +
      "A coin flip scores about 50%, and a few dozen results are too few to tell skill from luck."),
    h("div", { class: "stats" },
      h("div", { class: "stat" }, h("b", {}, rate(resolved)), h("span", {}, "hit rate")),
      h("div", { class: "stat" }, h("b", {}, String(resolved.length)), h("span", {}, "scored")),
      h("div", { class: "stat" }, h("b", {}, String(open)), h("span", {}, "still open"))),
  ];
  if (!resolved.length) {
    nodes.push(h("p", { class: "empty" }, "Nothing scored yet. The first results arrive 5 trading days after the first digest."));
  } else {
    nodes.push(
      ...breakdown("By confidence", resolved, "confidence"),
      ...breakdown("By concept", resolved, "concept"),
      h("h2", {}, "Scored predictions"),
      h("div", { class: "rows" }, resolved.map((p) => h("details", { class: "row" },
        h("summary", {},
          h("span", { class: "ticker" }, p.ticker),
          h("span", { class: `change ${direction(p.excess_return_pct)}` }, pct(p.excess_return_pct)),
          h("span", { class: "headline" }, `${p.concept} · ${p.made_on}`),
          callChip(p.call, p)),
        h("div", { class: "detail" },
          h("p", { class: "company" }, `${p.name} · ${p.made_on} to ${p.resolved_on} · `,
            h("a", { href: `#/d/${p.made_on}` }, "open that day's digest")),
          h("p", {},
            `Called ${p.call} (${p.confidence}). Stock ${pct(p.stock_return_pct)}, ` +
            `S&P 500 ${pct(p.benchmark_return_pct)}, difference ${pct(p.excess_return_pct)}.`),
          h("p", {}, h("span", { class: "label" }, "Reasoning then"), p.reasoning),
          p.retrospective ? h("p", {}, h("span", { class: "label" }, "Looking back"), p.retrospective) : null)))));
  }
  app.replaceChildren(...nodes.flat(Infinity));
}

async function route() {
  const hash = location.hash || "#/";
  const scoreboard = hash === "#/scoreboard";
  for (const a of document.querySelectorAll("[data-nav]")) {
    a.classList.toggle("active", (a.dataset.nav === "scoreboard") === scoreboard);
  }
  try {
    if (scoreboard) await showScoreboard();
    else await showDigest(hash.startsWith("#/d/") ? hash.slice(4) : null);
  } catch (e) {
    app.replaceChildren(h("p", { class: "empty" }, `Could not load data: ${e.message}`));
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
