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

function moverRow(mover, prediction) {
  return h("details", { class: "row" },
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
    digest.movers.length
      ? [
          h("p", { class: "hint" }, "Click a stock to see the full story."),
          moverGroup("Gainers", digest.movers.filter((m) => m.change_pct >= 0), byId, day),
          moverGroup("Losers", digest.movers.filter((m) => m.change_pct < 0), byId, day),
        ]
      : h("p", { class: "empty" }, "No movers were analysed for this day."),
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
