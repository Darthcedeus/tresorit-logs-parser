"use strict";
// Country-level analysis uses recorded export locations and a local public map.
window.LocationAnalysis = (() => {
  const unknown = "__unknown";
  const missing = value => ["", "n/a", "na", "-"].includes(String(value || "").trim().toLowerCase());
  const yes = value => ["yes", "enabled", "true"].includes((value || "").toLowerCase());
  const $ = id => document.getElementById(id);
  const element = (tag, text, className) => {
    const result = document.createElement(tag);
    if (text !== undefined) result.textContent = text;
    if (className) result.className = className;
    return result;
  };
  const svgElement = tag => document.createElementNS("http://www.w3.org/2000/svg", tag);
  let mapPromise;

  function create(onChange, onSourceChange) {
    let report, source, map, svg, paths = [], zoom = 1, offsetX = 0, offsetY = 0, drag;
    let lastBase = [], lastCurrent = [], mapError = false;
    const countries = new Map();
    const names = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames(["en"], {type: "region"}) : null;
    const countryName = code => {
      if (code === unknown) return "Unknown country";
      const name = countries.get(code)?.name || names?.of(code);
      return !name || name === code || name === "Unknown Region" ? `Unmapped country (${code})` : name;
    };
    const location = row => row.locations?.[source?.key] || {country: "", city: ""};
    const selectedCountry = () => $("location-country").value;
    const selectedCity = () => $("location-city").value;

    function matches(row) {
      if (!source) return true;
      const geo = location(row);
      return (!selectedCountry() || (geo.country || unknown) === selectedCountry()) &&
        (!selectedCity() || (geo.city || unknown) === selectedCity());
    }

    function reset() { $("location-country").value = ""; $("location-city").value = ""; }
    function setReport(next) {
      report = next;
      const sources = report.location_sources || [];
      source = sources[0];
      $("location-source").replaceChildren(...sources.map(item => new Option(item.label, item.key)));
      $("location-country").replaceChildren(new Option("All countries", ""));
      $("location-city").replaceChildren(new Option("All cities", ""));
      const measures = [["Records", "records"], ["Rows with review notes", "review"]];
      if (report.kind === "link_activity") measures.splice(1, 0, ["Failed events", "failed"], ["External events", "external"]);
      $("location-measure").replaceChildren(...measures.map(([label, value]) => new Option(label, value)));
      $("location-content").hidden = !source;
      $("location-unavailable").hidden = !!source;
      $("location-description").textContent = !source ? "Locations are available in activity and device exports." :
        report.kind === "link_activity" ? "Recorded country and city for each link event." :
          "One location per device snapshot. Choose latest activity, creation or revocation; these are not historical event counts.";
      if (source) loadMap();
    }

    function options(select, values, label, name) {
      const selected = select.value;
      select.replaceChildren(new Option(label, ""));
      [...values].sort((a, b) => name(a).localeCompare(name(b))).forEach(value => select.add(new Option(name(value), value)));
      if (selected && !values.has(selected)) select.add(new Option(`${name(selected)} (no matches)`, selected));
      select.value = selected;
    }

    function aggregate(rows) {
      const totals = new Map();
      for (const row of rows) {
        const code = location(row).country || unknown;
        if (!totals.has(code)) totals.set(code, {records: 0, failed: 0, external: 0, review: 0, ips: new Set()});
        const entry = totals.get(code);
        entry.records++;
        entry.failed += (row.cells.Event || "").toLowerCase().includes("fail") ? 1 : 0;
        entry.external += yes(row.cells.IsExternal) ? 1 : 0;
        entry.review += row.notes.length ? 1 : 0;
        const ip = row.cells[source.ip];
        if (!missing(ip)) entry.ips.add(ip.trim());
      }
      return totals;
    }

    function focusCountry(code) {
      $("location-country").value = selectedCountry() === code ? "" : code;
      $("location-city").value = "";
      onChange();
    }

    function render(baseRows, currentRows) {
      lastBase = baseRows; lastCurrent = currentRows;
      if (!source) return;
      const totals = aggregate(baseRows), measure = $("location-measure").value;
      options($("location-country"), new Set(totals.keys()), "All countries", countryName);
      const cityRows = baseRows.filter(row => !selectedCountry() || (location(row).country || unknown) === selectedCountry());
      options($("location-city"), new Set(cityRows.map(row => location(row).city || unknown)), "All cities", value => value === unknown ? "Unknown city" : value);
      const current = aggregate(currentRows);
      const countryCount = [...current.keys()].filter(code => code !== unknown).length;
      const noCountry = current.get(unknown)?.records || 0;
      const ips = new Set(currentRows.map(row => row.cells[source.ip]).filter(value => !missing(value)).map(value => value.trim()));
      $("location-summary").textContent = `${currentRows.length.toLocaleString()} selected ${report.kind === "device_status" ? "device snapshots" : "events"} · ${countryCount} recorded country codes · ${ips.size} unique recorded IPs · ${noCountry} without a country`;
      const ranking = $("location-countries"); ranking.replaceChildren();
      const sorted = [...totals].sort((a, b) => b[1][measure] - a[1][measure] || b[1].records - a[1].records);
      for (const [code, entry] of sorted) {
        const button = element("button", undefined, "country-row"); button.type = "button";
        button.setAttribute("aria-pressed", String(selectedCountry() === code));
        const text = element("span", countryName(code));
        const detail = element("small", `${entry.records.toLocaleString()} records · ${entry.ips.size} IPs`);
        text.append(detail);
        button.append(text, element("strong", entry[measure].toLocaleString()));
        button.addEventListener("click", () => focusCountry(code)); ranking.append(button);
      }
      if (!totals.size) ranking.append(element("p", "No locations match these filters.", "hint"));
      const cities = new Map();
      for (const row of currentRows) {
        const geo = location(row), key = JSON.stringify([geo.country || unknown, geo.city || unknown]);
        if (!cities.has(key)) cities.set(key, {country: geo.country || unknown, city: geo.city || unknown, count: 0, ips: new Set()});
        const entry = cities.get(key); entry.count++;
        if (!missing(row.cells[source.ip])) entry.ips.add(row.cells[source.ip].trim());
      }
      const breakdown = $("location-city-breakdown"); breakdown.replaceChildren();
      for (const entry of [...cities.values()].sort((a, b) => b.count - a.count).slice(0, 12)) {
        const button = element("button", undefined, "city-card"); button.type = "button";
        button.append(element("strong", entry.city === unknown ? "Unknown city" : entry.city),
          element("span", countryName(entry.country)), element("small", `${entry.count} records · ${entry.ips.size} IPs`));
        button.addEventListener("click", () => {
          $("location-country").value = entry.country;
          // Populate city choices for the new country before selecting the city.
          options($("location-city"), new Set(baseRows.filter(row => (location(row).country || unknown) === entry.country).map(row => location(row).city || unknown)), "All cities", value => value === unknown ? "Unknown city" : value);
          $("location-city").value = entry.city; onChange();
        });
        breakdown.append(button);
      }
      if (!cities.size) breakdown.append(element("p", "No matching cities. Reset filters to see more locations.", "hint"));
      if (cities.size > 12) breakdown.append(element("p", `Top 12 of ${cities.size} city/country groups. Use the city filter for the full list.`, "hint"));
      const visibleTotals = [...totals].filter(([code]) => !map || countries.has(code));
      const maximum = Math.max(0, ...visibleTotals.map(([, entry]) => entry[measure]));
      $("map-maximum").textContent = `${maximum} ${$("location-measure").selectedOptions[0].textContent.toLowerCase()}`;
      for (const {shape, code, title, marker} of paths) {
        const entry = totals.get(code), value = entry?.[measure] || 0;
        shape.style.setProperty("--map-intensity", String(value ? 0.28 + 0.72 * Math.sqrt(value / maximum) : 0));
        shape.classList.toggle("has-records", !!entry);
        shape.classList.toggle("is-selected", selectedCountry() === code);
        shape.setAttribute("tabindex", entry ? "0" : "-1");
        shape.setAttribute("aria-pressed", String(selectedCountry() === code));
        shape.setAttribute("aria-disabled", String(!entry));
        const label = `${countryName(code)}: ${value} ${$("location-measure").selectedOptions[0].textContent.toLowerCase()}, ${entry?.records || 0} total records`;
        shape.setAttribute("aria-label", label); title.textContent = label;
        marker.setAttribute("aria-label", label);
        marker.hidden = !entry;
        marker.style.display = entry ? "" : "none";
        marker.classList.toggle("is-selected", selectedCountry() === code);
      }
      if (map) {
        const unmapped = [...totals].filter(([code]) => code !== unknown && !countries.has(code)).reduce((n, [, entry]) => n + entry.records, 0);
        $("map-status").textContent = unmapped ? `${unmapped} ${unmapped === 1 ? "record has" : "records have"} no matching country outline` : `${totals.size - (totals.has(unknown) ? 1 : 0)} countries in view`;
      } else if (mapError) $("map-status").textContent = "Map unavailable. Country and city analysis still works.";
    }

    function updateView() {
      if (!svg) return;
      const width = 1000 / zoom, height = 500 / zoom;
      offsetX = Math.max(0, Math.min(1000 - width, offsetX));
      offsetY = Math.max(0, Math.min(500 - height, offsetY));
      svg.setAttribute("viewBox", `${offsetX} ${offsetY} ${width} ${height}`);
      $("map-zoom-out").disabled = zoom <= 1;
      $("map-zoom-in").disabled = zoom >= 8;
    }
    function scale(factor) {
      const previous = zoom; zoom = Math.max(1, Math.min(8, zoom * factor));
      offsetX += 500 / previous - 500 / zoom; offsetY += 250 / previous - 250 / zoom; updateView();
    }

    async function loadMap() {
      if (svg || mapError) return;
      try {
        mapPromise ||= fetch(document.querySelector(".location-panel").dataset.mapUrl).then(response => {
          if (!response.ok) throw new Error("Map asset unavailable");
          return response.json();
        });
        map = await mapPromise;
        if (svg) return;
        svg = svgElement("svg"); svg.setAttribute("viewBox", "0 0 1000 500");
        svg.setAttribute("role", "group"); svg.setAttribute("aria-label", "Country activity. Highlighted countries filter records.");
        const title = svgElement("title"); title.textContent = "Country-level activity from recorded locations"; svg.append(title);
        const markers = svgElement("g");
        for (const country of map.countries) {
          countries.set(country.code, country);
          const shape = svgElement("path"), tip = svgElement("title");
          shape.setAttribute("d", country.path); shape.setAttribute("fill-rule", "evenodd");
          shape.setAttribute("role", "button"); shape.dataset.country = country.code; shape.append(tip);
          const activate = () => { if (aggregate(lastBase).has(country.code)) focusCountry(country.code); };
          shape.addEventListener("click", () => { if (!drag?.moved) activate(); });
          shape.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); } });
          svg.append(shape);
          const marker = svgElement("circle"); marker.setAttribute("cx", country.x); marker.setAttribute("cy", country.y); marker.setAttribute("r", "4");
          marker.setAttribute("class", "country-marker"); marker.dataset.country = country.code;
          marker.setAttribute("role", "button"); marker.setAttribute("tabindex", "-1");
          const markerTitle = svgElement("title"); markerTitle.textContent = country.name; marker.append(markerTitle);
          marker.addEventListener("click", () => { if (!drag?.moved) activate(); });
          markers.append(marker);
          paths.push({shape, code: country.code, title: tip, marker});
        }
        svg.append(markers); $("world-map").replaceChildren(svg);
        svg.addEventListener("pointerdown", event => {
          drag = {x: event.clientX, y: event.clientY, offsetX, offsetY, moved: false};
          // Capture only when panning so ordinary country clicks keep their target.
        });
        svg.addEventListener("pointermove", event => {
          if (!drag || !(event.buttons & 1) || zoom === 1) return;
          const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
          if (Math.abs(dx) + Math.abs(dy) > 5) { drag.moved = true; svg.setPointerCapture(event.pointerId); }
          const box = svg.getBoundingClientRect();
          offsetX = drag.offsetX - dx * 1000 / box.width / zoom;
          offsetY = drag.offsetY - dy * 500 / box.height / zoom; updateView();
        });
        svg.addEventListener("pointerup", () => { setTimeout(() => { drag = undefined; }, 0); });
        svg.addEventListener("pointercancel", () => { drag = undefined; });
        updateView(); render(lastBase, lastCurrent);
      } catch { mapError = true; render(lastBase, lastCurrent); }
    }

    $("location-source").addEventListener("change", () => {
      source = report.location_sources.find(item => item.key === $("location-source").value);
      reset(); onSourceChange(source.date);
    });
    $("location-country").addEventListener("change", () => { $("location-city").value = ""; onChange(); });
    $("location-city").addEventListener("change", onChange);
    $("location-measure").addEventListener("change", () => render(lastBase, lastCurrent));
    $("map-zoom-in").addEventListener("click", () => scale(2));
    $("map-zoom-out").addEventListener("click", () => scale(0.5));
    $("map-reset").addEventListener("click", () => { zoom = 1; offsetX = offsetY = 0; updateView(); });
    return {setReport, matches, render, reset};
  }
  return {create};
})();
