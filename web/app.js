/* AI 每日前沿 —— 前端逻辑
 *
 * 要点：
 *  - 无框架、无构建步骤，直接把 feed.json 渲染成信息流
 *  - 已读 / 收藏 / 主题只存在浏览器本地（localStorage）
 *  - 每次加载自动清理已不在列表里的已读记录，收藏永不自动清理
 */

// 部署后把 Actions 工作流页面地址填在这里，手动更新按钮才会出现
var MANUAL_UPDATE_URL = "";

var DATA_URL = "feed.json";
var KEY_READ = "aifeed.read";
var KEY_FAV = "aifeed.fav";
var KEY_THEME = "aifeed.theme";
var CATEGORY_LABEL = { lab: "实验室", paper: "论文", "cn-media": "中文媒体" };

var state = {
  items: [],
  category: "all",
  query: "",
  read: {},
  fav: {},
  feed: null
};

/* ---------------- 本地存储 ---------------- */

function loadSet(key) {
  try {
    var raw = localStorage.getItem(key);
    if (!raw) return {};
    var list = JSON.parse(raw);
    var map = {};
    if (Array.isArray(list)) {
      for (var i = 0; i < list.length; i++) map[list[i]] = true;
    }
    return map;
  } catch (err) {
    return {};
  }
}

function saveSet(key, map) {
  try {
    localStorage.setItem(key, JSON.stringify(Object.keys(map)));
  } catch (err) {
    /* 存储写满时静默失败，不影响阅读 */
  }
}

/* ---------------- 时间显示 ---------------- */

function relativeTime(iso, estimated) {
  if (estimated) return "时间未知";
  var then = new Date(iso).getTime();
  if (isNaN(then)) return "时间未知";
  var diff = Date.now() - then;
  if (diff < 0) diff = 0;
  var mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return mins + " 分钟前";
  var hours = Math.floor(mins / 60);
  if (hours < 24) return hours + " 小时前";
  var days = Math.floor(hours / 24);
  if (days < 7) return days + " 天前";
  return iso.slice(0, 10);
}

function absoluteTime(iso) {
  var d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
         " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
}

/* ---------------- 渲染 ---------------- */

function matchesQuery(item) {
  if (!state.query) return true;
  var q = state.query.toLowerCase();
  return item.title.toLowerCase().indexOf(q) >= 0 ||
         item.source.toLowerCase().indexOf(q) >= 0;
}

function visibleItems() {
  return state.items.filter(function (item) {
    if (state.category === "fav") return !!state.fav[item.id] && matchesQuery(item);
    if (state.category !== "all" && item.category !== state.category) return false;
    return matchesQuery(item);
  });
}

function buildItem(item) {
  var li = document.createElement("li");
  li.className = "item";
  if (state.read[item.id]) li.className += " is-read";
  if (state.fav[item.id]) li.className += " is-fav";

  var main = document.createElement("div");
  main.className = "item-main";

  var meta = document.createElement("div");
  meta.className = "item-meta";

  var source = document.createElement("span");
  source.className = "source-name";
  source.textContent = item.source;
  meta.appendChild(source);

  var cat = document.createElement("span");
  cat.className = "tag";
  cat.textContent = CATEGORY_LABEL[item.category] || item.category;
  meta.appendChild(cat);

  var time = document.createElement("span");
  time.textContent = relativeTime(item.published_at, item.date_estimated);
  if (!item.date_estimated) time.title = absoluteTime(item.published_at);
  meta.appendChild(time);

  main.appendChild(meta);

  var link = document.createElement("a");
  link.className = "title";
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = item.title;
  link.addEventListener("click", function () {
    state.read[item.id] = true;
    saveSet(KEY_READ, state.read);
    if (li.className.indexOf("is-read") < 0) li.className += " is-read";
  });
  main.appendChild(link);
  li.appendChild(main);

  var star = document.createElement("button");
  star.type = "button";
  star.className = "star" + (state.fav[item.id] ? " is-on" : "");
  star.textContent = state.fav[item.id] ? "★" : "☆";
  star.title = "收藏 / 稍后读";
  star.addEventListener("click", function () {
    if (state.fav[item.id]) {
      delete state.fav[item.id];
      star.textContent = "☆";
      star.className = "star";
      li.className = li.className.replace(" is-fav", "");
    } else {
      state.fav[item.id] = true;
      star.textContent = "★";
      star.className = "star is-on";
      if (li.className.indexOf("is-fav") < 0) li.className += " is-fav";
    }
    saveSet(KEY_FAV, state.fav);
    if (state.category === "fav") render();
  });
  li.appendChild(star);

  return li;
}
function render() {
  var feedEl = document.getElementById("feed");
  var emptyEl = document.getElementById("empty");
  var list = visibleItems();

  feedEl.textContent = "";
  for (var i = 0; i < list.length; i++) feedEl.appendChild(buildItem(list[i]));

  emptyEl.hidden = list.length > 0;
  if (list.length === 0) {
    emptyEl.textContent = state.category === "fav" ? "还没有收藏任何内容" : "没有匹配的内容";
  }
}

