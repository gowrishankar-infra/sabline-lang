/* The documentation site's one script. build_docs.py copies it into every
   built tree as assets/site.js. It sets the theme before the page paints,
   then adds the light/dark toggle, the menu under 960px, a copy button on
   each code block, and search over this tree's search-index.json - the one
   file it requests. No framework, no third party, nothing sent anywhere. */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "sabline-docs-theme";
  root.classList.add("js");

  function stored() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (e) {
      return null;                       // storage refused: follow the system
    }
  }

  function remember(value) {
    try {
      window.localStorage.setItem(KEY, value);
    } catch (e) {
      // storage refused: the choice holds for this page only
    }
  }

  var choice = stored();
  if (choice === "light" || choice === "dark") {
    root.setAttribute("data-theme", choice);
  }

  var script = document.currentScript;
  var treeRoot = new URL("../", script && script.src ? script.src : window.location.href);
  var system = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function isDark() {
    var set = root.getAttribute("data-theme");
    return set ? set === "dark" : !!(system && system.matches);
  }

  function say(text) {
    var live = document.getElementById("live");
    if (live) {
      live.textContent = "";
      window.setTimeout(function () { live.textContent = text; }, 50);
    }
  }

  function theme() {
    var button = document.querySelector(".theme");
    if (!button) return;
    function show() {
      button.setAttribute("aria-pressed", isDark() ? "true" : "false");
    }
    show();
    button.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      remember(next);
      show();
    });
    if (system && system.addEventListener) system.addEventListener("change", show);
  }

  function menu() {
    var button = document.querySelector(".menu");
    var nav = document.getElementById("sidebar");
    if (!button || !nav) return;
    function set(open) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
      root.classList.toggle("nav-open", open);
    }
    button.addEventListener("click", function () {
      set(button.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
        set(false);
        button.focus();
      }
    });
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.className = "vh";
      document.body.appendChild(area);
      area.select();
      var done = false;
      try {
        done = document.execCommand("copy");
      } catch (e) {
        done = false;
      }
      document.body.removeChild(area);
      if (done) resolve(); else reject(new Error("the browser refused to copy"));
    });
  }

  function copyButtons() {
    Array.prototype.forEach.call(document.querySelectorAll(".code"), function (block) {
      var bar = block.querySelector(".code-bar");
      var pre = block.querySelector("pre");
      if (!bar || !pre) return;
      var label = bar.querySelector(".code-lang");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "Copy";
      button.setAttribute("aria-label", "Copy the " + (label ? label.textContent : "") + " code");
      button.addEventListener("click", function () {
        copyText(pre.textContent || "").then(function () {
          button.textContent = "Copied";
          say("Copied to the clipboard");
          window.setTimeout(function () { button.textContent = "Copy"; }, 2000);
        }, function () {
          say("The browser refused to copy; select the code and copy it");
        });
      });
      bar.appendChild(button);
    });
  }

  function search() {
    var box = document.querySelector(".search");
    var input = document.getElementById("search");
    var panel = document.getElementById("search-results");
    if (!box || !input || !panel) return;
    var index = null;
    var loading = null;
    var timer = 0;
    var MOST = 40;

    function load() {
      if (!loading) {
        loading = fetch(new URL("search-index.json", treeRoot).href).then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        }).then(function (data) {
          var titles = {};
          var entries = data.entries.map(function (e) {
            if (e[2] === 1) titles[e[0] + "#" + e[1]] = e[3];
            return { page: e[0], anchor: e[1], heading: e[2] === 1, text: e[3], lower: e[3].toLowerCase() };
          });
          index = { pages: data.pages, entries: entries, titles: titles };
          return index;
        });
        loading.catch(function () { loading = null; });
      }
      return loading;
    }

    function close() {
      panel.hidden = true;
    }

    function find(query) {
      var terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      var phrase = terms.join(" ");
      var hits = [];
      index.entries.forEach(function (e) {
        for (var i = 0; i < terms.length; i++) {
          if (e.lower.indexOf(terms[i]) < 0) return;
        }
        var score = e.heading ? 50 : 0;
        var at = e.lower.indexOf(phrase);
        if (e.heading && e.lower === phrase) score += 40;
        if (at === 0) score += 30; else if (at > 0) score += 10;
        score -= Math.min(20, e.text.length / 200);
        hits.push({ entry: e, score: score });
      });
      hits.sort(function (a, b) { return b.score - a.score; });
      return { terms: terms, hits: hits.slice(0, MOST), total: hits.length };
    }

    function snippet(node, text, terms) {
      var lower = text.toLowerCase();
      var at = lower.indexOf(terms[0]);
      var start = Math.max(0, at - 60);
      var end = Math.min(text.length, Math.max(at, 0) + 120);
      var part = (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
      var partLower = part.toLowerCase();
      var pos = 0;
      while (pos < part.length) {
        var next = -1;
        var length = 0;
        terms.forEach(function (term) {
          var found = partLower.indexOf(term, pos);
          if (found >= 0 && (next < 0 || found < next)) {
            next = found;
            length = term.length;
          }
        });
        if (next < 0) {
          node.appendChild(document.createTextNode(part.slice(pos)));
          break;
        }
        node.appendChild(document.createTextNode(part.slice(pos, next)));
        var mark = document.createElement("mark");
        mark.textContent = part.slice(next, next + length);
        node.appendChild(mark);
        pos = next + length;
      }
    }

    function show(query) {
      var found = find(query);
      panel.textContent = "";
      var count = document.createElement("p");
      count.className = "results-count";
      count.textContent = found.total === 0 ? "No results for " + query
        : found.total > MOST ? "The first " + MOST + " of " + found.total + " results"
        : found.total + (found.total === 1 ? " result" : " results");
      panel.appendChild(count);
      if (found.hits.length) {
        var list = document.createElement("ul");
        found.hits.forEach(function (hit) {
          var e = hit.entry;
          var page = index.pages[e.page];
          var link = document.createElement("a");
          link.href = new URL(page[0] + (e.anchor ? "#" + e.anchor : ""), treeRoot).href;
          var where = document.createElement("span");
          where.className = "r-where";
          var section = e.heading ? e.text : index.titles[e.page + "#" + e.anchor];
          where.textContent = page[1] + (section && section !== page[1] ? " › " + section : "");
          link.appendChild(where);
          if (!e.heading) {
            var text = document.createElement("span");
            text.className = "r-text";
            snippet(text, e.text, found.terms);
            link.appendChild(text);
          }
          var item = document.createElement("li");
          item.appendChild(link);
          list.appendChild(item);
        });
        panel.appendChild(list);
      }
      panel.hidden = false;
      say(count.textContent);
    }

    function failed() {
      panel.textContent = "";
      var note = document.createElement("p");
      note.className = "results-count";
      note.textContent = "The search index could not be loaded.";
      panel.appendChild(note);
      panel.hidden = false;
    }

    input.addEventListener("focus", function () { load(); });
    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        var query = input.value.trim();
        if (!query) {
          close();
          return;
        }
        load().then(function () {
          if (input.value.trim() === query) show(query);
        }, failed);
      }, 120);
    });
    input.addEventListener("keydown", function (event) {
      var links = panel.querySelectorAll("a");
      if (event.key === "ArrowDown" && !panel.hidden && links.length) {
        event.preventDefault();
        links[0].focus();
      } else if (event.key === "Enter" && !panel.hidden && links.length) {
        event.preventDefault();
        window.location.href = links[0].href;
      } else if (event.key === "Escape" && !panel.hidden) {
        event.preventDefault();
        close();
      }
    });
    panel.addEventListener("keydown", function (event) {
      var links = Array.prototype.slice.call(panel.querySelectorAll("a"));
      var at = links.indexOf(document.activeElement);
      if (at < 0) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        (links[at + 1] || links[at]).focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (at === 0) input.focus(); else links[at - 1].focus();
      } else if (event.key === "Escape") {
        event.preventDefault();
        close();
        input.focus();
      }
    });
    box.addEventListener("focusout", function (event) {
      if (!event.relatedTarget || !box.contains(event.relatedTarget)) close();
    });
  }

  function ready() {
    theme();
    menu();
    copyButtons();
    search();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
