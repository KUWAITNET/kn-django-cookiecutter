{%- raw -%}
/*
 * Live recipient count on the newsletter composer.
 *
 * Wired entirely through data attributes: the CSP has no 'unsafe-inline' for
 * scripts, so an onchange attribute would silently do nothing.
 */
(function () {
  function init() {
    var select = document.querySelector("[data-newsletter-audience]");
    var output = document.querySelector("[data-newsletter-count]");
    if (!select || !output) {
      return;
    }
    var source = document.getElementById(output.dataset.countsId);
    if (!source) {
      return;
    }

    var counts;
    try {
      counts = JSON.parse(source.textContent);
    } catch (error) {
      return;
    }

    function update() {
      var value = counts[select.value];
      output.textContent = value === undefined ? "0" : String(value);
    }

    select.addEventListener("change", update);
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
{%- endraw %}