function updateHeader(feed) {
  document.getElementById("updated").textContent =
    "更新于 " + absoluteTime(feed.generated_at) + " · " + feed.item_count + " 条";

  var noticeEl = document.getElementById("notice");
  var failed = feed.sources_failed || [];
  if (failed.length) {
    noticeEl.hidden = false;
    noticeEl.textContent = "有 " + failed.length + " 个来源本次未取到内容：" +
                           failed.join("、") + "（其余内容不受影响）";
  } else {
    noticeEl.hidden = true;
  }
}

/* ---------------- 数据加载 ---------------- */

function loadFeed() {
  var loadingEl = document.getElementById("loading");
  loadingEl.hidden = false;
  loadingEl.textContent = "正在读取数据…";

  fetch(DATA_URL + "?t=" + Date.now(), { cache: "no-store" })
    .then(function (resp) {
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return resp.json();
    })
    .then(function (feed) {
      state.feed = feed;
      state.items = feed.items || [];

      // 自动清理：已读记录只保留当前列表里还存在的条目，收藏不动
      var alive = {};
      for (var i = 0; i < state.items.length; i++) alive[state.items[i].id] = true;
      var cleaned = {};
      var before = 0;
      for (var id in state.read) {
        before++;
        if (alive[id]) cleaned[id] = true;
      }
      var after = Object.keys(cleaned).length;
      state.read = cleaned;
      if (after !== before) saveSet(KEY_READ, cleaned);

      loadingEl.hidden = true;
      updateHeader(feed);
      render();
    })
    .catch(function (err) {
      loadingEl.textContent = "读取数据失败：" + err.message + "（可点右上角刷新重试）";
    });
}

/* ---------------- 主题 ---------------- */

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem(KEY_THEME, theme); } catch (err) { /* 忽略 */ }
}

function initTheme() {
  var saved = null;
  try { saved = localStorage.getItem(KEY_THEME); } catch (err) { /* 忽略 */ }
  if (!saved) {
    var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    saved = dark ? "dark" : "light";
  }
  applyTheme(saved);
}

/* ---------------- 事件绑定 ---------------- */

function initEvents() {
  document.getElementById("tabs").addEventListener("click", function (ev) {
    var btn = ev.target.closest(".tab");
    if (!btn) return;
    state.category = btn.getAttribute("data-cat");
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) tabs[i].classList.remove("is-active");
    btn.classList.add("is-active");
    render();
  });

  var searchEl = document.getElementById("search");
  var timer = null;
  searchEl.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      state.query = searchEl.value.trim();
      render();
    }, 120);
  });

  document.getElementById("refresh").addEventListener("click", loadFeed);

  document.getElementById("theme").addEventListener("click", function () {
    var now = document.documentElement.getAttribute("data-theme");
    applyTheme(now === "dark" ? "light" : "dark");
  });

  var manualBtn = document.getElementById("manual");
  if (MANUAL_UPDATE_URL) {
    manualBtn.hidden = false;
    manualBtn.addEventListener("click", function () {
      window.open(MANUAL_UPDATE_URL, "_blank", "noopener");
    });
  }

  var settingsEl = document.getElementById("settings");
  document.getElementById("settings-toggle").addEventListener("click", function () {
    settingsEl.hidden = false;
    document.getElementById("storage-info").textContent =
      "当前已读 " + Object.keys(state.read).length + " 条，收藏 " +
      Object.keys(state.fav).length + " 条。";
  });
  document.getElementById("settings-close").addEventListener("click", function () {
    settingsEl.hidden = true;
  });
  settingsEl.addEventListener("click", function (ev) {
    if (ev.target === settingsEl) settingsEl.hidden = true;
  });

  document.getElementById("clear-read").addEventListener("click", function () {
    state.read = {};
    saveSet(KEY_READ, state.read);
    document.getElementById("storage-info").textContent = "已读记录已清空。";
    render();
  });

  document.getElementById("clear-fav").addEventListener("click", function () {
    state.fav = {};
    saveSet(KEY_FAV, state.fav);
    document.getElementById("storage-info").textContent = "收藏已清空。";
    render();
  });
}

function init() {
  initTheme();
  state.read = loadSet(KEY_READ);
  state.fav = loadSet(KEY_FAV);
  initEvents();
  loadFeed();
}

document.addEventListener("DOMContentLoaded", init);