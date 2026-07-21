(function () {
  "use strict";

  var navToggle = document.querySelector(".nav-toggle");
  var nav = document.querySelector(".nav");

  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.matchMedia("(max-width: 768px)").matches) {
          nav.classList.remove("is-open");
          navToggle.setAttribute("aria-expanded", "false");
        }
      });
    });
  }

  document.querySelectorAll(".flash--success").forEach(function (message) {
    setTimeout(function () {
      message.classList.add("is-dismissing");
      setTimeout(function () {
        message.remove();
      }, 250);
    }, 7000);
  });

  var authForm = document.querySelector("[data-auth-form]");
  var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function clearFormErrors(formEl) {
    formEl.querySelectorAll(".field--error").forEach(function (field) {
      field.classList.remove("field--error");
    });
    formEl.querySelectorAll(".field__error").forEach(function (errorEl) {
      errorEl.textContent = "";
    });
  }

  function setFormError(formEl, name, message) {
    var field = formEl.querySelector('[data-field="' + name + '"]');
    if (!field) return;
    field.classList.add("field--error");
    var errorEl = field.querySelector(".field__error");
    if (errorEl) errorEl.textContent = message;
  }

  function getAuthField(formEl, name) {
    return formEl.elements[name] ? formEl.elements[name].value.trim() : "";
  }

  function validateAuthForm(formEl) {
    var mode = formEl.dataset.authForm;
    var ok = true;
    var email = getAuthField(formEl, "email");
    var password = getAuthField(formEl, "password");

    clearFormErrors(formEl);

    if (mode === "signup" && !getAuthField(formEl, "name")) {
      setFormError(formEl, "name", "Enter your full name");
      ok = false;
    }

    if (!emailPattern.test(email)) {
      setFormError(formEl, "email", "Enter a valid email address");
      ok = false;
    }

    if (password.length < 8) {
      setFormError(formEl, "password", "Use at least 8 characters");
      ok = false;
    }

    if (mode === "signup") {
      var confirmPassword = getAuthField(formEl, "confirm_password");
      if (confirmPassword !== password) {
        setFormError(formEl, "confirm_password", "Passwords do not match");
        ok = false;
      }
    }

    return ok;
  }

  if (authForm) {
    authForm.addEventListener("input", function () {
      validateAuthForm(authForm);
    });

    authForm.addEventListener("submit", function (e) {
      if (!validateAuthForm(authForm)) e.preventDefault();
    });
  }

  var form = document.getElementById("estimate-form");
  if (!form) return;

  var submitBtn = form.querySelector('[type="submit"]');
  var resultCard = document.querySelector(".result-card");
  var priceEl = document.querySelector("[data-result-price]");

  function showToast(message) {
    var existing = document.querySelector(".toast");
    if (existing) existing.remove();

    var t = document.createElement("div");
    t.className = "toast toast--success";
    t.setAttribute("role", "status");
    t.textContent = message;
    document.body.appendChild(t);
    requestAnimationFrame(function () {
      t.classList.add("is-visible");
    });
    setTimeout(function () {
      t.classList.remove("is-visible");
      setTimeout(function () {
        t.remove();
      }, 400);
    }, 4200);
  }

  function clearFieldErrors() {
    form.querySelectorAll(".field--error").forEach(function (f) {
      f.classList.remove("field--error");
    });
    form.querySelectorAll(".field__error").forEach(function (e) {
      e.textContent = "";
    });
    form.querySelectorAll("[aria-invalid='true']").forEach(function (input) {
      input.removeAttribute("aria-invalid");
    });
  }

  function clearFieldError(name) {
    var wrap = form.querySelector('[data-field="' + name + '"]');
    if (!wrap) return;
    wrap.classList.remove("field--error");
    var err = wrap.querySelector(".field__error");
    if (err) err.textContent = "";
    var input = wrap.querySelector("input, select");
    if (input) input.removeAttribute("aria-invalid");
  }

  function setFieldError(name, msg) {
    var wrap = form.querySelector('[data-field="' + name + '"]');
    if (!wrap) return;
    wrap.classList.add("field--error");
    var err = wrap.querySelector(".field__error");
    if (err) err.textContent = msg || "Invalid value";
    var input = wrap.querySelector("input, select");
    if (input) input.setAttribute("aria-invalid", "true");
  }

  function formatRuleValue(value) {
    return Number.isInteger(value) ? String(value) : String(value);
  }

  function getDatasetRule(name, fallback) {
    var datasetRules = window.VEHICLE_VALIDATION_RULES || {};
    return Object.assign({}, fallback, datasetRules[name] || {});
  }

  var vehicleNumberRules = {
    km_driven: getDatasetRule("km_driven", {
      label: "Kilometers driven",
      unit: "km",
      min: 0,
      max: 225000,
      average: 69820,
      integer: true,
      required: "Enter kilometers driven.",
    }),
    mileage: getDatasetRule("mileage", {
      label: "Mileage",
      unit: "kmpl",
      min: 11,
      max: 28,
      average: 19,
      required: "Enter mileage in kmpl.",
    }),
    engine: getDatasetRule("engine", {
      label: "Engine size",
      unit: "CC",
      min: 796,
      max: 2967,
      average: 1459,
      required: "Enter engine size in CC.",
    }),
    max_power: getDatasetRule("max_power", {
      label: "Maximum power",
      unit: "bhp",
      min: 37,
      max: 212.9,
      average: 91.2,
      required: "Enter maximum power in bhp.",
    })
  };

  var textRules = {
    brand: "Enter a brand.",
    model: "Enter a model."
  };

  var choiceRules = {
    fuel: ["CNG", "Petrol", "Diesel", "LPG"],
    transmission: ["Manual", "Automatic"],
    seller_type: ["Individual", "Dealer", "Trustmark Dealer"],
    owner: ["First Owner", "Second Owner", "Third Owner", "Fourth & Above Owner"],
    seats: ["4", "6", "7"]
  };

  function validateVehicleNumberField(name, showRequired) {
    var input = form.elements[name];
    var value = input ? input.value.trim() : "";
    var rule = vehicleNumberRules[name];
    if (!rule) return true;

    if (!value) {
      if (showRequired) setFieldError(name, rule.required);
      else clearFieldError(name);
      return !showRequired;
    }

    var number = Number(value);
    if (!Number.isFinite(number)) {
      setFieldError(name, rule.label + " must be a number.");
      return false;
    }

    if (rule.integer && !Number.isInteger(number)) {
      setFieldError(name, rule.label + " must be a whole number.");
      return false;
    }

    if (number < rule.min || number > rule.max) {
      setFieldError(
        name,
        rule.label +
          " should be between " +
          formatRuleValue(rule.min) +
          " and " +
          formatRuleValue(rule.max) +
          " " +
          rule.unit +
          ". Average in the dataset is " +
          formatRuleValue(rule.average) +
          " " +
          rule.unit +
          "."
      );
      return false;
    }

    clearFieldError(name);
    return true;
  }

  function validateTextField(name, showRequired) {
    var input = form.elements[name];
    var value = input ? input.value.trim() : "";
    var catalogLookup = window.vehicleCatalogLookup;
    if (!value) {
      if (showRequired) setFieldError(name, textRules[name]);
      else clearFieldError(name);
      return !showRequired;
    }

    if (catalogLookup && catalogLookup.isReady && catalogLookup.isReady()) {
      if (name === "brand" && !catalogLookup.isValidBrand(value)) {
        setFieldError("brand", "Select a brand from the suggestions.");
        return false;
      }

      if (name === "model") {
        var brand = form.elements.brand ? form.elements.brand.value.trim() : "";
        if (brand && catalogLookup.isValidBrand(brand) && !catalogLookup.isValidModelForBrand(brand, value)) {
          setFieldError("model", "Select a valid model for the selected brand.");
          return false;
        }
      }
    }

    clearFieldError(name);
    return true;
  }

  function validateYearField(showRequired) {
    var input = form.elements.year;
    var value = input ? input.value.trim() : "";
    if (!value) {
      if (showRequired) setFieldError("year", "Enter a manufacturing year.");
      else clearFieldError("year");
      return !showRequired;
    }

    var year = Number(value);
    if (!Number.isInteger(year) || year < 1980 || year > 2030) {
      setFieldError("year", "Use a year between 1980 and 2030.");
      return false;
    }

    clearFieldError("year");
    return true;
  }

  function validateChoiceField(name) {
    var input = form.elements[name];
    var value = input ? input.value : "";
    if (choiceRules[name].indexOf(value) === -1) {
      setFieldError(name, "Choose a valid option.");
      return false;
    }

    clearFieldError(name);
    return true;
  }

  function validate() {
    clearFieldErrors();
    var ok = true;

    Object.keys(textRules).forEach(function (name) {
      if (!validateTextField(name, true)) ok = false;
    });
    if (!validateYearField(true)) ok = false;
    Object.keys(vehicleNumberRules).forEach(function (name) {
      if (!validateVehicleNumberField(name, true)) ok = false;
    });
    Object.keys(choiceRules).forEach(function (name) {
      if (!validateChoiceField(name)) ok = false;
    });

    return ok;
  }

  Object.keys(textRules).forEach(function (name) {
    var input = form.elements[name];
    if (!input) return;
    input.addEventListener("input", function () {
      validateTextField(name, false);
    });
    input.addEventListener("blur", function () {
      validateTextField(name, true);
    });
  });

  window.addEventListener("vehiclecatalogready", function () {
    Object.keys(textRules).forEach(function (name) {
      validateTextField(name, false);
    });
  });

  if (form.elements.year) {
    form.elements.year.addEventListener("input", function () {
      validateYearField(false);
    });
    form.elements.year.addEventListener("blur", function () {
      validateYearField(true);
    });
  }

  Object.keys(vehicleNumberRules).forEach(function (name) {
    var input = form.elements[name];
    if (!input) return;
    input.addEventListener("input", function () {
      validateVehicleNumberField(name, false);
    });
    input.addEventListener("blur", function () {
      validateVehicleNumberField(name, true);
    });
  });

  Object.keys(choiceRules).forEach(function (name) {
    var group = form.querySelector('[data-choice-group="' + name + '"]');
    if (!group) return;
    group.querySelectorAll('input[type="checkbox"]').forEach(function (choice) {
      choice.addEventListener("change", function () {
        validateChoiceField(name);
      });
    });
  });

  form.addEventListener("submit", function (e) {
    if (!validate()) {
      e.preventDefault();
      showToast("Please fix the highlighted fields.");
      return;
    }

    if (submitBtn) submitBtn.disabled = true;
    if (resultCard) {
      resultCard.classList.add("is-loading");
      if (priceEl) {
        priceEl.innerHTML = '<span class="spinner" aria-hidden="true"></span>';
      }
    }
  });
})();
