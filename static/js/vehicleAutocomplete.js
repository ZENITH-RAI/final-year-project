(function () {
  "use strict";

  var CATALOG_URL =
    window.VEHICLE_CATALOG_URL || "/static/data/vehicle_catalog.json";
  var DATASET_CATALOG_URL =
    window.VEHICLE_DATASET_CATALOG_URL || "/api/vehicle-catalog";
  var MAX_SUGGESTIONS = 35;

  var datasetCatalog = null;
  var fallbackCatalog = null;
  var catalogError = null;

  function normalize(s) {
    return String(s || "")
      .toLowerCase()
      .trim()
      .replace(/\s+/g, " ");
  }

  function scoreMatch(text, query) {
    var t = normalize(text);
    var q = normalize(query);
    if (!q) return 1;
    if (t === q) return 100;
    if (t.startsWith(q)) return 85;
    var words = t.split(" ");
    for (var i = 0; i < words.length; i++) {
      if (words[i].startsWith(q)) return 72;
    }
    if (t.indexOf(q) !== -1) return 55;
    var qi = 0;
    for (var j = 0; j < t.length && qi < q.length; j++) {
      if (t[j] === q[qi]) qi++;
    }
    if (qi === q.length) return 35;
    return 0;
  }

  function filterAndSort(items, query) {
    var scored = [];
    for (var i = 0; i < items.length; i++) {
      var s = scoreMatch(items[i], query);
      if (s > 0) scored.push({ value: items[i], score: s });
    }
    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.value.localeCompare(b.value);
    });
    return scored.map(function (x) {
      return x.value;
    });
  }

  function filterPrefix(items, query) {
    var q = normalize(query);
    if (!q) return items.slice();
    return items
      .filter(function (item) {
        return normalize(item).startsWith(q);
      })
      .sort(function (a, b) {
        return a.localeCompare(b);
      });
  }

  function uniqueByNormalized(primary, fallback) {
    var seen = {};
    var merged = [];
    [primary || [], fallback || []].forEach(function (items) {
      items.forEach(function (item) {
        var key = normalize(item);
        if (!key || seen[key]) return;
        seen[key] = true;
        merged.push(item);
      });
    });
    return merged;
  }

  function findBrandKey(catalogData, brand) {
    if (!catalogData || !catalogData.brands) return "";
    var target = normalize(brand);
    for (var i = 0; i < catalogData.brands.length; i++) {
      if (normalize(catalogData.brands[i]) === target) {
        return catalogData.brands[i];
      }
    }
    return "";
  }

  function loadJson(url, errorMessage) {
    return fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error(errorMessage);
        return r.json();
      })
      .catch(function (e) {
        catalogError = e.message || "Load failed";
        return null;
      });
  }

  function loadCatalogs() {
    return Promise.all([
      loadJson(DATASET_CATALOG_URL, "Could not load dataset vehicle list"),
      loadJson(CATALOG_URL, "Could not load fallback vehicle catalog"),
    ]).then(function (results) {
      datasetCatalog = results[0];
      fallbackCatalog = results[1];
      if (!datasetCatalog && !fallbackCatalog) {
        throw new Error(catalogError || "Could not load vehicle suggestions");
      }
      catalogError = null;
      return {
        dataset: datasetCatalog,
        fallback: fallbackCatalog,
      };
    });
  }

  function getBrandList(catalogData) {
    if (!catalogData || !catalogData.brands) return [];
    return catalogData.brands;
  }

  function getModelsFromCatalog(catalogData, brand) {
    if (!catalogData || !catalogData.modelsByBrand) return [];
    var key = findBrandKey(catalogData, brand);
    if (!key) return [];
    var list = catalogData.modelsByBrand[key];
    return Array.isArray(list) ? list : [];
  }

  function getBrandSuggestions(query) {
    var datasetMatches = filterPrefix(getBrandList(datasetCatalog), query);
    if (normalize(query) && datasetMatches.length > 0) return datasetMatches;

    var fallbackMatches = filterPrefix(getBrandList(fallbackCatalog), query);
    if (normalize(query) && datasetMatches.length === 0) return fallbackMatches;
    return uniqueByNormalized(datasetMatches, fallbackMatches);
  }

  function getModelsForBrand(brand, query) {
    var datasetModels = getModelsFromCatalog(datasetCatalog, brand);
    var fallbackModels = getModelsFromCatalog(fallbackCatalog, brand);

    if (!normalize(query)) {
      return uniqueByNormalized(datasetModels, fallbackModels);
    }

    var datasetMatches = filterAndSort(datasetModels, query);
    if (datasetMatches.length > 0) return datasetMatches;
    return filterAndSort(fallbackModels, query);
  }

  function findExactItem(items, value) {
    var target = normalize(value);
    for (var i = 0; i < items.length; i++) {
      if (normalize(items[i]) === target) return items[i];
    }
    return "";
  }

  window.vehicleCatalogLookup = {
    isReady: function () {
      return Boolean(datasetCatalog || fallbackCatalog);
    },
    isValidBrand: function (brand) {
      return Boolean(
        findBrandKey(datasetCatalog, brand) || findBrandKey(fallbackCatalog, brand),
      );
    },
    isValidModelForBrand: function (brand, model) {
      if (!brand || !model) return false;
      return Boolean(findExactItem(getModelsForBrand(brand, ""), model));
    },
  };

  function attachCombo(options) {
    var input = options.input;
    var listEl = options.listEl;
    var getItems = options.getItems;
    var container = input.closest(".combo");
    if (!input || !listEl) return;

    var activeIndex = -1;

    function setOpen(open) {
      listEl.hidden = !open;
      input.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function renderItems(items) {
      listEl.innerHTML = "";
      activeIndex = -1;
      if (items === null) {
        var hint = document.createElement("li");
        hint.className = "combo__empty";
        hint.setAttribute("role", "presentation");
        hint.textContent = "Choose a brand first";
        listEl.appendChild(hint);
        return;
      }
      var slice = items.slice(0, MAX_SUGGESTIONS);
      for (var i = 0; i < slice.length; i++) {
        var li = document.createElement("li");
        li.setAttribute("role", "option");
        li.id = input.id + "-opt-" + i;
        li.textContent = slice[i];
        li.dataset.value = slice[i];
        listEl.appendChild(li);
      }
      if (slice.length === 0) {
        var empty = document.createElement("li");
        empty.className = "combo__empty";
        empty.setAttribute("role", "presentation");
        empty.textContent = "No matches";
        listEl.appendChild(empty);
      }
    }

    function refresh() {
      var q = input.value;
      var items = getItems(q);
      renderItems(items);
    }

    input.addEventListener("input", function () {
      refresh();
      setOpen(true);
    });

    input.addEventListener("focus", function () {
      refresh();
      setOpen(true);
    });

    listEl.addEventListener("click", function (e) {
      var li = e.target.closest("li[role='option']");
      if (!li || !li.dataset.value) return;
      input.value = li.dataset.value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      setOpen(false);
      input.focus();
    });

    input.addEventListener("keydown", function (e) {
      var opts = listEl.querySelectorAll("li[role='option']");
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (listEl.hidden) {
          refresh();
          setOpen(true);
        }
        activeIndex = Math.min(activeIndex + 1, opts.length - 1);
        highlight(opts);
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        highlight(opts);
      }
      if (
        e.key === "Enter" &&
        !listEl.hidden &&
        activeIndex >= 0 &&
        opts[activeIndex]
      ) {
        e.preventDefault();
        opts[activeIndex].click();
      }
    });

    function highlight(opts) {
      for (var i = 0; i < opts.length; i++) {
        opts[i].classList.toggle("combo__option--active", i === activeIndex);
        if (i === activeIndex) opts[i].scrollIntoView({ block: "nearest" });
      }
    }

    document.addEventListener("click", function (e) {
      if (container && !container.contains(e.target)) setOpen(false);
    });

    return { refresh: refresh, setOpen: setOpen };
  }

  function setStatus(el, msg, isError) {
    if (!el) return;
    el.textContent = msg || "";
    el.style.color = isError ? "var(--error)" : "var(--text-muted)";
  }

  function init() {
    var brandInput = document.getElementById("brand");
    var modelInput = document.getElementById("model");
    var brandList = document.getElementById("brand-listbox");
    var modelList = document.getElementById("model-listbox");
    var catalogStatus = document.getElementById("catalog-status");

    if (!brandInput || !modelInput || !brandList || !modelList) return;

    brandInput.setAttribute("autocomplete", "off");
    modelInput.setAttribute("autocomplete", "off");

    var lastBrand = "";

    var brandCombo = attachCombo({
      input: brandInput,
      listEl: brandList,
      getItems: function (q) {
        return getBrandSuggestions(q);
      },
    });

    var modelCombo = attachCombo({
      input: modelInput,
      listEl: modelList,
      getItems: function (q) {
        var b = brandInput.value.trim();
        if (!b) return null;
        return getModelsForBrand(b, q);
      },
    });

    function syncModelAfterBrandChange() {
      var b = brandInput.value.trim();
      if (b === lastBrand) return;
      lastBrand = b;
      var models = getModelsForBrand(b, "");
      var mv = modelInput.value.trim();
      if (mv && models.indexOf(mv) === -1) {
        modelInput.value = "";
      }
      modelCombo.refresh();
    }

    brandInput.addEventListener("change", syncModelAfterBrandChange);
    brandInput.addEventListener("blur", function () {
      window.setTimeout(syncModelAfterBrandChange, 120);
    });

    loadCatalogs()
      .then(function () {
        var totalBrands = uniqueByNormalized(
          getBrandList(datasetCatalog),
          getBrandList(fallbackCatalog),
        ).length;
        setStatus(
          catalogStatus,
          "Vehicle list ready — dataset first, catalog fallback. " + totalBrands + " brands available.",
          false,
        );
        lastBrand = brandInput.value.trim();
        brandCombo.refresh();
        modelCombo.refresh();
        window.dispatchEvent(new Event("vehiclecatalogready"));
      })
      .catch(function () {
        setStatus(
          catalogStatus,
          "Could not load suggestions. Run the Flask app from the project folder, or rebuild static/data/vehicle_catalog.json.",
          true,
        );
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
