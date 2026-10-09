"use strict";
(() => {
  const data = JSON.parse(document.getElementById("dashboard-data").textContent);
  if (!data.reports.length) return;
  const order = ["shared_links", "link_activity", "folder_summary", "folder_members", "external_users", "device_status"];
  const reports = data.reports.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
  const $ = id => document.getElementById(id);
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const isYes = value => ["yes", "enabled", "true"].includes((value || "").toLowerCase());
  const count = (rows, predicate) => rows.filter(predicate).length;
  const sum = (rows, col) => rows.reduce((total, row) => total + (row.numbers[col] || 0), 0);
  const bytes = value => {
    const units = ["B", "KiB", "MiB", "GiB", "TiB"];
    let i = 0;
    while (value >= 1024 && i < units.length - 1) { value /= 1024; i++; }
    return `${value.toLocaleString(undefined, {maximumFractionDigits: i ? 1 : 0})} ${units[i]}`;
  };
  let selected = reports[0], page = 1, sortColumn = "", direction = 1, currentRows = [];
  let renderTimer;
  const geography = window.LocationAnalysis.create(
    () => { page = 1; render(); },
    dateColumn => { if (selected.date_columns.includes(dateColumn)) $("date-field").value = dateColumn; page = 1; render(); }
  );

  function matches(row, report, local = true, locationFilter = true) {
    const query = $("search").value.trim().toLowerCase();
    if (query && !Object.values(row.cells).some(value => String(value).toLowerCase().includes(query))) return false;
    if (!local) return true;
    if ($("status").value && row.cells[report.status_column] !== $("status").value) return false;
    if ($("review-only").checked && !row.notes.length) return false;
    const from = $("from").value, to = $("to").value;
    if (from || to) {
      if (from && to && from > to) return false;
      const date = row.dates[$("date-field").value]?.slice(0, 10);
      if (!date || (from && date < from) || (to && date > to)) return false;
    }
    return !locationFilter || geography.matches(row);
  }

  function tabs() {
    $("tabs").replaceChildren(...reports.map(report => {
      const button = node("button", report.label);
      button.type = "button";
      button.setAttribute("aria-pressed", String(report === selected));
      button.append(node("span", report.rows.filter(row => matches(row, report, false)).length.toLocaleString(), "tab-count"));
      button.addEventListener("click", () => select(report));
      return button;
    }));
  }

  function select(report) {
    selected = report;
    page = 1; sortColumn = ""; direction = 1;
    $("status").replaceChildren(new Option("All values", ""));
    [...new Set(report.rows.map(row => row.cells[report.status_column]).filter(Boolean))].sort().forEach(value => $("status").add(new Option(value, value)));
    $("status").disabled = !report.status_column;
    $("status-label").textContent = report.status_column || "Status (not available)";
    $("date-field").replaceChildren(...report.date_columns.map(col => new Option(col, col)));
    $("group-field").replaceChildren(...report.columns.filter(col => col !== "Review notes" && !report.date_columns.includes(col)).map(col => new Option(col, col)));
    $("group-field").value = report.group_column;
    if (report.date_column) $("date-field").value = report.date_column;
    for (const id of ["date-field", "from", "to"]) $(id).disabled = !report.date_columns.length;
    $("from").value = ""; $("to").value = ""; $("review-only").checked = false;
    $("report-title").textContent = report.label;
    $("report-source").textContent = report.filename;
    $("warnings").replaceChildren(...report.warnings.map(text => node("p", text, "warning")));
    geography.setReport(report);
    render();
    const scroll = $("records").closest(".table-scroll");
    scroll.scrollLeft = 0;
    scroll.scrollTop = 0;
  }

  function metrics(rows) {
    const reviewed = count(rows, row => row.notes.length > 0);
    let items = [["Matching records", rows.length]];
    switch (selected.kind) {
      case "shared_links": items.push(["Marked active", count(rows, row => isYes(row.cells.Active))], ["Recorded link opens", sum(rows, "Open Count")]); break;
      case "link_activity": items.push(["Failed events", count(rows, row => row.cells.Event.toLowerCase().includes("fail"))], ["External events", count(rows, row => isYes(row.cells.IsExternal))]); break;
      case "folder_summary": items.push(["Overall storage", bytes(sum(rows, "Overall Size (byte)"))], ["Deleted storage", bytes(sum(rows, "Deleted Items (byte)"))]); break;
      case "folder_members": items.push(["Unique users", new Set(rows.map(row => row.cells.User).filter(Boolean)).size], ["Outside subscription", count(rows, row => !isYes(row.cells["Subscription Member"]))]); break;
      case "external_users": items.push(["Accepted invitations", count(rows, row => isYes(row.cells["Invitation Accepted"]))], ["Pending invitations", count(rows, row => !isYes(row.cells["Invitation Accepted"]))]); break;
      case "device_status": items.push(["Unrevoked devices", count(rows, row => !isYes(row.cells.Revocation))], ["Stale unrevoked devices", count(rows, row => row.notes.some(note => note.startsWith("Unrevoked device inactive")))]); break;
    }
    items.push(["Rows with review notes", reviewed]);
    $("metrics").replaceChildren(...items.map(([label, value]) => {
      const card = node("div", undefined, "metric");
      card.append(node("span", label), node("strong", typeof value === "number" ? value.toLocaleString() : value));
      return card;
    }));
  }

  function bars(target, rows, col, weighted = false) {
    const totals = new Map();
    for (const row of rows) {
      const key = row.cells[col] || "Unknown";
      totals.set(key, (totals.get(key) || 0) + (weighted ? row.numbers["Overall Size (byte)"] || 0 : 1));
    }
    const values = [...totals].sort((a,b) => b[1] - a[1]).slice(0, 7);
    const max = Math.max(...values.map(entry => entry[1]), 1);
    target.replaceChildren();
    if (!values.length) { target.append(node("p", "No matching records.", "hint")); return; }
    for (const [label, value] of values) {
      const item = node("div", undefined, "bar-item");
      const title = node("span", label, "bar-label"); title.title = label;
      const track = node("div", undefined, "bar-track");
      const fill = node("div", undefined, "bar-fill"); fill.style.width = `${value / max * 100}%`;
      track.append(fill);
      item.append(title, track, node("span", weighted ? bytes(value) : value.toLocaleString(), "bar-value"));
      target.append(item);
    }
    if (totals.size > 7) target.append(node("p", `Showing top 7 of ${totals.size} groups.`, "hint"));
  }

  function timeline(rows, col) {
    const dates = rows.map(row => row.dates[col]?.slice(0,10)).filter(Boolean).sort();
    const target = $("secondary"); target.replaceChildren();
    if (!dates.length) { target.append(node("p", "No valid dates in matching records.", "hint")); return; }
    const start = Date.parse(dates[0]), end = Date.parse(dates[dates.length - 1]);
    const day = 86400000;
    const bucketDays = Math.max(1, Math.ceil(((end - start) / day + 1) / 90));
    const totals = new Array(Math.floor((end - start) / day / bucketDays) + 1).fill(0);
    for (const date of dates) totals[Math.floor((Date.parse(date) - start) / day / bucketDays)]++;
    const max = Math.max(...totals, 1);
    const chart = node("div", undefined, "timeline");
    chart.setAttribute("role", "img");
    chart.setAttribute("aria-label", `${dates.length} records by ${col}, from ${dates[0]} to ${dates[dates.length - 1]}. Maximum ${max} records per ${bucketDays}-day interval.`);
    totals.forEach((value, i) => {
      const bar = node("div", undefined, "day");
      bar.title = `${new Date(start + i * bucketDays * day).toISOString().slice(0,10)}: ${value} records in ${bucketDays} day(s)`;
      const fill = node("span"); fill.style.height = `${value / max * 100}%`;
      bar.append(fill); chart.append(bar);
    });
    const labels = node("div", undefined, "timeline-labels");
    labels.append(node("span", dates[0]), node("span", `${bucketDays === 1 ? "Daily" : `${bucketDays}-day`} intervals · peak ${max}`), node("span", dates[dates.length - 1]));
    target.append(chart, labels, node("p", `${rows.length - dates.length} rows without a valid date excluded.`, "hint"));
  }

  function charts(rows) {
    const weighted = selected.kind === "folder_summary";
    const group = $("group-field").value;
    $("distribution-title").textContent = weighted ? "Storage distribution · top 7" : "Record distribution · top 7";
    bars($("distribution"), rows, group, weighted);
    if (selected.kind === "folder_members") {
      $("secondary-title").textContent = "Memberships by tresor · top 7";
      bars($("secondary"), rows, "Tresor");
    } else {
      const col = $("date-field").value;
      $("secondary-title").textContent = `Records by ${col || "date"}`;
      timeline(rows, col);
    }
  }

  function compare(a, b) {
    if (sortColumn in a.numbers) {
      const left = a.numbers[sortColumn], right = b.numbers[sortColumn];
      if (left === null || right === null) return left === right ? 0 : left === null ? 1 : -1;
      return (left - right) * direction;
    }
    if (sortColumn in a.dates) {
      const left = a.dates[sortColumn], right = b.dates[sortColumn];
      if (!left || !right) return left === right ? 0 : !left ? 1 : -1;
      return left.localeCompare(right) * direction;
    }
    return (a.cells[sortColumn] || "").localeCompare(b.cells[sortColumn] || "", undefined, {numeric:true}) * direction;
  }

  function table() {
    const size = Number($("page-size").value);
    const pages = Math.max(1, Math.ceil(currentRows.length / size));
    page = Math.min(page, pages);
    const header = node("tr");
    for (const col of selected.columns) {
      const th = node("th");
      th.setAttribute("scope", "col");
      th.setAttribute("aria-sort", sortColumn === col ? direction === 1 ? "ascending" : "descending" : "none");
      const button = node("button", col + (sortColumn === col ? direction === 1 ? " ↑" : " ↓" : ""));
      button.type = "button";
      button.addEventListener("click", () => { direction = sortColumn === col ? -direction : 1; sortColumn = col; currentRows.sort(compare); page = 1; table(); });
      th.append(button); header.append(th);
    }
    $("records").querySelector("thead").replaceChildren(header);
    const body = $("records").querySelector("tbody"); body.replaceChildren();
    for (const row of currentRows.slice((page - 1) * size, page * size)) {
      const tr = node("tr");
      for (const col of selected.columns) {
        const value = row.cells[col] || "—";
        const td = node("td", undefined, col === "Review notes" ? "note-cell" : "");
        const related = col === "Link ID" || col.includes("Email") || col === "User";
        if (related && value !== "—" && value.toLowerCase() !== "n/a") {
          const button = node("button", value, "cell-link"); button.type = "button";
          button.title = "Search this value across loaded exports";
          button.addEventListener("click", () => { reset(); $("search").value = value; render(); }); td.append(button);
        } else td.textContent = col.endsWith("(byte)") && row.numbers[col] !== null ? `${bytes(row.numbers[col] || 0)} (${value})` : value;
        tr.append(td);
      }
      body.append(tr);
    }
    if (!currentRows.length) {
      const td = node("td", "No records match these filters. Try resetting filters or choosing another export.");
      td.colSpan = selected.columns.length; const tr = node("tr"); tr.append(td); body.append(tr);
    }
    $("result-count").textContent = `${currentRows.length.toLocaleString()} of ${selected.rows.length.toLocaleString()} rows · Charts and metrics reflect these filters`;
    $("page-label").textContent = `Page ${page} of ${pages}`;
    $("previous").disabled = page === 1; $("next").disabled = page === pages;
    $("export").disabled = currentRows.length === 0;
  }

  function render() {
    const invalidRange = $("from").value && $("to").value && $("from").value > $("to").value;
    $("filter-error").hidden = !invalidRange;
    $("filter-error").textContent = invalidRange ? "The From date must be on or before the To date." : "";
    currentRows = selected.rows.filter(row => matches(row, selected));
    if (sortColumn) currentRows.sort(compare);
    tabs(); metrics(currentRows); charts(currentRows); geography.render(selected.rows.filter(row => matches(row, selected, true, false)), currentRows); table();
  }

  function reset() {
    geography.reset();
    $("search").value = ""; $("status").value = ""; $("from").value = ""; $("to").value = ""; $("review-only").checked = false; page = 1;
  }

  function csvCell(value) {
    // Prevent spreadsheet formula execution while preserving literal data in the UI.
    value = String(value ?? "");
    if (/^[\s]*[=+@-]/.test(value) || /^[\t\r\n]/.test(value)) value = "'" + value;
    return `"${value.replaceAll('"', '""')}"`;
  }

  $("export").addEventListener("click", () => {
    const lines = [selected.columns.map(csvCell).join(","), ...currentRows.map(row => selected.columns.map(col => csvCell(row.cells[col])).join(","))];
    const url = URL.createObjectURL(new Blob(["\ufeff" + lines.join("\r\n")], {type:"text/csv;charset=utf-8"}));
    const link = node("a"); link.href = url; link.download = `${selected.kind}_filtered.csv`; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $("search").addEventListener("input", () => { clearTimeout(renderTimer); renderTimer = setTimeout(() => { page = 1; render(); }, 120); });
  for (const id of ["status", "review-only", "date-field", "from", "to"]) $(id).addEventListener("change", () => { page = 1; render(); });
  $("reset").addEventListener("click", () => { reset(); render(); });
  $("page-size").addEventListener("change", () => { page = 1; table(); });
  $("group-field").addEventListener("change", () => charts(currentRows));
  $("previous").addEventListener("click", () => { page--; table(); });
  $("next").addEventListener("click", () => { page++; table(); });
  select(selected);
})();
