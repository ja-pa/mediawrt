/* MediaWrt 2: offline SPA. No filename or metadata is inserted as HTML. */
(() => {
  "use strict";
  const TEXT = window.MEDIAWRT_TEXT;
  const $ = (id) => document.getElementById(id);
  const read = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem("mediawrt." + key)) ?? fallback;
    } catch {
      return fallback;
    }
  };
  const pref = (key, fallback) => {
    try {
      return localStorage.getItem("mediawrt." + key) ?? fallback;
    } catch {
      return fallback;
    }
  };
  const THEMES = [
    ["01-terracotta-archive", "Terracotta Archive"],
    ["02-midnight-cobalt", "Midnight Cobalt"],
    ["03-emerald-nocturne", "Emerald Nocturne"],
    ["04-burgundy-velvet", "Burgundy Velvet"],
    ["05-amber-espresso", "Amber Espresso"],
    ["06-obsidian-monochrome", "Obsidian Monochrome"],
    ["07-nordic-petrol", "Nordic Petrol"],
    ["08-plum-aubergine", "Plum Aubergine"],
    ["09-gallery-ivory", "Gallery Ivory"],
    ["10-alabaster-sage", "Alabaster Sage"],
  ];
  function applyTheme(value) {
    const theme = THEMES.some((x) => x[0] === value) ? value : THEMES[0][0];
    document.documentElement.dataset.theme = theme;
    document.getElementById("palette").href =
      "/app/css/palettes/" + theme + ".css";
    document.querySelector('meta[name="color-scheme"]').content =
      theme.startsWith("09-") || theme.startsWith("10-") ? "light" : "dark";
    return theme;
  }
  applyTheme(pref("theme", THEMES[0][0]));
  let lang = pref(
    "language",
    navigator.language.startsWith("cs") ? "cs" : "en",
  );
  const t = (key) =>
    TEXT[key]?.[lang === "cs" ? 0 : 1] ??
    TEXT[key]?.[1] ??
    TEXT.error[lang === "cs" ? 0 : 1];
  function save(key, value) {
    try {
      localStorage.setItem("mediawrt." + key, JSON.stringify(value));
    } catch {
      toast(t("storageError"));
    }
  }
  function savePref(key, value) {
    try {
      localStorage.setItem("mediawrt." + key, String(value));
    } catch {
      toast(t("storageError"));
    }
  }
  let personal = read("personal.v1", {});
  if (!personal || typeof personal !== "object" || Array.isArray(personal))
    personal = {};
  let config,
    serial = 0,
    thumbSession,
    queue = read("queue.v2", []),
    queueIndex = 0,
    shuffle = false,
    repeat = false,
    playingVideo = null,
    lastVideoSave = 0,
    slideTimer,
    toastTimer;
  if (!Array.isArray(queue)) queue = [];
  queue = queue.filter(
    (x) =>
      x &&
      typeof x.url === "string" &&
      x.url.startsWith("/media/") &&
      typeof x.id === "string",
  );
  const audio = $("audio"),
    modal = $("modal"),
    videoModal = $("video-modal");
  const icons = {
    home: "⌂",
    movies: "▸",
    series: "▤",
    music: "♫",
    pictures: "▧",
    files: "▱",
    settings: "⚙",
  };
  function el(tag, text, attrs = {}) {
    const n = document.createElement(tag);
    if (text !== null && text !== undefined) n.textContent = String(text);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
    return n;
  }
  function btn(text, action, cls = "", attrs = {}) {
    const b = el("button", text, { type: "button", ...attrs });
    b.className = cls;
    b.onclick = action;
    return b;
  }
  function action(key, fn, cls = "") {
    return btn(t(key), fn, cls);
  }
  function link(text, href) {
    return el("a", text, { href });
  }
  function toast(text) {
    $("toast").textContent = text;
    $("toast").hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => ($("toast").hidden = true), 6000);
  }
  function fmtSize(n) {
    if (!Number.isFinite(n)) return "—";
    const u = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1024 && i < 4) {
      n /= 1024;
      i++;
    }
    return n.toFixed(i ? 1 : 0) + " " + u[i];
  }
  function fmtTime(n) {
    if (!Number.isFinite(n)) return "—";
    return (
      Math.floor(n / 60) + ":" + String(Math.floor(n % 60)).padStart(2, "0")
    );
  }
  function urlPath(path) {
    return config.volume + path.split("/").map(encodeURIComponent).join("/");
  }
  function route() {
    const raw = location.hash.slice(1) || "home";
    const [v, q] = raw.split("?");
    return { view: v, p: new URLSearchParams(q || "") };
  }
  function navigate(view, params = {}) {
    history.replaceState({ scroll: window.scrollY }, "");
    const q = new URLSearchParams(params);
    location.hash = view + (q.size ? "?" + q : "");
  }
  async function api(route, params = {}, method = "GET", v = 2) {
    const q = new URLSearchParams(params);
    const res = await fetch(
      "/.cpr/media/v" + v + "/" + route + (q.size ? "?" + q : ""),
      method === "POST"
        ? {
            method,
            headers: { [v === 2 ? "X-MediaWrt" : "X-Copyparty-Media"]: "1" },
            body: "",
          }
        : { cache: "no-store" },
    );
    let data;
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    if (!res.ok) {
      const err = new Error(
        t(
          res.status === 401 || res.status === 403 || res.status === 503
            ? "unavailable"
            : "error",
        ) +
          " (" +
          res.status +
          ")",
      );
      err.data = data;
      throw err;
    }
    return data;
  }
  async function listing(path = "") {
    const res = await fetch(
      urlPath(path) + (path && !path.endsWith("/") ? "/" : "") + "?ls",
      { cache: "no-store" },
    );
    if (!res.ok) throw new Error(t("unavailable"));
    return res.json();
  }
  function catalog(params) {
    return api("catalog", params);
  }
  async function allCatalog(params) {
    let values = [],
      page = 0,
      data;
    do {
      data = await catalog({ ...params, page });
      values.push(...data.items);
      page++;
    } while (values.length < data.total && page < 100);
    return values;
  }
  function remember() {
    const entries = Object.entries(personal);
    const history = entries
      .filter(([, v]) => !v.favorite)
      .sort((a, b) => (b[1].at || 0) - (a[1].at || 0));
    for (const [k] of history.slice(1000)) delete personal[k];
    save("personal.v1", personal);
  }
  function toggleFavorite(value) {
    const old = personal[value.id] || {};
    personal[value.id] = { ...old, favorite: !old.favorite };
    remember();
    return personal[value.id].favorite;
  }
  function personalIds(mode) {
    return Object.entries(personal)
      .filter(
        ([, x]) =>
          x &&
          (mode === "favorites"
            ? x.favorite
            : mode === "watched"
              ? x.watched
              : mode === "inProgress"
                ? x.position > 1 && !x.watched
                : x.at),
      )
      .map(([id]) => id);
  }
  function openModal(title) {
    clearInterval(slideTimer);
    modal.onclose = null;
    modal.replaceChildren(
      btn("×", () => modal.close(), "close", { "aria-label": t("close") }),
      el("h2", title),
    );
    if (!modal.open) modal.showModal();
    return modal;
  }
  function empty(text = t("emptyHint")) {
    const box = el("div", null, { class: "empty" });
    box.append(el("h2", t("empty")), el("p", text));
    return box;
  }
  function heading(name, kicker) {
    const box = el("div");
    if (kicker) box.append(el("p", kicker, { class: "eyebrow" }));
    box.append(el("h1", name));
    return box;
  }
  function setShell() {
    document.documentElement.lang = lang;
    document.title = "MediaWrt";
    const side = $("sidebar");
    side.replaceChildren();
    const brand = el("div", null, { class: "brand" });
    brand.append("Media", el("span", "Wrt"));
    side.append(brand);
    const nav = el("nav", null, { "aria-label": "MediaWrt" });
    for (const key of Object.keys(icons)) {
      const a = link("", "#" + key);
      a.className = "navlink";
      a.dataset.view = key;
      a.append(
        el("span", icons[key], { class: "navicon", "aria-hidden": "true" }),
        el("span", t(key)),
      );
      nav.append(a);
    }
    side.append(nav);
    const bottom = el("div", null, { class: "navbottom" });
    const status = el("div", null, { class: "serverbadge" });
    status.append(el("span", "", { class: "dot" }), el("span", t("offline")));
    bottom.append(status);
    side.append(bottom);
    const top = $("topbar");
    top.replaceChildren();
    const form = el("form"),
      input = el("input", null, {
        type: "search",
        placeholder: t("search"),
        "aria-label": t("search"),
        maxlength: 200,
      });
    const submit = el("button", "⌕", {
      type: "submit",
      "aria-label": t("searchAction"),
    });
    form.append(input, submit);
    form.onsubmit = (e) => {
      e.preventDefault();
      navigate("search", { q: input.value });
    };
    top.append(
      form,
      btn(
        config && config.user !== "*" ? config.user : t("login"),
        login,
        "account",
      ),
    );
  }
  function thumbStatus(s) {
    let status = $("thumb-status");
    if (!status) {
      status = el("span", "", {
        id: "thumb-status",
        role: "status",
        class: "thumb-status",
      });
      $("topbar").append(status);
    }
    const count =
      s && !s.stopped
        ? s.tasks.filter((x) => x.pending && !x.done && x.visible).length
        : 0;
    status.hidden = !count;
    status.textContent = count ? t("generatingThumbs") + " · " + count : "";
  }
  function thumbStop() {
    thumbStatus(null);
    if (thumbSession) {
      thumbSession.stopped = true;
      thumbSession.observer.disconnect();
      thumbSession.controllers.forEach((c) => c.abort());
      thumbSession.urls.forEach(URL.revokeObjectURL);
      thumbSession = null;
    }
  }
  function thumbnail(slot, value) {
    if (pref("thumbs", "1") !== "1") return;
    if (!thumbSession) {
      const session = {
        stopped: false,
        controllers: new Set(),
        urls: new Set(),
        active: 0,
        tasks: [],
        observer: null,
      };
      session.observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            const task = session.tasks.find((x) => x.slot === entry.target);
            if (task) task.visible = entry.isIntersecting;
          }
          thumbStatus(session);
          pump(session);
        },
        { rootMargin: "100px" },
      );
      thumbSession = session;
    }
    const task = {
      slot,
      value,
      visible: false,
      done: false,
      next: 0,
      until: Date.now() + 90000,
    };
    thumbSession.tasks.push(task);
    thumbSession.observer.observe(slot);
  }
  function pump(s) {
    if (s.stopped || document.hidden) return;
    for (const task of s.tasks) {
      if (s.active >= 2) break;
      if (!task.visible || task.done || task.busy || Date.now() < task.next)
        continue;
      task.busy = true;
      s.active++;
      (async () => {
        let controller = new AbortController();
        s.controllers.add(controller);
        const timeout = setTimeout(() => controller.abort(), 5000);
        try {
          let res = await fetch(
            "/.cpr/media/v2/artwork?" +
              new URLSearchParams({ path: task.value.path }),
            { signal: controller.signal },
          );
          if (
            res.status === 204 &&
            config.thumbnails &&
            ["pictures", "series", "movies"].includes(task.value.kind)
          )
            res = await fetch(
              "/.cpr/media/v2/thumbnail?" +
                new URLSearchParams({ path: task.value.path }),
              { signal: controller.signal },
            );
          if (
            res.status === 200 &&
            res.headers.get("content-type")?.startsWith("image/")
          ) {
            const blob = await res.blob();
            if (s.stopped) return;
            const url = URL.createObjectURL(blob);
            s.urls.add(url);
            task.slot.replaceChildren(
              el("img", null, { src: url, alt: "", loading: "lazy" }),
            );
            task.done = true;
          } else if ([202, 429].includes(res.status)) {
            task.pending = true;
            task.slot.setAttribute("aria-busy", "true");
            if (!task.slot.querySelector(".thumb-pending"))
              task.slot.append(
                el("span", t("thumbPending"), { class: "thumb-pending" }),
              );
          } else if (![503].includes(res.status)) task.done = true;
        } catch {
        } finally {
          clearTimeout(timeout);
          s.controllers.delete(controller);
          task.busy = false;
          s.active--;
          task.next = Date.now() + 2000;
          if (Date.now() > task.until) task.done = true;
          if (task.done) {
            task.pending = false;
            task.slot.removeAttribute("aria-busy");
            const label = task.slot.querySelector(".thumb-pending");
            if (label) {
              label.className = "thumb-unavailable";
              label.textContent = t("thumbUnavailable");
            }
          }
          if (!s.stopped) thumbStatus(s);
          if (!s.stopped) setTimeout(() => pump(s), 2000);
        }
      })();
    }
  }
  function cover(value) {
    const slot = el("div", null, { class: "cover" });
    slot.append(
      el("span", icons[value.kind] || "▸", {
        class: "placeholder",
        "aria-hidden": "true",
      }),
    );
    thumbnail(slot, value);
    return slot;
  }
  function card(value) {
    const article = el("article", null, {
      class:
        "card " +
        (value.kind === "music"
          ? "square"
          : value.kind === "pictures" ||
              (value.kind === "series" && !value.group)
            ? "landscape"
            : ""),
    });
    const open = btn("", () => openItem(value), "open");
    const image = cover(value);
    open.append(
      image,
      el("h3", value.title),
      el(
        "small",
        value.group
          ? String(value.count) +
              " · " +
              t(
                value.kind === "music"
                  ? "tracks"
                  : value.kind === "pictures"
                    ? "pictures"
                    : "episode",
              )
          : value.year || value.album || value.folder || "",
      ),
    );
    article.append(open);
    if (!value.group) {
      const f = btn(
        personal[value.id]?.favorite ? "★" : "☆",
        () => {
          const yes = toggleFavorite(value);
          f.textContent = yes ? "★" : "☆";
          f.setAttribute("aria-label", t(yes ? "unfavorite" : "favorite"));
        },
        "fav",
        {
          "aria-label": t(
            personal[value.id]?.favorite ? "unfavorite" : "favorite",
          ),
        },
      );
      article.append(f);
      if (personal[value.id]?.watched)
        image.append(
          el("span", "✓", { class: "badge", "aria-label": t("watched") }),
        );
      const p = personal[value.id];
      if (p?.position > 0 && p.duration && !p.watched) {
        const bar = el("div", null, { class: "progress" });
        bar.style.width = Math.min(100, (p.position / p.duration) * 100) + "%";
        image.append(bar);
      }
    }
    return article;
  }
  function grid(items) {
    const box = el("div", null, {
      class: "grid" + (pref("smallCards", "0") === "1" ? " small" : ""),
    });
    for (const value of items) box.append(card(value));
    if (!items.length) return empty();
    return box;
  }
  function openItem(value) {
    if (value.group) {
      const params = {};
      if (value.group === "album") params.folder = value.group_key;
      else params[value.group] = value.group_key;
      navigate(
        value.kind === "series"
          ? "series"
          : value.kind === "music"
            ? "music"
            : "pictures",
        params,
      );
    } else if (value.kind === "pictures") gallery(value);
    else if (value.kind === "music") playAudio([value]);
    else navigate("detail", { id: value.id });
  }
  function section(parent, key, items, view, params = {}) {
    if (!items.length) return;
    const head = el("div", null, { class: "section-head" });
    head.append(
      el("h2", t(key)),
      btn(t("seeAll") + " →", () => navigate(view, params)),
    );
    parent.append(head, grid(items.slice(0, 8)));
  }
  async function home(content, id) {
    content.append(heading(t("home"), t("localLibrary")));
    const hero = el("section", null, { class: "hero" }),
      text = el("div");
    text.append(el("h1", t("welcome")), el("p", t("intro")));
    const actions = el("div", null, { class: "actions" });
    actions.append(
      action("browseMovies", () => navigate("movies"), "primary"),
      action("openFiles", () => navigate("files")),
    );
    text.append(actions);
    hero.append(text, el("span", "◉", { class: "orb", "aria-hidden": "true" }));
    content.append(hero);
    const [resume, fav, recent] = await Promise.all([
      catalog({ ids: personalIds("inProgress").join(",") }),
      catalog({ ids: personalIds("favorites").join(",") }),
      catalog({ new: 1, sort: "added" }),
    ]);
    if (id !== serial) return;
    section(content, "continue", resume.items, "movies", {
      filter: "inProgress",
    });
    section(content, "favorites", fav.items, "search", { filter: "favorites" });
    section(content, "recent", recent.items, "search", {
      new: 1,
      sort: "added",
    });
    const [movies, music] = await Promise.all([
      catalog({ kind: "movies" }),
      catalog({ kind: "music", group: "album" }),
    ]);
    if (id !== serial) return;
    section(content, "movies", movies.items, "movies");
    section(content, "music", music.items, "music");
  }
  function selector(label, options, value, onchange) {
    const select = el("select", null, { "aria-label": t(label) });
    for (const [key, name] of options)
      select.append(el("option", name, { value: key }));
    select.value = value;
    select.onchange = () => onchange(select.value);
    return select;
  }
  async function libraryView(content, r, id) {
    const view = r.view,
      params = Object.fromEntries(r.p),
      kind = view === "search" ? "all" : view;
    const title =
      params.series ||
      params.album ||
      params.artist ||
      params.folder?.split("/").pop() ||
      t(view === "search" ? "searchResults" : view);
    content.append(heading(title, t("localLibrary")));
    const filters = el("div", null, { class: "filters" });
    const update = (key, value) =>
      navigate(view, { ...params, [key]: value, page: 0 });
    filters.append(
      selector(
        "sort",
        [
          ["title", t("title")],
          ["year", t("year")],
          ["added", t("added")],
        ],
        params.sort || "title",
        (v) => update("sort", v),
      ),
    );
    filters.append(
      selector(
        "filter",
        ["all", "favorites", "inProgress", "watched", "unwatched"].map((k) => [
          k,
          t(k),
        ]),
        params.filter || "all",
        (v) => update("filter", v),
      ),
    );
    filters.append(
      selector(
        "view",
        [
          ["grid", t("grid")],
          ["list", t("list")],
        ],
        pref("layout", "grid"),
        (v) => {
          savePref("layout", v);
          render();
        },
      ),
    );
    if (["movies", "series", "search"].includes(view)) {
      const label = el("label"),
        checkbox = el("input", null, { type: "checkbox" });
      checkbox.checked = pref("hideAvi", "1") === "1";
      checkbox.onchange = () => {
        savePref("hideAvi", checkbox.checked ? "1" : "0");
        render();
      };
      label.append(checkbox, " " + t("hideAvi"));
      filters.append(label);
    }
    if (view === "music" && !params.folder && !params.artist) {
      const tabs = el("div", null, { class: "tabs" });
      for (const group of ["album", "artist", "tracks"])
        tabs.append(
          btn(
            t(
              group === "album"
                ? "albums"
                : group === "artist"
                  ? "artists"
                  : "tracks",
            ),
            () => update("group", group),
            "",
            { "aria-pressed": String((params.group || "album") === group) },
          ),
        );
      filters.append(tabs);
    }
    if (params.series || params.folder || params.artist)
      filters.append(action("back", () => navigate(view)));
    content.append(filters);
    const query = { ...params, kind, hide_avi: pref("hideAvi", "1") };
    if (
      params.filter &&
      params.filter !== "all" &&
      params.filter !== "unwatched"
    )
      query.ids = personalIds(params.filter).join(",");
    if (
      view === "series" &&
      !params.series &&
      (!params.filter || params.filter === "all")
    )
      query.group = "series";
    if (view === "series" && params.series) {
      query.sort = "episode";
      const episodes = await allCatalog({
        kind: "series",
        series: params.series,
      });
      if (id !== serial) return;
      const seasons = [
        ...new Set(episodes.map((x) => x.season).filter((x) => x !== null)),
      ].sort((a, b) => a - b);
      filters.append(
        selector(
          "season",
          [
            ["", t("all")],
            ...seasons.map((x) => [String(x), t("season") + " " + x]),
          ],
          params.season || "",
          (v) => update("season", v),
        ),
      );
    }
    if (
      view === "music" &&
      !params.folder &&
      !params.artist &&
      (!params.group || params.group !== "tracks")
    )
      query.group = params.group || "album";
    if (
      view === "pictures" &&
      !params.folder &&
      (!params.filter || params.filter === "all")
    )
      query.group = "folder";
    if (view === "music" && params.folder && !params.sort) query.sort = "track";
    let data = await catalog(query);
    if (id !== serial) return;
    if (params.filter === "unwatched") {
      const all = await allCatalog({ ...query, page: 0 });
      if (id !== serial) return;
      const filtered = all.filter((x) => !personal[x.id]?.watched);
      const page = Number(params.page || 0);
      data = {
        ...data,
        total: filtered.length,
        items: filtered.slice(page * 60, page * 60 + 60),
      };
    }
    if (
      view === "music" &&
      (params.folder || params.artist || params.group === "tracks")
    ) {
      const controls = el("div", null, { class: "actions" });
      controls.append(
        action(
          "play",
          async () =>
            playAudio(
              await allCatalog({
                ...query,
                group: "",
                sort: params.sort || "track",
              }),
            ),
          "primary",
        ),
        action("enqueue", async () =>
          enqueue(await allCatalog({ ...query, group: "" })),
        ),
      );
      content.append(controls);
      const list = el("section", null, { class: "panel" });
      data.items.forEach((x, i) => {
        const row = el("div", null, { class: "row" });
        row.append(
          el("small", i + 1),
          btn(x.title, () => playAudio([x]), "title"),
          btn("+", () => enqueue([x]), "", { "aria-label": t("enqueue") }),
          action("playNext", () => enqueue([x], true)),
          action("details", () => navigate("detail", { id: x.id })),
        );
        list.append(row);
      });
      content.append(data.items.length ? list : empty());
    } else {
      const body = el("div", null, {
        class: pref("layout", "grid") === "list" ? "library-list" : "",
      });
      body.append(grid(data.items));
      content.append(body);
    }
    if (data.scanning)
      content.append(el("p", t("scanning"), { role: "status" }));
    const pages = Math.max(1, Math.ceil(data.total / 60)),
      page = Number(params.page || 0);
    if (pages > 1) {
      const nav = el("nav", null, { class: "pager", "aria-label": t("page") });
      const prev = action("previous", () => update("page", page - 1)),
        next = action("next", () => update("page", page + 1)); // page navigation must preserve the selected page.
      prev.onclick = () => navigate(view, { ...params, page: page - 1 });
      next.onclick = () => navigate(view, { ...params, page: page + 1 });
      prev.disabled = page === 0;
      next.disabled = page + 1 >= pages;
      nav.append(prev, el("span", page + 1 + " / " + pages), next);
      content.append(nav);
    }
  }
  async function detail(content, r, id) {
    let value = await api("detail", { id: r.p.get("id") });
    if (id !== serial) return;
    content.append(action("back", () => history.back()));
    const panel = el("section", null, { class: "detail panel" }),
      text = el("div");
    panel.append(cover(value));
    text.append(
      el("p", t(value.kind), { class: "eyebrow" }),
      el("h1", value.local?.title || value.title),
    );
    const facts = el("div", null, { class: "facts" });
    facts.append(
      el("span", value.local?.year || value.year || ""),
      el("span", value.ext.toUpperCase()),
      el("span", fmtSize(value.size)),
    );
    text.append(facts);
    if (value.local?.plot) text.append(el("p", value.local.plot));
    if (value.local?.genre)
      text.append(el("p", value.local.genre, { class: "muted" }));
    const actions = el("div", null, { class: "actions" });
    actions.append(
      action(
        personal[value.id]?.position && !personal[value.id]?.watched
          ? "resume"
          : "play",
        () => (value.kind === "music" ? playAudio([value]) : playVideo(value)),
        "primary",
      ),
      action("restart", () =>
        value.kind === "music" ? playAudio([value]) : playVideo(value, true),
      ),
    );
    const fav = action(
      personal[value.id]?.favorite ? "unfavorite" : "favorite",
      () => {
        fav.textContent = t(toggleFavorite(value) ? "unfavorite" : "favorite");
      },
    );
    const watched = action(
      personal[value.id]?.watched ? "markUnwatched" : "markWatched",
      () => {
        personal[value.id] = {
          ...personal[value.id],
          watched: !personal[value.id]?.watched,
          at: Date.now(),
        };
        remember();
        watched.textContent = t(
          personal[value.id].watched ? "markUnwatched" : "markWatched",
        );
      },
    );
    actions.append(fav, watched);
    text.append(actions, el("p", value.path, { class: "path" }));
    panel.append(text);
    content.append(panel);
    const tools = el("div", null, { class: "actions" });
    tools.append(
      action("openFiles", () => navigate("files", { path: value.folder })),
      link(t("download"), value.url + "?dl"),
      action("copyUrl", () => copyLink(value.url)),
    );
    if (config.move)
      tools.append(
        action("move", () =>
          chooseMove([{ path: value.path, name: value.name }]),
        ),
      );
    if (config.admin)
      tools.append(action("editMetadata", () => editMetadata(value)));
    content.append(tools);
    const meta = el("section", null, { class: "panel" });
    content.append(meta);
    function showTechnical() {
      meta.replaceChildren(el("h2", t("metadata")));
      const f = value.technical?.format || {},
        tags = f.tags || {};
      for (const [key, val] of Object.entries({
        duration: f.duration ? fmtTime(Number(f.duration)) : null,
        artist: tags.artist,
        album: tags.album,
        title: tags.title,
      })) {
        if (val) meta.append(el("p", t(key) + ": " + val));
      }
      for (const stream of value.technical?.streams || [])
        meta.append(
          el(
            "p",
            [
              stream.codec_type,
              stream.codec_name,
              stream.width && stream.width + " × " + stream.height,
            ]
              .filter(Boolean)
              .join(" · "),
          ),
        );
      if (value.metadata_pending)
        meta.append(el("p", t("metadataPending"), { class: "muted" }));
      else if (!value.technical?.format)
        meta.append(el("p", t("unknown"), { class: "muted" }));
    }
    showTechnical();
    let attempts = 0;
    async function poll() {
      if (id !== serial || !value.metadata_pending || attempts++ > 20) return;
      try {
        value = await api("detail", { id: value.id });
        if (id !== serial) return;
        showTechnical();
        if (value.metadata_pending) setTimeout(poll, 1200);
      } catch {}
    }
    if (value.metadata_pending) setTimeout(poll, 1200);
  }
  function editMetadata(value) {
    const box = openModal(t("editMetadata")),
      form = el("form");
    const title = el("input", null, {
        value: value.title,
        "aria-label": t("title"),
      }),
      series = el("input", null, {
        value: value.series || "",
        "aria-label": t("series"),
      });
    const kind = selector(
      "view",
      [
        ["movies", t("movies")],
        ["series", t("series")],
      ],
      value.kind,
      () => {},
    );
    form.append(
      title,
      series,
      kind,
      el("button", t("save"), { type: "submit" }),
    );
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(
          "override",
          {
            id: value.id,
            title: title.value,
            series: series.value,
            kind: kind.value,
          },
          "POST",
        );
        modal.close();
        render();
      } catch (e) {
        toast(e.message);
      }
    };
    box.append(form);
  }
  async function copyLink(url) {
    try {
      await navigator.clipboard.writeText(new URL(url, location.origin).href);
      toast(t("copied"));
    } catch {
      const box = openModal(t("copyUrl"));
      const input = el("input", null, {
        value: new URL(url, location.origin).href,
        readonly: "",
      });
      box.append(input);
      input.select();
    }
  }
  function saveVideo() {
    const video = videoModal.querySelector("video");
    if (!playingVideo || !video || video.currentTime < 1) return;
    personal[playingVideo.id] = {
      ...personal[playingVideo.id],
      position: video.currentTime,
      duration: Number.isFinite(video.duration) ? video.duration : 0,
      at: Date.now(),
      watched: video.ended || personal[playingVideo.id]?.watched || false,
    };
    remember();
  }
  async function playVideo(value, fromStart = false) {
    if (!value.subtitles) {
      try {
        value = await api("detail", { id: value.id });
      } catch (e) {
        toast(e.message);
        return;
      }
    }
    audio.pause();
    saveVideo();
    videoModal.querySelector("video")?.pause();
    playingVideo = value;
    videoModal.replaceChildren();
    const video = el("video", null, {
      controls: "",
      playsinline: "",
      preload: "metadata",
      src: value.url,
    });
    videoModal.append(
      btn("×", () => videoModal.close(), "close", { "aria-label": t("close") }),
      el("h2", value.title),
      video,
    );
    const controls = el("div", null, { class: "actions player-tools" });
    const sub = selector(
      "subtitles",
      [["", t("noSubtitles")], ...value.subtitles.map((x) => [x.path, x.name])],
      "",
      (path) => {
        video.querySelectorAll("track").forEach((x) => x.remove());
        if (path)
          video.append(
            el("track", null, {
              kind: "subtitles",
              src: "/.cpr/media/v2/subtitle?" + new URLSearchParams({ path }),
              label: path.split("/").pop(),
              default: "",
            }),
          );
      },
    );
    controls.append(
      sub,
      action("fullscreen", async () => {
        try {
          if (document.fullscreenElement === video)
            await document.exitFullscreen();
          else if (video.requestFullscreen) await video.requestFullscreen();
          else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
          else throw new Error("unsupported");
        } catch {
          error.textContent = t("fullscreenError");
        }
      }),
    );
    if (document.pictureInPictureEnabled)
      controls.append(
        action("pip", () => video.requestPictureInPicture?.().catch(() => {})),
      );
    const local = el("input", null, {
      type: "file",
      accept: ".srt,.vtt",
      "aria-label": t("localSubtitle"),
    });
    let localUrl;
    local.onchange = async () => {
      const file = local.files[0];
      if (!file) return;
      let text = await file.text();
      if (file.name.toLowerCase().endsWith(".srt"))
        text =
          "WEBVTT\n\n" + text.replace(/(\d\d:\d\d:\d\d),(\d{3})/g, "$1.$2");
      if (localUrl) URL.revokeObjectURL(localUrl);
      localUrl = URL.createObjectURL(new Blob([text], { type: "text/vtt" }));
      video.querySelectorAll("track").forEach((x) => x.remove());
      video.append(
        el("track", null, {
          kind: "subtitles",
          src: localUrl,
          default: "",
          label: file.name,
        }),
      );
    };
    local.hidden = true;
    controls.append(
      local,
      action("localSubtitle", () => local.click(), "local-subtitle"),
      action("copyUrl", () => copyLink(value.url)),
      link(t("download"), value.url + "?dl"),
    );
    videoModal.append(controls);
    const error = el("p", "", { role: "status" });
    videoModal.append(error);
    video.onerror = () => (error.textContent = t("codec"));
    video.onloadedmetadata = () => {
      const pos = personal[value.id]?.position || 0;
      if (
        !fromStart &&
        !personal[value.id]?.watched &&
        pos < video.duration - 3
      )
        video.currentTime = pos;
    };
    video.ontimeupdate = () => {
      if (Date.now() - lastVideoSave > 15000) {
        saveVideo();
        lastVideoSave = Date.now();
      }
    };
    video.onpause = saveVideo;
    video.onended = async () => {
      saveVideo();
      if (value.kind === "series" && pref("autoplay", "0") === "1") {
        const episodes = await allCatalog({
          kind: "series",
          series: value.series,
          sort: "episode",
        });
        const at = episodes.findIndex((x) => x.id === value.id);
        if (episodes[at + 1] && videoModal.open)
          playVideo(episodes[at + 1], true);
      }
    };
    videoModal.onclose = async () => {
      saveVideo();
      playingVideo = null;
      video.pause();
      try {
        if (document.fullscreenElement === video)
          await document.exitFullscreen();
        else if (video.webkitDisplayingFullscreen)
          video.webkitExitFullscreen?.();
      } catch {}
      video.removeAttribute("src");
      video.load();
      if (localUrl) URL.revokeObjectURL(localUrl);
    };
    if (!videoModal.open) videoModal.showModal();
    video.play().catch(() => {});
  }
  window.addEventListener("pagehide", saveVideo);
  function enqueue(items, next = false) {
    if (next) queue.splice(queueIndex + 1, 0, ...items);
    else queue.push(...items);
    save("queue.v2", queue);
    toast(t("enqueue"));
    updateDock();
  }
  function playAudio(items) {
    if (!items.length) return;
    queue = items;
    queueIndex = 0;
    save("queue.v2", queue);
    startTrack();
  }
  function startTrack() {
    const value = queue[queueIndex];
    if (!value) return;
    videoModal.querySelector("video")?.pause();
    audio.src = value.url;
    audio.play().catch(() => toast(t("codec")));
    updateDock();
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: value.title,
          artist: value.artist || "",
          album: value.album || "",
        });
        navigator.mediaSession.setActionHandler("play", () => audio.play());
        navigator.mediaSession.setActionHandler("pause", () => audio.pause());
        navigator.mediaSession.setActionHandler("nexttrack", () =>
          stepTrack(1),
        );
        navigator.mediaSession.setActionHandler("previoustrack", () =>
          stepTrack(-1),
        );
      } catch {}
    }
  }
  function stepTrack(delta) {
    if (!queue.length) return;
    if (shuffle && delta > 0)
      queueIndex = Math.floor(Math.random() * queue.length);
    else {
      const next = queueIndex + delta;
      if (next < 0 || next >= queue.length) {
        if (!repeat) return;
        queueIndex = (next + queue.length) % queue.length;
      } else queueIndex = next;
    }
    startTrack();
  }
  audio.onended = () => stepTrack(1);
  audio.onerror = () => toast(t("codec"));
  audio.onplay = audio.onpause = () => {
    const b = $("audio-toggle");
    if (b) b.textContent = audio.paused ? "▶" : "Ⅱ";
  };
  audio.ontimeupdate = () => {
    const seek = $("audio-seek");
    if (seek && !seek.matches(":active"))
      seek.value = audio.duration
        ? (audio.currentTime / audio.duration) * 100
        : 0;
    const time = $("audio-time");
    if (time)
      time.textContent =
        fmtTime(audio.currentTime) + " / " + fmtTime(audio.duration);
  };
  function updateDock() {
    const dock = $("audio-dock"),
      value = queue[queueIndex];
    dock.hidden = !value;
    if (!value) return;
    dock.replaceChildren();
    const track = el("div", null, { class: "track" });
    track.append(
      el("strong", value.title),
      el("small", value.artist || value.album || t("music")),
    );
    const controls = el("div", null, { class: "player-buttons" });
    controls.append(
      btn("‹", () => stepTrack(-1), "", { "aria-label": t("previous") }),
      btn(
        audio.paused ? "▶" : "Ⅱ",
        () => {
          if (!audio.src) startTrack();
          else if (audio.paused) audio.play();
          else audio.pause();
        },
        "primary",
        { id: "audio-toggle", "aria-label": t("play") },
      ),
      btn("›", () => stepTrack(1), "", { "aria-label": t("next") }),
    );
    const seek = el("input", null, {
      id: "audio-seek",
      class: "seek",
      type: "range",
      min: 0,
      max: 100,
      step: 0.1,
      value: 0,
      "aria-label": t("position"),
    });
    seek.oninput = () => {
      if (Number.isFinite(audio.duration))
        audio.currentTime = (audio.duration * Number(seek.value)) / 100;
    };
    const volume = el("input", null, {
      class: "volume",
      type: "range",
      min: 0,
      max: 1,
      step: 0.05,
      value: audio.volume,
      "aria-label": t("volume"),
    });
    volume.oninput = () => (audio.volume = Number(volume.value));
    dock.append(
      track,
      controls,
      seek,
      el("small", "", { id: "audio-time" }),
      volume,
      action("queue", showQueue, "queue-button"),
    );
  }
  function showQueue() {
    const box = openModal(t("queue"));
    const actions = el("div", null, { class: "actions" });
    const random = action("shuffle", () => {
      shuffle = !shuffle;
      random.setAttribute("aria-pressed", String(shuffle));
    });
    random.setAttribute("aria-pressed", String(shuffle));
    const loop = action("repeat", () => {
      repeat = !repeat;
      loop.setAttribute("aria-pressed", String(repeat));
    });
    loop.setAttribute("aria-pressed", String(repeat));
    actions.append(
      random,
      loop,
      action("clearQueue", () => {
        audio.pause();
        audio.removeAttribute("src");
        queue = [];
        save("queue.v2", queue);
        updateDock();
        showQueue();
      }),
    );
    box.append(actions);
    queue.forEach((value, i) => {
      const row = el("div", null, { class: "row" });
      row.append(
        btn(
          (i === queueIndex ? "♪ " : "") + value.title,
          () => {
            queueIndex = i;
            startTrack();
          },
          "title",
        ),
        btn(
          "↑",
          () => {
            if (i > 0) {
              const current = queue[queueIndex];
              [queue[i - 1], queue[i]] = [queue[i], queue[i - 1]];
              queueIndex = queue.indexOf(current);
              save("queue.v2", queue);
              showQueue();
            }
          },
          "",
          { "aria-label": t("moveUp") },
        ),
        btn(
          "↓",
          () => {
            if (i + 1 < queue.length) {
              const current = queue[queueIndex];
              [queue[i], queue[i + 1]] = [queue[i + 1], queue[i]];
              queueIndex = queue.indexOf(current);
              save("queue.v2", queue);
              showQueue();
            }
          },
          "",
          { "aria-label": t("moveDown") },
        ),
        btn(
          "×",
          () => {
            const current = queue[queueIndex];
            queue.splice(i, 1);
            if (current === value) {
              audio.pause();
              audio.removeAttribute("src");
              queueIndex = Math.min(i, queue.length - 1);
            } else queueIndex = queue.indexOf(current);
            save("queue.v2", queue);
            updateDock();
            showQueue();
          },
          "",
          { "aria-label": t("remove") },
        ),
      );
      box.append(row);
    });
  }
  async function gallery(value) {
    const items = await allCatalog({ kind: "pictures", folder: value.folder });
    let index = Math.max(
        0,
        items.findIndex((x) => x.id === value.id),
      ),
      seconds = 5;
    const box = openModal(value.title);
    const image = el("img", null, {
      class: "gallery-image",
      alt: value.title,
      src: value.url,
    });
    box.append(image);
    const controls = el("div", null, { class: "actions" });
    function show(delta) {
      index = (index + delta + items.length) % items.length;
      image.src = items[index].url;
      image.alt = items[index].title;
      box.querySelector("h2").textContent = items[index].title;
    }
    controls.append(
      action("previous", () => show(-1)),
      action("next", () => show(1)),
      action("zoom", () => image.classList.toggle("zoomed")),
      action("fullscreen", () => box.requestFullscreen?.()),
    );
    const slide = action("slideshow", () => {
      if (slideTimer) {
        clearInterval(slideTimer);
        slideTimer = null;
        slide.textContent = t("slideshow");
      } else {
        slideTimer = setInterval(() => show(1), seconds * 1000);
        slide.textContent = t("stop");
      }
    });
    controls.append(
      slide,
      selector(
        "interval",
        [
          ["3", "3 s"],
          ["5", "5 s"],
          ["10", "10 s"],
        ],
        "5",
        (v) => {
          seconds = Number(v);
          if (slideTimer) {
            clearInterval(slideTimer);
            slideTimer = setInterval(() => show(1), seconds * 1000);
          }
        },
      ),
    );
    box.append(controls);
    box.onclose = () => {
      clearInterval(slideTimer);
      slideTimer = null;
    };
  }
  function entries(data, path) {
    const parse = (x, dir) => {
      const u = new URL(
        x.href,
        location.origin + urlPath(path) + (path ? "/" : ""),
      );
      if (u.origin !== location.origin || !u.pathname.startsWith(config.volume))
        return null;
      let rel = decodeURIComponent(
        u.pathname.slice(config.volume.length),
      ).replace(/\/$/, "");
      return {
        path: rel,
        name: rel.split("/").pop(),
        dir,
        size: x.sz,
        modified: x.ts,
      };
    };
    return [
      ...(data.dirs || []).map((x) => parse(x, true)),
      ...(data.files || []).map((x) => parse(x, false)),
    ].filter(Boolean);
  }
  async function fileManager(content, r, id) {
    const path = r.p.get("path") || "";
    content.append(heading(t("files"), t("localLibrary")));
    const crumbs = el("nav", null, {
      class: "crumbs",
      "aria-label": t("folder"),
    });
    crumbs.append(btn(t("root"), () => navigate("files")));
    let current = "";
    for (const part of path.split("/").filter(Boolean)) {
      current += (current ? "/" : "") + part;
      const dest = current;
      crumbs.append(
        el("span", "/"),
        btn(part, () => navigate("files", { path: dest })),
      );
    }
    content.append(crumbs);
    const data = await listing(path);
    if (id !== serial) return;
    let values = entries(data, path),
      selected = new Set();
    const controls = el("div", null, { class: "actions" }),
      status = el("small", "");
    const pick = el("input", null, { type: "file", multiple: "", hidden: "" });
    pick.onchange = () => uploadFiles(path, [...pick.files]);
    content.append(pick);
    if (config.upload) {
      controls.append(
        action("upload", () => pick.click(), "primary"),
        action("newFolder", () => newFolder(path)),
      );
    }
    if (config.move) {
      controls.append(
        action("move", () => {
          const list = values.filter((x) => selected.has(x.path));
          if (!list.length) return toast(t("noSelection"));
          chooseMove(list);
        }),
        action("rename", () => {
          const list = values.filter((x) => selected.has(x.path));
          if (list.length !== 1) return toast(t("noSelection"));
          renameFile(list[0]);
        }),
      );
    }
    controls.append(
      action("download", () => {
        for (const value of values.filter(
          (x) => selected.has(x.path) && !x.dir,
        )) {
          const a = link("", urlPath(value.path) + "?dl");
          a.download = value.name;
          document.body.append(a);
          a.click();
          a.remove();
        }
      }),
      status,
    );
    content.append(controls);
    const wrap = el("div", null, { class: "table-wrap" }),
      table = el("table", null, { class: "file-table" }),
      thead = el("thead"),
      header = el("tr"),
      all = el("input", null, {
        type: "checkbox",
        "aria-label": t("selectAll"),
      });
    const first = el("th");
    first.append(all);
    header.append(first);
    for (const key of ["name", "size", "modified"])
      header.append(
        el("th", t(key), { class: key === "modified" ? "date" : "" }),
      );
    thead.append(header);
    table.append(thead);
    const body = el("tbody");
    table.append(body);
    function draw() {
      body.replaceChildren();
      for (const value of values) {
        const row = el("tr"),
          check = el("input", null, {
            type: "checkbox",
            "aria-label": value.name,
          });
        check.checked = selected.has(value.path);
        check.onchange = () => {
          if (check.checked) selected.add(value.path);
          else selected.delete(value.path);
          status.textContent = t("selected") + ": " + selected.size;
        };
        const cell = el("td");
        cell.append(check);
        const name = el("td", null, { class: "name" });
        name.append(
          btn((value.dir ? "▱  " : "") + value.name, async () => {
            if (value.dir) return navigate("files", { path: value.path });
            const found = await catalog({
              q: value.name,
              kind: "all",
              hide_avi: 0,
            });
            const item = found.items.find((x) => x.path === value.path);
            if (item) openItem(item);
            else {
              const a = link("", urlPath(value.path) + "?dl");
              document.body.append(a);
              a.click();
              a.remove();
            }
          }),
        );
        row.append(
          cell,
          name,
          el("td", value.dir ? "—" : fmtSize(value.size)),
          el(
            "td",
            value.modified
              ? new Date(value.modified * 1000).toLocaleDateString(lang)
              : "—",
            { class: "date" },
          ),
        );
        body.append(row);
      }
    }
    all.onchange = () => {
      selected = new Set(all.checked ? values.map((x) => x.path) : []);
      draw();
      status.textContent = t("selected") + ": " + selected.size;
    };
    const sort = selector(
      "sort",
      [
        ["name", t("name")],
        ["size", t("size")],
        ["modified", t("modified")],
      ],
      "name",
      (key) => {
        values.sort(
          (a, b) =>
            Number(b.dir) - Number(a.dir) ||
            (key === "name"
              ? a.name.localeCompare(b.name, lang)
              : (b[key] || 0) - (a[key] || 0)),
        );
        draw();
      },
    );
    controls.append(sort);
    draw();
    wrap.append(table);
    content.append(values.length ? wrap : empty());
  }
  function newFolder(path) {
    const box = openModal(t("newFolder")),
      form = el("form"),
      input = el("input", null, {
        required: "",
        maxlength: 200,
        "aria-label": t("name"),
      });
    form.append(
      input,
      el("button", t("create"), { type: "submit", class: "primary" }),
    );
    form.onsubmit = async (e) => {
      e.preventDefault();
      if (!input.value || /[\\/]/.test(input.value)) return toast(t("error"));
      try {
        const full = (path ? path + "/" : "") + input.value;
        const res = await fetch(
          "/.cpr/media/v2/mkdir?" + new URLSearchParams({ path: full }),
          { method: "POST", headers: { "X-MediaWrt": "1" }, body: "" },
        );
        if (!res.ok) throw new Error(t("error"));
        modal.close();
        render();
      } catch (e) {
        toast(e.message);
      }
    };
    box.append(form);
    input.focus();
  }
  let uploadsRunning = false;
  async function uploadFiles(path, files) {
    if (uploadsRunning) return toast(t("loading"));
    uploadsRunning = true;
    const box = $("transfers");
    box.hidden = false;
    box.replaceChildren(
      el("strong", t("upload")),
      el("p", t("transferNote"), { class: "muted" }),
    );
    const status = el("p"),
      progress = el("progress", null, { max: 100, value: 0 });
    box.append(status, progress);
    try {
      for (const file of files) {
        status.textContent = file.name;
        await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("PUT", urlPath((path ? path + "/" : "") + file.name));
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) progress.value = (e.loaded / e.total) * 100;
          };
          xhr.onload = () =>
            xhr.status < 300 ? resolve() : reject(new Error(t("uploadFail")));
          xhr.onerror = () => reject(new Error(t("uploadFail")));
          xhr.send(file);
        });
      }
      toast(t("done"));
      if (route().view === "files") render();
    } catch (e) {
      toast(e.message);
    } finally {
      uploadsRunning = false;
      box.hidden = true;
    }
  }
  window.addEventListener("beforeunload", (e) => {
    if (uploadsRunning) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  async function chooseMove(values) {
    const box = openModal(t("destination"));
    let current = "";
    const crumb = el("p", "", { class: "path" }),
      dirs = el("div", null, { class: "destination-list" }),
      choose = action(
        "chooseHere",
        () => prepareMoves(values, current),
        "primary",
      );
    box.append(crumb, dirs, choose);
    async function browse(path) {
      current = path;
      crumb.textContent = "/" + path;
      dirs.replaceChildren(el("p", t("loading")));
      try {
        const data = await listing(path);
        dirs.replaceChildren();
        if (path)
          dirs.append(
            action("back", () =>
              browse(path.split("/").slice(0, -1).join("/")),
            ),
          );
        for (const folder of entries(data, path).filter((x) => x.dir))
          dirs.append(btn("▱ " + folder.name, () => browse(folder.path)));
        choose.disabled = !(data.perms || []).includes("write");
      } catch (e) {
        dirs.replaceChildren(el("p", e.message));
        choose.disabled = true;
      }
    }
    await browse("");
  }
  function renameFile(value) {
    const box = openModal(t("rename")),
      form = el("form"),
      input = el("input", null, {
        value: value.name,
        required: "",
        "aria-label": t("name"),
      });
    form.append(
      input,
      el("button", t("next"), { type: "submit", class: "primary" }),
    );
    form.onsubmit = (e) => {
      e.preventDefault();
      if (/[\\/]/.test(input.value)) return toast(t("error"));
      const parent = value.path.split("/").slice(0, -1).join("/");
      prepareMoves([value], parent, input.value);
    };
    box.append(form);
  }
  async function prepareMoves(values, destination, newName) {
    try {
      const plans = [];
      for (const value of values) {
        const target =
          (destination ? destination + "/" : "") + (newName || value.name);
        plans.push(
          await api("move-preview", { source: value.path, target }, "GET", 1),
        );
      }
      const box = openModal(t("previewMove"));
      box.append(el("p", t("moveNote")));
      for (const plan of plans) {
        const list = el("div", null, { class: "move-plan" });
        plan.checks = [];
        plan.files.forEach((file, i) => {
          const line = el("label", null, { class: "row" }),
            check = el("input", null, { type: "checkbox" });
          check.checked = true;
          check.disabled = i === 0;
          plan.checks.push({ file, check });
          line.append(check, el("span", file.source + " → " + file.target));
          list.append(line);
        });
        box.append(list);
      }
      const confirm = action(
        "confirmMove",
        async () => {
          confirm.disabled = true;
          const completed = [];
          try {
            for (const plan of plans) {
              const result = await api(
                "move",
                {
                  token: plan.token,
                  include: JSON.stringify(
                    plan.checks
                      .filter((x) => x.check.checked)
                      .map((x) => x.file.source),
                  ),
                },
                "POST",
                1,
              );
              completed.push(...result.completed);
            }
            modal.close();
            toast(t("done"));
            render();
          } catch (e) {
            box.append(
              el("p", t("partial")),
              el(
                "pre",
                JSON.stringify(
                  [...completed, ...(e.data?.completed || [])],
                  null,
                  2,
                ),
              ),
            );
          }
        },
        "primary",
      );
      box.append(el("div", null, { class: "actions" }));
      box.lastChild.append(
        action("cancel", () => modal.close()),
        confirm,
      );
    } catch (e) {
      toast(e.message);
    }
  }
  async function login() {
    const box = openModal(t("login"));
    if (config?.user && config.user !== "*") {
      box.append(
        el("p", config.user),
        action("logout", async () => {
          const body = new FormData();
          body.append("act", "logout");
          await fetch("/media/", { method: "POST", body });
          modal.close();
          await boot();
        }),
      );
      return;
    }
    const form = el("form"),
      input = el("input", null, {
        type: "password",
        autocomplete: "current-password",
        required: "",
        "aria-label": t("password"),
      });
    const status = el("p", "", { role: "status" });
    form.append(
      input,
      el("button", t("login"), { type: "submit", class: "primary" }),
      status,
    );
    form.onsubmit = async (e) => {
      e.preventDefault();
      try {
        const body = new FormData();
        body.append("act", "login");
        body.append("cppwd", input.value);
        await fetch("/media/", { method: "POST", body });
        const next = await api("config");
        if (next.user === "*") throw new Error(t("loginError"));
        config = next;
        modal.close();
        setShell();
        render();
      } catch {
        status.textContent = t("loginError");
      }
    };
    box.append(form);
    input.focus();
  }
  function settings(content) {
    content.append(heading(t("settings"), t("localLibrary")));
    const p = el("section", null, { class: "panel" });
    p.append(
      el("h2", t("personal")),
      el("p", t("localNote"), { class: "muted" }),
    );
    const language = selector(
      "language",
      [
        ["cs", "Čeština"],
        ["en", "English"],
      ],
      lang,
      (value) => {
        lang = value;
        savePref("language", lang);
        setShell();
        updateDock();
        render();
      },
    );
    p.append(settingRow("language", language));
    const theme = selector(
      "theme",
      THEMES,
      document.documentElement.dataset.theme,
      (value) => {
        savePref("theme", applyTheme(value));
      },
    );
    p.append(
      settingRow("theme", theme),
      el("p", t("themeHint"), { class: "muted" }),
    );
    for (const key of ["thumbs", "smallCards", "autoplay"]) {
      const checkbox = el("input", null, {
        type: "checkbox",
        "aria-label": t(key),
      });
      checkbox.checked = pref(key, key === "thumbs" ? "1" : "0") === "1";
      checkbox.onchange = () => savePref(key, checkbox.checked ? "1" : "0");
      p.append(settingRow(key, checkbox));
    }
    const actions = el("div", null, { class: "actions" });
    for (const key of ["clearHistory", "clearFavorites"])
      actions.append(
        action(key, () => {
          if (!confirm(t("confirmClear"))) return;
          for (const id of Object.keys(personal)) {
            if (key === "clearFavorites") delete personal[id].favorite;
            else personal[id] = { favorite: personal[id].favorite || false };
          }
          if (key === "clearHistory") playingVideo = null;
          remember();
          toast(t("done"));
        }),
      );
    actions.append(
      action("exportData", () => {
        const url = URL.createObjectURL(
          new Blob([JSON.stringify({ version: 2, personal, queue })], {
            type: "application/json",
          }),
        );
        const a = link("", url);
        a.download = "mediawrt-personal.json";
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }),
    );
    const input = el("input", null, {
      type: "file",
      accept: ".json",
      hidden: "",
    });
    input.onchange = async () => {
      try {
        const file = input.files[0];
        if (!file || file.size > 5 * 1024 * 1024) throw Error();
        const data = JSON.parse(await file.text());
        if (
          data.version !== 2 ||
          !data.personal ||
          Array.isArray(data.personal) ||
          typeof data.personal !== "object"
        )
          throw Error();
        const clean = {};
        for (const [id, v] of Object.entries(data.personal)) {
          if (!/^[a-f0-9]{32}$/.test(id) || !v || typeof v !== "object")
            continue;
          clean[id] = {
            favorite: v.favorite === true,
            watched: v.watched === true,
            position: Math.max(0, Number(v.position) || 0),
            duration: Math.max(0, Number(v.duration) || 0),
            at: Math.max(0, Number(v.at) || 0),
          };
        }
        personal = { ...personal, ...clean };
        remember();
        toast(t("done"));
      } catch {
        toast(t("invalidData"));
      }
    };
    actions.append(
      action("importData", () => input.click()),
      input,
    );
    p.append(actions);
    content.append(p);
    const server = el("section", null, { class: "panel" });
    server.append(
      el("h2", t("server")),
      el("p", "MediaWrt " + config.version),
      el("p", t(config.move ? "manage" : config.upload ? "write" : "readonly")),
      el("p", t("sourceNote"), { class: "muted" }),
    );
    server.append(el("h3", t("sources")));
    for (const source of config.sources.length
      ? config.sources
      : [{ path: "/", kind: "all" }])
      server.append(el("p", source.path + " · " + t(source.kind)));
    if (config.admin)
      for (const [k, v] of Object.entries(config.paths))
        server.append(el("p", k + ": " + v, { class: "path" }));
    if (config.upload)
      server.append(
        action("scan", async () => {
          if (!confirm(t("manualScan"))) return;
          try {
            await api("scan", {}, "POST", 1);
            toast(t("scanStarted"));
          } catch (e) {
            toast(e.message);
          }
        }),
      );
    if (config.admin) {
      const native = link(t("native"), "/media/?native=1");
      native.target = "_blank";
      native.rel = "noopener";
      server.append(el("p"), native);
    }
    content.append(server);
  }
  function settingRow(key, input) {
    const row = el("div", null, { class: "settings-row" });
    row.append(el("label", t(key)), input);
    return row;
  }
  async function render() {
    const id = ++serial;
    thumbStop();
    const r = route();
    for (const a of document.querySelectorAll(".navlink")) {
      if (a.dataset.view === r.view) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
    const content = $("content");
    content.replaceChildren();
    if (!config) {
      content.append(
        empty(t("unavailable")),
        action("login", login, "primary"),
      );
      return;
    }
    try {
      if (r.view === "home") await home(content, id);
      else if (
        ["movies", "series", "music", "pictures", "search"].includes(r.view)
      )
        await libraryView(content, r, id);
      else if (r.view === "detail") await detail(content, r, id);
      else if (r.view === "files") await fileManager(content, r, id);
      else settings(content);
      if (id === serial) window.scrollTo(0, history.state?.scroll || 0);
    } catch (e) {
      if (id === serial)
        content.append(empty(e.message), action("retry", render));
    }
  }
  window.addEventListener("hashchange", render);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) saveVideo();
    else if (thumbSession) pump(thumbSession);
  });
  document.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key))
      return;
    const button = e.target.closest(".card .open");
    if (!button) return;
    const cards = [...button.closest(".grid").querySelectorAll(".open")],
      i = cards.indexOf(button);
    const columns = Math.max(
      1,
      Math.round(
        button.closest(".grid").clientWidth /
          button.closest(".card").offsetWidth,
      ),
    );
    const delta =
      e.key === "ArrowLeft"
        ? -1
        : e.key === "ArrowRight"
          ? 1
          : e.key === "ArrowUp"
            ? -columns
            : columns;
    if (cards[i + delta]) {
      e.preventDefault();
      cards[i + delta].focus();
    }
  });
  new ResizeObserver((entries) => {
    document.documentElement.style.setProperty(
      "--dock-height",
      entries[0].target.hidden
        ? "0px"
        : entries[0].target.getBoundingClientRect().height + "px",
    );
  }).observe($("audio-dock"));
  async function boot() {
    try {
      config = await api("config");
    } catch {
      config = null;
    }
    setShell();
    updateDock();
    render();
  }
  boot();
})();
