const DATA = JSON.parse(document.getElementById("page-data").textContent);
const $ = selector => document.querySelector(selector);
const fmt = new Intl.NumberFormat("en-US", {maximumFractionDigits: 0});
const one = value => Number(value).toFixed(1);
const esc = value => String(value ?? "").replace(/[&<>\"]/g, char =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[char]));
const SVG = "http://www.w3.org/2000/svg";
const tip = $("#tooltip");

function css(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function node(tag, attributes = {}, text = "") {
  const element = document.createElementNS(SVG, tag);
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
  element.textContent = text;
  return element;
}

function add(parent, tag, attributes = {}, text = "") {
  const element = node(tag, attributes, text);
  parent.append(element);
  return element;
}

function svgFrame(selector, width, height) {
  const svg = $(selector);
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  return svg;
}

function scale(value, low, high, start, stop) {
  return start + (value - low) * (stop - start) / (high - low || 1);
}

function path(points) {
  return points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}

function showTip(event, html) {
  tip.innerHTML = html;
  tip.classList.add("visible");
  tip.style.left = `${Math.min(event.clientX + 13, innerWidth - 345)}px`;
  tip.style.top = `${Math.min(event.clientY + 13, innerHeight - 150)}px`;
}

function hideTip() { tip.classList.remove("visible"); }

function xAxis(svg, box, low, high, step, label, y = box.y1) {
  add(svg, "line", {x1: box.x0, x2: box.x1, y1: y, y2: y, class: "axis"});
  const first = Math.ceil(low / step) * step;
  for (let value = first; value <= high + 1e-9; value += step) {
    const x = scale(value, low, high, box.x0, box.x1);
    add(svg, "line", {x1: x, x2: x, y1: box.y0, y2: box.y1, class: "rule"});
    add(svg, "text", {x, y: y + 17, "text-anchor": "middle", class: "tick"}, value);
  }
  add(svg, "text", {x: (box.x0 + box.x1) / 2, y: y + 37,
    "text-anchor": "middle", class: "axis-name"}, label);
}

function yAxis(svg, box, ticks, map, label) {
  add(svg, "line", {x1: box.x0, x2: box.x0, y1: box.y0, y2: box.y1, class: "axis"});
  for (const value of ticks) {
    const y = map(value);
    add(svg, "line", {x1: box.x0, x2: box.x1, y1: y, y2: y, class: "rule"});
    add(svg, "text", {x: box.x0 - 8, y: y + 3, "text-anchor": "end", class: "tick"}, fmt.format(value));
  }
  add(svg, "text", {x: 14, y: (box.y0 + box.y1) / 2,
    transform: `rotate(-90 14 ${(box.y0 + box.y1) / 2})`,
    "text-anchor": "middle", class: "axis-name"}, label);
}

function legend(target, entries) {
  $(target).innerHTML = entries.map(([label, colour, shape = "square"]) =>
    `<span><i class="key" style="background:${colour};${shape === "diamond" ? "transform:rotate(45deg)" : ""}"></i>${esc(label)}</span>`).join("");
}

function weightedQuantile(rows, fraction, value = "ability", weight = "seats") {
  const ordered = [...rows].sort((a, b) => a[value] - b[value]);
  const target = ordered.reduce((sum, row) => sum + row[weight], 0) * fraction;
  let carried = 0;
  for (const row of ordered) {
    carried += row[weight];
    if (carried >= target) return row[value];
  }
  return ordered.at(-1)?.[value];
}

function ladderData() {
  const bins = 50;
  const stacks = {general: Array(bins).fill(0), tech: Array(bins).fill(0)};
  for (const row of DATA.departments) {
    const index = Math.max(0, Math.min(bins - 1, Math.floor(row.ability / 2)));
    stacks[row.system][index] += row.seats;
  }
  const ordered = [...DATA.departments].sort((a, b) => a.ability - b.ability);
  let below = 0;
  const total = ordered.reduce((sum, row) => sum + row.seats, 0);
  const cumulative = ordered.map(row => {
    const point = [row.ability, total - below];
    below += row.seats;
    return point;
  });
  return {bins, stacks, cumulative, total};
}

function ladderFigure() {
  const svg = svgFrame("#ladder-svg", 960, 530);
  const data = ladderData();
  const top = {x0: 78, x1: 930, y0: 24, y1: 224};
  const bottom = {x0: 78, x1: 930, y0: 310, y1: 474};
  const heights = data.stacks.general.map((value, i) => value + data.stacks.tech[i]);
  const maximum = Math.ceil(Math.max(...heights) / 500) * 500;
  xAxis(svg, top, 0, 100, 10, "ability percentile within the age cohort");
  yAxis(svg, top, [0, maximum / 2, maximum], value =>
    scale(value, 0, maximum, top.y1, top.y0), "threshold seats per 2 points");
  for (let index = 0; index < data.bins; index++) {
    let floor = 0;
    for (const system of ["general", "tech"]) {
      const value = data.stacks[system][index];
      const x = scale(index * 2, 0, 100, top.x0, top.x1);
      const y = scale(floor + value, 0, maximum, top.y1, top.y0);
      const yFloor = scale(floor, 0, maximum, top.y1, top.y0);
      add(svg, "rect", {x, y, width: (top.x1 - top.x0) / data.bins + .3,
        height: yFloor - y, fill: css(`--${system}`), opacity: .88});
      floor += value;
    }
  }
  const logMap = value => scale(Math.log10(Math.max(200, value)),
    Math.log10(200), Math.log10(data.total * 1.35), bottom.y1, bottom.y0);
  xAxis(svg, bottom, 0, 100, 10, "ability percentile within the age cohort");
  yAxis(svg, bottom, [500, 1000, 5000, 10000, 50000, 100000], logMap,
        "seats at or above this ability");
  const curve = data.cumulative.map(([ability, seats]) =>
    [scale(ability, 0, 100, bottom.x0, bottom.x1), logMap(seats)]);
  add(svg, "path", {d: path(curve), fill: "none", stroke: css("--ink"), "stroke-width": 2.2});
  add(svg, "text", {x: top.x0, y: 14, class: "axis-name"}, "Where the seats are");
  add(svg, "text", {x: bottom.x0, y: 294, class: "axis-name"}, "What each rung costs");
  ladderHover(svg, top, data, maximum);
  $("#ladder-seats").textContent = fmt.format(data.total);
  $("#ladder-departments").textContent = fmt.format(DATA.metrics.departments);
  $("#ladder-floor").textContent = `${Math.min(...DATA.departments.map(row => row.ability)).toFixed(0)}th`;
  $("#ladder-pool").textContent = fmt.format(DATA.metrics.assessment_pool);
  legend("#ladder-legend", [["一般大學 · GSAT / AST", css("--general")],
    ["科技大學 · TVE", css("--tech")], ["cumulative seats", css("--ink")]]);
}

function ladderHover(svg, box, data, maximum) {
  const overlay = add(svg, "rect", {x: box.x0, y: box.y0, width: box.x1 - box.x0,
    height: box.y1 - box.y0, fill: "transparent"});
  overlay.addEventListener("mousemove", event => {
    const bounds = svg.getBoundingClientRect();
    const local = (event.clientX - bounds.left) / bounds.width * 960;
    const ability = Math.max(0, Math.min(99.9, scale(local, box.x0, box.x1, 0, 100)));
    const index = Math.floor(ability / 2);
    const general = data.stacks.general[index], tech = data.stacks.tech[index];
    const above = data.cumulative.find(point => point[0] >= ability)?.[1] || 0;
    showTip(event, `<b>Ability ${index * 2}–${index * 2 + 2}</b><br>` +
      `${fmt.format(general)} general-university threshold seats<br>` +
      `${fmt.format(tech)} technology-university threshold seats<br>` +
      `${fmt.format(above)} seats at or above this rung`);
  });
  overlay.addEventListener("mouseleave", hideTip);
}

function interpolate(points, x) {
  const index = Math.max(1, points.findIndex(point => point[0] >= x));
  const left = points[index - 1], right = points[index] || left;
  return scale(x, left[0], right[0], left[1], right[1]);
}

function invert(points, y) {
  const index = points.findIndex(point => point[1] >= y);
  if (index <= 0) return index === 0 ? points[0][0] : null;
  return scale(y, points[index - 1][1], points[index][1],
               points[index - 1][0], points[index][0]);
}

function bridgeFigure() {
  const svg = svgFrame("#bridge-svg", 960, 450);
  const box = {x0: 58, x1: 930, y0: 25, y1: 390};
  const maximum = Math.ceil(Math.max(...DATA.curves.flatMap(curve =>
    curve.density.map(point => point[1]))) * 2) / 2;
  const y = value => scale(value, 0, maximum, box.y1, box.y0);
  xAxis(svg, box, 0, 100, 10, "ability percentile in the age cohort");
  yAxis(svg, box, [0, maximum / 2, maximum], y,
        "relative candidate density · uniform = 1");
  const bands = [[12,"底"],[25,"後"],[50,"均"],[75,"前"],[88,"頂"]];
  const gsat = DATA.curves.find(curve => curve.exam === "gsat");
  for (const [mark, label] of bands) {
    const ability = interpolate(gsat.points, mark);
    const x = scale(ability, 0, 100, box.x0, box.x1);
    add(svg, "line", {x1: x, x2: x, y1: box.y0, y2: box.y1,
      stroke: DATA.exams.gsat.colour, opacity: .18});
    add(svg, "text", {x, y: box.y1 - 7, "text-anchor": "middle", class: "tick"}, label);
  }
  for (const curve of DATA.curves) {
    const points = curve.density.map(([ability, density]) =>
      [scale(ability, 0, 100, box.x0, box.x1), y(density)]);
    const area = [[points[0][0], box.y1], ...points, [points.at(-1)[0], box.y1]];
    add(svg, "path", {d: `${path(area)} Z`, fill: DATA.exams[curve.exam].colour,
      opacity: .055, stroke: "none"});
    add(svg, "path", {d: path(points), fill: "none",
      stroke: DATA.exams[curve.exam].colour, "stroke-width": 2.6});
  }
  bridgeHover(svg, box);
  legend("#bridge-legend", DATA.curves.map(curve =>
    [`${DATA.exams[curve.exam].label} (${DATA.exams[curve.exam].english})`,
     DATA.exams[curve.exam].colour]));
  crosswalk(bands);
}

function bridgeHover(svg, box) {
  const overlay = add(svg, "rect", {x: box.x0, y: box.y0, width: box.x1 - box.x0,
    height: box.y1 - box.y0, fill: "transparent"});
  overlay.addEventListener("mousemove", event => {
    const bounds = svg.getBoundingClientRect();
    const local = (event.clientX - bounds.left) / bounds.width * 960;
    const ability = Math.max(0, Math.min(100, scale(local, box.x0, box.x1, 0, 100)));
    const lines = DATA.curves.map(curve =>
      `${DATA.exams[curve.exam].label}: ${one(interpolate(curve.density, ability))}× uniform`);
    showTip(event, `<b>Ability ${one(ability)}</b><br>${lines.join("<br>")}`);
  });
  overlay.addEventListener("mouseleave", hideTip);
}

function crosswalk(bands) {
  const gsat = DATA.curves.find(curve => curve.exam === "gsat");
  const exams = DATA.curves.map(curve => curve.exam);
  $("#crosswalk thead").innerHTML = `<tr><th>GSAT landmark</th><th>Cohort ability</th>${exams.map(exam => `<th>${esc(DATA.exams[exam].label)}</th>`).join("")}</tr>`;
  $("#crosswalk tbody").innerHTML = bands.map(([mark, label]) => {
    const ability = interpolate(gsat.points, mark);
    const cells = exams.map(exam => {
      const curve = DATA.curves.find(item => item.exam === exam);
      const value = invert(curve.points, ability);
      return `<td class="n">${value == null ? "—" : one(value)}</td>`;
    }).join("");
    return `<tr><td>${label}標 · GSAT ${mark}</td><td class="n">${one(ability)}</td>${cells}</tr>`;
  }).join("");
}

function routeFigure() {
  const limit = Number($("#route-limit").value);
  const order = $("#route-order").value;
  const sorted = [...DATA.universities].sort((a, b) =>
    order === "spread" ? b.spread - a.spread : b.ability - a.ability).slice(0, limit);
  const width = 1050, height = 105 + sorted.length * 28;
  const svg = svgFrame("#route-svg", width, height);
  svg.style.minWidth = "850px";
  const values = sorted.flatMap(row => [row.ability, ...Object.values(row.exams)]);
  const low = Math.max(0, Math.floor((Math.min(...values) - 4) / 10) * 10);
  const box = {x0: 265, x1: 1015, y0: 38, y1: height - 24};
  xAxis(svg, box, low, 100, 10, "ability percentile", 32);
  sorted.forEach((row, index) => routeRow(svg, row, index, box, low));
  const entries = Object.entries(DATA.exams).filter(([exam]) =>
    sorted.some(row => row.exams[exam] != null)).map(([, meta]) => [meta.label, meta.colour]);
  entries.unshift(["seat-weighted university estimate", css("--ink"), "diamond"]);
  legend("#route-legend", entries);
}

function routeRow(svg, row, index, box, low) {
  const y = 92 + index * 28;
  const values = Object.values(row.exams);
  const minimum = Math.min(...values), maximum = Math.max(...values);
  const x = value => scale(value, low, 100, box.x0, box.x1);
  add(svg, "text", {x: box.x0 - 12, y: y + 4, "text-anchor": "end", fill: css("--ink"),
    "font-size": 12}, `${row.rank}. ${row.school}`);
  add(svg, "line", {x1: x(minimum), x2: x(maximum), y1: y, y2: y,
    stroke: css("--faint"), "stroke-width": 1.2});
  for (const [exam, value] of Object.entries(row.exams)) {
    const point = add(svg, "circle", {cx: x(value), cy: y, r: 4.2,
      fill: DATA.exams[exam].colour, stroke: css("--card"), "stroke-width": 1});
    point.addEventListener("mousemove", event => showTip(event,
      `<b>${esc(row.school)}</b>${row.school_en ? `<br>${esc(row.school_en)}` : ""}<br>` +
      `${esc(DATA.exams[exam].label)}: ${one(value)}<br>` +
      `Combined estimate ${one(row.ability)} · ${fmt.format(row.seats)} threshold seats` +
      `${row.former ? `<br>Includes ${esc(row.former)}` : ""}`));
    point.addEventListener("mouseleave", hideTip);
  }
  const centre = x(row.ability);
  add(svg, "polygon", {points: `${centre},${y-5} ${centre+5},${y} ${centre},${y+5} ${centre-5},${y}`,
    fill: css("--ink")});
}

let programGroups;
function preparePrograms() {
  programGroups = new Map();
  for (const row of DATA.departments) {
    if (!programGroups.has(row.school)) programGroups.set(row.school, []);
    programGroups.get(row.school).push(row);
  }
  const ordered = [...programGroups].sort((a, b) =>
    weightedQuantile(b[1], .5) - weightedQuantile(a[1], .5));
  $("#program-school").innerHTML = ordered.map(([school, rows]) => {
    const english = rows[0].school_en ? ` · ${rows[0].school_en}` : "";
    return `<option value="${esc(school)}">${esc(school + english)}</option>`;
  }).join("");
  if (programGroups.has("國立臺灣大學")) $("#program-school").value = "國立臺灣大學";
}

function programFigure() {
  const school = $("#program-school").value;
  const rows = programGroups.get(school) || [];
  const q10 = weightedQuantile(rows, .1), median = weightedQuantile(rows, .5);
  const q90 = weightedQuantile(rows, .9), total = rows.reduce((sum, row) => sum + row.seats, 0);
  $("#program-count").textContent = fmt.format(rows.length);
  $("#program-seats").textContent = fmt.format(total);
  $("#program-median").textContent = one(median);
  $("#program-span").textContent = `${one(q90 - q10)} pts`;
  const low = Math.max(0, Math.floor((Math.min(...rows.map(row => row.ability)) - 4) / 5) * 5);
  const high = Math.min(100, Math.ceil((Math.max(...rows.map(row => row.ability)) + 4) / 5) * 5);
  const svg = svgFrame("#program-svg", 960, 350);
  const box = {x0: 58, x1: 930, y0: 30, y1: 290};
  xAxis(svg, box, low, high, high - low > 40 ? 10 : 5, "department ability percentile");
  const x = value => scale(value, low, high, box.x0, box.x1);
  add(svg, "rect", {x: x(q10), y: 80, width: x(q90) - x(q10), height: 165,
    fill: css("--accent"), opacity: .08});
  add(svg, "line", {x1: x(median), x2: x(median), y1: 68, y2: 260,
    stroke: css("--accent"), "stroke-dasharray": "5 4"});
  const ordered = [...rows].sort((a, b) => a.ability - b.ability);
  ordered.forEach((row, index) => programPoint(svg, row, index, x));
  const strongest = [...rows].sort((a, b) => b.ability - a.ability).slice(0, 8);
  $("#program-table tbody").innerHTML = strongest.map(row =>
    `<tr><td>${esc(row.department)}${row.department_en ? ` <span class="caption">${esc(row.department_en)}</span>` : ""}</td>` +
    `<td class="n">${one(row.ability)}</td><td class="n">${fmt.format(row.seats)}</td></tr>`).join("");
}

function programPoint(svg, row, index, x) {
  const lanes = 11;
  const lane = (index * 7) % lanes;
  const y = 82 + lane * 16 + 7 * Math.sin(index * 1.71);
  const radius = Math.min(10, 2.8 + Math.sqrt(row.seats) / 2.8);
  const point = add(svg, "circle", {cx: x(row.ability), cy: y, r: radius,
    fill: css(row.system === "tech" ? "--tech" : "--general"), opacity: .72,
    stroke: css("--card"), "stroke-width": 1});
  point.addEventListener("mousemove", event => showTip(event,
    `<b>${esc(row.department)}</b>${row.department_en ? `<br>${esc(row.department_en)}` : ""}<br>` +
    `Ability ${one(row.ability)} · ${fmt.format(row.seats)} threshold seats` +
    `${row.spread ? `<br>Own readings span ${one(row.spread)} points` : ""}`));
  point.addEventListener("mouseleave", hideTip);
}

function destinationSummary(named) {
  const total = DATA.destinations.reduce((sum, row) => sum + row.students, 0);
  const graduates = DATA.destinations[0]?.graduates || total;
  const domestic = DATA.destinations.filter(row => row.type === "domestic_other")
    .reduce((sum, row) => sum + row.students, 0);
  const foreign = DATA.destinations.filter(row => row.type.startsWith("foreign"))
    .reduce((sum, row) => sum + row.students, 0);
  const pieces = [["Named domestic", named, "#2474d2"],
    ["Other domestic", domestic, "#7c5ce0"], ["Overseas", foreign, "#d28b36"],
    ["Unreported", graduates - total, css("--faint")]];
  $("#destination-stack").innerHTML = pieces.map(([label, count, colour]) =>
    `<span title="${esc(label)}: ${count}" style="width:${100 * count / graduates}%;background:${colour}">` +
    `${count / graduates > .055 ? `${esc(label)} · ${count}` : ""}</span>`).join("");
}

function beiyiFigure() {
  const rows = DATA.destinations.filter(row => row.type === "university" && row.ability != null)
    .sort((a, b) => b.students - a.students);
  const named = rows.reduce((sum, row) => sum + row.students, 0);
  const expanded = rows.flatMap(row => Array(row.students).fill(row.ability)).sort((a, b) => a - b);
  const median = expanded[Math.floor(expanded.length / 2)];
  const ninety = rows.filter(row => row.ability >= 90).reduce((sum, row) => sum + row.students, 0);
  $("#beiyi-named").textContent = fmt.format(named);
  $("#beiyi-median").textContent = one(median);
  $("#beiyi-ninety").textContent = `${fmt.format(ninety)} · ${one(100 * ninety / named)}%`;
  $("#beiyi-entry").textContent = DATA.entry_floor ? `top ${one(DATA.entry_floor.top_share)}%` : "—";
  const svg = svgFrame("#beiyi-svg", 960, 540);
  const box = {x0: 235, x1: 875, y0: 42, y1: 520};
  const low = 70;
  xAxis(svg, box, low, 100, 5, "destination university ability", 30);
  rows.forEach((row, index) => destinationRow(svg, row, index, box, low));
  destinationSummary(named);
}

function destinationRow(svg, row, index, box, low) {
  const y = 92 + index * 28;
  const x = scale(row.ability, low, 100, box.x0, box.x1);
  add(svg, "text", {x: box.x0 - 12, y: y + 4, "text-anchor": "end",
    fill: css("--ink"), "font-size": 12}, row.name);
  add(svg, "line", {x1: box.x0, x2: x, y1: y, y2: y, stroke: css("--grid")});
  const point = add(svg, "circle", {cx: x, cy: y, r: 3 + .72 * Math.sqrt(row.students),
    fill: DATA.exams.gsat.colour, opacity: .82, stroke: css("--card"), "stroke-width": 1});
  add(svg, "text", {x: box.x1 + 12, y: y + 4, fill: css("--mid"),
    "font-family": "var(--mono)", "font-size": 11}, `${row.students} graduates`);
  point.addEventListener("mousemove", event => showTip(event,
    `<b>${esc(row.name)}</b><br>${row.students} 北一女 graduates<br>` +
    `University ability ${one(row.ability)}`));
  point.addEventListener("mouseleave", hideTip);
}

function coverageFigure() {
  const years = [...new Set(DATA.coverage.map(row => row.year))].sort();
  const order = ["uac", "tech", "star", "apply", "tech_apply"];
  const paths = order.filter(path => DATA.coverage.some(row => row.path === path));
  const target = $("#coverage-grid");
  target.style.gridTemplateColumns = `150px repeat(${years.length}, minmax(82px, 1fr))`;
  target.innerHTML = `<div></div>${years.map(year => `<div class="head">${year}<br>${Number(year) + 1911}</div>`).join("")}`;
  for (const pathName of paths) {
    const representative = DATA.coverage.find(row => row.path === pathName);
    target.insertAdjacentHTML("beforeend", `<div class="path">${esc(representative.label)}</div>`);
    for (const year of years) {
      const row = DATA.coverage.find(item => item.path === pathName && item.year === year);
      target.insertAdjacentHTML("beforeend", coverageCell(row));
    }
  }
}

function coverageCell(row) {
  if (!row) return `<div class="coverage-cell"><b>—</b><span>no bars</span></div>`;
  const alpha = row.share == null ? .13 : .16 + .68 * Math.min(1, row.share);
  const colour = row.share == null ? `rgba(227,138,66,${alpha})` : `rgba(36,116,210,${alpha})`;
  const headline = row.share == null ? "total n/a" : `${Math.round(100 * row.share)}% intake`;
  return `<div class="coverage-cell" style="background:${colour}" title="${fmt.format(row.seats)} seats from ${fmt.format(row.bars)} bars">` +
    `<b>${headline}</b><span>${fmt.format(row.bars)} bars</span><span>${fmt.format(row.seats)} seats</span></div>`;
}

function watchNav() {
  const links = [...document.querySelectorAll("nav a")];
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting)
      links.forEach(link => link.classList.toggle("on", link.hash === `#${entry.target.id}`));
  }, {rootMargin: "-20% 0px -70%"});
  document.querySelectorAll("main section").forEach(section => observer.observe(section));
}

const DRAWERS = [ladderFigure, bridgeFigure, routeFigure, programFigure, beiyiFigure];
function theme() {
  const light = document.documentElement.dataset.theme === "light";
  document.documentElement.dataset.theme = light ? "dark" : "light";
  $("#theme").textContent = light ? "Use light theme" : "Use dark theme";
  DRAWERS.forEach(draw => draw());
}

preparePrograms();
DRAWERS.forEach(draw => draw());
coverageFigure();
watchNav();
$("#route-limit").addEventListener("change", routeFigure);
$("#route-order").addEventListener("change", routeFigure);
$("#program-school").addEventListener("change", programFigure);
$("#theme").addEventListener("click", theme);
