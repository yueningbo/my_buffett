/**
 * Buffett Letters — year page + index interactions
 * Views: guide | zh
 * Theme: light | dark
 * Terms: data-term="id" → assets/glossary.json (local data-term-title/body override)
 */
(function () {
  const root = document.documentElement;
  const body = document.body;
  const buttons = document.querySelectorAll(".view-switch [data-view]");
  const panels = {
    guide: document.querySelector(".panel-guide"),
    zh: document.querySelector(".panel-zh"),
  };
  const VALID = ["guide", "zh"];
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

  function normalize(view) {
    if (view === "original" || view === "en" || view === "split") return "zh";
    return VALID.includes(view) ? view : "guide";
  }

  function setView(view) {
    const next = normalize(view);
    body.dataset.view = next;

    buttons.forEach((btn) => {
      btn.setAttribute("aria-selected", String(btn.dataset.view === next));
    });

    Object.values(panels).forEach((p) => p?.classList.remove("is-active"));
    if (panels[next]) panels[next].classList.add("is-active");

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

  let saved = "guide";
  try {
    saved = localStorage.getItem(VIEW_KEY) || "guide";
  } catch (_) {}
  if (buttons.length) setView(saved);

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

  /* —— Index catalog + timeline —— */
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

  const indexList = document.querySelector("[data-catalog]");
  const timelineMount = document.querySelector("[data-timeline]");
  if (indexList || timelineMount) {
    const url =
      (indexList && indexList.getAttribute("data-catalog")) ||
      (timelineMount && timelineMount.getAttribute("data-catalog")) ||
      "catalog.json";
    fetch(url)
      .then((r) => r.json())
      .then((catalog) => {
        const years = catalog.years || [];
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
              const a = document.createElement("a");
              a.href = y.href;
              const ready = y.status === "ready";
              if (ready) a.classList.add("is-ready");
              else {
                a.classList.add("is-stub");
                if (y.status === "stub") a.setAttribute("aria-disabled", "true");
              }
              a.innerHTML = String(y.year) + "<em></em>";
              const em = a.querySelector("em");
              const scoreBits = [];
              if (y.dow_display) scoreBits.push("道指 " + y.dow_display);
              if (y.partnership_display) scoreBits.push("合伙 " + y.partnership_display);
              em.textContent =
                scoreBits.join(" · ") ||
                y.blurb ||
                (ready ? "已完成" : y.status === "wip" ? "制作中" : "待制作");
              if (y.status === "stub") {
                a.addEventListener("click", (e) => e.preventDefault());
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
