/**
 * Buffett Letters — year page + index interactions
 * Views: easy | deck | glance | guide | zh
 *   easy = 最易读连续解读（1964+ 默认）；deck/glance 为旧实验
 * Theme: light | dark
 * Terms: data-term="id" → assets/glossary.json (local data-term-title/body override)
 */
(function () {
  const root = document.documentElement;
  const body = document.body;
  const buttons = document.querySelectorAll(".view-switch [data-view]");
  const panels = {
    easy: document.querySelector(".panel-easy"),
    deck: document.querySelector(".panel-deck"),
    glance: document.querySelector(".panel-glance"),
    guide: document.querySelector(".panel-guide"),
    zh: document.querySelector(".panel-zh"),
  };
  const VALID = ["easy", "deck", "glance", "guide", "zh"];
  const THEME_KEY = "buffett-letter-theme";
  const VIEW_KEY = "buffett-letter-view";

  function preferredTheme() {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch (_) {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function setTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    root.setAttribute("data-theme", next);
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(next === "dark"));
      btn.setAttribute(
        "aria-label",
        next === "dark" ? "切换到日间模式" : "切换到夜间模式"
      );
    });
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (_) {}
  }

  function defaultView() {
    if (panels.easy) return "easy";
    if (panels.deck) return "deck";
    if (panels.glance) return "glance";
    if (panels.guide) return "guide";
    return "zh";
  }

  function normalize(view) {
    if (view === "original" || view === "en" || view === "split") return "zh";
    if (view === "deck" || view === "glance") {
      if (panels.easy && !panels[view]) return "easy";
    }
    if (view === "glance" && !panels.glance && panels.deck) return "deck";
    if (view === "deck" && !panels.deck) {
      return panels.glance ? "glance" : defaultView();
    }
    if (view === "easy" && !panels.easy) return defaultView();
    if (view === "glance" && !panels.glance) return defaultView();
    if (view === "guide" && !panels.guide) return defaultView();
    if (VALID.includes(view) && panels[view]) return view;
    return defaultView();
  }

  function setView(view) {
    const next = normalize(view);
    body.dataset.view = next;

    buttons.forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.view === next));
    });

    Object.values(panels).forEach((p) => p?.classList.remove("is-active"));
    if (panels[next]) panels[next].classList.add("is-active");

    if (next === "deck" && window.__buffettDeck) {
      window.__buffettDeck.sync();
    }

    try {
      localStorage.setItem(VIEW_KEY, next);
    } catch (_) {}
  }

  setTheme(root.getAttribute("data-theme") || preferredTheme());

  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cur = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
      setTheme(cur === "dark" ? "light" : "dark");
    });
  });

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });

  document.querySelectorAll("[data-goto-view]").forEach((el) => {
    el.addEventListener("click", (e) => {
      const view = el.getAttribute("data-goto-view");
      setView(view);
      document.getElementById("reading")?.scrollIntoView({ behavior: "smooth" });
      e.preventDefault();
    });
  });

  let saved = defaultView();
  try {
    const raw = localStorage.getItem(VIEW_KEY);
    if (raw) saved = raw;
  } catch (_) {}
  // Easy/deck-only pages have no view tabs; keep the primary reading panel active.
  if (
    buttons.length ||
    body.getAttribute("data-easy-only") === "true" ||
    body.getAttribute("data-deck-only") === "true"
  ) {
    const forced = body.getAttribute("data-easy-only") === "true"
      ? "easy"
      : body.getAttribute("data-deck-only") === "true"
        ? "deck"
        : saved;
    setView(forced);
  }

  /* —— Deck (PPT / 分镜翻页) —— */
  (function initDeck() {
    const rootEl = document.querySelector("[data-deck]");
    if (!rootEl) return;

    const slides = [...rootEl.querySelectorAll("[data-deck-slide]")];
    if (!slides.length) return;

    const prevBtn = rootEl.querySelector("[data-deck-prev]");
    const nextBtn = rootEl.querySelector("[data-deck-next]");
    const curEl = rootEl.querySelector("[data-deck-current]");
    const totalEl = rootEl.querySelector("[data-deck-total]");
    const dotsHost = rootEl.querySelector("[data-deck-dots]");
    let index = 0;
    let touchX = null;

    if (totalEl) totalEl.textContent = String(slides.length);

    if (dotsHost) {
      dotsHost.innerHTML = "";
      slides.forEach((_, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "deck-dot";
        b.setAttribute("aria-label", "第 " + (i + 1) + " 页");
        b.addEventListener("click", () => go(i));
        dotsHost.appendChild(b);
      });
    }

    function go(i) {
      index = Math.max(0, Math.min(slides.length - 1, i));
      slides.forEach((s, n) => {
        s.classList.toggle("is-active", n === index);
        s.setAttribute("aria-hidden", String(n !== index));
      });
      if (curEl) curEl.textContent = String(index + 1);
      if (prevBtn) prevBtn.disabled = index === 0;
      if (nextBtn) {
        nextBtn.disabled = false;
        const last = index === slides.length - 1;
        const deckOnly = body.getAttribute("data-deck-only") === "true";
        nextBtn.textContent = last
          ? deckOnly || !panels.zh
            ? "再看一遍"
            : "读全文 →"
          : "下一页";
      }
      if (dotsHost) {
        [...dotsHost.children].forEach((d, n) => {
          d.classList.toggle("is-active", n === index);
        });
      }
      // animate bars if slide contains them
      const svg = slides[index].querySelector("[data-animate-bars]");
      if (svg && !svg.dataset.deckAnimated) {
        svg.dataset.deckAnimated = "1";
        // trigger intersection-style grow by resetting heights briefly
        svg.querySelectorAll("[data-bar]").forEach((bar) => {
          const h = Number(bar.getAttribute("height")) || 0;
          const y = Number(bar.getAttribute("data-y") || bar.getAttribute("y"));
          bar.setAttribute("height", "0");
          bar.setAttribute("y", String(y + h));
          requestAnimationFrame(() => {
            bar.style.transition = "height 0.7s cubic-bezier(0.22,1,0.36,1), y 0.7s cubic-bezier(0.22,1,0.36,1)";
            bar.setAttribute("height", String(h));
            bar.setAttribute("y", String(y));
          });
        });
      }
    }

    function next() {
      if (index >= slides.length - 1) {
        const deckOnly = body.getAttribute("data-deck-only") === "true";
        if (!deckOnly && panels.zh) {
          setView("zh");
          document
            .getElementById("reading")
            ?.scrollIntoView({ behavior: "smooth" });
          return;
        }
        go(0);
        return;
      }
      go(index + 1);
    }

    function prev() {
      go(index - 1);
    }

    prevBtn?.addEventListener("click", prev);
    nextBtn?.addEventListener("click", next);

    document.addEventListener("keydown", (e) => {
      if (body.dataset.view !== "deck") return;
      if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        prev();
      } else if (e.key === "Home") {
        e.preventDefault();
        go(0);
      } else if (e.key === "End") {
        e.preventDefault();
        go(slides.length - 1);
      }
    });

    rootEl.addEventListener(
      "touchstart",
      (e) => {
        if (body.dataset.view !== "deck") return;
        touchX = e.changedTouches[0].clientX;
      },
      { passive: true }
    );
    rootEl.addEventListener(
      "touchend",
      (e) => {
        if (touchX === null || body.dataset.view !== "deck") return;
        const dx = e.changedTouches[0].clientX - touchX;
        touchX = null;
        if (Math.abs(dx) < 48) return;
        if (dx < 0) next();
        else prev();
      },
      { passive: true }
    );

    rootEl.querySelectorAll("[data-deck-goto]").forEach((el) => {
      el.addEventListener("click", (e) => {
        const n = Number(el.getAttribute("data-deck-goto"));
        if (!Number.isNaN(n)) {
          e.preventDefault();
          go(n);
        }
      });
    });

    window.__buffettDeck = {
      sync() {
        go(index);
      },
      go,
    };
    go(0);
  })();

  /* —— Glossary —— */
  function glossaryUrl() {
    const el = document.querySelector('script[src*="letter.js"]');
    if (el && el.src) {
      return el.src.replace(/js\/letter\.js(\?.*)?$/, "glossary.json");
    }
    return "assets/glossary.json";
  }

  let glossary = {};

  function termCopy(btn) {
    const id = btn.getAttribute("data-term");
    const fromGloss = id && glossary[id] ? glossary[id] : null;
    return {
      title:
        btn.getAttribute("data-term-title") ||
        (fromGloss && fromGloss.title) ||
        btn.textContent.trim(),
      body:
        btn.getAttribute("data-term-body") ||
        (fromGloss && fromGloss.body) ||
        "",
    };
  }

  const pop = document.createElement("div");
  pop.className = "term-popover";
  pop.setAttribute("role", "tooltip");
  pop.hidden = true;
  document.body.appendChild(pop);

  let activeTerm = null;

  function placePopover(anchor) {
    const r = anchor.getBoundingClientRect();
    const pad = 12;
    const width = Math.min(352, window.innerWidth - 24);
    let left = r.left + window.scrollX;
    let top = r.bottom + window.scrollY + 8;
    if (left + width > window.scrollX + window.innerWidth - pad) {
      left = window.scrollX + window.innerWidth - width - pad;
    }
    if (left < window.scrollX + pad) left = window.scrollX + pad;
    pop.style.width = width + "px";
    pop.style.left = left + "px";
    pop.style.top = top + "px";
  }

  function closeTerm() {
    if (activeTerm) activeTerm.setAttribute("aria-expanded", "false");
    activeTerm = null;
    pop.classList.remove("is-open");
    pop.hidden = true;
  }

  function openTerm(btn) {
    const copy = termCopy(btn);
    pop.innerHTML = "<strong></strong><span></span>";
    pop.querySelector("strong").textContent = copy.title;
    pop.querySelector("span").textContent = copy.body;
    if (activeTerm && activeTerm !== btn) {
      activeTerm.setAttribute("aria-expanded", "false");
    }
    activeTerm = btn;
    btn.setAttribute("aria-expanded", "true");
    pop.hidden = false;
    placePopover(btn);
    requestAnimationFrame(() => pop.classList.add("is-open"));
  }

  function bindTerms() {
    document.querySelectorAll(".term").forEach((btn) => {
      if (btn.dataset.termBound) return;
      btn.dataset.termBound = "1";
      btn.setAttribute("type", "button");
      btn.setAttribute("aria-expanded", "false");
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (activeTerm === btn) closeTerm();
        else openTerm(btn);
      });
    });
  }

  bindTerms();

  fetch(glossaryUrl())
    .then((r) => (r.ok ? r.json() : {}))
    .then((data) => {
      glossary = data || {};
      bindTerms();
    })
    .catch(() => {});

  document.addEventListener("click", (e) => {
    if (
      !pop.contains(e.target) &&
      !(e.target instanceof Element && e.target.closest(".term"))
    ) {
      closeTerm();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTerm();
  });

  window.addEventListener(
    "scroll",
    () => {
      if (activeTerm) placePopover(activeTerm);
    },
    { passive: true }
  );

  /* —— Story thread metrics (year pages) —— */
  function metaUrl() {
    try {
      return new URL("meta.json", window.location.href).href;
    } catch (_) {
      return "meta.json";
    }
  }

  function catalogUrlForPage() {
    const el = document.querySelector('script[src*="letter.js"]');
    if (el && el.src) {
      return el.src.replace(/assets\/js\/letter\.js(\?.*)?$/, "catalog.json");
    }
    return "../../catalog.json";
  }

  function formatSignedClass(display) {
    const s = String(display || "");
    if (/^[−\-－]/.test(s) || /↓/.test(s)) return "is-down";
    if (/^\+/.test(s) || /↑/.test(s)) return "is-up";
    return "";
  }

  function renderThreadMetrics(meta, prevMeta) {
    const host = document.querySelector("[data-thread-metrics]");
    if (!host || !meta) return;

    const cells = [];
    if (meta.dow_display) {
      cells.push({
        label: "道指",
        value: meta.dow_display,
        note: meta.dow_detail || "",
        cls: formatSignedClass(meta.dow_display),
      });
    }
    if (meta.partnership_display) {
      cells.push({
        label: "合伙",
        value: meta.partnership_display,
        note: meta.partnership_detail || "",
        cls: formatSignedClass(meta.partnership_display),
      });
    }
    if (meta.aum_display) {
      cells.push({
        label: "规模",
        value: meta.aum_display,
        note: meta.aum_detail || "",
        cls: "",
      });
    }
    if (meta.age) {
      cells.push({
        label: "年龄",
        value: meta.age,
        note: /岁/.test(String(meta.age)) ? "" : "岁",
        cls: "",
      });
    }

    if (!cells.length && !meta.thread_note && !meta.market_mood) {
      host.hidden = true;
      return;
    }

    host.hidden = false;
    host.className = "thread-metrics";
    host.innerHTML = "";

    if (cells.length) {
      const row = document.createElement("div");
      row.className = "thread-metrics-row";
      cells.forEach((c) => {
        const el = document.createElement("div");
        el.className = "thread-metric" + (c.cls ? " " + c.cls : "");
        el.innerHTML =
          '<div class="thread-metric-label"></div>' +
          '<div class="thread-metric-value"></div>' +
          '<div class="thread-metric-note"></div>';
        el.querySelector(".thread-metric-label").textContent = c.label;
        el.querySelector(".thread-metric-value").textContent = c.value;
        el.querySelector(".thread-metric-note").textContent = c.note;
        row.appendChild(el);
      });
      host.appendChild(row);
    }

    if (meta.market_mood) {
      const mood = document.createElement("p");
      mood.className = "thread-mood";
      mood.textContent = "气氛 · " + meta.market_mood;
      host.appendChild(mood);
    }

    if (prevMeta && (prevMeta.dow_display || prevMeta.partnership_display)) {
      const bridge = document.createElement("p");
      bridge.className = "thread-bridge";
      const bits = [];
      if (prevMeta.partnership_display) {
        bits.push("上年合伙 " + prevMeta.partnership_display);
      }
      if (prevMeta.dow_display) {
        bits.push("道指 " + prevMeta.dow_display);
      }
      bridge.textContent = "主线衔接：" + bits.join(" · ") + " → 带着这个背景读这一年。";
      host.appendChild(bridge);
    }
    if (meta.thread_note) {
      const note = document.createElement("p");
      note.className = "thread-bridge";
      note.textContent = meta.thread_note;
      host.appendChild(note);
    }
  }

  function loadYearThread() {
    if (!document.querySelector("[data-thread-metrics]")) return;
    fetch(metaUrl())
      .then((r) => (r.ok ? r.json() : null))
      .then((meta) => {
        if (!meta) return null;
        return fetch(catalogUrlForPage())
          .then((r) => (r.ok ? r.json() : { years: [] }))
          .then((catalog) => {
            const years = (catalog && catalog.years) || [];
            let prevMeta = null;
            if (meta.prev != null) {
              prevMeta = years.find((y) => y.year === meta.prev) || null;
            }
            renderThreadMetrics(meta, prevMeta);
          })
          .catch(() => renderThreadMetrics(meta, null));
      })
      .catch(() => {});
  }

  loadYearThread();

  /* —— Index catalog + timeline + cumulative chart —— */
  function parseReturnPct(display) {
    const s = String(display || "")
      .replace(/,/g, "")
      .replace(/\s+/g, "")
      .trim();
    const m = s.match(/^([+＋−\-－]?)(\d+(?:\.\d+)?)%/);
    if (!m) return null;
    const neg = m[1] === "−" || m[1] === "-" || m[1] === "－";
    return (neg ? -1 : 1) * parseFloat(m[2]);
  }

  function buildCumulativeSeries(years) {
    const points = [];
    let dowIdx = 1;
    let partIdx = 1;
    years.forEach((y) => {
      const d = parseReturnPct(y.dow_display);
      const p = parseReturnPct(y.partnership_display);
      if (d === null || p === null) return;
      dowIdx *= 1 + d / 100;
      partIdx *= 1 + p / 100;
      points.push({
        year: y.year,
        href: y.href,
        status: y.status,
        dowCum: (dowIdx - 1) * 100,
        partCum: (partIdx - 1) * 100,
        dowYear: d,
        partYear: p,
      });
    });
    return points;
  }

  function renderStoryChart(years, mount) {
    if (!mount) return;
    const points = buildCumulativeSeries(years);
    mount.innerHTML = "";
    mount.className = "story-chart";
    if (points.length < 2) {
      mount.hidden = true;
      return;
    }
    mount.hidden = false;

    const head = document.createElement("div");
    head.className = "story-chart-head";
    const title = document.createElement("h2");
    title.className = "story-chart-title";
    title.textContent = "累计回报";
    const note = document.createElement("p");
    note.className = "story-chart-note";
    note.textContent =
      "自有完整年回报数据起复利累计（跳过无百分比的年份）。点击圆点进入该年。";
    const legend = document.createElement("div");
    legend.className = "story-chart-legend";
    legend.innerHTML =
      '<span class="is-dow">道指</span><span class="is-partnership">合伙</span>';
    head.appendChild(title);
    head.appendChild(note);
    head.appendChild(legend);
    mount.appendChild(head);

    const W = 720;
    const H = 260;
    const pad = { t: 18, r: 18, b: 36, l: 52 };
    const innerW = W - pad.l - pad.r;
    const innerH = H - pad.t - pad.b;
    const vals = points.reduce(
      (acc, pt) => {
        acc.push(pt.dowCum, pt.partCum);
        return acc;
      },
      [0]
    );
    let minV = Math.min.apply(null, vals);
    let maxV = Math.max.apply(null, vals);
    if (minV > 0) minV = 0;
    if (maxV < 0) maxV = 0;
    const span = maxV - minV || 1;
    const xAt = (i) =>
      pad.l + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
    const yAt = (v) => pad.t + ((maxV - v) / span) * innerH;

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      "道指与合伙累计回报折线，自 " +
        points[0].year +
        " 至 " +
        points[points.length - 1].year
    );

    function el(name, attrs) {
      const node = document.createElementNS(svgNS, name);
      Object.keys(attrs).forEach((k) => node.setAttribute(k, attrs[k]));
      return node;
    }

    // zero line
    const zeroY = yAt(0);
    svg.appendChild(
      el("line", {
        class: "story-chart-zero",
        x1: String(pad.l),
        y1: String(zeroY),
        x2: String(W - pad.r),
        y2: String(zeroY),
      })
    );

    // y ticks
    const tickCount = 4;
    for (let t = 0; t <= tickCount; t++) {
      const v = minV + (span * t) / tickCount;
      const y = yAt(v);
      svg.appendChild(
        el("line", {
          class: "story-chart-grid",
          x1: String(pad.l),
          y1: String(y),
          x2: String(W - pad.r),
          y2: String(y),
        })
      );
      const label = el("text", {
        class: "story-chart-axis",
        x: String(pad.l - 8),
        y: String(y + 4),
        "text-anchor": "end",
      });
      label.textContent = (v >= 0 ? "+" : "") + Math.round(v) + "%";
      svg.appendChild(label);
    }

    function poly(key, className) {
      const d = points
        .map((pt, i) => xAt(i) + "," + yAt(pt[key]))
        .join(" ");
      svg.appendChild(el("polyline", { class: className, points: d, fill: "none" }));
    }
    poly("dowCum", "story-chart-line is-dow");
    poly("partCum", "story-chart-line is-partnership");

    points.forEach((pt, i) => {
      const x = xAt(i);
      const yearLabel = el("text", {
        class: "story-chart-year",
        x: String(x),
        y: String(H - 12),
        "text-anchor": "middle",
      });
      yearLabel.textContent = String(pt.year);
      svg.appendChild(yearLabel);

      [
        { key: "dowCum", cls: "is-dow", name: "道指" },
        { key: "partCum", cls: "is-partnership", name: "合伙" },
      ].forEach((series) => {
        const cy = yAt(pt[series.key]);
        const tip =
          pt.year +
          " " +
          series.name +
          " 累计 " +
          (pt[series.key] >= 0 ? "+" : "") +
          pt[series.key].toFixed(1) +
          "%";
        if (pt.href && pt.status === "ready") {
          const a = document.createElementNS(svgNS, "a");
          a.setAttribute("href", pt.href);
          a.setAttributeNS("http://www.w3.org/1999/xlink", "href", pt.href);
          const c = el("circle", {
            class: "story-chart-dot " + series.cls,
            cx: String(x),
            cy: String(cy),
            r: "4.5",
          });
          const titleEl = document.createElementNS(svgNS, "title");
          titleEl.textContent = tip;
          c.appendChild(titleEl);
          a.appendChild(c);
          svg.appendChild(a);
        } else {
          const c = el("circle", {
            class: "story-chart-dot " + series.cls,
            cx: String(x),
            cy: String(cy),
            r: "4",
          });
          const titleEl = document.createElementNS(svgNS, "title");
          titleEl.textContent = tip;
          c.appendChild(titleEl);
          svg.appendChild(c);
        }
      });
    });

    const wrap = document.createElement("div");
    wrap.className = "story-chart-svg-wrap";
    wrap.appendChild(svg);
    mount.appendChild(wrap);

    const end = points[points.length - 1];
    const foot = document.createElement("p");
    foot.className = "story-chart-foot";
    foot.textContent =
      "至 " +
      end.year +
      "：道指累计约 +" +
      end.dowCum.toFixed(1) +
      "%，合伙累计约 +" +
      end.partCum.toFixed(1) +
      "%";
    mount.appendChild(foot);
  }

  function renderTimeline(years, mount) {
    if (!mount || !years.length) return;
    mount.innerHTML = "";
    mount.className = "story-timeline";
    const track = document.createElement("div");
    track.className = "story-timeline-track";
    years.forEach((y, i) => {
      if (i > 0) {
        const rail = document.createElement("div");
        rail.className = "story-timeline-rail";
        rail.setAttribute("aria-hidden", "true");
        track.appendChild(rail);
      }
      const node = document.createElement(y.status === "stub" ? "div" : "a");
      if (y.status !== "stub") node.href = y.href;
      node.className =
        "story-timeline-node" +
        (y.status === "ready" ? " is-ready" : "") +
        (y.status === "stub" ? " is-stub" : "") +
        (y.status === "wip" ? " is-wip" : "");
      const yearEl = document.createElement("div");
      yearEl.className = "story-timeline-year";
      yearEl.textContent = String(y.year);
      node.appendChild(yearEl);
      const scores = document.createElement("div");
      scores.className = "story-timeline-scores";
      if (y.dow_display) {
        const d = document.createElement("span");
        d.className = "score-dow " + formatSignedClass(y.dow_display);
        d.textContent = "道 " + y.dow_display;
        scores.appendChild(d);
      }
      if (y.partnership_display) {
        const p = document.createElement("span");
        p.className = "score-partnership " + formatSignedClass(y.partnership_display);
        p.textContent = "伙 " + y.partnership_display;
        scores.appendChild(p);
      }
      if (!y.dow_display && !y.partnership_display) {
        const p = document.createElement("span");
        p.textContent = y.status === "ready" ? "已完成" : "待制作";
        scores.appendChild(p);
      }
      node.appendChild(scores);
      track.appendChild(node);
    });
    mount.appendChild(track);
  }

  /* Prefer .catalog-root so timeline ([data-timeline]) is never wiped by the list. */
  const indexList =
    document.querySelector(".catalog-root[data-catalog]") ||
    document.querySelector("[data-catalog]:not([data-timeline])") ||
    document.querySelector("[data-catalog]");
  const timelineMount = document.querySelector("[data-timeline]");
  const chartMount = document.querySelector("[data-story-chart]");
  if (indexList || timelineMount || chartMount) {
    const url =
      (indexList && indexList.getAttribute("data-catalog")) ||
      (timelineMount && timelineMount.getAttribute("data-catalog")) ||
      "catalog.json";
    fetch(url)
      .then((r) => r.json())
      .then((catalog) => {
        const years = catalog.years || [];
        if (chartMount) renderStoryChart(years, chartMount);
        if (timelineMount) renderTimeline(years, timelineMount);

        if (!indexList) return;
        indexList.innerHTML = "";
        if (!years.length) {
          indexList.innerHTML =
            '<p class="catalog-empty">还没有年份页。复制 years/_template 开始手搓，然后运行 sync_catalog.py。</p>';
          return;
        }

        const eras = [];
        years.forEach((y) => {
          const key = y.era || "other";
          if (!eras.find((e) => e.key === key)) {
            eras.push({
              key,
              label:
                y.era_label ||
                (key === "partnership"
                  ? "Partnership"
                  : key === "berkshire"
                    ? "Berkshire"
                    : key),
            });
          }
        });

        eras.forEach((era) => {
          const section = document.createElement("section");
          section.className = "catalog-section";
          const h = document.createElement("h2");
          h.className = "catalog-era";
          h.textContent = era.label;
          section.appendChild(h);
          const grid = document.createElement("div");
          grid.className = "index-list";
          years
            .filter((y) => (y.era || "other") === era.key)
            .forEach((y) => {
              const ready = y.status === "ready";
              const a = document.createElement(ready || y.status === "wip" ? "a" : "div");
              if (a.tagName === "A") a.href = y.href;
              a.className =
                "index-item" +
                (ready ? " is-ready" : "") +
                (y.status === "stub" ? " is-stub" : "") +
                (y.status === "wip" ? " is-wip" : "");

              const yearEl = document.createElement("span");
              yearEl.className = "index-year";
              yearEl.textContent = String(y.year);
              a.appendChild(yearEl);

              const titleEl = document.createElement("span");
              titleEl.className = "index-title";
              if (ready || y.status === "wip") {
                titleEl.textContent = y.title || y.blurb || "继续阅读";
              } else {
                titleEl.textContent = "待制作";
              }
              a.appendChild(titleEl);

              const em = document.createElement("em");
              em.className = "index-blurb";
              if (ready || y.status === "wip") {
                const scoreBits = [];
                if (y.dow_display) scoreBits.push("道指 " + y.dow_display);
                if (y.partnership_display) {
                  scoreBits.push("合伙 " + y.partnership_display);
                }
                em.textContent =
                  y.blurb ||
                  scoreBits.join(" · ") ||
                  (ready ? "已完成" : "制作中");
              } else {
                em.textContent = "尚未开始";
              }
              a.appendChild(em);

              if (y.status === "stub") {
                a.setAttribute("aria-disabled", "true");
              }
              grid.appendChild(a);
            });
          section.appendChild(grid);
          indexList.appendChild(section);
        });

        const meta = document.querySelector("[data-catalog-meta]");
        if (meta) {
          meta.textContent =
            "已完成 " +
            (catalog.ready_count || 0) +
            " / " +
            (catalog.total || years.length) +
            " 年";
        }

        const cont = document.querySelector("[data-catalog-continue]");
        if (cont) {
          let latest = null;
          for (let i = years.length - 1; i >= 0; i--) {
            if (years[i].status === "ready" && years[i].href) {
              latest = years[i];
              break;
            }
          }
          if (latest) {
            cont.href = latest.href;
            cont.hidden = false;
            cont.textContent =
              "从最新一年继续 · " + latest.year + " →";
          } else {
            cont.hidden = true;
          }
        }
      })
      .catch(() => {
        if (indexList) {
          indexList.innerHTML =
            '<p class="catalog-empty">目录加载失败。请先运行：python3 web/tools/sync_catalog.py</p>';
        }
      });
  }

  /* —— Charts —— */
  document.querySelectorAll("[data-animate-bars]").forEach((svg) => {
    const zeroY = Number(svg.dataset.zeroY || 140);
    const bars = [...svg.querySelectorAll("[data-bar]")].map((bar) => ({
      el: bar,
      h: Number(bar.getAttribute("height")),
      y: Number(bar.getAttribute("data-y") || bar.getAttribute("y")),
    }));

    // Keep authored heights until animation starts, so charts never stay blank
    // if IntersectionObserver never hits a high threshold (short viewports, etc.).
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    let ran = false;
    const run = () => {
      if (ran) return;
      ran = true;
      bars.forEach(({ el }) => {
        el.setAttribute("y", String(zeroY));
        el.setAttribute("height", "0");
      });
      bars.forEach((bar, i) => {
        const start = performance.now() + i * 90;
        const dur = 700;
        const tick = (now) => {
          if (now < start) {
            requestAnimationFrame(tick);
            return;
          }
          const t = Math.min(1, (now - start) / dur);
          const e = ease(t);
          bar.el.setAttribute("height", String(bar.h * e));
          bar.el.setAttribute("y", String(zeroY + (bar.y - zeroY) * e));
          if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
    };

    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            run();
            io.disconnect();
          }
        },
        { threshold: 0, rootMargin: "48px 0px" }
      );
      io.observe(svg);
    } else {
      run();
    }
  });
})();
