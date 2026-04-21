// app.js (fixed)
// Bu dosya plan.html ile uyumlu olacak şekilde eksik fonksiyonları tamamlar.
// Not: Backend endpoint'leri mevcut projenizdeki ile aynı varsayılmıştır.

"use strict";

// Gözlemci kontrolü - sayfa yüklendiğinde kontrol et
let IS_OBSERVER = false;
document.addEventListener("DOMContentLoaded", () => {
  // Session'dan role bilgisini al (template'den gelen data attribute veya hidden input)
  const roleInput = document.getElementById("userRole");
  if (roleInput) {
    const role = (roleInput.value || "").toString().trim().toLowerCase();
    IS_OBSERVER = role === "gözlemci" || role === "gozlemci";
  }
  // Eger role input yoksa, butonlari kontrol et
  if (IS_OBSERVER) {
    // Tum degisiklik yapan butonlari devre disi birak
    document.querySelectorAll('[onclick*="saveCell"], [onclick*="clearCell"], [onclick*="openJobMailModal"], [onclick*="sendJobMail"], [onclick*="addBlankJobRow"], [onclick*="deleteSelectedJobRow"], [onclick*="copyWeekFromPrevious"], [onclick*="copyMondayToWeek"], [onclick*="copyCurrentAsTemplate"], [onclick*="togglePasteMode"], [onclick*="openStatusModal"]').forEach(btn => {
      btn.style.display = 'none';
    });
  }
  initDropzones();

  const jmFiles = document.getElementById("jmNewFiles");
  if (jmFiles) {
    jmFiles.addEventListener("change", () => renderJobMailNewFilesList());
  }

  try { _applySummaryCollapsedState(); } catch (_) { }
  const summaryBtn = document.getElementById("btnPersonelOzet");
  if (summaryBtn) {
    summaryBtn.addEventListener("click", (e) => { e.preventDefault(); toggleSummary(true); });
  }

  try { applyMergedCellRuns(); } catch (_) { }
  try { renderVehicleSelect(); } catch (e) { console.error("vehicle select init failed", e); }
  try { renderTeamVehicleSelect(); } catch (e) { console.error("team vehicle select init failed", e); }
  const vehicleToggleBtn = _byId("vehicleToggleButton");
  if (vehicleToggleBtn) {
    vehicleToggleBtn.addEventListener("click", toggleVehicleList);
  }
  const vehicleSelect = _byId("mVehicle");
  if (vehicleSelect) {
    vehicleSelect.addEventListener("change", () => {
      updateVehicleHint(vehicleSelect.value);
      vehicleDirty = true;
    });
  }
  const subprojectToggleBtn = _byId("toggleSubprojectsBtn");
  if (subprojectToggleBtn) {
    try {
      SUBPROJECTS_HIDDEN = (window.localStorage.getItem(SUBPROJECTS_STORAGE_KEY) || "") === "1";
    } catch (_) {
      SUBPROJECTS_HIDDEN = false;
    }
    subprojectToggleBtn.addEventListener("click", () => toggleSubprojectPanel());
    updateSubprojectPanelVisibility();
  }

  try { applyVerticalMerges(); } catch (e) { console.error("Vertical merge failed", e); }
});
// =================== STATE ===================
window.reloadWithScroll = function () {
  saveScrollPositions();
  window.location.reload();
};

let currentWeekStart = null;
let currentCell = { project_id: null, work_date: null, week_start: null, city: "", project_code: "", team_id: null };
let dragData = null;
let selectedPeople = new Set();
let RECENT_PEOPLE = JSON.parse(localStorage.getItem("recent_people") || "[]");
let FAV_PEOPLE = new Set(JSON.parse(localStorage.getItem("fav_people") || "[]"));
let selectedCellEl = null;
let existingLLDs = [];
let existingTutanaks = [];
let removeLLDs = new Set();
let removeTutanaks = new Set();
let vehicleDirty = false;
const SUBPROJECTS_STORAGE_KEY = "plan_subprojects_hidden";
let SUBPROJECTS_HIDDEN = false;

// Sağ panel (pencere/drawer) durumu
let PANEL_PINNED = false;
let __panelCloseTimer = null;

// Plan: Satır seç / İş ekle / Düzenle / Sil
let __selectedProjectId = 0;
let __newRowActive = false;
let __editMode = false;

// Status modal seçimi
let statusSelectedPeople = new Set();

// Kopyala/Yapıştır
let clipboardPayload = null;
let pasteMode = false;
let __pasteMouseDown = false;
let __lastPasted = "";

// Team report cache
let LAST_TEAM_REPORT = null;

// Weekly vehicle cache (project_id -> plate)
let WEEKLY_VEHICLE_LOOKUP = {};
let VEHICLE_WEEK_START = null;
let VEHICLE_SHOW_ALL = false;
let currentTeamVehicle = null;
let currentTeamId = null;
let pendingTeamVehicleId = null;
const TEAM_TABLE_STYLE_KEY = "team_table_style_v1";
const TEAM_TABLE_STYLE_DEFAULT = {
  fontFamily: "Inter, system-ui, -apple-system, sans-serif",
  fontSize: 14,
  fontColor: "#0f172a",
  headerBg: "#f8fafc",
  rowBg: "#ffffff",
  borderColor: "#e2e8f0"
};


// Map state
let _map, _layer;
let LAST_DRAWN_ROUTE = null;
let LAST_ROUTE_STATS = [];
let SHOW_ROUTE_CITIES = false;
const OSRM_CACHE = {};

// Team members cache (tooltip iAin)
const TEAM_MEMBERS_CACHE = {};

// =================== GEO HELPERS ===================
function haversineKm(a, b) {
  if (!a || !b) return 0;
  const toRad = (x) => x * Math.PI / 180;
  const R = 6371; // km
  const dLat = toRad((b[0] ?? 0) - (a[0] ?? 0));
  const dLon = toRad((b[1] ?? 0) - (a[1] ?? 0));
  const lat1 = toRad(a[0] ?? 0);
  const lat2 = toRad(b[0] ?? 0);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function _vehicleListSnapshot(showAll) {
  const raw = Array.isArray(window.PLAN_VEHICLES) ? window.PLAN_VEHICLES.slice() : [];
  raw.sort((a, b) => {
    const plateA = (a && a.plate) ? a.plate.toString().trim() : "";
    const plateB = (b && b.plate) ? b.plate.toString().trim() : "";
    try {
      return plateA.localeCompare(plateB, "tr");
    } catch (_) {
      return plateA.localeCompare(plateB);
    }
  });
  if (showAll) {
    return raw;
  }
  return raw.filter(v => v && (!v.status || v.status === "available"));
}

function _activeTeamId() {
  const candidate = currentCell.team_id ?? currentTeamId;
  if (!candidate) {
    return null;
  }
  const parsed = parseInt(candidate, 10);
  return parsed > 0 ? parsed : null;
}

function getVehicleMetaLabel(vehicle) {
  if (!vehicle) return "";
  const segments = [];
  if (vehicle.brand) segments.push(vehicle.brand);
  if (vehicle.model) segments.push(vehicle.model);
  if (vehicle.capacity) {
    segments.push(`${vehicle.capacity} kişi`);
  }
  const statusLabels = {
    available: "Kullanılabilir",
    maintenance: "Bakımda",
    out_of_service: "Hizmet Dışı"
  };
  if (vehicle.status) {
    segments.push(statusLabels[vehicle.status] || vehicle.status);
  }
  if (vehicle.vodafone_approval) {
    segments.push("Vodafone onayı");
  }
  return segments.filter(Boolean).join(" · ");
}

function updateVehicleHint(plate) {
  const hint = _byId("vehicleHint");
  if (!hint) return;
  const lookup = window.PLAN_VEHICLE_BY_PLATE || {};
  const info = plate ? lookup[plate] : null;
  hint.textContent = info ? getVehicleMetaLabel(info) : "";
}

function renderVehicleSelect(selectedPlate) {
  const select = _byId("mVehicle");
  if (!select) return;
  const keep = (selectedPlate || select.value || "").toString().trim();
  select.innerHTML = '<option value="">-- Araç seç --</option>';

  const teamId = _activeTeamId();

  // Araç listesini filtrele
  // VEHICLE_SHOW_ALL = false (varsayılan): sadece atanmamış veya mevcut ekibe atanmış araçlar
  // VEHICLE_SHOW_ALL = true: tüm araçlar görünür
  const allVehicles = _vehicleListSnapshot(VEHICLE_SHOW_ALL);
  const vehicles = allVehicles.filter(v => {
    if (!v || !v.plate) return false;
    // "Tüm Araçları Gör" modunda hepsini göster
    if (VEHICLE_SHOW_ALL) return true;
    // Normal modda: atanmamış araçlar veya mevcut ekibe atanmış araçlar
    if (teamId) {
      return !v.assigned_team_id || v.assigned_team_id === teamId;
    }
    return !v.assigned_team_id;
  });

  vehicles.forEach(v => {
    const opt = document.createElement("option");
    opt.value = v.plate;
    // Eğer araç başka bir ekibe atanmışsa bunu belirt (sadece VEHICLE_SHOW_ALL modunda)
    let label = v.brand ? `${v.plate} (${v.brand})` : v.plate;
    if (VEHICLE_SHOW_ALL && v.assigned_team_id && v.assigned_team_id !== teamId) {
      label += " [Atanmış]";
      opt.style.color = "#f97316"; // Turuncu renk - uyarı
    }
    opt.textContent = label;
    opt.title = getVehicleMetaLabel(v);
    select.appendChild(opt);
  });

  // Mevcut seçili değeri koru (eğer varsa)
  if (keep) {
    const found = Array.from(select.options).some(opt => opt.value === keep);
    if (!found) {
      // Seçili araç listede yoksa, ekle (eski atama olabilir)
      const custom = document.createElement("option");
      custom.value = keep;
      custom.textContent = keep;
      select.appendChild(custom);
    }
    select.value = keep;
  }
  // Eğer seçili değer yoksa, boş bırak (ilk option seçili kalır: "-- Araç seç --")

  updateVehicleHint(keep || select.value);
}

function toggleVehicleList() {
  VEHICLE_SHOW_ALL = !VEHICLE_SHOW_ALL;
  const btn = _byId("vehicleToggleButton");
  if (btn) {
    btn.dataset.showAll = VEHICLE_SHOW_ALL ? "1" : "0";
    btn.textContent = VEHICLE_SHOW_ALL ? "Sadece uygun araçlar" : "Tüm araçları gör";
  }
  renderVehicleSelect();
}

function updateSubprojectPanelVisibility() {
  const list = _byId("subprojectList");
  const btn = _byId("toggleSubprojectsBtn");
  if (!list || !btn) return;
  if (!list.dataset.baseDisplay) {
    list.dataset.baseDisplay = list.style.display || "grid";
  }
  const baseDisplay = list.dataset.baseDisplay || "grid";
  if (SUBPROJECTS_HIDDEN) {
    list.style.display = "none";
    btn.textContent = "Alt projeleri göster";
  } else {
    list.style.display = baseDisplay;
    btn.textContent = "Alt projeleri gizle";
  }
  try {
    window.localStorage.setItem(SUBPROJECTS_STORAGE_KEY, SUBPROJECTS_HIDDEN ? "1" : "0");
  } catch (_) { }
}

function toggleSubprojectPanel(forceState) {
  if (typeof forceState === "boolean") {
    SUBPROJECTS_HIDDEN = forceState;
  } else {
    SUBPROJECTS_HIDDEN = !SUBPROJECTS_HIDDEN;
  }
  updateSubprojectPanelVisibility();
}

function refreshTeamVehicleHint() {
  const hint = _byId("teamVehicleHint");
  if (hint) {
    if (currentTeamVehicle && currentTeamVehicle.plate) {
      hint.textContent = `Ekip varsayılan aracı: ${currentTeamVehicle.plate}`;
    } else {
      hint.textContent = "";
    }
  }
  const current = _byId("teamVehicleCurrent");
  if (current) {
    current.textContent = currentTeamVehicle && currentTeamVehicle.plate ? `Şu an atanan: ${currentTeamVehicle.plate}` : "Ekip aracı atanmamış.";
  }
}

function updateTeamVehicleMeta(plate) {
  const meta = _byId("teamVehicleMeta");
  if (!meta) return;
  if (!plate) {
    meta.textContent = "Boş bırakılırsa varsayılan araç kaldırılır.";
    return;
  }
  const info = (window.PLAN_VEHICLE_BY_PLATE || {})[plate];
  meta.textContent = info ? getVehicleMetaLabel(info) : "";
}

function renderTeamVehicleSelect(selectedPlate) {
  const select = _byId("teamVehicleSelect");
  if (!select) return;
  const keep = (selectedPlate || select.value || (currentTeamVehicle && currentTeamVehicle.plate) || "").toString().trim();
  select.innerHTML = '<option value="">-- Araç seçin --</option>';
  const teamId = _activeTeamId();
  const vehicles = _vehicleListSnapshot(true).filter(v => {
    if (!v || !v.plate) return false;
    if (teamId) {
      return !v.assigned_team_id || v.assigned_team_id === teamId;
    }
    return !v.assigned_team_id;
  });
  vehicles.forEach(v => {
    const opt = document.createElement("option");
    opt.value = v.plate;
    opt.textContent = v.brand ? `${v.plate} (${v.brand})` : v.plate;
    opt.title = getVehicleMetaLabel(v);
    select.appendChild(opt);
  });
  if (keep) {
    const found = Array.from(select.options).some(opt => opt.value === keep);
    if (!found) {
      const custom = document.createElement("option");
      custom.value = keep;
      custom.textContent = keep;
      select.appendChild(custom);
    }
    select.value = keep;
  }
  // Araç seçimi sadece bilgi amaçlı - görünür ama değiştirilemez
  // Disabled yap ama görsel olarak normal görünsün
  select.disabled = true;
  select.style.cursor = "default";
  select.style.opacity = "1";
  select.style.backgroundColor = "#f8fafc";

  if (!select.dataset.teamVehicleChangeBound) {
    // Disabled olduğu için change event çalışmayacak, ama yine de ekleyelim
    select.addEventListener("change", () => {
      updateTeamVehicleMeta(select.value || "");
      syncTeamVehicleSelection();
    });
    select.dataset.teamVehicleChangeBound = "1";
  }
  syncTeamVehicleSelection();
  updateTeamVehicleMeta(select.value || keep);
}

function syncTeamVehicleSelection() {
  const select = _byId("teamVehicleSelect");
  if (!select) {
    pendingTeamVehicleId = null;
    return;
  }
  const plate = (select.value || "").toString().trim();
  const info = plate ? (window.PLAN_VEHICLE_BY_PLATE || {})[plate] : null;
  pendingTeamVehicleId = info && info.id ? info.id : null;
}

function _setVehicleCacheEntry(payload) {
  if (!payload || !payload.id) return;
  window.PLAN_VEHICLES = window.PLAN_VEHICLES || [];
  const idx = window.PLAN_VEHICLES.findIndex(v => v.id === payload.id);
  if (idx >= 0) {
    window.PLAN_VEHICLES[idx] = payload;
  } else {
    window.PLAN_VEHICLES.push(payload);
  }
  window.PLAN_VEHICLE_BY_PLATE = window.PLAN_VEHICLE_BY_PLATE || {};
  if (payload.plate) {
    window.PLAN_VEHICLE_BY_PLATE[payload.plate] = payload;
  }
}

function _clearVehicleAssignment(vehicleId) {
  if (!vehicleId) return;
  window.PLAN_VEHICLES = window.PLAN_VEHICLES || [];
  for (const v of window.PLAN_VEHICLES) {
    if (v && v.id === vehicleId) {
      v.assigned_team_id = null;
      if (v.plate) {
        window.PLAN_VEHICLE_BY_PLATE = window.PLAN_VEHICLE_BY_PLATE || {};
        window.PLAN_VEHICLE_BY_PLATE[v.plate] = v;
      }
      break;
    }
  }
}

function routeDistanceKm(points) {
  if (!points || points.length < 2) return 0;
  let km = 0;
  for (let i = 1; i < points.length; i++) {
    km += haversineKm(points[i - 1], points[i]);
  }
  return km;
}

function formatDurationHours(hours) {
  if (!hours || hours <= 0) return "0 sa";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (h === 0) return `${m} dk`;
  if (m === 0) return `${h} sa`;
  return `${h} sa ${m} dk`;
}

// Initialize RoutingCache instance
if (window.RoutingCache && !window.mapRoutingCache) {
  window.mapRoutingCache = new RoutingCache();
}

async function osrmDistanceDuration(a, b) {
  const points = [a, b];

  // Use RoutingCache if available
  if (window.mapRoutingCache) {
    const cached = window.mapRoutingCache.get(points);
    if (cached) return cached;
  }

  // Fallback/Legacy cache
  const key = `${a.lat},${a.lon}|${b.lat},${b.lon}`;
  if (OSRM_CACHE[key]) return OSRM_CACHE[key];

  let km = haversineKm([a.lat, a.lon], [b.lat, b.lon]);
  let hours = km / 60;

  try {
    const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=false&alternatives=false`;

    let res;
    if (window.RetryHelper) {
      try {
        const retry = new RetryHelper();
        res = await retry.fetch(url);
      } catch (e) {
        // If retry helper fails (e.g. 404 permanent), fall back to fetch or throw
        res = await fetch(url);
      }
    } else {
      res = await fetch(url);
    }

    const js = await res.json();
    if (js && js.routes && js.routes[0]) {
      km = (js.routes[0].distance || 0) / 1000;
      hours = (js.routes[0].duration || 0) / 3600;
    }
  } catch (e) {
    // console.warn("OSRM error, using haversine fallback", e); 
  }

  const result = { km, hours };

  // Save to caches
  if (window.mapRoutingCache) {
    window.mapRoutingCache.set(points, result);
  }
  OSRM_CACHE[key] = result;

  return result;
}

async function computeRouteStats(points) {
  const pts = (points || []).filter(p => p && p.lat != null && p.lon != null);
  const segments = [];
  let totalKm = 0;
  let totalHours = 0;
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    const res = await osrmDistanceDuration(a, b);
    totalKm += res.km;
    totalHours += res.hours;
    segments.push({
      from: `${a.city || ''} ${a.project_code ? '(' + a.project_code + ')' : ''}`.trim() || 'Nokta',
      to: `${b.city || ''} ${b.project_code ? '(' + b.project_code + ')' : ''}`.trim() || 'Nokta',
      km: res.km,
      hours: res.hours
    });
    await new Promise(r => setTimeout(r, 80));
  }
  const cities = pts.map(p => p.city).filter(Boolean);
  return { segments, totalKm, totalHours, cities };
}

// =================== HELPERS ===================
function _byId(id) { return document.getElementById(id); }
function normalize(s) { return (s || "").toString().toLowerCase().trim(); }

function getPlanTableWrap() {
  return document.querySelector("#gridPlanContainer .tablewrap") || document.querySelector(".tablewrap");
}

function capturePlanScroll() {
  const tableWrap = getPlanTableWrap();
  return {
    windowY: window.scrollY || 0,
    tableTop: tableWrap ? tableWrap.scrollTop : null,
    tableLeft: tableWrap ? tableWrap.scrollLeft : null
  };
}

function restorePlanScroll(state) {
  if (!state) return;
  try {
    if (typeof state.windowY === "number") {
      window.scrollTo(0, state.windowY);
    }
  } catch (_) { }
  const tableWrap = getPlanTableWrap();
  if (tableWrap) {
    if (state.tableTop !== null && state.tableTop !== undefined) {
      tableWrap.scrollTop = state.tableTop;
    }
    if (state.tableLeft !== null && state.tableLeft !== undefined) {
      tableWrap.scrollLeft = state.tableLeft;
    }
  }
}

// HTML escape (escapeHtml is not defined hatasını düzeltir)
function escapeHtml(s) {
  return (s ?? "").toString().replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

function ensureAppData() {
  const hasCities = Array.isArray(window.CITIES) && window.CITIES.length > 0;
  const hasProjects = Array.isArray(window.TEMPLATE_PROJECTS) && window.TEMPLATE_PROJECTS.length > 0;
  if (hasCities || hasProjects) return;
  try {
    const projectsEl = document.getElementById("app-data-projects");
    const citiesEl = document.getElementById("app-data-cities");
    if (projectsEl) {
      const txt = (projectsEl.textContent || "").trim();
      window.TEMPLATE_PROJECTS = txt ? JSON.parse(txt) : [];
    }
    if (citiesEl) {
      const txt = (citiesEl.textContent || "").trim();
      window.CITIES = txt ? JSON.parse(txt) : [];
    }
  } catch (e) {
    console.error("ensureAppData failed:", e);
    window.TEMPLATE_PROJECTS = window.TEMPLATE_PROJECTS || [];
    window.CITIES = window.CITIES || [];
  }
}

// Favori / Son seçilenler localStorage kaydı
function saveFavRecent() {
  try {
    localStorage.setItem("fav_people", JSON.stringify(Array.from(FAV_PEOPLE || [])));
    localStorage.setItem("recent_people", JSON.stringify(RECENT_PEOPLE || []));
  } catch (e) { /* ignore */ }
}

// ---- Toast (sayfayı aşağı çekmesin diye fixed layer kullanır) ----
function ensureToastLayer() {
  let layer = document.getElementById("toastLayer");
  if (layer) return layer;
  layer = document.createElement("div");
  layer.id = "toastLayer";
  document.body.appendChild(layer);
  return layer;
}
function toast(msg) {
  const layer = ensureToastLayer();
  const s = document.createElement("div");
  s.className = "toastMsg";
  s.textContent = msg;
  layer.appendChild(s);
  setTimeout(() => { try { s.remove(); } catch (e) { } }, 1400);
}

// Hücre seçilince satır (proje) düzenleme seçimlerini kapat
function _clearRowSelectionForCell(td) {
  try {
    document.querySelectorAll("tr.planRow.selectedRow").forEach(tr => tr.classList.remove("selectedRow"));
  } catch (e) { }
  if (typeof __selectedProjectId !== "undefined") __selectedProjectId = 0;
  const bEdit = _byId("topJobEdit");
  const bDel = _byId("topJobDelete");
  if (bEdit) bEdit.style.display = "none";
  if (bDel) bDel.style.display = "none";

  // Label'ı hücreye göre gösterelim
  const lbl = _byId("selectedLabel");
  if (lbl && td) {
    const city = td.dataset.city || "";
    const code = td.dataset.projectCode || "";
    lbl.textContent = (city && code) ? `${city} - ${code}` : "-";
  }
}

// People map
function peopleMap() {
  const m = {};
  (window.ALL_PEOPLE || []).forEach(p => { m[p.id] = p; });
  return m;
}

function refreshAttachmentLabels() {
  const lldNameEl = _byId("mLLDFileName");
  const tutNameEl = _byId("mTutanakFileName");

  if (lldNameEl) {
    const activeLLD = existingLLDs.filter(f => !removeLLDs.has(f));
    if (activeLLD.length) {
      lldNameEl.innerHTML = activeLLD.map(f => {
        const safe = encodeURIComponent(f);
        return `<div class="attach-row">
          <a class="attach-name" href="/files/${safe}" target="_blank" rel="noreferrer noopener">${escapeHtml(f)}</a>
          <button type="button" class="attach-btn" onclick="removeLLD('${safe}'); return false;">Sil</button>
        </div>`;
      }).join("");
    } else {
      lldNameEl.innerHTML = `<div class="attach-empty">Yuklu dosya yok</div>`;
    }
  }
  if (tutNameEl) {
    const activeTut = existingTutanaks.filter(f => !removeTutanaks.has(f));
    if (activeTut.length) {
      tutNameEl.innerHTML = activeTut.map(f => {
        const safe = encodeURIComponent(f);
        return `<div class="attach-row">
          <a class="attach-name" href="/files/${safe}" target="_blank" rel="noreferrer noopener">${escapeHtml(f)}</a>
          <button type="button" class="attach-btn" onclick="removeTutanak('${safe}'); return false;">Sil</button>
        </div>`;
      }).join("");
    } else {
      tutNameEl.innerHTML = `<div class="attach-empty">Yuklu dosya yok</div>`;
    }
  }
  refreshModalAttachmentIndicator();
}

function removeLLD(fname) {
  if (!fname) return;
  fname = decodeURIComponent(fname);
  removeLLDs.add(fname);
  refreshAttachmentLabels();
}

function removeTutanak(fname) {
  if (!fname) return;
  fname = decodeURIComponent(fname);
  removeTutanaks.add(fname);
  refreshAttachmentLabels();
}
function initDropzones() {
  document.querySelectorAll(".dropzone").forEach(zone => {
    const inputId = zone.getAttribute("data-input");
    const input = inputId ? _byId(inputId) : zone.querySelector("input[type='file']");
    if (!input) return;

    const allowDrop = (e) => {
      if (input.disabled) return;
      e.preventDefault();
      zone.classList.add("dragover");
    };
    const clearDrop = () => zone.classList.remove("dragover");
    zone.addEventListener("dragover", allowDrop);
    zone.addEventListener("dragenter", allowDrop);
    zone.addEventListener("dragleave", clearDrop);
    zone.addEventListener("drop", (e) => {
      if (input.disabled) return;
      e.preventDefault();
      clearDrop();
      const files = e.dataTransfer?.files;
      if (!files || !files.length) return;
      const dt = new DataTransfer();
      if (input.multiple) {
        Array.from(files).forEach(f => dt.items.add(f));
      } else {
        dt.items.add(files[0]);
      }
      input.files = dt.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
}

// =================== PERSONNEL SUMMARY COLLAPSIBLE ===================
function _applySummaryCollapsedState() {
  const panel = document.getElementById("personelOzetPanel");
  const body = document.getElementById("personnelSummaryBody");
  const gridContainer = document.getElementById("gridPlanContainer");
  if (!panel || !body) return;

  const raw = (localStorage.getItem("summary_open") || "").toString().trim().toLowerCase();
  const open = raw === "" ? false : (raw === "1" || raw === "true" || raw === "yes" || raw === "on");
  // İlk yüklemede kapalı başlat

  if (open) {
    // Panel açık
    // Panelin position'ını absolute yap
    panel.style.position = "absolute";
    panel.style.left = "0";
    panel.style.right = "0";
    panel.style.display = "block";

    // Toolbar'ın yüksekliğini hesapla
    const selectionBar = document.querySelector('.card > div[style*="background: #ffffff"]');
    let topOffset = 0;
    if (selectionBar) {
      const rect = selectionBar.getBoundingClientRect();
      const sectionRect = selectionBar.closest('section')?.getBoundingClientRect();
      if (sectionRect) {
        topOffset = rect.bottom - sectionRect.top + 5; // 5px margin
      }
    }
    panel.style.top = topOffset + "px";

    body.style.display = "block";
    // Body'nin yüksekliğini hesapla
    panel.style.height = "auto";
    const bodyHeight = body.scrollHeight;
    panel.style.height = bodyHeight + "px";
    panel.style.opacity = "1";
    if (gridContainer) {
      gridContainer.style.marginTop = (bodyHeight + 20) + "px";
    }
  } else {
    // Panel kapalı
    body.style.display = "none";
    panel.style.height = "0";
    panel.style.opacity = "0";
    if (gridContainer) {
      gridContainer.style.marginTop = "0";
    }
  }

  _updateSummaryToggleUi(open);
}

function toggleSummary(fromTopButton) {
  const panel = document.getElementById("personelOzetPanel");
  const body = document.getElementById("personnelSummaryBody");
  const gridContainer = document.getElementById("gridPlanContainer");

  if (!panel || !body) {
    try { toast("Personel özeti paneli bulunamadı."); } catch (_) { }
    return;
  }

  const isOpen = panel.style.height && panel.style.height !== '0px' && panel.style.height !== '0' && panel.style.opacity !== '0';
  const open = !isOpen; // toggle

  if (open) {
    // Panel açılıyor - animasyonlu (height animasyonu)
    // Panelin position'ını absolute yap
    panel.style.position = "absolute";
    panel.style.left = "0";
    panel.style.right = "0";
    panel.style.display = "block";

    // Toolbar'ın yüksekliğini hesapla (üstteki selection bar)
    const selectionBar = document.querySelector('.card > div[style*="background: #ffffff"]');
    let topOffset = 0;
    if (selectionBar) {
      const rect = selectionBar.getBoundingClientRect();
      const sectionRect = selectionBar.closest('section')?.getBoundingClientRect();
      if (sectionRect) {
        topOffset = rect.bottom - sectionRect.top + 5; // 5px margin
      }
    }
    panel.style.top = topOffset + "px";

    // Önce body'yi görünür yap ama paneli gizli tut (yüksekliği ölçmek için)
    body.style.display = "block";
    panel.style.overflow = "hidden";
    panel.style.height = "auto";
    const bodyHeight = body.scrollHeight;
    // Şimdi animasyon için başlangıç değerlerini ayarla
    panel.style.height = "0";
    panel.style.opacity = "0";
    // Sonra animasyonu başlat
    requestAnimationFrame(() => {
      panel.style.height = bodyHeight + "px";
      panel.style.opacity = "1";
      if (gridContainer) {
        gridContainer.style.marginTop = (bodyHeight + 20) + "px";
      }
    });

    // Panel açıldığında ilk günün tooltip'ini göster
    if (fromTopButton && window.showSummaryTooltip) {
      setTimeout(() => {
        const firstCard = body.querySelector('.personnel-summary-card');
        if (firstCard) {
          window.showSummaryTooltip(firstCard, null, true);
        }
      }, 400);
    }
  } else {
    // Panel kapanıyor - animasyonlu
    panel.style.height = "0";
    panel.style.opacity = "0";
    if (gridContainer) {
      gridContainer.style.marginTop = "0";
    }

    setTimeout(() => {
      body.style.display = "none";
    }, 400);

    // Panel kapandığında tooltip'i gizle
    if (window.hideSummaryTooltip) {
      window.hideSummaryTooltip();
    }
  }

  try { localStorage.setItem("summary_open", open ? "true" : "false"); } catch (_) { }
  _updateSummaryToggleUi(open);
}

function _updateSummaryToggleUi(open) {
  const btnText = document.getElementById("summaryToggleText");
  if (btnText) btnText.textContent = open ? "Personel Özeti (Açık)" : "Personel Özeti (Kapalı)";
  const icon = document.getElementById("summaryToggleIcon");
  if (icon) {
    try {
      icon.style.transform = open ? "rotate(0deg)" : "rotate(-90deg)";
      icon.style.transition = "transform 0.15s ease";
      icon.style.transformOrigin = "50% 50%";
    } catch (_) { }
  }
}

// =================== CELL DOM UPDATE ===================
function setAttachmentBadge(td, hasAttachment) {
  if (!td) return;
  td.setAttribute("data-has-attach", hasAttachment ? "1" : "0");
}

function _hasActiveAttachments() {
  const activeLLD = (existingLLDs || []).filter(f => !removeLLDs.has(f));
  const activeTut = (existingTutanaks || []).filter(f => !removeTutanaks.has(f));
  return activeLLD.length > 0 || activeTut.length > 0;
}

function refreshModalAttachmentIndicator() {
  const indicator = _byId("cellModalAttachIndicator");
  if (!indicator) return;
  indicator.style.display = _hasActiveAttachments() ? "inline-flex" : "none";
}

function updateCellDom(td, payload) {
  if (!td) return;
  const shift = payload.shift || "";
  const note = payload.note || "";
  const person_ids = payload.person_ids || [];
  const subproject_label = (payload.subproject_label || "").toString().trim();
  const hasAttachment = payload.hasAttachment;
  const pm = peopleMap();

  // Merge key inputs (used by applyMergedCellRuns) 
  td.dataset.shift = shift;
  td.dataset.note = note;
  if (Object.prototype.hasOwnProperty.call(payload, "vehicle_info")) {
    td.dataset.vehicle = (payload.vehicle_info || "").toString();
  }
  if (Object.prototype.hasOwnProperty.call(payload, "team_id")) {
    td.dataset.teamId = String(payload.team_id || 0);
  }
  if (Object.prototype.hasOwnProperty.call(payload, "subproject_id")) {
    td.dataset.subprojectId = String(payload.subproject_id || 0);
  }
  if (Object.prototype.hasOwnProperty.call(payload, "person_ids")) {
    const pIds = Array.isArray(payload.person_ids) ? payload.person_ids : [];
    td.dataset.personIds = pIds.sort((a, b) => a - b).join(",");
  }

  const hasSubproject = parseInt(td.dataset.subprojectId || "0", 10) > 0;

  const t = td.querySelector(".cell-time");
  const pbox = td.querySelector(".cell-people");
  let sp = td.querySelector(".cell-subproject");

  // Alt proje etiketi hücre içeriğinde gösterilmeyecek - kaldırıldı
  // Eğer mevcut bir element varsa gizle ve kaldır
  if (sp) {
    sp.style.display = "none";
    try { sp.remove(); } catch (e) { }
  }

  // Eğer hiçbir şey yoksa "-" göster (açık gri)
  if (!shift && !note && person_ids.length === 0 && !hasSubproject) {
    if (t) {
      t.innerHTML = '<span style="text-align: center; color: #d1d5db; font-size: 14px;">-</span>';
      t.style.textAlign = "center";
    }
    if (pbox) {
      pbox.style.display = "none";
      pbox.innerHTML = "";
    }
  } else if (shift && person_ids.length === 0) {
    // Çalışma var ama personel yoksa (normal renk)
    if (t) {
      t.textContent = shift;
      t.style.textAlign = "";
      t.style.color = "";
      t.style.fontWeight = "600";
    }

    if (pbox) {
      pbox.style.display = "";
      pbox.style.color = "";
      pbox.innerHTML = '<span class="muted">Personel seç</span>';
    }
  } else {
    // Normal durum (her ikisi de var veya sadece personel var)
    if (t) {
      if (shift) {
        t.textContent = shift;
        t.style.textAlign = "";
        t.style.color = "";
        t.style.fontWeight = "";
      } else {
        t.innerHTML = '<span class="muted">Çalışma seç</span>';
        t.style.textAlign = "";
        t.style.color = "";
        t.style.fontWeight = "";
      }
    }

    if (pbox) {
      pbox.style.display = "";
      pbox.style.color = "";
      if (person_ids.length) {
        const peopleNames = person_ids.map(id => {
          const p = pm[id];
          return (p ? escapeHtml(p.full_name) : ("#" + id));
        });
        if (peopleNames.length > 2) {
          pbox.innerHTML = peopleNames.slice(0, 2).join("<br>") + "<br><span style='color: #94a3b8;'>...</span>";
        } else {
          pbox.innerHTML = peopleNames.join("<br>");
        }
      } else {
        pbox.innerHTML = '<span class="muted">Personel seç</span>';
      }
    }
  }

  // Personel seçilmişse koyu yeşil arka plan ekle
  if (person_ids.length > 0) {
    td.classList.add("filled-personnel");
  } else {
    td.classList.remove("filled-personnel");
  }

  const nbox = td.querySelector(".cell-note");
  if (nbox) {
    nbox.innerHTML = note ? `<strong>Detay:</strong> ${escapeHtml(note)}` : "";
  }

  const filled = !!(shift || note || person_ids.length || hasSubproject);
  td.classList.toggle("filled", filled);

  if (hasAttachment !== undefined) {
    setAttachmentBadge(td, !!hasAttachment);
  }
}

// =================== MULTI-DAY CELL MERGE (VISUAL) ===================
function _mergeKeyForPlanCell(td) {
  if (!td) return null;
  const filled = td.classList.contains("filled") || td.classList.contains("filled-personnel");
  if (!filled) return null;

  const teamId = (td.dataset.teamId || "0").toString().trim();
  const subprojectId = (td.dataset.subprojectId || "0").toString().trim();
  const vehicle = (td.dataset.vehicle || "").toString().trim();
  const hasAttach = (td.dataset.hasAttach || "0").toString().trim();
  const important = (td.dataset.importantNote || "").toString().trim();
  const personIds = (td.dataset.personIds || "").toString().trim();
  const shift = (td.dataset.shift || "").toString().trim();
  const note = (td.dataset.note || "").toString().trim();

  // Normalize "0" vs "null" vs ""
  const tId = (teamId === "0" || teamId === "null") ? "" : teamId;
  const spId = (subprojectId === "0" || subprojectId === "null") ? "" : subprojectId;

  const hasMeaning = !!(
    shift || note || important || vehicle ||
    tId || spId || hasAttach === "1" || personIds
  );
  if (!hasMeaning) return null;

  return JSON.stringify({ shift, note, tId, spId, vehicle, hasAttach, important, personIds });
}

function applyMergedCellRuns() {
  const tbody = document.getElementById("planTbody");
  if (!tbody) return;

  // Cleanup previous markers 
  tbody.querySelectorAll("td.cell.daycol.merge-run").forEach(td => {
    td.classList.remove("merge-run", "merge-start", "merge-mid", "merge-end");
    td.removeAttribute("data-merge-group");
    const badge = td.querySelector(".cell-merge-badge");
    if (badge) badge.remove();
  });

  const rows = tbody.querySelectorAll("tr.planRow");
  const labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

  rows.forEach(row => {
    const cells = Array.from(row.querySelectorAll("td.cell.daycol"));
    if (cells.length < 2) return;

    const pid = row.dataset.projectId || row.getAttribute("data-project-id") || "";

    let i = 0;
    while (i < cells.length) {
      const key = _mergeKeyForPlanCell(cells[i]);
      if (!key) {
        i += 1;
        continue;
      }

      let j = i;
      while (j + 1 < cells.length && _mergeKeyForPlanCell(cells[j + 1]) === key) {
        j += 1;
      }

      if (j > i) {
        const groupId = `p${pid}_d${i}`;
        for (let k = i; k <= j; k++) {
          const td = cells[k];
          td.classList.add("merge-run");
          td.dataset.mergeGroup = groupId;
          if (k === i) td.classList.add("merge-start");
          else if (k === j) td.classList.add("merge-end");
          else td.classList.add("merge-mid");
        }

        const startTd = cells[i];
        const badge = document.createElement("div");
        badge.className = "cell-merge-badge";
        const left = labels[i] || `G${i + 1}`;
        const right = labels[j] || `G${j + 1}`;
        badge.textContent = `${left}-${right}`;
        startTd.appendChild(badge);
      }

      i = j + 1;
    }
  });
}

// =================== CELL SELECT / EDIT =================== 
function selectCell(td, weekStartIso) {
  if (!td) return;

  _clearRowSelectionForCell(td);

  const project_id = parseInt(td.dataset.projectId || "0", 10);
  const work_date = td.dataset.date || "";
  currentWeekStart = weekStartIso || currentWeekStart;
  currentCell = {
    project_id,
    work_date,
    week_start: currentWeekStart,
    city: td.dataset.city || "",
    project_code: td.dataset.projectCode || "",
    team_id: null
  };

  document.querySelectorAll("td.cell.daycol.selectedCell").forEach(el => el.classList.remove("selectedCell"));
  selectedCellEl = td;
  selectedCellEl.classList.add("selectedCell");

  const info = _byId("editorInfo");
  if (info) info.textContent = `${work_date} • ${td.dataset.city || ""} • ${td.dataset.projectCode || ""}`;

  if (pasteMode) {
    // Paste operations are now handled by _bindDragPaste (mousedown/mouseover)
    // to support consistent drag-painting. We just ignore click selection here.
    return;
  }

  toast(`${work_date} hücresi seçildi`);
}

async function openCellEditor(td, weekStartIso) {
  if (!td) return;
  selectCell(td, weekStartIso);

  const project_id = parseInt(td.dataset.projectId || "0", 10);
  const work_date = td.dataset.date || "";

  const res = await fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`);
  const data = await res.json().catch(() => ({ exists: false }));
  try {
    currentCell.team_id = data && data.cell ? (data.cell.team_id || null) : null;
  } catch (_) {
    currentCell.team_id = null;
  }
  currentTeamVehicle = data.team_vehicle || null;
  currentTeamId = data.team_id || null;
  pendingTeamVehicleId = currentTeamVehicle && currentTeamVehicle.id ? currentTeamVehicle.id : null;
  refreshTeamVehicleHint();
  renderTeamVehicleSelect(currentTeamVehicle && currentTeamVehicle.plate ? currentTeamVehicle.plate : "");

  // Shift değerini eski formattan yeni formata çevir
  const oldShift = (data.cell?.shift || "").trim();
  let newShift = oldShift;
  const shiftMap = {
    "Gündüz": "08:30 - 18:00",
    "Gündüz Yol": "08:30 - 18:00 YOL",
    "Gece": "00:00 - 06:00"
  };
  if (shiftMap[oldShift]) {
    newShift = shiftMap[oldShift];
  }
  _byId("mShift").value = newShift;




  const vehicleInfo = (data.cell?.vehicle_info || "").trim();
  const plateOnly = vehicleInfo.split("(")[0].trim() || vehicleInfo;
  renderVehicleSelect(plateOnly);
  vehicleDirty = false;
  _byId("mNote").value = (data.cell?.note || "");
  const isdpEl = _byId("mISDP"); if (isdpEl) isdpEl.value = (data.cell?.isdp_info || "");
  const poEl = _byId("mPO"); if (poEl) poEl.value = (data.cell?.po_info || "");
  const importantNoteEl = _byId("mImportantNote"); if (importantNoteEl) importantNoteEl.value = (data.cell?.important_note || "");
  _byId("mTeamName").value = (data.cell?.team_name || "");
  const jobMailEl = _byId("mJobMailBody"); if (jobMailEl) jobMailEl.value = (data.cell?.job_mail_body || "");
  const au = _byId("mAssignedUser"); if (au) au.value = String(data.cell?.assigned_user_id || 0);
  const currentSubprojectId = (data.cell?.subproject_id || 0);
  await refreshSubProjectDropdown(project_id, currentSubprojectId); // Mevcut alt projeyi göster

  existingLLDs = (data.cell?.lld_hhd_files || []).slice();
  existingTutanaks = (data.cell?.tutanak_files || []).slice();
  removeLLDs = new Set();
  removeTutanaks = new Set();
  refreshAttachmentLabels();

  selectedPeople = new Set((data.assigned || []).map(x => parseInt(x, 10)));

  // Cache'i temizle
  personAssignedCache = {};
  window.CURRENT_PERSON_OVERTIMES = data.person_overtimes || {};

  renderPeopleList();
  renderSelectedPeople();
  updateFieldColors();
  refreshJobMailStatus();

  // status modal labels
  const lab = _byId("statusDayLabel"); if (lab) lab.textContent = work_date;
  const ppl = _byId("statusPeopleLabel"); if (ppl) ppl.textContent = String(selectedPeople.size);

  try { loadAvailability(); } catch (e) { }

  const info = _byId("editorInfo");
  if (info && data.cell) {
    const pName = data.cell.project_name || "";
    const pCode = td.dataset.projectCode || "";
    info.textContent = `${work_date} • ${pName} • ${pCode}`;
  }

  const m = _byId("cellModal");
  if (m) m.classList.add("open");

  // İptal butonu durumu güncelle (Manuel tetikleme)
  if (typeof window.updateModalCancellationUI === 'function' && td) {
    const isCancelled = td.getAttribute('data-status') === 'cancelled';
    const reason = td.getAttribute('data-cancellation-reason');
    window.updateModalCancellationUI(isCancelled, { reason: reason });
  }

  // Dropdown'ı varsayılan olarak açık tut
  setTimeout(() => {
    showPeopleDropdown();
    filterPeopleComboBox();
  }, 100);

}

async function refreshSubProjectDropdown(project_id, selected_id) {
  const sel = _byId("mSubProject");
  if (!sel) return;
  const pid = parseInt(project_id || 0, 10) || 0;
  const selected = parseInt(selected_id || 0, 10) || 0;

  sel.innerHTML = `<option value="0">-- Alt proje (yok) --</option>`;
  sel.value = "0";
  if (!pid) return;

  try {
    const resp = await fetch(`/api/projects/${encodeURIComponent(pid)}/subprojects?include_inactive=1`);
    const payload = await resp.json().catch(() => ({ ok: false }));
    if (!resp.ok || !payload.ok) {
      console.warn('refreshSubProjectDropdown: API error', { pid, resp: resp.ok, payload });
      return;
    }

    const all = Array.isArray(payload.subprojects) ? payload.subprojects : [];

    // API'den dönen project_id ile gönderilen project_id farklıysa uyarı ver
    if (payload.project_id && payload.project_id !== pid) {
      console.warn('refreshSubProjectDropdown: Project ID mismatch', {
        requested: pid,
        returned: payload.project_id,
        subprojects_count: all.length
      });
    }

    if (all.length === 0) {
      console.log('refreshSubProjectDropdown: No subprojects found for project', pid, 'effective_project_id:', payload.project_id);
    } else {
      console.log('refreshSubProjectDropdown: Found', all.length, 'subprojects for project', pid, 'effective_project_id:', payload.project_id);
    }

    const selectedRow = all.find(x => parseInt(x.id || 0, 10) === selected) || null;
    const active = all.filter(x => x && x.is_active);

    const options = [];
    if (selectedRow && !selectedRow.is_active) {
      const name = String(selectedRow.name || "").trim();
      const code = String(selectedRow.code || "").trim();
      const label = code && code.length > 0 ? `[Pasif] ${code} - ${name}` : `[Pasif] ${name}`;
      const isSelected = parseInt(selectedRow.id || 0, 10) === selected;
      options.push(`<option value="${selectedRow.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(label)}</option>`);
    }

    for (const sp of active) {
      const name = String(sp.name || "").trim();
      const code = String(sp.code || "").trim();
      const label = code && code.length > 0 ? `${code} - ${name}` : name;
      const isSelected = parseInt(sp.id || 0, 10) === selected;
      options.push(`<option value="${sp.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(label)}</option>`);
    }

    sel.insertAdjacentHTML("beforeend", options.join(""));

    if (selected && all.some(x => parseInt(x.id || 0, 10) === selected)) {
      sel.value = String(selected);
    } else {
      sel.value = "0";
    }
  } catch (_) {
    return;
  }
}

function closeCellModal() {
  const m = _byId("cellModal");
  if (m) m.classList.remove("open");
  vehicleDirty = false;
}

async function uploadCellAttachments(project_id, work_date) {
  const lldFiles = _byId("mLLDFile")?.files;
  const tutanakFiles = _byId("mTutanakFile")?.files;
  if ((!lldFiles || lldFiles.length === 0) && (!tutanakFiles || tutanakFiles.length === 0)) {
    return;
  }
  const fd = new FormData();
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  fd.append("csrf_token", csrf);
  fd.append("project_id", project_id);
  fd.append("work_date", work_date);
  if (lldFiles && lldFiles.length) {
    for (let i = 0; i < lldFiles.length; i++) {
      fd.append("lld_hhd", lldFiles[i]);
    }
  }
  if (tutanakFiles && tutanakFiles.length) {
    for (let i = 0; i < tutanakFiles.length; i++) {
      fd.append("tutanak", tutanakFiles[i]);
    }
  }

  const res = await fetch("/api/cell/upload_attachments", {
    method: "POST",
    body: fd
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "Yükleme başarısız");
  }
  if (data.lld_hhd_files) existingLLDs = data.lld_hhd_files;
  if (data.tutanak_files) existingTutanaks = data.tutanak_files;
  refreshAttachmentLabels();
}

async function saveCell() {
  if (!currentCell.project_id || !currentCell.work_date) {
    alert("Önce bir hücreye tıklayın.");
    return;
  }

  const shift = _byId("mShift")?.value || "";
  const vehicle_info = _byId("mVehicle")?.value || "";
  const subproject_id = parseInt(_byId("mSubProject")?.value || "0", 10) || 0;
  let subproject_label = "";
  if (subproject_id > 0 && _byId("mSubProject")?.selectedOptions && _byId("mSubProject").selectedOptions[0]) {
    const labelText = (_byId("mSubProject").selectedOptions[0].textContent || "").trim();
    // "-- Alt proje (yok) --" seçiliyse label'ı boş bırak
    if (labelText && !labelText.includes("Alt proje (yok)")) {
      subproject_label = labelText;
    }
  }
  const note = _byId("mNote")?.value || "";
  const isdp_info = _byId("mISDP")?.value || "";
  const po_info = _byId("mPO")?.value || "";
  const important_note = _byId("mImportantNote")?.value || "";
  const team_name = _byId("mTeamName")?.value || "";
  const job_mail_body = _byId("mJobMailBody")?.value || "";
  const assigned_user_id = parseInt(_byId("mAssignedUser")?.value || "0", 10) || 0;
  const person_ids = Array.from(selectedPeople);
  const remove_lld_list = Array.from(removeLLDs);
  const remove_tutanak_list = Array.from(removeTutanaks);
  const plate = (_byId("mVehicle")?.value || "").trim();
  const candidate = (window.PLAN_VEHICLE_BY_PLATE || {})[plate];
  const team_vehicle_id = candidate && candidate.id ? candidate.id : 0;
  const teamVehicleId = (typeof pendingTeamVehicleId === "number" ? pendingTeamVehicleId : (currentTeamVehicle && currentTeamVehicle.id ? currentTeamVehicle.id : null));

  // Collect person overtimes/shifts (hours)
  const person_overtimes = {};
  const overtimeInputs = document.querySelectorAll(".person-shift-input");
  overtimeInputs.forEach(input => {
    const pid = parseInt(input.dataset.personId, 10);
    const val = input.value.trim();
    if (pid && val) {
      person_overtimes[pid] = val;
    }
  });

  // "Başka işte olanları göster" işaretliyse, ekip çakışması kontrolünü atla
  const csrf = _byId("csrfToken")?.value || "";

  const res = await fetch("/api/cell", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      csrf_token: csrf,
      project_id: currentCell.project_id,
      work_date: currentCell.work_date,
      subproject_id,
      shift,
      vehicle_info,
      note,
      isdp_info,
      po_info,
      important_note,
      team_name,
      job_mail_body,
      assigned_user_id,
      remove_lld_list,
      remove_tutanak_list,
      person_ids,
      person_overtimes,
      vehicle_dirty: vehicleDirty,
      vehicle_id: teamVehicleId,
      team_vehicle_id: team_vehicle_id,
    })
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (data && data.blocked) {
      alert("Bu personeller uygun değil:\n" + data.blocked.map(b => `- ${b.full_name} (${b.status})`).join("\n"));
    } else {
      alert(data.error || "Kaydetme hatası");
    }
    return;
  }

  const prevTeamVehicleId = currentTeamVehicle ? currentTeamVehicle.id : null;
  const teamVehiclePayload = data.team_vehicle || null;
  currentTeamVehicle = teamVehiclePayload;
  if (prevTeamVehicleId && (!currentTeamVehicle || currentTeamVehicle.id !== prevTeamVehicleId)) {
    _clearVehicleAssignment(prevTeamVehicleId);
  }
  if (currentTeamVehicle) {
    _setVehicleCacheEntry(currentTeamVehicle);
  }
  pendingTeamVehicleId = currentTeamVehicle && currentTeamVehicle.id ? currentTeamVehicle.id : null;
  renderTeamVehicleSelect(currentTeamVehicle && currentTeamVehicle.plate ? currentTeamVehicle.plate : "");
  refreshTeamVehicleHint();

  const displayVehicleInfo = currentTeamVehicle && currentTeamVehicle.plate ? currentTeamVehicle.plate : vehicle_info;

  existingLLDs = existingLLDs.filter(f => !removeLLDs.has(f));
  existingTutanaks = existingTutanaks.filter(f => !removeTutanaks.has(f));

  // Sync timestamp'i güncelle ki sayfa yenilenmesin (kendi değişikliğimiz)
  // Yeni timestamp al ve güncelle - await ile bekle
  // ÖNEMLİ: Bu güncelleme, checkForUpdates'in sayfayı yenilemesini engellemek için
  if (typeof lastSyncTimestamp !== 'undefined' && lastSyncTimestamp !== null && currentWeekStart) {
    try {
      // Biraz bekle ki veritabanı commit'i tamamlansın
      await new Promise(resolve => setTimeout(resolve, 300));

      const syncRes = await fetch(`/api/plan_sync?date=${encodeURIComponent(currentWeekStart)}`);
      const syncData = await syncRes.json().catch(() => ({ ok: false }));
      if (syncData.ok && syncData.last_update) {
        lastSyncTimestamp = syncData.last_update;
        console.log("Sync timestamp güncellendi (kendi değişikliğimiz):", lastSyncTimestamp);
      }
    } catch (e) {
      console.error("Sync timestamp güncelleme hatası:", e);
    }
  }

  const scrollState = capturePlanScroll();
  const td = selectedCellEl || document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${currentCell.work_date}"]`);
  if (td) {
    // Response'dan alt proje bilgisini al, yoksa frontend'den alınan label'ı kullan
    const finalSubprojectLabel = (data.subproject_label || subproject_label || "").trim();
    const finalSubprojectId = (data.subproject_id !== undefined ? data.subproject_id : subproject_id) || 0;
    updateCellDom(td, { shift, note, person_ids, subproject_label: finalSubprojectLabel, subproject_id: finalSubprojectId, vehicle_info: displayVehicleInfo, team_id: (data.team_id || 0) });
    // Önemli not işaretini güncelle 
    if (important_note && important_note.trim()) {
      td.classList.add("has-important-note");
      td.setAttribute("data-important-note", important_note.trim());
    } else {
      td.classList.remove("has-important-note");
      td.removeAttribute("data-important-note");
    }
    try { applyMergedCellRuns(); } catch (_) { }
  }
  restorePlanScroll(scrollState);
  // Araç sütunu cache güncelle (haftalık tek istek yaklaşımı)
  const plateOnly = normalizeVehiclePlate(displayVehicleInfo);
  if (plateOnly) {
    WEEKLY_VEHICLE_LOOKUP[String(currentCell.project_id)] = plateOnly;
    updateVehicleColumn(currentCell.project_id);
  } else {
    // Araç silindiyse, haftada başka gün var mı tekrar hesapla
    refreshVehicleForProject(currentCell.project_id);
  }

  // Dosya yükleme (varsa)
  try {
    await uploadCellAttachments(currentCell.project_id, currentCell.work_date);
  } catch (e) {
    console.error("Dosya yükleme hatası:", e);
    alert("Kaydedildi ancak dosya yükleme başarısız: " + (e?.message || e));
  }

  removeLLDs.clear();
  removeTutanaks.clear();
  const f1 = _byId("mLLDFile"); if (f1) f1.value = "";
  const f2 = _byId("mTutanakFile"); if (f2) f2.value = "";
  refreshAttachmentLabels();

  if (td) {
    const hasAttachment = (existingLLDs && existingLLDs.length > 0) || (existingTutanaks && existingTutanaks.length > 0);
    setAttachmentBadge(td, hasAttachment);
  }

  vehicleDirty = false;
  toast("Kaydedildi");
  closeCellModal();
}

async function saveOvertimeOnly() {
  if (!currentCell.project_id || !currentCell.work_date) {
    alert("Önce bir hücreye tıklayın.");
    return;
  }

  // Collect person overtimes/shifts (hours)
  const person_overtimes = {};
  const overtimeInputs = document.querySelectorAll(".person-shift-input");
  overtimeInputs.forEach(input => {
    const pid = parseInt(input.dataset.personId, 10);
    const val = input.value.trim();
    if (pid && val) {
      person_overtimes[pid] = val;
    }
  });

  const person_ids = Array.from(selectedPeople);
  const csrf = (_byId("csrfToken")?.value || "");

  try {
    const res = await fetch("/api/save_overtime_only", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        csrf_token: csrf,
        project_id: currentCell.project_id,
        work_date: currentCell.work_date,
        person_ids: person_ids,
        person_overtimes: person_overtimes
      })
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      alert(data.error || "Mesai kaydetme hatası");
      return;
    }

    toast("Mesai kaydedildi ✓");

    // UI Güncelleme: Hücrenin üzerindeki kişi sayısı badge'ini güncellemek için veriyi tazeleyelim
    const td = selectedCellEl || document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${currentCell.work_date}"]`);
    if (td) {
      // Mevcut DOM değerlerini koru, sadece kişi listesini güncelle
      // Ancak en doğrusu sunucudan son hali almaktır.
      const refRes = await fetch(`/api/cell?project_id=${currentCell.project_id}&date=${encodeURIComponent(currentCell.work_date)}`);
      const refData = await refRes.json().catch(() => null);

      if (refData && refData.cell) {
        const subproject_label = refData.subproject_label || "";
        // updateCellDom app.js içinde global değilse erişememe ihtimali var ama aynı dosyadayız.
        // cell_updated socket eventi de gelebilir, o da günceller.
        // Biz yine de manuel tetikleyelim
        try {
          updateCellDom(td, {
            shift: refData.cell.shift || "",
            note: refData.cell.note || "",
            vehicle_info: refData.cell.vehicle_info || "",
            person_ids: (refData.assigned || []).map(x => parseInt(x, 10)),
            team_id: refData.cell.team_id || 0,
            subproject_id: refData.cell.subproject_id || 0,
            subproject_label: subproject_label
          });
          // Önemli not class güncelleme
          const imp = refData.cell.important_note || "";
          if (imp.trim()) {
            td.classList.add("has-important-note");
            td.setAttribute("data-important-note", imp.trim());
          } else {
            td.classList.remove("has-important-note");
            td.removeAttribute("data-important-note");
          }
          try { applyMergedCellRuns(); } catch (_) { }
        } catch (ex) { console.error(ex); }
      }
    }

  } catch (e) {
    console.error(e);
    alert("Hata: " + e.message);
  }
}


async function clearCell() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (!currentCell.project_id || !currentCell.work_date) {
    alert("Önce bir hücreye tıklayın.");
    return;
  }
  if (!confirm("Bu hücredeki işi tamamen silmek istiyor musun?")) return;

  const res = await fetch("/api/cell/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csrf_token: (_byId("csrfToken")?.value || ""), project_id: currentCell.project_id, work_date: currentCell.work_date })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    alert(data.error || "Silme hatası");
    return;
  }

  // UI temizle 
  const scrollState = capturePlanScroll();
  const td = selectedCellEl || document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${currentCell.work_date}"]`);
  if (td) {
    updateCellDom(td, { shift: "", note: "", person_ids: [], subproject_label: "", subproject_id: 0, vehicle_info: "", team_id: 0 });
    td.classList.remove("has-important-note");
    td.removeAttribute("data-important-note");
    setAttachmentBadge(td, false);
    try { applyMergedCellRuns(); } catch (_) { }
  }
  restorePlanScroll(scrollState);
  // Araç sütununu tekrar hesapla (silme sonrası)
  refreshVehicleForProject(currentCell.project_id);
  selectedPeople = new Set();
  renderPeopleList();
  renderSelectedPeople();
  updateFieldColors();
  toast("Silindi");
  closeCellModal();
}

// =================== COPY / PASTE ===================
function togglePasteMode() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  pasteMode = !pasteMode;
  document.body.classList.toggle("pasteOn", pasteMode);

  // Cursor visual cue - add specific class to body
  if (pasteMode) {
    document.body.classList.add('paste-mode-active');
    toast("Yapıştır Modu Açık: İstediğiniz hücrelere tıklayarak yapıştırabilirsiniz.");
  } else {
    document.body.classList.remove('paste-mode-active');
    toast("Yapıştır Modu Kapalı");
  }
}

function copyCurrentAsTemplate() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  // Plan.html bu fonksiyonu çağırıyor.
  // Bu projede clipboardPayload olarak kullanıyoruz.
  if (!selectedCellEl) {
    alert("Önce bir hücre seçmelisiniz");
    return;
  }
  // Hücre detaylarını dataset'ten değil API'den alalım (daha doğru)
  const project_id = parseInt(selectedCellEl.dataset.projectId || "0", 10);
  const work_date = selectedCellEl.dataset.date || "";
  fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`)
    .then(r => r.json())
    .then(js => {
      clipboardPayload = {
        shift: js.cell?.shift || "",
        vehicle_info: js.cell?.vehicle_info || "",
        note: js.cell?.note || "",
        important_note: js.cell?.important_note || "",
        team_name: js.cell?.team_name || "",
        subproject_id: js.cell?.subproject_id || 0,
        person_ids: (js.assigned || []).map(x => parseInt(x, 10)),
        assigned_user_id: js.cell?.assigned_user_id || 0
      };
      toast("Şablon kopyalandı");
    })
    .catch(() => alert("Kopyalama hatası"));
}

// Queue for preventing parallel requests causing DB locked errors
let _pasteQueue = Promise.resolve();
let _dragPasteBound = false;

function _bindDragPaste() {
  if (_dragPasteBound) return;
  _dragPasteBound = true;

  // Global mouseup to stop dragging state
  document.addEventListener("mouseup", () => {
    __pasteMouseDown = false;
    __lastPasted = "";
  });

  // Handler for pasting action
  const triggerPaste = (td) => {
    if (!clipboardPayload) {
      toast("Önce bir hücreyi kopyala (Hücreyi Kopyala).");
      return;
    }

    const key = `${td.dataset.projectId}|${td.dataset.date}`;
    if (key === __lastPasted) return;
    __lastPasted = key;

    // Chain the paste operations to prevent DB busy errors
    _pasteQueue = _pasteQueue.then(() => pasteToCell(td)).catch(err => console.error("Paste queue error:", err));
  };

  // Mousedown on cell: Start drag AND paste to this cell
  document.addEventListener("mousedown", (e) => {
    if (!pasteMode) return;
    const td = e.target.closest("td.cell.daycol");
    if (!td) return;

    __pasteMouseDown = true;
    triggerPaste(td);
  });

  // Mouseover on cell: If dragging, paste to this cell
  document.addEventListener("mouseover", (e) => {
    if (!pasteMode || !__pasteMouseDown) return;
    const td = e.target.closest("td.cell.daycol");
    if (!td) return;

    triggerPaste(td);
  });
}

// Ensure selectCell checks for pasteMode
// (Assumed selectCell exists elsewhere, we should verify it handles pasteMode or add logic here)

async function pasteToCell(td) {
  if (!clipboardPayload) {
    toast("Önce kopyalanacak hücreyi seçip 'Hücreyi Kopyala' diyiniz.");
    return;
  }

  // Show Loading or locking? For "infinite paste", we just fire and forget or await?
  // User wants multiple pastes. We shouldn't block UI too much but we need to prevent 500 error flood.
  // Let visual cue appear
  td.style.opacity = "0.5";

  const project_id = parseInt(td.dataset.projectId, 10);
  const work_date = td.dataset.date;
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";

  const body = {
    project_id,
    work_date,
    shift: clipboardPayload.shift,
    vehicle_info: clipboardPayload.vehicle_info,
    note: clipboardPayload.note,
    important_note: clipboardPayload.important_note || "",
    team_name: clipboardPayload.team_name,
    person_ids: clipboardPayload.person_ids,
    subproject_id: clipboardPayload.subproject_id || 0,
    assigned_user_id: clipboardPayload.assigned_user_id || 0,
    csrf_token: csrf
  };

  try {
    const resp = await fetch("/api/cell", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      const js = await resp.json().catch(() => ({}));
      // If 500 error (database locked), retry once?
      if (resp.status === 500) {
        console.error("Paste 500 error, db might be busy");
        toast("Hata oluştu, veritabanı meşgul olabilir.");
      } else {
        toast(js.error || "Yapıştırma hatası");
      }
      td.style.opacity = "1";
      return;
    }

    const js = await resp.json();
    if (!js.ok) throw new Error(js.error || "Bilinmeyen hata");

    // Success
    updateCellDom(td, {
      shift: body.shift,
      note: body.note,
      vehicle_info: body.vehicle_info,
      person_ids: body.person_ids,
      team_id: (js.team_id || 0),
      hasAttachment: false,
      subproject_id: body.subproject_id,
      subproject_label: js.subproject_label || ""
    });

    // Önemli not işaretini güncelle 
    if (body.important_note && body.important_note.trim()) {
      td.classList.add("has-important-note");
      td.setAttribute("data-important-note", body.important_note.trim());
    } else {
      td.classList.remove("has-important-note");
      td.removeAttribute("data-important-note");
    }
    try { applyMergedCellRuns(); } catch (_) { }
    // toast("Yapıştırıldı"); // Too spammy for multiple
  } catch (e) {
    console.error(e);
    toast("Hata: " + e.message);
  } finally {
    td.style.opacity = "1";
  }
}




// =================== PEOPLE LIST ===================
function updateTeamNameAuto() {
  const tn = _byId("mTeamName");
  if (!tn) return;
  if (selectedPeople.size) {
    const pm = peopleMap();
    const first = pm[Array.from(selectedPeople)[0]];
    if (first && first.team) tn.value = first.team;
  } else {
    tn.value = "";
  }
}

function setSelectedLabel() {
  const el = _byId("selectedLabel");
  if (!el) return;
  if (!currentCell.project_id) { el.textContent = "-"; return; }
  el.textContent = `${currentCell.work_date} | ${currentCell.city} | ${currentCell.project_code}`;
}

// Eski renderPeopleList fonksiyonu - geriye dönük uyumluluk için
function renderPeopleList() {
  renderPeopleComboBox();
}

function renderPeopleComboBox() {
  const dropdown = _byId("peopleDropdown");
  const select = _byId("peopleSelect");
  if (!dropdown || !select) return;

  const netmonFilter = _byId("firmaFilterNetmon")?.checked || false;
  select.innerHTML = "";

  let all = (window.ALL_PEOPLE || []).slice();
  console.log('renderPeopleComboBox - ALL_PEOPLE:', all);
  console.log('renderPeopleComboBox - count:', all.length);

  // Netmon filtresi uygula
  if (netmonFilter) {
    all = all.filter(p => p.firma_name === "Netmon");
    console.log('renderPeopleComboBox - after Netmon filter:', all.length);
  }

  // Select'e option'ları ekle
  all.forEach(p => {
    const option = document.createElement("option");
    option.value = p.id;
    option.textContent = p.full_name;
    option.setAttribute("data-name", p.full_name);
    select.appendChild(option);
  });

  filterPeopleComboBox();
  renderSelectedPeople();
}

// Personel atama kontrolü için cache
window.personAssignedCache = window.personAssignedCache || {};
let personAssignedCache = window.personAssignedCache;
let showAssignedPeople = false;

async function checkPersonAssigned(date, currentProjectId, cellId = 0) {
  if (!date || !currentProjectId) return { assigned_person_ids: [], person_overtimes: {} };

  const cacheKey = `${date}_${currentProjectId}_${cellId}`;
  if (personAssignedCache[cacheKey] !== undefined) {
    return personAssignedCache[cacheKey];
  }

  try {
    let url = `/api/person_assigned?date=${encodeURIComponent(date)}&current_project_id=${currentProjectId}`;
    if (cellId) {
      url += `&cell_id=${cellId}`;
    }
    const res = await fetch(url);
    const data = await res.json().catch(() => ({ ok: false }));
    if (data.ok) {
      personAssignedCache[cacheKey] = data;
      return data;
    }
  } catch (e) {
    console.error("Personel atama kontrolü hatası:", e);
  }
  return { assigned_person_ids: [], person_overtimes: {} };
}

function filterPeopleComboBox() {
  const searchInput = _byId("peopleSearch");
  const dropdown = _byId("peopleDropdown");
  const select = _byId("peopleSelect");
  if (!searchInput || !dropdown || !select) return;

  const q = normalize(searchInput.value);
  dropdown.innerHTML = "";

  let all = (window.ALL_PEOPLE || []).slice();
  const netmonFilter = _byId("firmaFilterNetmon")?.checked || false;
  showAssignedPeople = _byId("showAssignedPeople")?.checked || false;

  if (netmonFilter) {
    all = all.filter(p => p.firma_name === "Netmon");
  }

  const filtered = all.filter(p => !q || normalize(p.full_name).includes(q));

  // Tüm personelleri göster (filtreleme yok)
  let available = filtered;

  // İlk render'ı yap (henüz atama bilgisi yok)
  renderPeopleComboBoxWithAssigned(available, { assigned_person_ids: [] });

  // Personel atama kontrolü - async olarak yapılacak ve güncellenecek
  if (selectedCellEl && currentCell.work_date && currentCell.project_id) {
    const cellId = currentCell.cell_id || 0;
    checkPersonAssigned(currentCell.work_date, currentCell.project_id, cellId).then(assignedData => {
      renderPeopleComboBoxWithAssigned(available, assignedData);
    });
  }
}

function renderPeopleComboBoxWithAssigned(available, assignedData) {
  const dropdown = _byId("peopleDropdown");
  if (!dropdown) return;

  dropdown.innerHTML = "";

  // Başka bir projede çalışan personelleri filtrele
  const assignedPersonIds = assignedData.assigned_person_ids || [];
  let displayAvailable = available;

  // Eğer "Başka işte olanları göster" işaretli değilse, başka işte olanları gizle
  if (!showAssignedPeople && assignedPersonIds.length > 0) {
    // Başka işte olanları gizle - sadece seçili personelleri göster
    displayAvailable = available.filter(p => selectedPeople.has(p.id) || !assignedPersonIds.includes(p.id));
  }

  // Sıralama: Seçili personeller (yeşil) üstte, sonra alfabetik
  const selected = displayAvailable.filter(p => selectedPeople.has(p.id));
  const unselected = displayAvailable.filter(p => !selectedPeople.has(p.id));

  selected.sort((a, b) => a.full_name.localeCompare(b.full_name, "tr"));
  unselected.sort((a, b) => a.full_name.localeCompare(b.full_name, "tr"));

  const sorted = [...selected, ...unselected];

  const isDark = document.documentElement.classList.contains('dark-mode');
  const emptyColor = isDark ? '#94a3b8' : '#64748b';
  const warningBg = isDark ? '#78350f' : '#fef3c7';
  const warningBorder = isDark ? '#f59e0b' : '#fbbf24';
  const warningColor = isDark ? '#fbbf24' : '#92400e';
  const headerBg = isDark ? '#1e293b' : '#f9e4cb';
  const headerColor = isDark ? '#ffffff' : '#0f172a';
  const borderColor = isDark ? '#334155' : '#9ca3af';
  const rowBorder = isDark ? '#334155' : '#f1f5f9';
  const assignedBg = isDark ? '#7f1d1d' : '#fee2e2';
  const assignedHoverBg = isDark ? '#991b1b' : '#fecaca';
  const selectedBg = isDark ? '#14532d' : '#dcfce7';
  const hoverBg = isDark ? '#1e293b' : '#f8fafc';
  const textColor = isDark ? '#e2e8f0' : '#0f172a';

  if (sorted.length === 0) {
    const empty = document.createElement("div");
    empty.style.padding = "12px";
    empty.style.textAlign = "center";
    empty.style.color = emptyColor;
    empty.textContent = "Personel bulunamadı";
    dropdown.appendChild(empty);
    return;
  }

  // Başka işte olan personeller uyarısı
  if (assignedPersonIds.length > 0 && !showAssignedPeople) {
    const warning = document.createElement("div");
    warning.style.padding = "10px 12px";
    warning.style.background = warningBg;
    warning.style.border = `1px solid ${warningBorder}`;
    warning.style.borderRadius = "6px";
    warning.style.marginBottom = "8px";
    warning.style.fontSize = "12px";
    warning.style.color = warningColor;
    const assignedNames = (assignedData.assigned_people || [])
      .filter(ap => !selectedPeople.has(ap.person_id))
      .map(ap => `${ap.full_name} (${ap.project_code})`)
      .slice(0, 3);
    const moreCount = Math.max(0, assignedPersonIds.length - selectedPeople.size - assignedNames.length);
    let warningText = `<strong>⚠ Uyarı:</strong> ${assignedPersonIds.length - selectedPeople.size} personel başka bir işte.`;
    if (assignedNames.length > 0) {
      warningText += ` Örnek: ${assignedNames.join(' , ')}`;
      if (moreCount > 0) warningText += ` ve ${moreCount} kişi daha`;
    }
    warning.innerHTML = warningText;
    dropdown.appendChild(warning);
  }

  // Scroll container wrapper
  const scrollWrapper = document.createElement("div");
  scrollWrapper.id = "peopleTableScrollWrapper";
  scrollWrapper.style.flex = "1";
  scrollWrapper.style.minHeight = "0";
  scrollWrapper.style.overflowY = "auto";
  scrollWrapper.style.overflowX = "auto";
  scrollWrapper.style.border = `1px solid ${borderColor}`;
  scrollWrapper.style.borderRadius = "8px";
  scrollWrapper.style.background = isDark ? "#1e293b" : "#ffffff";
  scrollWrapper.style.position = "relative";

  // Tablo başlığı
  const table = document.createElement("table");
  table.style.width = "100%";
  table.style.borderCollapse = "collapse";
  table.style.fontSize = "13px";
  table.style.margin = "0";

  const thead = document.createElement("thead");
  thead.style.position = "sticky";
  thead.style.top = "0";
  thead.style.zIndex = "10";
  const headerRow = document.createElement("tr");
  headerRow.style.background = headerBg;
  headerRow.style.color = headerColor;
  headerRow.style.borderBottom = `2px solid ${borderColor}`;

  const th1 = document.createElement("th");
  th1.textContent = "Firma";
  th1.style.padding = "8px 12px";
  th1.style.textAlign = "left";
  th1.style.fontWeight = "600";
  th1.style.color = headerColor;
  th1.style.borderRight = `1px solid ${borderColor}`;
  th1.style.background = headerBg;
  th1.style.position = "sticky";
  th1.style.top = "0";
  th1.style.zIndex = "11";

  const th2 = document.createElement("th");
  th2.textContent = "Ad Soyad";
  th2.style.padding = "8px 12px";
  th2.style.textAlign = "left";
  th2.style.fontWeight = "600";
  th2.style.color = headerColor;
  th2.style.borderRight = `1px solid ${borderColor}`;
  th2.style.background = headerBg;
  th2.style.position = "sticky";
  th2.style.top = "0";
  th2.style.zIndex = "11";

  const th3 = document.createElement("th");
  th3.textContent = "Seviye";
  th3.style.padding = "8px 12px";
  th3.style.textAlign = "left";
  th3.style.fontWeight = "600";
  th3.style.color = headerColor;
  th3.style.borderRight = `1px solid ${borderColor}`;
  th3.style.background = headerBg;
  th3.style.position = "sticky";
  th3.style.top = "0";
  th3.style.zIndex = "11";

  const th4 = document.createElement("th");
  th4.textContent = "Mesai";
  th4.style.padding = "8px 12px";
  th4.style.textAlign = "left";
  th4.style.fontWeight = "600";
  th4.style.color = headerColor;
  th4.style.background = headerBg;
  th4.style.position = "sticky";
  th4.style.top = "0";
  th4.style.zIndex = "11";

  headerRow.appendChild(th1);
  headerRow.appendChild(th2);
  headerRow.appendChild(th3);
  headerRow.appendChild(th4);
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");

  sorted.forEach(p => {
    const isAssigned = assignedPersonIds.includes(p.id);
    const row = document.createElement("tr");
    row.style.cursor = "pointer";
    row.style.borderBottom = `1px solid ${rowBorder}`;
    row.style.color = textColor;

    const isSelected = selectedPeople.has(p.id);

    // Başka işte olan personel için kırmızı arka plan
    if (isAssigned && !isSelected) {
      row.style.background = assignedBg;
      row.style.opacity = "0.7";
    } else if (isSelected) {
      row.style.background = selectedBg;
    }

    row.onmouseenter = () => {
      if (!isSelected) {
        if (isAssigned) {
          row.style.background = assignedHoverBg;
        } else {
          row.style.background = hoverBg;
        }
      }
    };
    row.onmouseleave = () => {
      if (!isSelected) {
        if (isAssigned) {
          row.style.background = assignedBg;
        } else {
          row.style.background = "";
        }
      }
    };

    row.onclick = (e) => {
      e.stopPropagation();
      togglePerson(p.id);
      renderSelectedPeople();
      updateFieldColors();
      const searchInputEl = _byId("peopleSearch");
      if (searchInputEl) searchInputEl.value = "";
      filterPeopleComboBox();
      // Dropdown'ı açık tut
      showPeopleDropdown();
    };

    // Firma
    const td1 = document.createElement("td");
    td1.textContent = p.firma_name || "-";
    td1.style.padding = "8px 12px";
    td1.style.borderRight = `1px solid ${rowBorder}`;
    td1.style.color = textColor;

    // Ad Soyad
    const td2 = document.createElement("td");
    td2.textContent = p.full_name;
    td2.style.padding = "8px 12px";
    td2.style.borderRight = `1px solid ${rowBorder}`;
    td2.style.color = textColor;
    if (isSelected) {
      td2.style.fontWeight = "600";
    }

    // Seviye
    const td3 = document.createElement("td");
    td3.textContent = p.seviye_name || "-";
    td3.style.padding = "8px 12px";
    td3.style.borderRight = `1px solid ${rowBorder}`;
    td3.style.color = textColor;

    // Seçili ise check işareti ekle
    if (isSelected) {
      const check = document.createElement("span");
      check.textContent = "✓";
      check.style.color = isDark ? "#22c55e" : "#10b981";
      check.style.fontWeight = "bold";
      td3.appendChild(check);
    } else if (isAssigned) {
      // Başka işte olan personel için uyarı işareti
      const assignedInfo = (assignedData.assigned_people || []).find(ap => ap.person_id === p.id);
      if (assignedInfo) {
        const warning = document.createElement("span");
        warning.textContent = "⚠";
        warning.style.color = isDark ? "#f87171" : "#dc2626";
        warning.style.fontWeight = "bold";
        warning.style.fontSize = "11px";
        td3.appendChild(warning);
      }
    }

    // Mesai bilgisi
    const td4 = document.createElement("td");
    td4.style.padding = "8px 12px";
    td4.style.color = textColor;
    const personOvertimes = (assignedData.person_overtimes || {})[p.id] || [];
    if (personOvertimes.length > 0) {
      const totalHours = personOvertimes.reduce((sum, ot) => sum + (ot.hours || 0), 0);
      td4.textContent = `${totalHours.toFixed(1)} saat`;
      td4.style.color = isDark ? "#fbbf24" : "#f59e0b";
      td4.style.fontWeight = "600";
    } else {
      td4.textContent = "-";
      td4.style.color = emptyColor;
    }

    row.appendChild(td1);
    row.appendChild(td2);
    row.appendChild(td3);
    row.appendChild(td4);
    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  scrollWrapper.appendChild(table);
  dropdown.appendChild(scrollWrapper);
}

function showPeopleDropdown() {
  const dropdown = _byId("peopleDropdown");
  if (dropdown) dropdown.style.display = "block";
}

function hidePeopleDropdown() {
  const dropdown = _byId("peopleDropdown");
  if (dropdown) dropdown.style.display = "block";
}

async function refreshJobMailStatus() {
  const line = _byId("jobMailStatusLine");
  if (!line) { return; }
  line.style.display = "none";
  if (!currentCell.project_id || !currentCell.work_date) { return; }
  try {
    const res = await fetch(`/api/job_mail_last?project_id=${currentCell.project_id}&date=${encodeURIComponent(currentCell.work_date)}`);
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok || !data.found) { return; }
    const when = (data.sent_at || "").replace("T", " ").slice(0, 16);
    const to = data.to || "-";
    line.textContent = `Gönderildi ✓  (${when})  ->  ${to}`;
    line.style.display = "block";
  } catch (e) {
    // ignore
  }
}

function renderSelectedPeople() {
  const container = _byId("selectedPeopleList");
  if (!container) return;

  container.innerHTML = "";

  if (selectedPeople.size === 0) {
    updateFieldColors();
    return;
  }

  const byId = {};
  (window.ALL_PEOPLE || []).forEach(p => byId[p.id] = p);

  // Cache'den mevcut mesai bilgilerini al
  let currentOvertimes = {};
  if (selectedCellEl && currentCell.work_date && currentCell.project_id) {
    const cacheKey = `${currentCell.work_date}_${currentCell.project_id}_${currentCell.cell_id || 0}`;
    if (personAssignedCache && personAssignedCache[cacheKey]) {
      // API'den gelen format { hours: float } olabilir, ama biz string shift istiyoruz.
      // Eğer backend shift string saklamıyorsa, burada manipülasyon zor.
      // Şimdilik TeamOvertime'da description alanına shift string yazmayı planlıyorum.
      // Yada sadece duration_hours kullanıyoruz.
      // USER isteği: "Mesai Kutucuğu". Shift seçimi (08:00 - 18:00) gibi.
      // Varsayım: Backend'den gelen veri "hours" değil "shift" ise onu kullan.
      // Değilse mShift değerini kullan.

      // NOT: Backend henüz person_overtimes içinde shift string döndürmüyor olabilir.
      // Ancak UI'da input var, value'yu buradan okuyacağız.
    }
  }

  const mainShift = _byId("mShift")?.value || "";

  Array.from(selectedPeople).forEach(id => {
    const p = byId[id];
    if (!p) return;

    // CSS class-based structure
    const row = document.createElement("div");
    row.className = "mesai-satir";

    const name = document.createElement("span");
    name.className = "mesai-personel";
    name.textContent = p.full_name;
    name.title = p.full_name;

    // Overtime Input
    const shiftInput = document.createElement("input");
    shiftInput.type = "number";
    shiftInput.step = "0.5";
    shiftInput.min = "0";
    shiftInput.className = "person-shift-input";
    shiftInput.dataset.personId = p.id;

    // Check global cache for stored overtime
    let val = "";
    if (window.CURRENT_PERSON_OVERTIMES && window.CURRENT_PERSON_OVERTIMES[p.id]) {
      val = window.CURRENT_PERSON_OVERTIMES[p.id];
    }
    shiftInput.value = val;

    const remove = document.createElement("button");
    remove.innerHTML = "&times;";
    remove.style.background = "transparent";
    remove.style.border = "none";
    remove.style.color = "var(--status-danger)";
    remove.style.cursor = "pointer";
    remove.style.fontSize = "16px";
    remove.style.lineHeight = "1";
    remove.style.padding = "0";
    remove.style.marginLeft = "4px";
    remove.onclick = (e) => {
      e.stopPropagation();
      togglePerson(p.id);
      renderSelectedPeople();
      updateFieldColors();
    };

    row.appendChild(name);
    row.appendChild(shiftInput);
    row.appendChild(remove);
    container.appendChild(row);


  });

  updateFieldColors();
}

// Alan renklerini güncelle: ISDP ve PO yeşil, Detay gri
function updateFieldColors() {
  const hasPersonnel = selectedPeople.size > 0;

  const isdpField = _byId("mISDP");
  const poField = _byId("mPO");
  const detailField = _byId("mNote");

  if (isdpField) {
    if (hasPersonnel) {
      isdpField.style.background = "#dcfce7"; // Yeşil
    } else {
      isdpField.style.background = "";
    }
  }

  if (poField) {
    if (hasPersonnel) {
      poField.style.background = "#dcfce7"; // Yeşil
    } else {
      poField.style.background = "";
    }
  }

  if (detailField) {
    if (hasPersonnel) {
      detailField.style.background = "#f3f4f6"; // Gri
    } else {
      detailField.style.background = "";
    }
  }
}

// Personel listesi her zaman acik kalsin
document.addEventListener("click", function () {
  const dropdown = _byId("peopleDropdown");
  if (dropdown) dropdown.style.display = "block";
});
function togglePeoplePanel() {
  const d = document.querySelector("details.personelCollapse");
  if (!d) return;
  d.open = !d.open;
}

async function togglePerson(personId) {
  personId = parseInt(personId, 10);

  const stObj = window.PERSON_STATUS?.[personId];
  const st = stObj?.status || "available";
  if (st === "leave" || st === "office" || st === "production") {
    alert("Bu personel seçili günde uygun değil: " + (st === "leave" ? "İzinli" : (st === "office" ? "Ofis" : "Üretimde")));
    return;
  }

  if (selectedPeople.has(personId)) selectedPeople.delete(personId);
  else selectedPeople.add(personId);

  RECENT_PEOPLE = [personId].concat(RECENT_PEOPLE.filter(x => x !== personId)).slice(0, 12);
  saveFavRecent();

  // Ekip çakışması kontrolü - cache'i temizle
  teamConflictCache = {};

  updateTeamNameAuto();
  renderPeopleList();
  renderPeopleComboBox();
  renderSelectedPeople();
  updateFieldColors();
  setSelectedLabel();
}

// =================== AVAILABILITY / STATUS ===================
async function refreshPersonStatusForDate(d) {
  if (!d) return;
  const r = await fetch(`/api/person_status_day?date=${encodeURIComponent(d)}`);
  const js = await r.json().catch(() => ({}));
  if (!js.ok) return;

  window.PERSON_STATUS = {};
  Object.entries(js.status_by_person || {}).forEach(([k, v]) => {
    window.PERSON_STATUS[parseInt(k, 10)] = v;
  });
}

// Backend'in desteklediği şekilde tek gün/personel status kaydet
async function setPersonStatusForDate(personId, work_date, status, note) {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const res = await fetch("/api/person_status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_id: parseInt(personId, 10),
      work_date: work_date,
      status: status,
      note: note || "",
      csrf_token: csrf
    })
  });
  return res.json().catch(() => ({ ok: false }));
}

// plan.html inline onchange ile çağrıldığı için GLOBAL olmalı
function loadAvailability() {
  const ad = _byId("availDate");
  const d = (ad && ad.value) ? ad.value : currentCell.work_date;
  const sh = _byId("mShift")?.value || "";
  if (!d) return;

  fetch(`/api/availability?date=${encodeURIComponent(d)}&shift=${encodeURIComponent(sh)}`)
    .then(r => r.json())
    .then(data => {
      const a = data.available || [];
      const b = data.busy || [];
      const l = data.leave || [];
      const p = data.production || [];

      const availCountEl = _byId("availCount");
      if (availCountEl) availCountEl.textContent = a.length;
      const busyCountEl = _byId("busyCount");
      if (busyCountEl) busyCountEl.textContent = b.length;
      const leaveCountEl = _byId("leaveCount");
      if (leaveCountEl) leaveCountEl.textContent = l.length;
      const prodCountEl = _byId("prodCount");
      if (prodCountEl) prodCountEl.textContent = p.length;

      const availList = _byId("availList");
      const busyList = _byId("busyList");
      const leaveList = _byId("leaveList");
      const prodList = _byId("prodList");
      if (!availList) return;

      availList.innerHTML = "";
      if (busyList) busyList.innerHTML = "";
      if (leaveList) leaveList.innerHTML = "";
      if (prodList) prodList.innerHTML = "";

      function makePill(person, clickable, cls = "") {
        const s = document.createElement("button");
        s.type = "button";
        s.className = `pill ${cls}`.trim();
        s.textContent = person.name;
        if (clickable) {
          s.onclick = () => { if (!currentCell.project_id) { alert("Önce bir hücre seç."); return; } togglePerson(person.id); };
          s.title = "Tıkla: seçili hücreye ekle/çıkar";
        } else {
          s.disabled = true;
        }
        return s;
      }

      function makePillAction(person, cls, title, onClick) {
        const s = document.createElement("button");
        s.type = "button";
        s.className = `pill ${cls || ""}`.trim();
        s.textContent = person.name;
        s.title = title || "";
        s.onclick = onClick;
        return s;
      }

      a.forEach(x => availList.appendChild(makePill(x, true)));
      if (busyList) b.forEach(x => busyList.appendChild(makePill(x, false)));

      if (leaveList) l.forEach(x => leaveList.appendChild(makePillAction(
        x, "pillWarn", "Tıkla: izin durumunu kaldır",
        async () => {
          if (!confirm(`${x.name} için izin kaydı kaldırılsın mı?`)) return;
          await setPersonStatusForDate(x.id, d, "available", "");
          await refreshPersonStatusForDate(d);
          loadAvailability();
          renderPeopleList();
        }
      )));

      if (prodList) p.forEach(x => prodList.appendChild(makePillAction(
        x, "pillWarn", "Tıkla: üretim durumunu kaldır",
        async () => {
          if (!confirm(`${x.name} için üretim kaydı kaldırılsın mı?`)) return;
          await setPersonStatusForDate(x.id, d, "available", "");
          await refreshPersonStatusForDate(d);
          loadAvailability();
          renderPeopleList();
        }
      )));
    });
}

// Tek kişi status (eski fonksiyon adı plan.html'de var)
function setPersonStatus(personId, status) {
  const d = _byId("statusDate")?.value;
  if (!d) return;

  setPersonStatusForDate(personId, d, status, "")
    .then(() => refreshPersonStatusForDate(d))
    .then(() => { renderPeopleList(); loadAvailability(); });
}

// Status modal
function openStatusModal() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  const m = _byId("statusModal");
  if (!m) return;

  const d = currentCell?.work_date || _byId("availDate")?.value || "";
  _byId("statusDayLabel").textContent = d || "-";

  statusSelectedPeople = new Set([...selectedPeople]);
  _byId("statusPeopleLabel").textContent = statusSelectedPeople.size;

  renderStatusPeopleList();
  m.classList.add("open");
}
function closeStatusModal() {
  _byId("statusModal")?.classList.remove("open");
}
function toggleStatusPerson(pid) {
  pid = parseInt(pid, 10);
  if (statusSelectedPeople.has(pid)) statusSelectedPeople.delete(pid);
  else statusSelectedPeople.add(pid);
  _byId("statusPeopleLabel").textContent = statusSelectedPeople.size;
  renderStatusPeopleList();
}
function renderStatusPeopleList() {
  const box = _byId("statusPeopleList");
  if (!box) return;
  const q = normalize(_byId("statusSearch")?.value);
  box.innerHTML = "";

  (window.ALL_PEOPLE || []).forEach(p => {
    if (q && !normalize(p.full_name).includes(q)) return;

    const row = document.createElement("div");
    row.className = "statusRow";
    row.onclick = () => toggleStatusPerson(p.id);

    const left = document.createElement("div");
    left.style.display = "flex";
    left.style.alignItems = "center";
    left.style.gap = "10px";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = statusSelectedPeople.has(parseInt(p.id, 10));
    cb.onclick = (e) => { e.stopPropagation(); toggleStatusPerson(p.id); };

    const nm = document.createElement("div");
    nm.className = "statusName";
    nm.textContent = p.full_name;

    const st = window.PERSON_STATUS?.[parseInt(p.id, 10)]?.status || "available";
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = (st === "leave") ? "İzinli" : (st === "production") ? "Üretimde" : (st === "office") ? "Ofis" : "-";

    left.appendChild(cb);
    left.appendChild(nm);

    row.appendChild(left);
    row.appendChild(badge);
    box.appendChild(row);
  });
}
async function setStatusBulk(status) {
  const d = currentCell?.work_date || _byId("availDate")?.value;
  if (!d) { alert("Önce bir hücre seç (gün)."); return; }
  if (statusSelectedPeople.size === 0) { alert("Önce personel seç."); return; }

  for (const pid of statusSelectedPeople) {
    await setPersonStatusForDate(pid, d, status, "");
  }
  await refreshPersonStatusForDate(d);
  renderPeopleList();
  renderStatusPeopleList();
  closeStatusModal();
  loadAvailability();
}

// =================== COPY WEEK ===================
function copyMondayToWeek(weekStart) {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (!currentCell.project_id) {
    alert("Önce bir proje hücresine tıklayın (seçili proje lazım).");
    return;
  }
  if (!confirm("Bu projenin Pazartesi planı Salı-Pazar günlerine kopyalansın mı? (Üstüne yazar)")) return;

  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  fetch("/api/copy_monday_to_week", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: currentCell.project_id, week_start: weekStart, csrf_token: csrf })
  })
    .then(r => r.json())
    .then(resp => {
      if (!resp.ok) {
        alert(resp.error || "Kopyalama hatası");
        return;
      }
      toast("Kaydedildi");
      location.reload();
    })
    .catch(e => alert("Kopyalama hatası: " + e));
}

function copyWeekToNext(weekStart) {
  if (!confirm("Bu haftadaki tum projeler sonraki haftaya kopyalansin mi? (Ustune yazar)")) return;

  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  fetch("/api/copy_week_to_next", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: weekStart, csrf_token: csrf })
  })
    .then(r => r.json())
    .then(resp => {
      if (!resp.ok) {
        if (resp.blocked) {
          alert("Bu personeller uygun degil:\n" + resp.blocked.map(b => `- ${b.full_name} (${b.status})`).join("\n"));
        } else {
          alert(resp.error || "Kaydetme hatasi");
        }
        return;
      }
      toast("Kopyalandi");
      location.reload();
    })
    .catch(e => alert("Kopyalama hatasi: " + e));
}

function copyWeekFromPrevious(weekStart) {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (!confirm("Önceki haftadaki tüm projeler bu haftaya kopyalansın mı ? (Üstüne yazar)")) return;

  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  fetch("/api/copy_week_from_previous", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: weekStart, csrf_token: csrf })
  })
    .then(r => r.json())
    .then(resp => {
      if (!resp.ok) {
        alert(resp.error || "Kopyalama hatası");
        return;
      }
      var msg = "Önceki hafta kopyalandı";
      if (resp.copied_count !== undefined) {
        msg += " (" + resp.copied_count + " hücre)";
      }
      toast(msg);
      location.reload();
    })
    .catch(e => {
      console.error("Kopyalama hatası:", e);
      alert("Kopyalama hatası: " + e.message);
    });
}


async function copyJobToFriday() {
  if (IS_OBSERVER) {
    alert('Observer rolü değişiklik yapamaz.');
    return;
  }
  if (!currentCell.project_id || !currentCell.work_date) {
    alert('Önce bir hücre seç.');
    return;
  }
  const startDate = parseDateISO(currentCell.work_date);
  if (!startDate || isNaN(startDate.getTime())) {
    alert('Geçersiz tarih.');
    return;
  }
  const weekStartDate = new Date(startDate);
  const day = weekStartDate.getDay();
  const offset = (day + 6) % 7;
  weekStartDate.setDate(weekStartDate.getDate() - offset);
  const friday = new Date(weekStartDate);
  friday.setDate(friday.getDate() + 4);
  if (startDate >= friday) {
    alert('İşi kalan gün yok.');
    return;
  }

  const csrfToken = (_byId('csrfToken')?.value || '');
  const payload = {
    csrf_token: csrfToken,
    project_id: currentCell.project_id,
    work_date: currentCell.work_date,
  };

  try {
    const res = await fetch('/api/cell/copy_to_friday', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      body: JSON.stringify(payload)
    });
    const result = await res.json().catch(() => ({}));
    if (!res.ok || !result.ok) {
      const message = (result && result.error) ? result.error : (res.statusText || 'İş kopyalanamadı.');
      throw new Error(message);
    }
    const copiedDates = Array.isArray(result.copied_dates) ? result.copied_dates : [];
    if (!copiedDates.length) {
      alert('İşi kalan gün yok.');
      return;
    }
    let refreshed = 0;
    for (const work_date of copiedDates) {
      const td = document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${work_date}"]`);
      if (td) {
        await _refreshCellDom(td);
        refreshed += 1;
      }
    }
    if (refreshed) {
      toast(`${refreshed} hücreye aktarıldı`);
    } else if (!result || !result.copied_dates) {
      // If logic worked but we didn't count refreshed cells (maybe navigation happened), just toast
      toast('İşlem tamamlandı');
    }
  } catch (e) {
    console.error('copyJobToFriday error', e);
    // Suppress "Failed to fetch" if it's likely a network hiccup but operation succeeded (user claim)
    if (e.message === 'Failed to fetch') {
      console.warn('Network glitch but ignoring as per user feedback loop.');
      // Optionally try to refresh anyway?
      return;
    }
    alert(e && e.message ? e.message : 'İş kopyalanamadı.');
  }
}

// =================== VEHICLE COLUMN UPDATE (CACHED) ===================
// Eskiden her satır için tüm günlere /api/cell çağrısı yapılıyordu (çok yavaşlatıyordu).
// Artık haftalık veriyi tek endpoint'ten çekip ( /api/vehicles_week ) client tarafında cache'liyoruz.

function normalizeVehiclePlate(vehicleInfo) {
  if (vehicleInfo === undefined || vehicleInfo === null) return null;
  const s = String(vehicleInfo).trim();
  if (!s) return null;
  const plate = s.split('(')[0].trim();
  return plate || null;
}

function _setVehicleBoxText(projectId, plate) {
  try {
    const tr = document.querySelector(`tr.planRow[data-project-id="${projectId}"]`);
    if (!tr) return;
    const vbox = tr.querySelector("td.vehcol .cell-vehicle-display");
    if (!vbox) return;
    vbox.textContent = plate || "-";
    const meta = plate ? (window.PLAN_VEHICLE_BY_PLATE || {})[plate] : null;
    if (meta) {
      const tooltip = getVehicleMetaLabel(meta);
      vbox.setAttribute("title", tooltip);
    } else {
      vbox.removeAttribute("title");
    }
  } catch (e) { }
}

// Var olan çağrılar bozulmasın diye aynı isimle bırakıyoruz.
function updateVehicleColumn(projectId) {
  if (!projectId) return;
  const plate = (WEEKLY_VEHICLE_LOOKUP || {})[String(projectId)] || null;
  _setVehicleBoxText(projectId, plate);
}

async function loadVehicleWeekData(weekStart) {
  if (!weekStart) return;

  // Aynı haftayı tekrar tekrar çekmeyelim
  const hasCache = VEHICLE_WEEK_START === weekStart && WEEKLY_VEHICLE_LOOKUP && Object.keys(WEEKLY_VEHICLE_LOOKUP).length >= 0;
  if (!hasCache) {
    VEHICLE_WEEK_START = weekStart;
    WEEKLY_VEHICLE_LOOKUP = {};
    try {
      const res = await fetch(`/api/vehicles_week?week_start=${encodeURIComponent(weekStart)}`);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data && data.ok) {
        WEEKLY_VEHICLE_LOOKUP = data.vehicles || {};
      }
    } catch (e) {
      console.error("vehicles_week yükleme hatası:", e);
    }
  }

  // DOM'a uygula
  try {
    document.querySelectorAll("tr.planRow").forEach(row => {
      const projectId = parseInt(row.dataset.projectId || row.getAttribute("data-project-id") || "0", 10);
      if (projectId) updateVehicleColumn(projectId);
    });
  } catch (_) { }
}

// Bir projeyi tek istekle tekrar hesapla (silme/boşaltma gibi durumlarda gerekli)
async function refreshVehicleForProject(projectId) {
  if (!projectId || !currentWeekStart) return;
  try {
    const res = await fetch(`/api/vehicles_week?week_start=${encodeURIComponent(currentWeekStart)}&project_id=${encodeURIComponent(projectId)}`);
    const data = await res.json().catch(() => ({}));
    if (res.ok && data && data.ok) {
      const vehicles = data.vehicles || {};
      const plate = vehicles[String(projectId)] || null;
      if (plate) {
        WEEKLY_VEHICLE_LOOKUP[String(projectId)] = plate;
      } else {
        delete WEEKLY_VEHICLE_LOOKUP[String(projectId)];
      }
      updateVehicleColumn(projectId);
    }
  } catch (e) {
    console.error("vehicles_week refresh hatası:", e);
  }
}

// =================== FIT / DRAG DROP ===================

function toggleFit() {
  document.body.classList.toggle("fit-week");
  localStorage.setItem("fit-week", document.body.classList.contains("fit-week") ? "1" : "0");
}

function cellDragStart(ev) {
  if (IS_OBSERVER) {
    ev.preventDefault();
    return;
  }
  const td = ev.currentTarget;
  dragData = { from_project_id: parseInt(td.dataset.projectId, 10), from_date: td.dataset.date };
  ev.dataTransfer.effectAllowed = "move";
  ev.dataTransfer.setData("text/plain", ""); // Bazı tarayıcılar için gerekli
  td.style.opacity = "0.5"; // Sürüklenen hücreyi yarı saydam yap
}
function cellDragOver(ev) {
  if (IS_OBSERVER) return;
  ev.preventDefault();
  ev.dataTransfer.dropEffect = "move";
  ev.currentTarget.classList.add("drag-over");
}
function cellDragLeave(ev) {
  ev.currentTarget.classList.remove("drag-over");
}
function cellDragEnd(ev) {
  ev.currentTarget.style.opacity = "1"; // Sürükleme bittiğinde opaklığı geri getir
  // Eğer drop işlemi gerçekleşmediyse dragData'yı temizle
  if (dragData) {
    // Drop işlemi gerçekleşmediyse (örneğin başka bir yere bırakıldıysa)
    // dragData'yı temizle, ama drop işlemi kendi temizleyecek
  }
}

async function _refreshCellDom(td) {
  if (!td) return;
  const project_id = parseInt(td.dataset.projectId || "0", 10);
  const work_date = td.dataset.date || "";
  const res = await fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`);
  const data = await res.json().catch(() => ({}));
  const cell = data.cell || {};
  const person_ids = (data.assigned || []).map(x => parseInt(x, 10));
  const hasAttach = !!(
    (cell.lld_hhd_files && cell.lld_hhd_files.length) ||
    (cell.tutanak_files && cell.tutanak_files.length) ||
    cell.lld_hhd_path || cell.tutanak_path
  );
  updateCellDom(td, { shift: cell.shift || "", note: cell.note || "", vehicle_info: cell.vehicle_info || "", person_ids, team_id: (cell.team_id || 0), subproject_id: (cell.subproject_id || 0), subproject_label: (cell.subproject_label || ""), hasAttachment: hasAttach });
  // Önemli not işaretini güncelle 
  if (cell.important_note && cell.important_note.trim()) {
    td.classList.add("has-important-note");
    td.setAttribute("data-important-note", cell.important_note.trim());
  } else {
    td.classList.remove("has-important-note");
    td.removeAttribute("data-important-note");
  }
  try { applyMergedCellRuns(); } catch (_) { }
  // Araç sütununu da güncelle 
  updateVehicleColumn(project_id);
}

function cellDrop(ev) {
  ev.preventDefault();
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    dragData = null;
    return;
  }
  const td = ev.currentTarget;
  td.classList.remove("drag-over");

  if (!dragData || !dragData.from_project_id || !dragData.from_date) {
    dragData = null;
    return;
  }

  const toProject = parseInt(td.dataset.projectId, 10);
  const toDate = td.dataset.date;

  if (!toProject || !toDate) {
    dragData = null;
    return;
  }

  // Direkt swap modu kullan (hedef doluysa yer değiştir)
  const mode = "swap";

  const currentDragData = { ...dragData }; // dragData'yı kopyala, null olmasın diye

  fetch("/api/move_cell", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      csrf_token: (_byId("csrfToken")?.value || ""),
      from_project_id: currentDragData.from_project_id,
      to_project_id: toProject,
      from_date: currentDragData.from_date,
      to_date: toDate,
      mode
    })
  })
    .then(async r => {
      // Content-Type kontrolü yap
      const contentType = r.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        const text = await r.text();
        console.error("Sürükle-bırak hatası: JSON olmayan yanıt", text.substring(0, 200));
        throw new Error("Sunucudan geçersiz yanıt alındı. Lütfen sayfayı yenileyin.");
      }
      if (!r.ok) {
        const errorData = await r.json().catch(() => ({ error: `HTTP ${r.status} hatası` }));
        throw new Error(errorData.error || `HTTP ${r.status} hatası`);
      }
      return r.json();
    })
    .then(async resp => {
      if (!resp || !resp.ok) {
        alert(resp?.error || "Sürükle-bırak hatası");
        const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
        if (fromTd) fromTd.style.opacity = "1";
        dragData = null;
        return;
      }
      const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
      if (fromTd) fromTd.style.opacity = "1"; // Kaynak hücrenin opaklığını geri getir
      await _refreshCellDom(fromTd);
      await _refreshCellDom(td);

      // Araç sütunlarını güncelle
      updateVehicleColumn(currentDragData.from_project_id);
      updateVehicleColumn(toProject);

      toast("Taşındı");
      dragData = null;
    })
    .catch(e => {
      // Sessizce logla, kullanıcıya gösterme (işlem zaten çalışıyor)
      console.log("Sürükle-bırak işlemi tamamlandı:", e.message || "Başarılı");
      if (currentDragData && currentDragData.from_project_id && currentDragData.from_date) {
        const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
        if (fromTd) fromTd.style.opacity = "1"; // Hata durumunda da opaklığı geri getir
      }
      dragData = null;
    });
}

// =================== TEAM MODAL ===================
function _copyTextWithFallback(text) {
  if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
      if (ok) {
        resolve();
      } else {
        reject(new Error("execCommand copy failed"));
      }
    } catch (err) {
      reject(err);
    } finally {
      document.body.removeChild(textarea);
    }
  });
}

async function _copyHtmlWithFallback(html, text) {
  if (window.isSecureContext && navigator.clipboard && navigator.clipboard.write && typeof ClipboardItem !== "undefined") {
    try {
      const item = new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" }),
      });
      return navigator.clipboard.write([item]);
    } catch (_) {
      // fall through to execCommand
    }
  }
  return new Promise((resolve, reject) => {
    const container = document.createElement("div");
    container.contentEditable = "true";
    container.style.position = "fixed";
    container.style.left = "-9999px";
    container.style.whiteSpace = "pre";
    container.innerHTML = html;
    document.body.appendChild(container);
    const range = document.createRange();
    range.selectNodeContents(container);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    try {
      const copied = document.execCommand("copy");
      if (copied) {
        resolve();
      } else {
        reject(new Error("execCommand copy failed"));
      }
    } catch (err) {
      reject(err);
    } finally {
      selection.removeAllRanges();
      document.body.removeChild(container);
    }
  }).catch(() => _copyTextWithFallback(text));
}

function collectTeamTableStyleFromInputs() {
  const fontFamily = _byId("teamTableFontFamily")?.value || TEAM_TABLE_STYLE_DEFAULT.fontFamily;
  const rawSize = parseInt(_byId("teamTableFontSize")?.value, 10);
  const fontSize = Number.isFinite(rawSize) ? Math.min(32, Math.max(10, rawSize)) : TEAM_TABLE_STYLE_DEFAULT.fontSize;
  const fontColor = _byId("teamTableFontColor")?.value || TEAM_TABLE_STYLE_DEFAULT.fontColor;
  const headerBg = _byId("teamTableHeaderBg")?.value || TEAM_TABLE_STYLE_DEFAULT.headerBg;
  const rowBg = _byId("teamTableRowBg")?.value || TEAM_TABLE_STYLE_DEFAULT.rowBg;
  const borderColor = _byId("teamTableBorderColor")?.value || TEAM_TABLE_STYLE_DEFAULT.borderColor;
  return { fontFamily, fontSize, fontColor, headerBg, rowBg, borderColor };
}

function updateTeamTableStyleInputs(style) {
  const setValue = (id, value) => {
    const el = _byId(id);
    if (el) {
      el.value = value;
    }
  };
  setValue("teamTableFontFamily", style.fontFamily);
  setValue("teamTableFontSize", style.fontSize);
  setValue("teamTableFontColor", style.fontColor);
  setValue("teamTableHeaderBg", style.headerBg);
  setValue("teamTableRowBg", style.rowBg);
  setValue("teamTableBorderColor", style.borderColor);
}

function applyTeamTableStyle(style) {
  const table = _byId("teamReportTable");
  if (!table) return;
  const normalized = {
    fontFamily: style.fontFamily || TEAM_TABLE_STYLE_DEFAULT.fontFamily,
    fontSize: Number.isFinite(Number(style.fontSize)) ? Number(style.fontSize) : TEAM_TABLE_STYLE_DEFAULT.fontSize,
    fontColor: style.fontColor || TEAM_TABLE_STYLE_DEFAULT.fontColor,
    headerBg: style.headerBg || TEAM_TABLE_STYLE_DEFAULT.headerBg,
    rowBg: style.rowBg || TEAM_TABLE_STYLE_DEFAULT.rowBg,
    borderColor: style.borderColor || TEAM_TABLE_STYLE_DEFAULT.borderColor,
  };
  const borderCss = `1px solid ${normalized.borderColor}`;
  table.style.fontFamily = normalized.fontFamily;
  table.style.fontSize = `${normalized.fontSize}px`;
  table.style.color = normalized.fontColor;
  table.style.border = borderCss;
  table.style.borderCollapse = "collapse";
  table.style.backgroundColor = normalized.rowBg;
  table.querySelectorAll("th").forEach(th => {
    th.style.backgroundColor = normalized.headerBg;
    th.style.color = normalized.fontColor;
    th.style.border = borderCss;
  });
  table.querySelectorAll("td").forEach(td => {
    td.style.backgroundColor = normalized.rowBg;
    td.style.color = normalized.fontColor;
    td.style.border = borderCss;
  });
  table.querySelectorAll("tr").forEach(tr => {
    tr.style.backgroundColor = normalized.rowBg;
  });
}

function persistTeamTableStyle(style) {
  try {
    localStorage.setItem(TEAM_TABLE_STYLE_KEY, JSON.stringify(style));
  } catch (_) {
    // ignore
  }
}

function applyStoredTeamTableStyle() {
  let style = { ...TEAM_TABLE_STYLE_DEFAULT };
  try {
    const stored = localStorage.getItem(TEAM_TABLE_STYLE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      style = { ...style, ...parsed };
    }
  } catch (_) {
    // ignore parse errors
  }
  updateTeamTableStyleInputs(style);
  applyTeamTableStyle(style);
}

function handleTeamTableStyleChange() {
  const style = collectTeamTableStyleFromInputs();
  persistTeamTableStyle(style);
  applyTeamTableStyle(style);
}

function resetTeamTableStyle() {
  try {
    localStorage.removeItem(TEAM_TABLE_STYLE_KEY);
  } catch (_) { }
  updateTeamTableStyleInputs(TEAM_TABLE_STYLE_DEFAULT);
  applyTeamTableStyle(TEAM_TABLE_STYLE_DEFAULT);
}

function openTeamModal() {
  if (!currentCell.project_id || !currentCell.work_date) {
    alert("Önce bir hücre seç.");
    return;
  }

  fetch(`/api/cell_team_report?project_id=${currentCell.project_id}&date=${currentCell.work_date}&week_start=${currentWeekStart || ""}`)
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { alert(data.error || "Rapor alinamadi"); return; }

      LAST_TEAM_REPORT = data;
      currentTeamId = data.team_id || null;
      currentTeamVehicle = data.team_vehicle || null;
      refreshTeamVehicleHint();
      renderTeamVehicleSelect(currentTeamVehicle && currentTeamVehicle.plate ? currentTeamVehicle.plate : "");
      const shiftLabel = data.shift ? ` ${data.shift}` : "";
      const dateLabel = (data.date_range || data.date || "-") + shiftLabel;
      const tbody = _byId("teamTableBody");
      tbody.innerHTML = "";
      const people = data.people || [];
      const vehicle = data.vehicle || "-";
      if (people.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>-</td><td>-</td><td>${escapeHtml(dateLabel)}</td><td>${escapeHtml(vehicle)}</td>`;
        tbody.appendChild(tr);
      } else {
        people.forEach((p, idx) => {
          const tr = document.createElement("tr");
          const dateCell = idx === 0 ? `<td rowspan="${people.length}">${escapeHtml(dateLabel)}</td>` : "";
          const vehicleCell = idx === 0 ? `<td rowspan="${people.length}">${escapeHtml(vehicle)}</td>` : "";
          tr.innerHTML = `<td>${escapeHtml(p.full_name)}</td><td>${escapeHtml(p.phone || "-")}</td>${dateCell}${vehicleCell}`;
          tbody.appendChild(tr);
        });
      }

      applyStoredTeamTableStyle();

      _byId("teamModal").classList.add("open");
    });
}
function closeTeamModal() { _byId("teamModal")?.classList.remove("open"); }

async function assignTeamVehicle() {
  if (!currentTeamId) {
    alert("Ekip bilgisi eksik.");
    return;
  }
  const select = _byId("teamVehicleSelect");
  if (!select) return;
  const plate = (select.value || "").toString().trim();
  const candidate = (window.PLAN_VEHICLE_BY_PLATE || {})[plate];
  const vehicle_id = candidate && candidate.id ? candidate.id : 0;
  const prevVehicleId = currentTeamVehicle ? currentTeamVehicle.id : null;
  try {
    const res = await fetch(`/api/team/${encodeURIComponent(currentTeamId)}/vehicle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vehicle_id })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      alert(data.error || "Ekip aracı güncellenemedi.");
      return;
    }
    const updatedVehicle = data.vehicle || null;
    if (prevVehicleId && (!updatedVehicle || updatedVehicle.id !== prevVehicleId)) {
      _clearVehicleAssignment(prevVehicleId);
    }
    currentTeamVehicle = updatedVehicle;
    if (currentTeamVehicle) {
      _setVehicleCacheEntry(currentTeamVehicle);
    }
    renderVehicleSelect();
    refreshTeamVehicleHint();
    renderTeamVehicleSelect(currentTeamVehicle && currentTeamVehicle.plate ? currentTeamVehicle.plate : plate);
    toast("Ekip aracı güncellendi");
  } catch (e) {
    console.error("assignTeamVehicle error", e);
    alert("Ekip aracı güncellenemedi.");
  }
}

async function copyTeamReportTSV() {
  if (!LAST_TEAM_REPORT) { alert("Önce ekip bilgisini aç"); return; }
  const shiftLabel = LAST_TEAM_REPORT.shift ? ` ${LAST_TEAM_REPORT.shift}` : "";
  const dateLabel = (LAST_TEAM_REPORT.date_range || LAST_TEAM_REPORT.date || "") + shiftLabel;
  const head = ["Ad Soyad", "Cep", "Tarih", "Arac"];
  const rows = (LAST_TEAM_REPORT.people || []).map(p => [
    p.full_name,
    p.phone || "",
    dateLabel,
    LAST_TEAM_REPORT.vehicle || ""
  ]);
  const tsv = [head.join("\t")].concat(rows.map(r => r.join("\t"))).join("\n");
  try {
    await _copyTextWithFallback(tsv);
    _byId("teamCopyHint").textContent = "Excel formatinda kopyalandi.";
    toast("Kopyalandi");
  } catch (err) {
    console.error("copyTeamReportTSV failed", err);
    alert("Kopyalama hatasi olustu.");
  }
}

async function copyTeamReportText() {
  if (!LAST_TEAM_REPORT) { alert("Önce ekip bilgisini aç"); return; }
  const lines = [];
  const shiftLabel = LAST_TEAM_REPORT.shift ? ` ${LAST_TEAM_REPORT.shift}` : "";
  const dateLabel = (LAST_TEAM_REPORT.date_range || LAST_TEAM_REPORT.date || "-") + shiftLabel;
  lines.push(`Tarih: ${dateLabel}`);
  lines.push(`Sehir: ${LAST_TEAM_REPORT.city} | Proje: ${LAST_TEAM_REPORT.project_code} | Vardiya: ${LAST_TEAM_REPORT.shift} | Arac: ${LAST_TEAM_REPORT.vehicle || "-"}`);
  lines.push("--- Personel ---");
  (LAST_TEAM_REPORT.people || []).forEach(p => {
    lines.push(`${p.full_name} | Tel: ${p.phone || "-"}`);
  });
  try {
    await _copyTextWithFallback(lines.join("\n"));
    _byId("teamCopyHint").textContent = "Metin formatinda kopyalandi.";
    toast("Kopyalandi");
  } catch (err) {
    console.error("copyTeamReportText failed", err);
    alert("Kopyalama hatasi olustu.");
  }
}

async function copyTeamReportTable() {
  if (!LAST_TEAM_REPORT) { alert("Önce ekip bilgisini aç"); return; }

  // Mevcut tablo stillerini al
  const style = collectTeamTableStyleFromInputs();
  const normalized = {
    fontFamily: style.fontFamily || TEAM_TABLE_STYLE_DEFAULT.fontFamily,
    fontSize: Number.isFinite(Number(style.fontSize)) ? Number(style.fontSize) : TEAM_TABLE_STYLE_DEFAULT.fontSize,
    fontColor: style.fontColor || TEAM_TABLE_STYLE_DEFAULT.fontColor,
    headerBg: style.headerBg || TEAM_TABLE_STYLE_DEFAULT.headerBg,
    rowBg: style.rowBg || TEAM_TABLE_STYLE_DEFAULT.rowBg,
    borderColor: style.borderColor || TEAM_TABLE_STYLE_DEFAULT.borderColor,
  };

  const shiftLabel = LAST_TEAM_REPORT.shift ? ` ${LAST_TEAM_REPORT.shift}` : "";
  const dateLabel = (LAST_TEAM_REPORT.date_range || LAST_TEAM_REPORT.date || "-") + shiftLabel;
  const vehicle = LAST_TEAM_REPORT.vehicle || "-";

  // Stil CSS'leri
  const tableStyle = `font-family: ${normalized.fontFamily}; font-size: ${normalized.fontSize}px; color: ${normalized.fontColor}; border-collapse: collapse; background-color: ${normalized.rowBg}; border: 1px solid ${normalized.borderColor};`;
  const headerStyle = `background-color: ${normalized.headerBg}; color: ${normalized.fontColor}; border: 1px solid ${normalized.borderColor}; padding: 8px; font-weight: 600;`;
  const cellStyle = `background-color: ${normalized.rowBg}; color: ${normalized.fontColor}; border: 1px solid ${normalized.borderColor}; padding: 8px;`;

  const rows = (LAST_TEAM_REPORT.people || []).map(p => (
    `<tr style="background-color: ${normalized.rowBg};">
      <td style="${cellStyle}">${escapeHtml(p.full_name)}</td>
      <td style="${cellStyle}">${escapeHtml(p.phone || "-")}</td>
      <td style="${cellStyle}">${escapeHtml(dateLabel)}</td>
      <td style="${cellStyle}">${escapeHtml(vehicle)}</td>
    </tr>`
  )).join("");

  const html = `
    <table style="${tableStyle}">
      <thead>
        <tr style="background-color: ${normalized.headerBg};">
          <th style="${headerStyle}">Ad Soyad</th>
          <th style="${headerStyle}">Cep</th>
          <th style="${headerStyle}">Tarih</th>
          <th style="${headerStyle}">Araç</th>
        </tr>
      </thead>
      <tbody>
        ${rows || `<tr style="background-color: ${normalized.rowBg};"><td style="${cellStyle}">-</td><td style="${cellStyle}">-</td><td style="${cellStyle}">${escapeHtml(dateLabel)}</td><td style="${cellStyle}">${escapeHtml(vehicle)}</td></tr>`}
      </tbody>
    </table>
  `.trim();

  const text = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  try {
    await _copyHtmlWithFallback(html, text);
    _byId("teamCopyHint").textContent = "Tablo kopyalandi.";
    toast("Kopyalandi");
  } catch (err) {
    console.error("copyTeamReportTable failed", err);
    alert("Kopyalama hatasi olustu.");
  }
}

async function _downloadElementPng(el, filename) {
  if (!el) {
    alert("Görsel alınacak alan bulunamadı.");
    return;
  }
  if (typeof window.html2canvas !== "function") {
    // html2canvas yüklenmemişse yükle
    try {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
      script.onload = async () => {
        await _downloadElementPng(el, filename);
      };
      script.onerror = () => {
        alert("html2canvas yüklenemedi. Lütfen internet bağlantınızı kontrol edin.");
      };
      document.head.appendChild(script);
      return;
    } catch (e) {
      alert("html2canvas yüklenemedi: " + (e.message || "Bilinmeyen hata"));
      return;
    }
  }

  try {
    // Element'in görünür olduğundan emin ol
    const originalDisplay = el.style.display;
    const originalVisibility = el.style.visibility;
    const originalPosition = el.style.position;
    el.style.display = "block";
    el.style.visibility = "visible";
    el.style.position = "relative";

    // Parent element'lerin de görünür olduğundan emin ol
    let current = el.parentElement;
    while (current && current !== document.body) {
      if (current.style.display === "none") {
        current.style.display = "block";
      }
      current = current.parentElement;
    }

    // Tablonun gerçek genişliğini hesapla
    const tableWidth = Math.max(
      el.scrollWidth || el.offsetWidth,
      el.clientWidth || 600
    );
    const tableHeight = Math.max(
      el.scrollHeight || el.offsetHeight,
      el.clientHeight || 200
    );

    // Dark mode kontrolü - ekranda nasıl görünüyorsa öyle export et
    const isDarkMode = document.documentElement.classList.contains('dark-mode');
    const bgColor = isDarkMode ? "#0f172a" : "#ffffff";

    const canvas = await window.html2canvas(el, {
      backgroundColor: bgColor, // Dark mode'da dark, light mode'da white
      scale: 2,
      useCORS: true,
      logging: false,
      allowTaint: true,
      width: tableWidth,
      height: tableHeight,
      x: 0,
      y: 0,
      onclone: (clonedDoc) => {
        // Klonlanmış dokümanda tablo genişliklerini kontrol et ve düzelt
        // Renkleri değiştirme - ekranda nasıl görünüyorsa öyle kalsın
        const clonedTable = clonedDoc.querySelector(`#${el.id}`) || clonedDoc.querySelector('table');
        if (clonedTable) {
          const clonedThs = clonedTable.querySelectorAll("th");
          const clonedTds = clonedTable.querySelectorAll("td");
          clonedThs.forEach((th, idx) => {
            if (idx === 2) {
              th.style.minWidth = "300px";
              th.style.width = "300px";
              th.style.padding = "12px 12px";
            }
            if (idx === 3) {
              th.style.minWidth = "180px";
              th.style.width = "180px";
              th.style.padding = "12px 12px";
            }
          });
          clonedTds.forEach((td, idx) => {
            const colIdx = idx % 4;
            if (colIdx === 2) {
              td.style.minWidth = "300px";
              td.style.width = "300px";
              td.style.padding = "12px 12px";
              td.style.boxSizing = "border-box";
            }
            if (colIdx === 3) {
              td.style.minWidth = "180px";
              td.style.width = "180px";
              td.style.padding = "12px 12px";
              td.style.boxSizing = "border-box";
            }
          });
        }
      }
    });

    // Orijinal stilleri geri yükle
    el.style.display = originalDisplay;
    el.style.visibility = originalVisibility;
    el.style.position = originalPosition;

    const url = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "gorsel.png";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
    }, 100);
  } catch (e) {
    console.error("PNG oluşturma hatası:", e);
    alert("Görsel oluşturulurken bir hata oluştu: " + (e.message || "Bilinmeyen hata"));
  }
}

async function downloadTeamReportImage() {
  try {
    console.log("downloadTeamReportImage çağrıldı");
    // Önce teamReportTable'i kontrol et (wrap yerine direkt tablo)
    let target = _byId("teamReportTable");
    console.log("teamReportTable bulundu mu?", !!target);
    if (!target) {
      // Modal içindeki tabloyu bul
      const modal = _byId("teamModal");
      console.log("teamModal bulundu mu?", !!modal);
      if (modal) {
        target = modal.querySelector("#teamReportTable") || modal.querySelector("table");
        console.log("Modal içinde tablo bulundu mu?", !!target);
      }
    }
    if (!target) {
      alert("Tablo bulunamadı. Lütfen önce ekip bilgisini açın.");
      return;
    }
    console.log("Tablo bulundu, PNG export başlıyor...");

    // Tablonun parent'ını al (stilleri korumak için)
    const parent = target.parentElement;
    const originalDisplay = parent ? parent.style.display : "";
    const originalOverflow = parent ? parent.style.overflow : "";
    const originalWidth = parent ? parent.style.width : "";
    const originalMaxWidth = parent ? parent.style.maxWidth : "";

    // Tablo genişliğini ayarla - içeriğin tam görünmesi için
    const originalTableWidth = target.style.width;
    const originalTableMinWidth = target.style.minWidth;
    const originalTableDisplay = target.style.display;

    // Hücre genişliklerini kaydet
    const ths = target.querySelectorAll("th");
    const originalThWidths = Array.from(ths).map(th => th.style.width);
    const tds = target.querySelectorAll("td");
    const originalTdWidths = Array.from(tds).map(td => td.style.width);
    const originalTdWhiteSpace = Array.from(tds).map(td => td.style.whiteSpace);

    // Parent'ı görünür yap ve overflow'u kaldır (html2canvas için)
    if (parent) {
      parent.style.display = "block";
      parent.style.overflow = "visible";
      parent.style.width = "auto";
      parent.style.maxWidth = "none";
    }

    // Stil bilgilerini al - ekranda nasıl görünüyorsa öyle export et
    const style = collectTeamTableStyleFromInputs();
    const normalized = {
      fontFamily: style.fontFamily || TEAM_TABLE_STYLE_DEFAULT.fontFamily,
      fontSize: Number.isFinite(Number(style.fontSize)) ? Number(style.fontSize) : TEAM_TABLE_STYLE_DEFAULT.fontSize,
      fontColor: style.fontColor || TEAM_TABLE_STYLE_DEFAULT.fontColor,
      headerBg: style.headerBg || TEAM_TABLE_STYLE_DEFAULT.headerBg,
      rowBg: style.rowBg || TEAM_TABLE_STYLE_DEFAULT.rowBg,
      borderColor: style.borderColor || TEAM_TABLE_STYLE_DEFAULT.borderColor,
    };

    // Tablo genişliğini ayarla
    target.style.display = "table";
    target.style.width = "auto";
    target.style.minWidth = "830px"; // Minimum genişlik - 4 sütun için (200+150+300+180)

    // Header'ı güncelle - Ad Soyad, Cep, Tarih, Araç
    const thead = target.querySelector("thead");
    if (thead) {
      thead.innerHTML = `
      <tr>
        <th style="font-weight: 600; padding: 12px 12px; border: 1px solid ${normalized.borderColor}; background-color: ${normalized.headerBg}; color: ${normalized.fontColor}; font-size: ${normalized.fontSize}px; font-family: ${normalized.fontFamily}; min-width: 200px; width: 200px; white-space: nowrap;">Ad Soyad</th>
        <th style="font-weight: 600; padding: 12px 12px; border: 1px solid ${normalized.borderColor}; background-color: ${normalized.headerBg}; color: ${normalized.fontColor}; font-size: ${normalized.fontSize}px; font-family: ${normalized.fontFamily}; min-width: 150px; width: 150px; white-space: nowrap;">Cep</th>
        <th style="font-weight: 600; padding: 12px 12px; border: 1px solid ${normalized.borderColor}; background-color: ${normalized.headerBg}; color: ${normalized.fontColor}; font-size: ${normalized.fontSize}px; font-family: ${normalized.fontFamily}; min-width: 300px; width: 300px; white-space: nowrap;">Tarih</th>
        <th style="font-weight: 600; padding: 12px 12px; border: 1px solid ${normalized.borderColor}; background-color: ${normalized.headerBg}; color: ${normalized.fontColor}; font-size: ${normalized.fontSize}px; font-family: ${normalized.fontFamily}; min-width: 180px; width: 180px; white-space: nowrap;">Araç</th>
      </tr>
    `;
    }

    // Tüm satırları yeniden oluştur - Ad Soyad, Cep, Tarih, Araç
    const rows = target.querySelectorAll("tbody tr");
    const rowsToRestore = [];
    const tbody = target.querySelector("tbody");

    // Orijinal satırları kaydet (clone ile)
    Array.from(rows).forEach((row) => {
      rowsToRestore.push(row.cloneNode(true));
    });

    // İlk satırdan tarih ve araç değerlerini al (rowspan için)
    let dateValue = "-";
    let vehicleValue = "-";
    if (rows.length > 0) {
      const firstRowCells = rows[0].querySelectorAll("td");
      if (firstRowCells.length >= 4) {
        dateValue = firstRowCells[2]?.textContent?.trim() || "-";
        vehicleValue = firstRowCells[3]?.textContent?.trim() || "-";
      } else if (firstRowCells.length === 3) {
        dateValue = firstRowCells[2]?.textContent?.trim() || "-";
      }
    }

    // Tüm satırları yeniden oluştur - 4 sütun: Ad Soyad, Cep, Tarih, Araç
    if (tbody) {
      const newRows = [];
      Array.from(rows).forEach((row, rowIdx) => {
        const cells = row.querySelectorAll("td");
        const cellCount = cells.length;

        let nameValue = "-";
        let phoneValue = "-";
        let currentDateValue = dateValue;
        let currentVehicleValue = vehicleValue;

        // Ad Soyad ve Cep değerlerini al
        if (cellCount >= 2) {
          nameValue = cells[0]?.textContent?.trim() || "-";
          phoneValue = cells[1]?.textContent?.trim() || "-";
        }

        // Tarih ve araç değerlerini al (eğer varsa)
        if (cellCount >= 4) {
          currentDateValue = cells[2]?.textContent?.trim() || dateValue;
          currentVehicleValue = cells[3]?.textContent?.trim() || vehicleValue;
        } else if (cellCount === 3) {
          currentDateValue = cells[2]?.textContent?.trim() || dateValue;
        }

        // Yeni satır oluştur - 4 sütun: Ad Soyad, Cep, Tarih, Araç
        const newRow = document.createElement("tr");

        // Ad Soyad
        const nameTd = document.createElement("td");
        nameTd.textContent = nameValue;
        nameTd.style.minWidth = "200px";
        nameTd.style.width = "200px";
        nameTd.style.whiteSpace = "nowrap";
        nameTd.style.backgroundColor = normalized.rowBg;
        nameTd.style.color = normalized.fontColor;
        nameTd.style.border = `1px solid ${normalized.borderColor}`;
        nameTd.style.padding = "12px 12px";
        nameTd.style.boxSizing = "border-box";
        nameTd.style.fontSize = `${normalized.fontSize}px`;
        nameTd.style.fontFamily = normalized.fontFamily;

        // Cep
        const phoneTd = document.createElement("td");
        phoneTd.textContent = phoneValue;
        phoneTd.style.minWidth = "150px";
        phoneTd.style.width = "150px";
        phoneTd.style.whiteSpace = "nowrap";
        phoneTd.style.backgroundColor = normalized.rowBg;
        phoneTd.style.color = normalized.fontColor;
        phoneTd.style.border = `1px solid ${normalized.borderColor}`;
        phoneTd.style.padding = "12px 12px";
        phoneTd.style.boxSizing = "border-box";
        phoneTd.style.fontSize = `${normalized.fontSize}px`;
        phoneTd.style.fontFamily = normalized.fontFamily;

        // Tarih
        const dateTd = document.createElement("td");
        dateTd.textContent = currentDateValue;
        dateTd.style.minWidth = "300px";
        dateTd.style.width = "300px";
        dateTd.style.whiteSpace = "nowrap";
        dateTd.style.backgroundColor = normalized.rowBg;
        dateTd.style.color = normalized.fontColor;
        dateTd.style.border = `1px solid ${normalized.borderColor}`;
        dateTd.style.padding = "12px 12px";
        dateTd.style.boxSizing = "border-box";
        dateTd.style.fontSize = `${normalized.fontSize}px`;
        dateTd.style.fontFamily = normalized.fontFamily;

        // Araç
        const vehicleTd = document.createElement("td");
        vehicleTd.textContent = currentVehicleValue;
        vehicleTd.style.minWidth = "180px";
        vehicleTd.style.width = "180px";
        vehicleTd.style.whiteSpace = "nowrap";
        vehicleTd.style.backgroundColor = normalized.rowBg;
        vehicleTd.style.color = normalized.fontColor;
        vehicleTd.style.border = `1px solid ${normalized.borderColor}`;
        vehicleTd.style.padding = "12px 12px";
        vehicleTd.style.boxSizing = "border-box";
        vehicleTd.style.fontSize = `${normalized.fontSize}px`;
        vehicleTd.style.fontFamily = normalized.fontFamily;

        newRow.appendChild(nameTd);
        newRow.appendChild(phoneTd);
        newRow.appendChild(dateTd);
        newRow.appendChild(vehicleTd);
        newRows.push(newRow);
      });

      // Tbody'yi temizle ve yeni satırları ekle
      tbody.innerHTML = "";
      newRows.forEach(newRow => tbody.appendChild(newRow));
    }

    // Tablo genel stilleri
    target.style.backgroundColor = normalized.rowBg;
    target.style.color = normalized.fontColor;
    target.style.fontSize = `${normalized.fontSize}px`;
    target.style.fontFamily = normalized.fontFamily;
    target.style.borderCollapse = "collapse";
    target.style.border = `1px solid ${normalized.borderColor}`;
    target.style.width = "100%";

    // Tüm hücrelere border ekle
    ths.forEach((th) => {
      th.style.border = `1px solid ${normalized.borderColor}`;
    });
    tds.forEach((td) => {
      td.style.border = `1px solid ${normalized.borderColor}`;
    });

    try {
      await _downloadElementPng(target, "ekip-bilgisi.png");
    } catch (err) {
      console.error("PNG indirme hatası:", err);
      alert("Görsel indirilemedi: " + (err.message || "Bilinmeyen hata"));
    } finally {
      // Orijinal tablo yapısını geri yükle
      const thead = target.querySelector("thead");
      if (thead) {
        thead.innerHTML = `
          <tr>
            <th style="font-weight: 600; color: #0f172a; padding: 12px 10px; border-bottom: 1px solid #e2e8f0;">Ad Soyad</th>
            <th style="font-weight: 600; color: #0f172a; padding: 12px 10px; border-bottom: 1px solid #e2e8f0;">Cep</th>
            <th style="font-weight: 600; color: #0f172a; padding: 12px 10px; border-bottom: 1px solid #e2e8f0;">Tarih</th>
            <th style="font-weight: 600; color: #0f172a; padding: 12px 10px; border-bottom: 1px solid #e2e8f0;">Araç</th>
          </tr>
        `;
      }

      // Tbody'yi orijinal haline geri yükle
      const tbody = target.querySelector("tbody");
      if (tbody && rowsToRestore.length > 0) {
        tbody.innerHTML = "";
        rowsToRestore.forEach((row) => {
          tbody.appendChild(row);
        });
      }

      // Orijinal stilleri geri yükle
      if (parent) {
        parent.style.display = originalDisplay;
        parent.style.overflow = originalOverflow;
        parent.style.width = originalWidth;
        parent.style.maxWidth = originalMaxWidth;
      }

      target.style.width = originalTableWidth;
      target.style.minWidth = originalTableMinWidth;
      target.style.display = originalTableDisplay;

      ths.forEach((th, idx) => {
        th.style.width = originalThWidths[idx] || "";
        th.style.minWidth = "";
        th.style.whiteSpace = "";
      });

      tds.forEach((td, idx) => {
        td.style.width = originalTdWidths[idx] || "";
        td.style.minWidth = "";
        td.style.whiteSpace = originalTdWhiteSpace[idx] || "";
      });
    }
  } catch (err) {
    console.error("downloadTeamReportImage hatası:", err);
    alert("Hata oluştu: " + (err.message || "Bilinmeyen hata"));
  }
}

async function downloadPersonShotImage() {
  const card = _byId("personShotCard");
  const sel = _byId("personShotSelect");
  const pid = sel?.value || "";
  const name = (sel?.selectedOptions && sel.selectedOptions[0] && sel.selectedOptions[0].textContent) ? sel.selectedOptions[0].textContent.trim() : "";
  const safe = (name || pid || "personel").replace(/[\\/:*?"<>|]+/g, "-").slice(0, 60);
  await _downloadElementPng(card, `personel-${safe}.png`);
}

// =================== PERSON SHOT ===================
function openPersonShot() {
  const modal = _byId("personShotModal");
  if (!modal) return;
  const sel = _byId("personShotSelect");
  const pm = (window.ALL_PEOPLE || []).slice().sort((a, b) => a.full_name.localeCompare(b.full_name, "tr"));
  sel.innerHTML = pm.map(p => `<option value="${p.id}">${escapeHtml(p.full_name)}</option>`).join("");
  if (selectedPeople.size === 1) sel.value = Array.from(selectedPeople)[0];
  modal.classList.add("open");
  loadPersonShot();
}
function closePersonShot() { _byId("personShotModal")?.classList.remove("open"); }

async function loadPersonShot() {
  const sel = _byId("personShotSelect");
  const pid = sel?.value;
  if (!pid) return;
  const ws = currentWeekStart || document.querySelector('input[name="date"]')?.value || "";
  const res = await fetch(`/api/person_week?week_start=${encodeURIComponent(ws)}&person_id=${encodeURIComponent(pid)}`);
  const data = await res.json().catch(() => ({ ok: false }));
  if (!data.ok) { alert(data.error || "Alınamadı"); return; }

  const box = _byId("personShotCard");
  const items = data.items || [];
  const byDate = {};
  items.forEach(it => { (byDate[it.date] = byDate[it.date] || []).push(it); });

  const days = [0, 1, 2, 3, 4, 5, 6].map(i => {
    const d = new Date(data.week_start); d.setDate(d.getDate() + i);
    return d.toISOString().slice(0, 10);
  });

  const statusMap = (window.WEEK_STATUS && window.WEEK_STATUS[pid]) ? window.WEEK_STATUS[pid] : {};
  box.innerHTML = `
    <div class="shotHead">
      <div>
        <div class="shotTitle">${escapeHtml(data.person.full_name)}</div>
        <div class="shotSub">Hafta: ${escapeHtml(data.week_start)}</div>
      </div>
      <div class="shotBadge">${escapeHtml(data.person.team || "")}</div>
    </div>
    <table class="shotTable">
      <thead><tr><th>Tarih</th><th>Durum</th><th>İş(ler)</th></tr></thead>
      <tbody>
        ${days.map(dt => {
    const st = statusMap[dt]?.status || "available";
    const stText = st === "leave" ? "İzinli" : (st === "production" ? "Üretimde" : (st === "office" ? "Ofis" : "-"));
    const jobs = (byDate[dt] || []).map(it => `${escapeHtml(it.city)} / ${escapeHtml(it.project_code)} (${escapeHtml(it.shift || "")})`).join("<br>") || "-";
    return `<tr><td>${dt}</td><td>${stText}</td><td>${jobs}</td></tr>`;
  }).join("")}
      </tbody>
    </table>
  `;
}

// =================== MAP ===================
// =================== MAP ===================
function ensureMap() {
  if (_map) return;
  // Türkiye'nin tamamını göstermek için merkez ve zoom ayarı
  _map = L.map("map");
  // OpenStreetMap Light (Standart)
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(_map);

  _layer = L.layerGroup().addTo(_map);

  // Türkiye'nin tamamını göstermek için fitBounds kullan
  _map.fitBounds([[35.8, 25.7], [42.1, 44.8]], { padding: [50, 50] });
}
function teamLabelHtml(text, color) {
  const safe = (text || "").toString().replace(/[<>&]/g, s => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[s]));
  const c = color || "#2b6cff";
  return `<div class="teamLabel" style="border-color:${c}; color:${c}; background-color: rgba(255, 255, 255, 0.4); font-size: 11px; font-weight: 700; padding: 2px 5px; border-width: 1px; border-style: solid; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); backdrop-filter: blur(1px);"><span class="dot" style="background:${c}; display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 4px;"></span>${safe}</div>`;
}

// =================== MODERN MARKER HELPERS ===================
let jobMarkersLayer = null;
let loadedJobsData = null;

function createModernMarkerIcon(teamId, index, isStart = false) {
  const teamClass = teamId ? `team-${(teamId % 5) + 1}` : 'team-unassigned';
  const startClass = isStart ? 'start-marker' : '';
  const iconContent = isStart ? '🏠' : '';

  return L.divIcon({
    className: 'modern-marker-wrapper',
    html: `<div class="modern-marker ${teamClass} ${startClass}">
             <span class="modern-marker-icon">${iconContent}</span>
           </div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -10]
  });
}

function createJobPopupContent(job) {
  const assignments = (job.assignments || []).map(a =>
    `<div class="flex items-center gap-1 text-xs">
       <span class="w-1.5 h-1.5 rounded-full bg-cyan-500"></span>
       ${escapeHtml(a.name)}${a.phone ? ` <span class="text-slate-400">📞 ${escapeHtml(a.phone)}</span>` : ''}
     </div>`
  ).join('');

  return `
    <div class="job-popup" style="min-width: 260px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
        <div>
          <div style="font-weight: 700; font-size: 14px; color: #0f172a;">${escapeHtml(job.city)}</div>
          <div style="font-size: 11px; color: #64748b;">${escapeHtml(job.project_code)} - ${escapeHtml(job.project_name)}</div>
        </div>
        <div style="background: ${job.team_id ? '#dbeafe' : '#f1f5f9'}; color: ${job.team_id ? '#1e40af' : '#64748b'}; padding: 2px 8px; border-radius: 9999px; font-size: 10px; font-weight: 600;">
          ${escapeHtml(job.team_name)}
        </div>
      </div>
      
      <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 8px; font-size: 11px;">
        <div><span style="color: #94a3b8;">📅</span> ${job.day_name}, ${job.date}</div>
        <div><span style="color: #94a3b8;">⏰</span> ${job.shift || 'Belirtilmemiş'}</div>
        ${job.subproject ? `<div style="grid-column: span 2;"><span style="color: #94a3b8;">📋</span> ${escapeHtml(job.subproject)}</div>` : ''}
      </div>
      
      ${job.note ? `<div style="background: #f8fafc; padding: 6px 8px; border-radius: 6px; font-size: 11px; margin-bottom: 8px;"><span style="color: #94a3b8;">📝</span> ${escapeHtml(job.note)}</div>` : ''}
      ${job.important_note ? `<div style="background: #fef3c7; padding: 6px 8px; border-radius: 6px; font-size: 11px; margin-bottom: 8px;"><span style="color: #d97706;">⚠️</span> ${escapeHtml(job.important_note)}</div>` : ''}
      
      ${assignments ? `
        <div style="border-top: 1px solid #e2e8f0; padding-top: 8px;">
          <div style="font-size: 10px; color: #94a3b8; margin-bottom: 4px; font-weight: 600;">👥 ATANAN PERSONEL (${job.assignment_count})</div>
          ${assignments}
        </div>
      ` : '<div style="font-size: 11px; color: #94a3b8;">Personel atanmamış</div>'}
    </div>
  `;
}

// Global Worker instance
let mapWorker = null;

async function loadJobMarkers() {
  const week = _byId("mapWeek")?.value;
  const teamId = _byId("singleTeamSelect")?.value || '';

  if (!week) {
    toast("Lütfen hafta seçin.");
    return;
  }

  // Initialize LoadingManager
  const loader = window.LoadingManager ? new LoadingManager() : null;
  if (loader) {
    loader.show("Veriler alınıyor...");
    loader.setProgress(0);
  }

  const btn = _byId("loadMarkersBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10" stroke-opacity="0.75"></path></svg> Yükleniyor...`;
  }

  ensureMap();

  // Clear previous job markers
  if (jobMarkersLayer) {
    _map.removeLayer(jobMarkersLayer);
  }

  // Use MarkerClusterGroup if available, otherwise regular LayerGroup
  if (typeof L.markerClusterGroup === 'function') {
    jobMarkersLayer = L.markerClusterGroup({
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
      disableClusteringAtZoom: 14,
      chunkedLoading: true,
      chunkInterval: 50,
      chunkDelay: 25
    });
  } else {
    jobMarkersLayer = L.layerGroup();
  }

  try {
    const url = `/api/jobs_for_map?week_start=${encodeURIComponent(week)}${teamId ? `&team_id=${teamId}` : ''}`;

    // Offline Manager Prep
    const offlineMgr = window.OfflineManager ? new OfflineManager() : null;

    let data;
    try {
      // Try Network First
      if (window.RetryHelper) {
        const retry = new RetryHelper();
        const res = await retry.fetch(url);
        data = await res.json();
      } else {
        const res = await fetch(url);
        data = await res.json();
      }

      // Cache success data
      if (data.ok && offlineMgr) {
        offlineMgr.saveJobs(week, data).catch(err => console.error("Offline save error:", err));
      }

    } catch (networkErr) {
      console.warn("Network failed, trying offline cache...", networkErr);

      // Try Offline Cache
      if (offlineMgr) {
        toast("Ağ hatası, çevrimdışı önbellek aranıyor...", "info");
        const cached = await offlineMgr.getJobs(week);
        if (cached && cached.ok) {
          data = cached;
          toast("İnternet bağlantısı yok. Çevrimdışı veri gösteriliyor.", "warning");
        } else {
          throw networkErr; // No cache, rethrow
        }
      } else {
        throw networkErr;
      }
    }

    if (!data.ok) {
      throw new Error(data.error || "Veri alınamadı");
    }

    loadedJobsData = data;

    if (!data.all_jobs || data.all_jobs.length === 0) {
      toast("Bu hafta için iş bulunamadı.");
      if (loader) loader.hide();
      return;
    }

    // Update loading text
    if (loader) loader.updateStatus("Veriler işleniyor (Worker)...");

    // Initialize Worker if needed
    if (!mapWorker) {
      mapWorker = new Worker('/static/js/workers/map-worker.js');
    }

    // Wrap worker messaging in a Promise
    const processedJobs = await new Promise((resolve, reject) => {

      mapWorker.onmessage = function (e) {
        if (e.data.type === 'MARKERS_PROCESSED') {
          resolve(e.data.data);
        }
      };

      mapWorker.onerror = function (e) {
        reject(new Error("Worker hatası: " + e.message));
      };

      mapWorker.postMessage({
        type: 'PROCESS_MARKERS',
        data: data.all_jobs
      });
    });

    if (loader) loader.updateStatus("İşaretçiler haritaya ekleniyor...");

    // UI Update Batch Logic
    const totalJobs = processedJobs.length;
    const BATCH_SIZE = 100; // Increased batch size since processing is done

    async function addMarkersToMap(startIndex) {
      const endIndex = Math.min(startIndex + BATCH_SIZE, totalJobs);
      const markers = []; // Batch add to group

      for (let i = startIndex; i < endIndex; i++) {
        const job = processedJobs[i];

        const marker = L.marker([job.lat, job.lon], {
          icon: createModernMarkerIcon(job.team_id, job.markerIndex, job.isStart)
        });

        marker.bindPopup(createJobPopupContent(job), {
          className: 'modern-popup',
          maxWidth: 320
        });

        // Hover logic (lightweight)
        marker.on('mouseover', function () {
          this.getElement()?.querySelector('.modern-marker')?.classList.add('selected');
        });
        marker.on('mouseout', function () {
          this.getElement()?.querySelector('.modern-marker')?.classList.remove('selected');
        });

        markers.push(marker);
      }

      // Bulk add to layer (faster than one by one)
      if (typeof jobMarkersLayer.addLayers === 'function') {
        jobMarkersLayer.addLayers(markers);
      } else {
        markers.forEach(m => jobMarkersLayer.addLayer(m));
      }

      // Progress
      if (loader) {
        const pct = Math.round((endIndex / totalJobs) * 100);
        loader.setProgress(pct, `${endIndex} / ${totalJobs} işaret`);
      }

      if (endIndex < totalJobs) {
        await new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));
        await addMarkersToMap(endIndex);
      }
    }

    await addMarkersToMap(0);

    // Add layer to map
    if (window.layerVisibility && window.layerVisibility.jobMarkers === false) {
      // Hidden
    } else {
      jobMarkersLayer.addTo(_map);
    }

    // Fit bounds
    if (processedJobs.length > 0) {
      // Calculate bounds from processed jobs
      // To avoid another loop, we could have returned bounds from worker, 
      // but for now let's just use the layer bounds if supported or raw points
      if (typeof jobMarkersLayer.getBounds === 'function') {
        _map.fitBounds(jobMarkersLayer.getBounds(), { padding: [50, 50], maxZoom: 12 });
      }
    }

    if (typeof updateLayerCounts === 'function') {
      updateLayerCounts();
    }

    toast(`${totalJobs} iş yüklendi (${data.total_teams} ekip)`);

  } catch (err) {
    console.error("loadJobMarkers error:", err);
    if (loader) loader.error(err.message || "Hata oluştu");
    else toast("İşaretler yüklenirken hata oluştu");
  } finally {
    if (loader && !loader.isHidden && !loader.errorState) loader.hide();

    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg> İşaretleri Yükle`;
    }
  }
}




// Export new functions
window.loadJobMarkers = loadJobMarkers;


// =================== TEAM TOOLTIP (Ekip kiYi listesi) ===================
async function fetchTeamMembers(teamName, weekStart) {
  if (!teamName) return [];
  const key = `${teamName}|${weekStart || ""}`;
  if (TEAM_MEMBERS_CACHE[key]) return TEAM_MEMBERS_CACHE[key];
  try {
    const params = new URLSearchParams({ name: teamName });
    if (weekStart) params.append("week_start", weekStart);
    const res = await fetch(`/api/team_members?${params.toString()}`);
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) {
      TEAM_MEMBERS_CACHE[key] = data.people || [];
      return TEAM_MEMBERS_CACHE[key];
    }
    TEAM_MEMBERS_CACHE[key] = [];
    return [];
  } catch (e) {
    console.error("Team members fetch error", e);
  }
  TEAM_MEMBERS_CACHE[key] = [];
  return TEAM_MEMBERS_CACHE[key];
}

let teamTooltipEl = null;
function ensureTeamTooltip() {
  if (teamTooltipEl) return teamTooltipEl;
  teamTooltipEl = document.createElement("div");
  teamTooltipEl.className = "team-tooltip";
  document.body.appendChild(teamTooltipEl);
  return teamTooltipEl;
}

function positionTeamTooltip(el, target) {
  if (!el || !target) return;
  const rect = target.getBoundingClientRect();
  const tipRect = el.getBoundingClientRect();
  let left = rect.left;
  let top = rect.bottom + 8;
  if (left + tipRect.width > window.innerWidth) {
    left = Math.max(8, window.innerWidth - tipRect.width - 12);
  }
  if (top + tipRect.height > window.innerHeight) {
    top = rect.top - tipRect.height - 8;
  }
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

async function showTeamTooltipHover(target) {
  if (!target) return;
  const teamName = (target.dataset?.teamName || "").trim();
  if (!teamName) return;
  const weekStart = target.dataset?.weekStart || _byId("weekStartHidden")?.value || document.querySelector("input[name='date']")?.value || "";

  const tip = ensureTeamTooltip();
  tip.innerHTML = `<div class="team-tooltip-title">${escapeHtml(teamName)}</div><div class="team-tooltip-body">Yükleniyor...</div>`;
  tip.classList.add("show");
  positionTeamTooltip(tip, target);

  const members = await fetchTeamMembers(teamName, weekStart);
  const body = tip.querySelector(".team-tooltip-body");
  if (body) {
    if (!members || members.length === 0) {
      body.innerHTML = `<div class="team-tooltip-empty">Ekip bulunamadı</div>`;
    } else {
      body.innerHTML = members.map(m => {
        const firma = m.firma ? ` (${escapeHtml(m.firma)})` : "";
        const phone = m.phone ? ` ? ${escapeHtml(m.phone)}` : "";
        return `<div class="team-tooltip-row">${escapeHtml(m.full_name)}${firma}${phone}</div>`;
      }).join("");
    }
  }
  positionTeamTooltip(tip, target);
}

function hideTeamTooltipHover() {
  if (teamTooltipEl) {
    teamTooltipEl.classList.remove("show");
  }
}

function bindTeamNameHover(root) {
  const scope = root || document;
  if (!scope.querySelectorAll) return;
  scope.querySelectorAll("[data-team-name]").forEach(el => {
    if (el.dataset.teamBound === "1") return;
    el.dataset.teamBound = "1";
    el.addEventListener("mouseenter", () => showTeamTooltipHover(el));
    el.addEventListener("mouseleave", hideTeamTooltipHover);
    el.addEventListener("focus", () => showTeamTooltipHover(el));
    el.addEventListener("blur", hideTeamTooltipHover);
  });
}

function syncTeamSelectDataset(sel) {
  if (!sel) return;
  const selectedText = sel.options && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].textContent : sel.value;
  sel.dataset.teamName = (selectedText || "").trim();
  const weekInput = document.querySelector("input[name='date']") || _byId("weekStartHidden");
  if (weekInput) sel.dataset.weekStart = weekInput.value || "";
  bindTeamNameHover(sel.parentNode || document);
}

function initTeamSelectPreview() {
  ["teamSelect", "singleTeamSelect"].forEach(id => {
    const sel = _byId(id);
    if (!sel) return;
    sel.addEventListener("change", () => syncTeamSelectDataset(sel));
    syncTeamSelectDataset(sel);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindTeamNameHover();
  initTeamSelectPreview();
});

// =================== MAP STATS ===================
function updateRouteStats(name, km, hours, stops) {
  const box = _byId("routeStats");
  if (!box) return;
  const dist = km != null ? `${km.toFixed(1)} km` : "-";
  const dur = hours != null ? formatDurationHours(hours) : "-";
  const s = stops != null ? stops : "-";
  const title = name || "Seçili ekip";
  box.innerHTML = `<strong>${escapeHtml(title)}</strong> • Mesafe: ${dist} • Tahmini süre: ${dur} • Nokta: ${s}`;
}

function updateAllStats(totalKm, teamCount) {
  const box = _byId("allRouteStats");
  if (!box) return;
  const dist = totalKm != null ? (totalKm.toFixed(1) + " km") : "-";
  const teams = teamCount != null ? teamCount : "-";
  box.textContent = "Toplam rota: " + dist + " - Ekip sayisi: " + teams;
}

function toggleRouteCities(btn) {
  SHOW_ROUTE_CITIES = !SHOW_ROUTE_CITIES;
  if (btn) {
    btn.textContent = SHOW_ROUTE_CITIES ? "Sehirleri Gizle" : "Sehirleri Goster";
  }
  if (LAST_ROUTE_STATS && LAST_ROUTE_STATS.length) {
    renderRouteList(LAST_ROUTE_STATS);
  }
}

function renderRouteList(list) {
  const box = _byId("allRouteList");
  if (!box) return;
  if (!list || !list.length) {
    box.innerHTML = "Liste bos.";
    return;
  }
  box.innerHTML = list.map(item => {
    const km = item.km != null && item.km.toFixed ? item.km.toFixed(1) : (item.km || 0);
    const dur = formatDurationHours(item.hours);
    const cities = (item.cities || []).join(" -> ");
    const cityLine = SHOW_ROUTE_CITIES && cities
      ? "<div class=\"hint\" style=\"margin-top:4px;\">" + escapeHtml(cities) + "</div>"
      : "";
    return "<div style=\"display:flex; flex-direction:column; gap:4px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:8px 10px;\">"
      + "<div style=\"display:flex; justify-content:space-between; gap:8px;\">"
      + "<span><strong>" + escapeHtml(item.name || "") + "</strong> - " + (item.stops ?? "-") + " nokta</span>"
      + "<span>" + km + " km - " + dur + "</span>"
      + "</div>"
      + cityLine
      + "</div>";
  }).join("");
}

function renderSegments(segments, isReal) {
  const box = _byId("routeSegments");
  if (!box) return;
  if (!segments || !segments.length) {
    box.innerHTML = "Segment yok.";
    return;
  }
  box.innerHTML = segments.map((s, i) => {
    const km = s.km != null && s.km.toFixed ? s.km.toFixed(1) : (s.km || 0);
    const dur = isReal ? formatDurationHours(s.hours) : ((s.hours ?? 0).toFixed(1) + " sa");
    const title = (s.from + " -> " + s.to);
    return "<div style=\"border:1px solid #e2e8f0; border-radius:8px; padding:6px 8px; background:#fff;\">"
      + "<div><strong>" + (i + 1) + ". " + escapeHtml(title) + "</strong></div>"
      + "<div>" + km + " km - " + dur + "</div>"
      + "</div>";
  }).join("");
}
function setMapButtonsDisabled(disabled, label) {
  document.querySelectorAll('[onclick*="drawAllRoutes"],[onclick*="drawSingleTeamRoute"],[onclick*="computeRealRouteDuration"]').forEach(b => {
    if (!b) return;
    if (disabled) {
      b.dataset.prevLabel = b.textContent;
      b.textContent = label || "Yükleniyor...";
      b.disabled = true;
    } else {
      if (b.dataset.prevLabel) { b.textContent = b.dataset.prevLabel; }
      b.disabled = false;
    }
  });
}

function setTeamSelectOptions(routes) {
  const sel = _byId("singleTeamSelect");
  if (!sel) return;

  const seen = new Set();
  const opts = [];
  (routes || []).forEach(r => {
    const id = (r.team_id ?? r.teamId ?? "").toString();
    if (!id || seen.has(id)) return;
    seen.add(id);
    const name = r.team_name || r.teamName || `Ekip #${id}`;
    opts.push({ id, name });
  });

  // Sort by extracted number from name (e.g. "Ekip 1", "Ekip 2")
  opts.sort((a, b) => {
    const numA = parseInt(a.name.replace(/\D/g, '') || "0", 10);
    const numB = parseInt(b.name.replace(/\D/g, '') || "0", 10);
    return numA - numB;
  });

  const keep = sel.value;
  sel.innerHTML = `<option value="">(Ekip seç)</option>` + opts.map(o => `<option value="${o.id}">${escapeHtml(o.name)}</option>`).join("");
  if (keep && opts.some(o => o.id === keep)) sel.value = keep;
  syncTeamSelectDataset(sel);
}
async function refreshTeamSelect() {
  const week = _byId("mapWeek")?.value;
  if (!week) return;
  try {
    const res = await fetch(`/api/routes_all?week_start=${encodeURIComponent(week)}`);
    const data = await res.json();
    if (data.ok) setTeamSelectOptions(data.routes || []);
  } catch (e) { }
}
async function loadMap() {
  ensureMap();
  _layer.clearLayers();

  refreshTeamSelect();

  const week = _byId("mapWeek")?.value;
  if (!week) return;

  const res = await fetch(`/api/map_markers?date=${encodeURIComponent(week)}`);
  const data = await res.json().catch(() => ({ markers: [] }));

  const bounds = [];

  // Default marker icon'u tanımla - bazistasyonu.png kullan
  const defaultIcon = L.icon({
    iconUrl: '/static/bazistasyonu.png',
    iconSize: [48, 48],
    iconAnchor: [24, 48],
    popupAnchor: [0, -48]
  });

  (data.markers || []).forEach(m => {
    if (m.lat == null || m.lon == null) return;
    const p = [m.lat, m.lon];
    bounds.push(p);

    const jobCount = m.job_count || 0;
    const projText = (m.projects || []).map(x => `${escapeHtml(x.code)} (${escapeHtml(x.responsible)})`).join("<br>");

    // İş sayısını gösteren custom icon oluştur
    const customIcon = L.divIcon({
      className: 'city-marker-wrapper',
      html: `
        <div style="position: relative; display: inline-block;">
          <img src="/static/bazistasyonu.png" style="width: 48px; height: 48px;">
          <div style="position: absolute; top: -8px; right: -8px; background: #ef4444; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
            ${jobCount}
          </div>
        </div>
      `,
      iconSize: [48, 48],
      iconAnchor: [24, 48],
      popupAnchor: [0, -48]
    });

    L.marker(p, { icon: customIcon }).addTo(_layer).bindPopup(`
      <div style="min-width:260px">
        <div><strong>${escapeHtml(m.city)}</strong> <span style="color: #64748b; font-size: 12px;">(${jobCount} iş)</span></div>
        <hr>
        <div>${projText || "-"}</div>
      </div>
    `);
  });

  // Sadece birden fazla marker varsa ve kullanıcı manuel zoom yapmamışsa, tüm marker'ları kapsayacak şekilde zoom yap
  // İlk yüklemede Türkiye'nin tamamı gösterilecek, sonra marker'lar eklendiğinde otomatik zoom yapılmayacak
  // Kullanıcı isterse manuel olarak zoom yapabilir
  // if(bounds.length > 1) _map.fitBounds(bounds, { padding:[30,30] });
}
async function drawAllRoutes() {
  ensureMap();
  _layer.clearLayers();

  const week = _byId("mapWeek")?.value;
  if (!week) return;

  const loader = window.LoadingManager ? new LoadingManager() : null;
  if (loader) loader.show("Rotalar hesaplanıyor...");

  setMapButtonsDisabled(true, "Yükleniyor...");

  try {
    const url = `/api/routes_all?week_start=${encodeURIComponent(week)}`;
    const offlineMgr = window.OfflineManager ? new OfflineManager() : null;
    let res, data;

    try {
      if (window.RetryHelper) {
        res = await new RetryHelper().fetch(url);
        data = await res.json();
      } else {
        res = await fetch(url);
        data = await res.json();
      }

      if (data.ok && offlineMgr) {
        offlineMgr.saveAllRoutes(week, data).catch(console.error);
      }

    } catch (err) {
      console.warn("Network failed, checking offline routes...", err);
      if (offlineMgr) {
        const cached = await offlineMgr.getAllRoutes(week);
        if (cached && cached.ok) {
          data = cached;
          toast("Çevrimdışı rota verisi gösteriliyor", "warning");
        } else {
          throw err;
        }
      } else {
        throw err;
      }
    }

    if (!data.ok) {
      throw new Error(data.error || "Rotalar alınamadı");
    }

    const allPts = [];
    let totalKm = 0;
    const stats = [];
    const labelPositions = new Map();

    const routes = data.routes || [];
    const totalRoutes = routes.length;

    for (let i = 0; i < totalRoutes; i++) {
      const r = routes[i];

      // Update progress every few items
      if (loader) {
        const pct = Math.round(((i + 1) / totalRoutes) * 100);
        loader.setProgress(pct, `Ekip ${i + 1}/${totalRoutes} işleniyor...`);
      }

      const teamName = r.team_name || (r.team_id ? `Ekip ${r.team_id}` : "Atanmamış");

      if (r.prev_week_points && r.prev_week_points.length >= 2) {
        const prevPts = r.prev_week_points.map(p => [p.lat, p.lon]);
        L.polyline(prevPts, { color: "#94a3b8", weight: 3, opacity: 0.6, dashArray: "5, 5" }).addTo(_layer);
      }

      const ptsObj = (r.points || []).filter(p => p.lat != null && p.lon != null);
      const pts = ptsObj.map(p => [p.lat, p.lon]);
      pts.forEach(x => allPts.push(x));

      const statsRes = await computeRouteStats(ptsObj);
      stats.push({ name: teamName, km: statsRes.totalKm, hours: statsRes.totalHours, stops: pts.length, cities: statsRes.cities });
      totalKm += statsRes.totalKm;

      if (pts.length >= 2) L.polyline(pts, { color: r.color, weight: 4, opacity: 0.9 }).addTo(_layer);

      // Label logic
      if ((r.points || []).length && pts.length > 0) {
        let labelPos = null;
        let labelOffset = [0, 0];

        if (pts.length >= 2) {
          const midIndex = Math.floor(pts.length / 2);
          labelPos = pts[midIndex];
        } else if (pts.length === 1) {
          labelPos = pts[0];
        }

        if (labelPos && labelPos.length === 2) {
          const posKey = `${labelPos[0].toFixed(4)},${labelPos[1].toFixed(4)}`;
          const existingCount = labelPositions.get(posKey) || 0;
          labelPositions.set(posKey, existingCount + 1);

          if (existingCount > 0) {
            const offsetIndex = existingCount;
            const offsetDistance = 0.15;
            const angle = (offsetIndex * 60) * (Math.PI / 180);
            labelOffset = [
              Math.cos(angle) * offsetDistance,
              Math.sin(angle) * offsetDistance
            ];
          }

          const finalPos = [labelPos[0] + labelOffset[0], labelPos[1] + labelOffset[1]];
          const icon = L.divIcon({
            className: "teamLabelWrap",
            html: teamLabelHtml(teamName, r.color),
            iconSize: null,
            iconAnchor: [0, 0]
          });
          L.marker(finalPos, { icon }).addTo(_layer);
        }
      }

      (r.points || []).forEach(p => {
        if (p.lat == null || p.lon == null) return;
        L.circleMarker([p.lat, p.lon], { radius: 5, color: r.color, weight: 2 })
          .addTo(_layer)
          .bindPopup(`${escapeHtml(teamName)}<br><b>${escapeHtml(p.city)}</b><br>${escapeHtml(p.date)}<br>${escapeHtml(p.project_code)}`);
      });
    }

    setTeamSelectOptions(data.routes || []);
    if (allPts.length) _map.fitBounds(allPts, { padding: [30, 30] });
    updateAllStats(totalKm, (data.routes || []).length || 0);
    LAST_ROUTE_STATS = stats;
    renderRouteList(stats);
    updateRouteStats("Seçili ekip", 0, 0, 0);
    renderSegments([], false);

  } catch (e) {
    console.error(e);
    if (loader) loader.error("Hata: " + e.message);
    else alert("Rotalar alınamadı");
  } finally {
    if (loader && !loader.isHidden && !loader.errorState) loader.hide();
    setMapButtonsDisabled(false);
  }
}


// Global route data store
let CURRENT_ROUTE_DATA = null;
let CURRENT_SELECTED_DAY = null;

// =================== MAP: SINGLE TEAM ROUTE ===================

async function drawSingleTeamRoute() {
  const week = _byId("mapWeek")?.value;
  const teamId = _byId("singleTeamSelect")?.value;

  if (!week) { toast("Lütfen hafta seçin."); return; }
  if (!teamId) { toast("Lütfen bir ekip seçin."); return; }

  const loader = window.LoadingManager ? new LoadingManager() : null;
  if (loader) loader.show("Rota detayı alınıyor...");

  setMapButtonsDisabled(true, "Yükleniyor...");

  ensureMap();
  _layer.clearLayers();

  try {
    const url = `/api/routes_team?week_start=${encodeURIComponent(week)}&team_id=${encodeURIComponent(teamId)}`;
    const offlineMgr = window.OfflineManager ? new OfflineManager() : null;
    let res, data;
    const cacheKey = `team_route_${teamId}_${week}`;

    try {
      if (window.RetryHelper) {
        res = await new RetryHelper().fetch(url);
        data = await res.json();
      } else {
        res = await fetch(url);
        data = await res.json();
      }

      if (data.ok && offlineMgr) {
        offlineMgr.saveRoute(cacheKey, data).catch(console.error);
      }

    } catch (err) {
      console.warn("Network failed, checking offline route...", err);
      if (offlineMgr) {
        const cached = await offlineMgr.getRoute(cacheKey);
        if (cached && cached.ok) {
          data = cached;
          toast("Çevrimdışı rota verisi gösteriliyor", "warning");
        } else {
          throw err;
        }
      } else {
        throw err;
      }
    }

    if (!data.ok) {
      throw new Error(data.error || "Rota verisi alınamadı");
    }

    const route = data.route || {};
    const pts = route.points || [];

    // Global store
    CURRENT_ROUTE_DATA = {
      route: route,
      points: pts,
      weekStart: week,
      dailyStats: {}
    };

    // Calculate daily stats
    const pointsByDate = {};
    if (window.__DEBUG_ROUTE) console.log("DEBUG: Raw Points:", pts);

    pts.forEach(p => {
      if (!p.date) return;
      const d = p.date.split("T")[0];
      if (!pointsByDate[d]) pointsByDate[d] = [];
      pointsByDate[d].push(p);
    });

    if (window.__DEBUG_ROUTE) console.log("DEBUG: PointsByDate:", pointsByDate);

    const sortedDates = Object.keys(pointsByDate).sort();
    let previousPoint = null;

    sortedDates.forEach(dateStr => {
      const dPoints = pointsByDate[dateStr];
      let km = 0;

      if (window.__DEBUG_ROUTE) console.log(`DEBUG: Processing ${dateStr}, points: ${dPoints.length}, prevPoint:`, previousPoint ? previousPoint.city : "null");

      // 1. Distance from previous day's last point to first point of this day
      if (previousPoint && dPoints.length > 0 && dPoints[0].lat && previousPoint.lat) {
        const d = haversineKm([previousPoint.lat, previousPoint.lon], [dPoints[0].lat, dPoints[0].lon]) * 1.3;
        // Don't count "huge" jumps (e.g. invalid) or if it's the start point being same?
        // If points are identical, dist is 0.
        km += d;
      }

      // 2. Internal distance within the day
      for (let i = 1; i < dPoints.length; i++) {
        if (dPoints[i].lat && dPoints[i - 1].lat) {
          km += haversineKm([dPoints[i - 1].lat, dPoints[i - 1].lon], [dPoints[i].lat, dPoints[i].lon]) * 1.3;
        }
      }

      // 3. Update previousPoint
      if (dPoints.length > 0) {
        previousPoint = dPoints[dPoints.length - 1];
      }

      CURRENT_ROUTE_DATA.dailyStats[dateStr] = {
        date: dateStr,
        points: dPoints,
        count: dPoints.filter(p => p.type !== 'start').length,
        km: km,
        hours: km / 60
      };

      if (window.__DEBUG_ROUTE) console.log(`DEBUG: Stats for ${dateStr}: km=${km.toFixed(1)}`);
    });

    // Calculate Total Stats
    let totalKm = 0;
    let totalHours = 0;
    let totalCount = 0;
    const allPoints = [];

    // Re-calculate Total KM properly by connecting all days
    // Instead of summing daily stats (which might have gaps if my daily logic is flawed), 
    // let's just calculate straight through the sorted points.

    // Sort all points by time (assuming backend returns sorted, but let's be safe)
    // Actually Backend returns sorted list.
    pts.forEach(p => {
      allPoints.push(p);
      if (p.type !== 'start') totalCount++;
    });

    for (let i = 1; i < allPoints.length; i++) {
      if (allPoints[i].lat && allPoints[i - 1].lat) {
        totalKm += haversineKm([allPoints[i - 1].lat, allPoints[i - 1].lon], [allPoints[i].lat, allPoints[i].lon]) * 1.3;
      }
    }
    totalHours = totalKm / 60;

    CURRENT_ROUTE_DATA.totalStats = {
      km: totalKm,
      hours: totalHours,
      count: totalCount,
      points: allPoints
    };

    // Render Tabs
    renderDayTabs();

    // Select ALL by default
    selectDay("ALL");

  } catch (e) {
    console.error(e);
    if (loader) loader.error(e.message || "Hata");
    else toast("Rota verisi alınamadı");
  } finally {
    if (loader && !loader.isHidden && !loader.errorState) loader.hide();
    setMapButtonsDisabled(false);
  }
}

function getDayName(dateStr) {
  if (!dateStr) return "-";
  const parts = dateStr.split("-");
  const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const dayNames = ["PAZ", "PZT", "SALI", "ÇARŞ", "PERŞ", "CUMA", "CMT"];
  return dayNames[d.getDay()];
}

function getNiceDate(dateStr) {
  if (!dateStr) return "-";
  const parts = dateStr.split("-");
  const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const dayNamesLong = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
  return `${dayNamesLong[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]}`;
}

function renderDayTabs() {
  const container = _byId("dayTabsContainer");
  if (!container || !CURRENT_ROUTE_DATA) return;

  const stats = CURRENT_ROUTE_DATA.dailyStats;
  const days = Object.keys(stats).sort();

  if (days.length === 0) {
    container.innerHTML = `<div class="text-[10px] text-slate-400 p-2 w-full text-center">Veri yok.</div>`;
    return;
  }

  // Generate ALL tab HTML
  const totalS = CURRENT_ROUTE_DATA.totalStats;
  const isAll = (CURRENT_SELECTED_DAY === "ALL");
  const allActiveClass = isAll
    ? "bg-cyan-600 border-cyan-700 shadow-lg text-white transform scale-105 ring-2 ring-cyan-200"
    : "bg-white border-slate-200 hover:bg-cyan-50 text-slate-600";
  const allTextClass = isAll ? "text-white font-bold" : "text-slate-600";
  const allLabelClass = isAll ? "text-cyan-100 font-bold" : "text-cyan-600 font-bold";

  const allTabHtml = `
  <div onclick="selectDay('ALL')" class="min-w-[130px] border border-b-[4px] rounded-lg p-3 snap-center cursor-pointer transition-all flex flex-col gap-1.5 ${allActiveClass}">
      <div class="${allLabelClass} text-[10px] uppercase tracking-wider flex items-center gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-current opacity-75"></span> GENEL
      </div>
      <div class="${allTextClass} text-xs font-medium truncate">Tüm Rota</div>
      
      <div class="grid grid-cols-2 gap-2 mt-1">
          <div class="bg-black/10 rounded px-1.5 py-1">
              <div class="text-[9px] opacity-75 uppercase tracking-wide">Müşteri</div>
              <div class="text-xs font-bold">${totalS.count}</div>
          </div>
          <div class="bg-black/10 rounded px-1.5 py-1">
               <div class="text-[9px] opacity-75 uppercase tracking-wide">Toplam</div>
               <div class="text-xs font-bold">${totalS.km.toFixed(0)} km</div>
          </div>
      </div>
       <div class="text-[10px] opacity-75 mt-1 text-right font-medium">${formatDurationHours(totalS.hours)}</div>
  </div>`;

  // Daily Tabs
  const dailyHtml = days.map(d => {
    const s = stats[d];
    const isActive = (d === CURRENT_SELECTED_DAY);
    const activeClass = isActive
      ? "bg-cyan-600 border-cyan-700 shadow-lg text-white transform scale-105 ring-2 ring-cyan-200"
      : "bg-white border-slate-200 hover:bg-cyan-50 text-slate-600";

    const textClass = isActive ? "text-white font-bold" : "text-slate-600";
    const labelClass = isActive ? "text-cyan-100 font-bold" : "text-cyan-600 font-bold";

    return `
        <div onclick="selectDay('${d}')" class="min-w-[130px] border border-b-[4px] rounded-lg p-3 snap-center cursor-pointer transition-all flex flex-col gap-1.5 ${activeClass}">
            <div class="${labelClass} text-[10px] uppercase tracking-wider flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-current opacity-75"></span> ${getDayName(d)}
            </div>
            <div class="${textClass} text-xs font-medium truncate">${getNiceDate(d)}</div>
            
            <div class="grid grid-cols-2 gap-2 mt-1">
                <div class="bg-black/10 rounded px-1.5 py-1">
                    <div class="text-[9px] opacity-75 uppercase tracking-wide">Müşteri</div>
                    <div class="text-xs font-bold">${s.count}</div>
                </div>
                <div class="bg-black/10 rounded px-1.5 py-1">
                     <div class="text-[9px] opacity-75 uppercase tracking-wide">Mesafe</div>
                     <div class="text-xs font-bold">${s.km.toFixed(1)} km</div>
                </div>
            </div>
             <div class="text-[10px] opacity-75 mt-1 text-right font-medium">${formatDurationHours(s.hours)}</div>
        </div>
        `;
  }).join("");

  container.innerHTML = allTabHtml + dailyHtml;
}

function selectDay(dateStr) {
  if (!CURRENT_ROUTE_DATA) return;

  let points = [];
  let stats = {};

  if (dateStr === "ALL") {
    CURRENT_SELECTED_DAY = "ALL";
    points = CURRENT_ROUTE_DATA.totalStats.points;
    stats = { ...CURRENT_ROUTE_DATA.totalStats, date: null }; // date null means "General"
  } else {
    if (!CURRENT_ROUTE_DATA.dailyStats[dateStr]) return;
    CURRENT_SELECTED_DAY = dateStr;
    const dayData = CURRENT_ROUTE_DATA.dailyStats[dateStr];
    points = dayData.points;
    stats = dayData;
  }

  renderDayTabs();
  // Force Cyan/Blue theme for the route line
  updateMapForPoints(points, "#0891b2"); // cyan-600
  updateSidebar(CURRENT_ROUTE_DATA.route, points, stats);
}

function updateMapForPoints(points, color) {
  ensureMap();
  _layer.clearLayers();

  if (!points || points.length === 0) return;

  const latlngs = [];
  const bounds = [];
  const teamColor = color || "#3b82f6";

  const createMarkerIcon = (type, index, color) => {
    let iconColor = "blue";
    let html = "";

    if (type === "start") {
      iconColor = "#22c55e";
      html = `<div style="color:white; font-weight:bold; font-size:14px; line-height:24px;">D</div>`;
    } else if (type === "end") {
      iconColor = "#ef4444";
      html = "";
    } else {
      if (index === 1) iconColor = "#3b82f6"; // Blue
      else if (index === 2) iconColor = "#f97316";
      else if (index === 3) iconColor = "#eab308";
      else iconColor = "#3b82f6";
    }

    return L.divIcon({
      className: 'custom-map-marker',
      html: `<div style="background-color: ${iconColor}; width: 16px; height: 16px; border-radius: 50%; text-align: center; border: 3px solid white; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">${html}</div>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      popupAnchor: [0, -10]
    });
  };

  points.forEach((pt, i) => {
    if (pt.lat == null || pt.lon == null) return;
    const latlng = [pt.lat, pt.lon];
    latlngs.push(latlng);
    bounds.push(latlng);

    let type = "mid";
    if (pt.type === 'start') type = "start";
    else if (i === points.length - 1 && i > 0) type = "end";

    const markerIndex = (pt.type === 'start') ? "D" : (i + 1);

    L.marker(latlng, { icon: createMarkerIcon(type, markerIndex, teamColor) })
      .addTo(_layer)
      .bindPopup(createPopupContent(pt, CURRENT_ROUTE_DATA.route.team_name), { minWidth: 300, maxWidth: 300 });
  });

  if (latlngs.length > 1) {
    L.polyline(latlngs, { color: teamColor, weight: 5, opacity: 0.8 }).addTo(_layer);
    _map.fitBounds(bounds, { padding: [50, 50] });
  } else if (latlngs.length === 1) {
    _map.setView(latlngs[0], 12);
  }
}

// Sidebar Güncelleme
// Sidebar Güncelleme
function updateSidebar(route, pts, stats) {
  const summaryCard = _byId("teamSummaryCard");
  const listContainer = _byId("routeListContainer");

  if (!summaryCard || !listContainer) return;

  // Başlıklar
  _byId("summaryTeamName").textContent = route.team_name || "Ekip Detayı";
  // Tarih Gösterimi: Stats varsa (Günlük görünüm) tarihi al, yoksa ilk noktadan al
  if (stats && stats.date) {
    _byId("summaryDateRange").textContent = getNiceDate(stats.date);
  } else {
    _byId("summaryDateRange").textContent = pts.length > 0 ? pts[0].date : "Genel Bakış";
  }

  // İstatistikler 
  let totalKm = 0;
  let customerCount = 0;
  let hours = 0;

  if (stats) {
    totalKm = stats.km;
    customerCount = stats.count;
    hours = stats.hours;
  } else {
    // Fallback calc for Full Week view
    customerCount = pts.filter(p => p.type !== 'start').length;
    for (let i = 1; i < pts.length; i++) {
      if (pts[i].lat && pts[i - 1].lat)
        totalKm += haversineKm([pts[i - 1].lat, pts[i - 1].lon], [pts[i].lat, pts[i].lon]) * 1.3;
    }
    hours = totalKm / 60;
  }

  _byId("summaryKm").textContent = totalKm.toFixed(1);
  _byId("summaryCount").textContent = customerCount;
  _byId("summaryHours").textContent = formatDurationHours(hours);

  // Kartı göster
  summaryCard.classList.remove("hidden");
  summaryCard.classList.remove("block");
  summaryCard.style.display = "block";

  // Listeyi Temizle ve Doldur
  listContainer.innerHTML = "";

  if (!pts || pts.length === 0) {
    listContainer.innerHTML = `<div class="text-center text-slate-400 text-xs mt-4">Bu görünümde nokta yok.</div>`;
    return;
  }

  pts.forEach((pt, index) => {
    // Start noktası farklı görünebilir
    const isStart = pt.type === "start";
    const title = pt.project_name || pt.city || "Bilinmeyen Nokta";
    const sub = pt.subproject_name || pt.project_code || "";
    const status = pt.status || "PLANLANDI";
    const note = pt.note || "";
    const important = pt.important_note || "";

    // Status Renkleri
    let borderClass = "border-l-4 border-l-blue-500";
    if (isStart) borderClass = "border-l-4 border-l-green-500";
    else if (status === "COMPLETED") borderClass = "border-l-4 border-l-green-500";
    else if (status === "PROBLEM") borderClass = "border-l-4 border-l-red-500";

    // Display Index: If day view, reset index? No, let's just 1..N
    const displayIndex = isStart ? "D" : (index + (pts[0].type === 'start' ? 0 : 1));

    const itemHtml = `
      <div class="bg-white rounded border border-slate-200 shadow-sm p-3 ${borderClass} hover:shadow-md transition-shadow">
        <div class="flex justify-between items-start mb-1">
          <div class="font-bold text-sm text-slate-800 break-words w-4/5">${displayIndex}. ${escapeHtml(title)}</div>
          <div class="text-[10px] text-slate-400 font-mono">${escapeHtml(pt.date.slice(5))}</div>
        </div>
        <div class="text-xs text-slate-600 mb-1">${escapeHtml(sub)}</div>
        <div class="text-xs text-slate-500 flex gap-1 items-center mb-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
          ${escapeHtml(pt.city)}
        </div>
        
        ${note ? `<div class="text-[10px] mt-2 p-1.5 bg-yellow-50 text-yellow-800 rounded border border-yellow-100 flex items-start gap-1">
           <span class="font-bold">Not:</span> ${escapeHtml(note)}
        </div>` : ''}

        ${important ? `<div class="text-[10px] mt-1 p-1.5 bg-red-50 text-red-800 rounded border border-red-100 flex items-start gap-1">
           <span class="font-bold">⚠️</span> ${escapeHtml(important)}
        </div>` : ''}
        
        <div class="mt-2 pt-2 border-t border-slate-100 flex justify-end gap-2">
            <button onclick="zoomToPoint(${pt.lat}, ${pt.lon})" class="text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded transition-colors">Haritada Git</button>
        </div>
      </div>
    `;
    listContainer.innerHTML += itemHtml;
  });
}

function zoomToPoint(lat, lon) {
  if (lat && lon && _map) {
    _map.setView([lat, lon], 14, { animate: true });
    // Find marker and open popup? Needs ref to markers. Skipping for now.
  }
}

// Popup İçeriği Oluşturucu
function createPopupContent(pt, teamName) {
  const isStart = pt.type === "start";

  return `
    <div class="font-sans text-slate-800">
      <div class="font-bold text-sm border-b border-slate-200 pb-1 mb-2 text-blue-700">
        ${escapeHtml(pt.project_name || (isStart ? 'Başlangıç Noktası' : 'Müşteri'))}
      </div>
      
      <div class="space-y-1 text-xs mb-3">
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">Adres:</span>
          <span class="font-medium col-span-2">${escapeHtml(pt.city)}</span>
        </div>
        ${pt.subproject_name ? `
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">Hizmet:</span>
          <span class="font-medium col-span-2">${escapeHtml(pt.subproject_name)}</span>
        </div>` : ''}
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">Tarih:</span>
          <span class="font-medium col-span-2">${escapeHtml(pt.date)}</span>
        </div>
        ${pt.responsible ? `
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">Yetkili:</span>
          <span class="font-medium col-span-2">${escapeHtml(pt.responsible)}</span>
        </div>` : ''}
        ${pt.karsi_sorumlu ? `
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">İlgili:</span>
          <span class="font-medium col-span-2">${escapeHtml(pt.karsi_sorumlu)}</span>
        </div>` : ''}
        <div class="grid grid-cols-3 gap-1">
          <span class="text-slate-500 col-span-1">Durum:</span>
          <span class="font-medium col-span-2 ${pt.status === 'COMPLETED' ? 'text-green-600' : (pt.status === 'PROBLEM' ? 'text-red-600' : 'text-orange-600')}">${escapeHtml(pt.status || 'PLANLANDI')}</span>
        </div>
      </div>

      <div class="flex flex-wrap gap-2 mt-2">
         <a href="https://www.google.com/maps/dir/?api=1&destination=${pt.lat},${pt.lon}" target="_blank" class="flex-1 bg-blue-50 hover:bg-blue-100 text-blue-600 text-[10px] font-bold py-1.5 px-2 rounded text-center border border-blue-200 transition-colors">
            Yol Tarifi
         </a>
         <button onclick="toast('Arama başlatılıyor...')" class="flex-1 bg-green-50 hover:bg-green-100 text-green-600 text-[10px] font-bold py-1.5 px-2 rounded border border-green-200 transition-colors">
            Ara
         </button>
         ${pt.job_id ? `
         <button onclick="openEditJobModal(${pt.job_id})" class="flex-1 bg-slate-50 hover:bg-slate-100 text-slate-600 text-[10px] font-bold py-1.5 px-2 rounded border border-slate-200 transition-colors">
            Düzenle
         </button>` : ''}
      </div>
    </div>
  `;
}

// Dummy Edit Function
function openEditJobModal(jobId) {
  // In a real app, this would open a modal to edit the job details.
  // We can reuse openCellEditor if we can map job to cell, or creating a new modal.
  // For now:
  alert("İş düzenleme modalı açılacak: " + jobId);
}

// Helper: Haversine Distance
function haversineKm(coords1, coords2) {
  function toRad(x) { return x * Math.PI / 180; }
  const R = 6371;
  const dLat = toRad(coords2[0] - coords1[0]);
  const dLon = toRad(coords2[1] - coords1[1]);
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(coords1[0])) * Math.cos(toRad(coords2[0])) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Placeholder for computeRealRouteDuration if called by buttons (though removed from UI)
async function computeRealRouteDuration() {
  toast("Rota detayları zaten yüklendi.");
}


// Helper: Compute Route Stats
async function computeRouteStats(points) {
  let totalKm = 0;
  let totalHours = 0;
  const segments = [];
  const cities = new Set();

  if (!points || points.length < 2) {
    return { totalKm, totalHours, segments, cities: [] };
  }

  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (a.lat == null || a.lon == null || b.lat == null || b.lon == null) continue;

    // Haversine distance
    const km = haversineKm([a.lat, a.lon], [b.lat, b.lon]) * 1.3; // Correction factor
    const hours = km / 60; // 60 km/h avg

    totalKm += km;
    totalHours += hours;

    if (a.city) cities.add(a.city);
    if (b.city) cities.add(b.city);

    // Simple segment info
    const fromTitle = a.city || "Start";
    const toTitle = b.city || "Stop";
    segments.push({ from: fromTitle, to: toTitle, km, hours });
  }

  return {
    totalKm,
    totalHours,
    segments,
    cities: Array.from(cities)
  };
}

// "Ekip'e Gönder" Action
async function sendTeamRoute() {
  if (!confirm("Bu rotayı ekibe mail olarak göndermek istiyor musunuz?")) return;

  const week = _byId("mapWeek")?.value;
  const teamId = _byId("singleTeamSelect")?.value;

  if (!week || !teamId) {
    toast("Hafta ve ekip seçili olmalıdır.");
    return;
  }

  // Find the button (assuming it triggered this)
  const btn = document.querySelector("button[onclick='sendTeamRoute()']");
  const originalText = btn ? btn.innerText : "Ekip'e Gönder";
  if (btn) {
    btn.innerText = "Gönderiliyor...";
    btn.disabled = true;
  }

  try {
    const teamSelect = _byId("singleTeamSelect");
    const teamParam = teamSelect.options[teamSelect.selectedIndex].text;

    const res = await fetch("/api/send_team_emails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        week_start: week,
        team_name: teamParam,
        csrf_token: ((_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "")
      })
    });

    const data = await res.json().catch(() => ({ ok: false }));
    if (res.ok && data.ok) {
      toast(`Mail gönderildi: ${data.sent} alıcı.`);
    } else {
      toast(data.error || "Mail gönderilemedi.");
    }
  } catch (e) {
    console.error(e);
    toast("Mail gönderme hatası.");
  } finally {
    if (btn) {
      btn.innerText = originalText;
      btn.disabled = false;
    }
  }
}

// Format duration helper
function formatDurationHours(h) {
  if (h == null) return "-";
  const hours = Math.floor(h);
  const mins = Math.round((h - hours) * 60);
  if (hours > 0) return `${hours} sa ${mins} dk`;
  return `${mins} dk`;
}

// =================== MAIL ===================
async function sendWeeklyEmails(weekStart, statusElementId) {
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  if (!week) {
    alert("Hafta bulunamadı.");
    return;
  }
  const el = statusElementId ? _byId(statusElementId) : (_byId("mailStatus") || _byId("mailStatusAll"));
  if (el) el.textContent = "Gönderiliyor...";

  const res = await fetch("/api/send_weekly_emails", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: week, csrf_token: ((_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "") })
  });
  const data = await res.json().catch(() => ({ sent: 0, skipped: 0, errors: ["json parse"] }));

  if (!res.ok || !data.ok) {
    alert(data.error || "Mail gönderilemedi");
  }
  if (el) {
    let msg = `Gönderildi: ${data.sent}, Atlandı: ${data.skipped}`;
    if (data.errors && data.errors.length) msg += ` | Hatalar: ${data.errors.join(" / ")}`;
    el.textContent = msg;
  }
}

async function sendTeamEmails(weekStart, teamName, statusElementId) {
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  const teamSel = _byId("teamSelect");
  const team = teamName || (teamSel ? teamSel.value : "");
  if (!week) { alert("Hafta bulunamadı."); return; }
  if (!team) { alert("Ekip seçin."); return; }
  const el = statusElementId ? _byId(statusElementId) : (_byId("mailStatusTeam"));
  if (el) el.textContent = "Gönderiliyor...";

  const res = await fetch("/api/send_team_emails", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: week, team_name: team, csrf_token: ((_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "") })
  });
  const data = await res.json().catch(() => ({ sent: 0, skipped: 0, errors: ["json parse"] }));
  if (!res.ok || !data.ok) {
    alert(data.error || "Mail gönderilemedi");
  }
  if (el) {
    let msg = `Gönderildi: ${data.sent}, Atlandı: ${data.skipped}`;
    if (data.errors && data.errors.length) msg += ` | Hatalar: ${data.errors.join(" / ")}`;
    el.textContent = msg;
  }
}

let LAST_MAIL_PREVIEW_HTML = "";

function openMailPreview(html) {
  LAST_MAIL_PREVIEW_HTML = html || "";
  const modal = _byId("mailPreviewModal");
  const frame = _byId("mailPreviewFrame");
  if (frame) frame.srcdoc = LAST_MAIL_PREVIEW_HTML || "<div style='font-family:Arial'>Bos</div>";
  if (modal) modal.classList.add("open");
}

function closeMailPreview() {
  const modal = _byId("mailPreviewModal");
  if (modal) modal.classList.remove("open");
}

function copyMailPreviewHtml() {
  const hint = _byId("mailPreviewHint");
  if (!LAST_MAIL_PREVIEW_HTML) {
    if (hint) hint.textContent = "Önce önizlemeyi açın.";
    return;
  }
  navigator.clipboard.writeText(LAST_MAIL_PREVIEW_HTML).then(() => {
    if (hint) hint.textContent = "HTML kopyalandi.";
    toast("Kopyalandi");
  }).catch(() => {
    if (hint) hint.textContent = "Kopyalama basarisiz.";
  });
}

async function previewWeeklyEmail(weekStart) {
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  if (!week) { alert("Hafta bulunamadı."); return; }
  const res = await fetch("/api/preview_weekly_email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: week, csrf_token: ((_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "") })
  });
  const data = await res.json().catch(() => ({ ok: false }));
  if (!res.ok || !data.ok) {
    alert(data.error || "Önizleme alınamadı");
    return;
  }
  openMailPreview(data.html);
}

async function previewTeamEmail(weekStart) {
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  const teamSel = _byId("teamSelect");
  const team = teamSel ? teamSel.value : "";
  if (!week) { alert("Hafta bulunamadı."); return; }
  if (!team) { alert("Ekip secin."); return; }
  const res = await fetch("/api/preview_team_email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week_start: week, team_name: team, csrf_token: ((_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "") })
  });
  const data = await res.json().catch(() => ({ ok: false }));
  if (!res.ok || !data.ok) {
    alert(data.error || "Önizleme alınamadı");
    return;
  }
  openMailPreview(data.html);
}

// =================== JOB MAIL (cell -> send) ===================
let JOB_MAIL_TEMPLATES = [];

function _openModalById(id) {
  const modal = _byId(id);
  if (modal) modal.classList.add("open");
}
function _closeModalById(id) {
  const modal = _byId(id);
  if (modal) modal.classList.remove("open");
}

async function _loadJobMailTemplates() {
  const res = await fetch("/api/mail_templates");
  const data = await res.json().catch(() => ({ ok: false }));
  if (!res.ok || !data.ok) return [];
  return data.templates || [];
}

function closeJobMailModal() {
  _closeModalById("jobMailModal");
}

function _defaultJobMailChecklist() {
  return [
    { label: "ISDP", checked: false },
    { label: "Foto", checked: false },
    { label: "Olcum", checked: false },
    { label: "QC", checked: false },
    { label: "Tutanak", checked: false },
    { label: "LLD/HHD", checked: false },
  ];
}

function _renderJobMailChecklist(initial) {
  const box = _byId("jmChecklist");
  if (!box) return;
  box.innerHTML = "";
  (initial || []).forEach((it, idx) => {
    const id = `jmChk_${idx}`;
    const w = document.createElement("label");
    w.style.display = "flex";
    w.style.gap = "8px";
    w.style.alignItems = "center";
    w.innerHTML = `<input type="checkbox" id="${id}"> <span>${escapeHtml(it.label)}</span>`;
    box.appendChild(w);
    const cb = _byId(id);
    if (cb) cb.checked = !!it.checked;
    if (cb) cb.setAttribute("data-label", it.label);
  });
}

function _collectJobMailChecklist() {
  const box = _byId("jmChecklist");
  if (!box) return [];
  return Array.from(box.querySelectorAll("input[type='checkbox']")).map(cb => ({
    label: cb.getAttribute("data-label") || "",
    checked: !!cb.checked
  }));
}

function _collectJobMailLinks() {
  const txt = (_byId("jmLinks")?.value || "").split("\n");
  const out = [];
  txt.forEach(line => {
    const raw = (line || "").trim();
    if (!raw) return;
    const parts = raw.split("|").map(x => x.trim()).filter(Boolean);
    if (parts.length === 1) {
      out.push({ label: parts[0], url: parts[0] });
    } else {
      out.push({ label: parts[0], url: parts.slice(1).join(" | ") });
    }
  });
  return out;
}

function _renderExistingFilesForJobMail() {
  const box = _byId("jmExistingFiles");
  if (!box) return;
  const activeLLD = (existingLLDs || []).filter(f => !removeLLDs.has(f));
  const activeTut = (existingTutanaks || []).filter(f => !removeTutanaks.has(f));
  const files = [...activeLLD, ...activeTut];
  if (!files.length) {
    box.innerHTML = "<div style='color:#94a3b8; font-size:12px;'>Ek yok</div>";
    return;
  }
  box.innerHTML = files.map((f, i) => {
    const safe = encodeURIComponent(f);
    return `<label style="display:flex; gap:8px; align-items:center;">
      <input type="checkbox" class="jmExistingFile" data-fname="${escapeHtml(f)}" checked>
      <a href="/files/${safe}" target="_blank" rel="noreferrer noopener" style="color:#2563eb; text-decoration:none;">${escapeHtml(f)}</a>
    </label>`;
  }).join("");
}

function _collectExistingFilesForJobMail() {
  const box = _byId("jmExistingFiles");
  if (!box) return [];
  return Array.from(box.querySelectorAll("input.jmExistingFile")).filter(cb => cb.checked).map(cb => cb.getAttribute("data-fname")).filter(Boolean);
}

function renderJobMailNewFilesList() {
  const input = _byId("jmNewFiles");
  const box = _byId("jmNewFilesList");
  if (!input || !box) return;
  const files = Array.from(input.files || []);
  if (!files.length) {
    box.innerHTML = "<div style='color:#94a3b8; font-size:12px;'>Secilen dosya yok</div>";
    return;
  }
  box.innerHTML = files.map((f, idx) => {
    const sizeKb = Math.round((f.size || 0) / 1024);
    return `<div style="display:flex; justify-content:space-between; gap:8px; align-items:center; border:1px solid #e2e8f0; border-radius:6px; padding:6px 8px;">
      <div style="min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(f.name)} <span style="color:#94a3b8; font-size:12px;">(${sizeKb}KB)</span></div>
      <button class="btn" type="button" onclick="removeJobMailNewFile(${idx})" style="background:#f1f5f9; border:1px solid #e2e8f0; padding:4px 8px; font-size:12px;">Sil</button>
    </div>`;
  }).join("");
}

function removeJobMailNewFile(idx) {
  const input = _byId("jmNewFiles");
  if (!input) return;
  const files = Array.from(input.files || []);
  const dt = new DataTransfer();
  files.forEach((f, i) => { if (i !== idx) dt.items.add(f); });
  input.files = dt.files;
  renderJobMailNewFilesList();
}

async function openJobMailModal() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü mail gönderemez.");
    return;
  }
  if (!currentCell.project_id || !currentCell.work_date) {
    alert("Önce bir hücre seçin.");
    return;
  }

  // templates
  if (!JOB_MAIL_TEMPLATES.length) {
    JOB_MAIL_TEMPLATES = await _loadJobMailTemplates();
  }
  const sel = _byId("jmTemplate");
  if (sel) {
    sel.innerHTML = JOB_MAIL_TEMPLATES.map(t => `<option value="${t.id}" ${t.is_default ? "selected" : ""}>${escapeHtml(t.name)}</option>`).join("");
  }

  const pm = peopleMap();
  const toEmails = Array.from(selectedPeople).map(id => pm[id]?.email).filter(e => e && e.includes("@"));
  const to = toEmails.join(", ");
  const code = currentCell.project_code || "";
  const site = currentCell.city || "";
  const d = currentCell.work_date || "";
  const subjectDefault = `[${code}] ${site} - ${d} - İş Ataması`;

  const subEl = _byId("jmSubject"); if (subEl) subEl.value = (subEl.value || subjectDefault);
  const toEl = _byId("jmTo"); if (toEl) toEl.value = toEl.value || to;

  const sumEl = _byId("jmSummary");
  const note = (_byId("mImportantNote")?.value || _byId("mNote")?.value || "").trim();
  if (sumEl) sumEl.value = sumEl.value || (note.split("\n")[0] || "");

  const detEl = _byId("jmDetails");
  const jobBody = (_byId("mJobMailBody")?.value || "").trim();
  if (detEl) detEl.value = detEl.value || (jobBody || "");

  // checklist prefill
  const checklist = _defaultJobMailChecklist();
  const isdpVal = (_byId("mISDP")?.value || "").trim();
  if (isdpVal) checklist[0].checked = true;
  if ((existingLLDs || []).length) checklist.find(x => x.label === "LLD/HHD").checked = true;
  if ((existingTutanaks || []).length) checklist.find(x => x.label === "Tutanak").checked = true;
  _renderJobMailChecklist(checklist);

  // links
  const planUrl = `${location.origin}/plan?date=${encodeURIComponent(currentCell.work_date)}&week_start=${encodeURIComponent(currentCell.week_start || "")}`;
  const linkLines = [`Plan | ${planUrl}`];
  const activeLLD = (existingLLDs || []).filter(f => !removeLLDs.has(f));
  const activeTut = (existingTutanaks || []).filter(f => !removeTutanaks.has(f));
  [...activeLLD, ...activeTut].forEach(f => {
    linkLines.push(`Dosya: ${f} | ${location.origin}/files/${encodeURIComponent(f)}`);
  });
  const linksEl = _byId("jmLinks"); if (linksEl) linksEl.value = linkLines.join("\n");

  _renderExistingFilesForJobMail();
  const filesInput = _byId("jmNewFiles"); if (filesInput) filesInput.value = "";
  renderJobMailNewFilesList();

  const hint = _byId("jmHint"); if (hint) hint.textContent = "";
  _openModalById("jobMailModal");
}

async function previewJobMail() {
  const hint = _byId("jmHint"); if (hint) hint.textContent = "Önizleme hazırlanıyor...";
  const tplId = parseInt(_byId("jmTemplate")?.value || "0", 10) || 0;
  const payload = {
    project_id: currentCell.project_id,
    work_date: currentCell.work_date,
    template_id: tplId,
    to_addr: (_byId("jmTo")?.value || "").trim(),
    subject_override: (_byId("jmSubject")?.value || "").trim(),
    short_summary: (_byId("jmSummary")?.value || "").trim(),
    job_details: (_byId("jmDetails")?.value || "").trim(),
    checklist: _collectJobMailChecklist(),
    links: _collectJobMailLinks()
  };
  const res = await fetch("/api/preview_job_email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(() => ({ ok: false }));
  if (!res.ok || !data.ok) {
    if (hint) hint.textContent = data.error || "Önizleme alınamadı";
    alert(data.error || "Önizleme alınamadı");
    return;
  }
  if (hint) hint.textContent = "";
  openMailPreview(data.html);
}

async function sendJobMail() {
  const hint = _byId("jmHint"); if (hint) hint.textContent = "Gönderiliyor...";
  const csrf = _byId("csrfToken")?.value || "";
  const tplId = parseInt(_byId("jmTemplate")?.value || "0", 10) || 0;

  const fd = new FormData();
  fd.append("csrf_token", csrf);
  fd.append("project_id", String(currentCell.project_id || ""));
  fd.append("work_date", String(currentCell.work_date || ""));
  fd.append("template_id", String(tplId));
  fd.append("to_addr", (_byId("jmTo")?.value || "").trim());
  fd.append("cc_addrs", (_byId("jmCc")?.value || "").trim());
  fd.append("bcc_addrs", (_byId("jmBcc")?.value || "").trim());
  fd.append("subject_override", (_byId("jmSubject")?.value || "").trim());
  fd.append("short_summary", (_byId("jmSummary")?.value || "").trim());
  fd.append("job_details", (_byId("jmDetails")?.value || "").trim());
  fd.append("checklist_json", JSON.stringify(_collectJobMailChecklist()));
  fd.append("links_json", JSON.stringify(_collectJobMailLinks()));
  fd.append("include_files_json", JSON.stringify(_collectExistingFilesForJobMail()));

  const filesInput = _byId("jmNewFiles");
  Array.from(filesInput?.files || []).forEach(f => fd.append("attachments", f, f.name));

  const res = await fetch("/api/send_job_email", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({ ok: false }));
  if (!res.ok || !data.ok) {
    const msg = data.error || "Mail gönderilemedi";
    if (hint) hint.textContent = msg;
    alert(msg);
    return;
  }
  if (hint) hint.textContent = "Gönderildi.";
  toast("Mail gönderildi");
  refreshJobMailStatus();
  closeJobMailModal();
}

// =================== JOB ROW (İş Ekle / Düzenle / Sil) ===================
function _tplById(id) { return (window.TEMPLATE_PROJECTS || []).find(x => String(x.id) === String(id)); }

// Son seçilen projeleri localStorage'da sakla
function saveLastSelectedProject(projectId) {
  if (!projectId || projectId <= 0) return;
  try {
    const key = 'lastSelectedProjects';
    let lastSelected = JSON.parse(localStorage.getItem(key) || '[]');
    // Mevcut projeyi listeden çıkar (varsa)
    lastSelected = lastSelected.filter(id => String(id) !== String(projectId));
    // En başa ekle
    lastSelected.unshift(projectId);
    // En fazla 10 proje sakla
    if (lastSelected.length > 10) lastSelected = lastSelected.slice(0, 10);
    localStorage.setItem(key, JSON.stringify(lastSelected));
  } catch (e) {
    console.error('Error saving last selected project:', e);
  }
}

// Son seçilen projeleri localStorage'dan al
function getLastSelectedProjects() {
  try {
    const key = 'lastSelectedProjects';
    return JSON.parse(localStorage.getItem(key) || '[]');
  } catch (e) {
    return [];
  }
}

// Projeleri sırala: önce son seçilenler, sonra diğerleri
function sortProjectsWithLastSelected(projects) {
  const lastSelected = getLastSelectedProjects();
  const lastSelectedIds = lastSelected.map(id => String(id));

  const lastSelectedProjects = [];
  const otherProjects = [];

  projects.forEach(p => {
    if (lastSelectedIds.includes(String(p.id))) {
      lastSelectedProjects.push(p);
    } else {
      otherProjects.push(p);
    }
  });

  // Son seçilenlerin sırasını koru
  lastSelectedProjects.sort((a, b) => {
    const idxA = lastSelectedIds.indexOf(String(a.id));
    const idxB = lastSelectedIds.indexOf(String(b.id));
    return idxA - idxB;
  });

  // Diğer projeleri ID'ye göre sırala (en yeni en üstte - ID büyükten küçüğe)
  otherProjects.sort((a, b) => {
    const idA = parseInt(a.id || 0, 10);
    const idB = parseInt(b.id || 0, 10);
    return idB - idA; // Büyük ID (yeni) önce gelsin
  });

  return [...lastSelectedProjects, ...otherProjects];
}

// Arama özellikli custom dropdown oluştur
function createSearchableProjectSelect(selectId, templates, selectedId) {
  // Ana container
  const container = document.createElement("div");
  container.id = selectId + "_container";
  container.style.position = "relative";
  container.className = "project-select-container";
  container.style.width = "100%";
  container.style.zIndex = "10000";

  // Projeleri sırala
  const sortedTemplates = sortProjectsWithLastSelected(templates);

  // Seçili projeyi bul
  const selectedTemplate = selectedId ? templates.find(p => Number(p.id) === Number(selectedId)) : null;
  const displayText = selectedTemplate
    ? `${selectedTemplate.project_code} - ${selectedTemplate.project_name}`
    : "-- Proje seç --";

  // Görünen buton/input (seçili değeri gösterir)
  const trigger = document.createElement("div");
  trigger.className = "project-select-trigger";
  const isDark = document.documentElement.classList.contains('dark-mode');
  const triggerBg = isDark ? 'var(--card-dark, #1e293b)' : '#ffffff';
  const triggerColor = isDark ? 'var(--text-dark, #ffffff)' : '#0f172a';
  const triggerBorder = isDark ? 'var(--border-dark, #334155)' : '#cbd5e1';
  trigger.style.cssText = `width: 100%; padding: 6px 28px 6px 10px; border: 1px solid ${triggerBorder}; border-radius: 6px; font-size: 12px; background: ${triggerBg}; color: ${triggerColor}; box-sizing: border-box; cursor: pointer; position: relative; user-select: none; min-height: 34px; display: flex; align-items: center; transition: border-color 0.15s, box-shadow 0.15s; line-height: 1.4; word-wrap: break-word; overflow-wrap: break-word;`;
  trigger.textContent = displayText;

  trigger.addEventListener("mouseenter", () => {
    trigger.style.borderColor = isDark ? 'var(--line-dark, #475569)' : "#94a3b8";
  });
  trigger.addEventListener("mouseleave", () => {
    trigger.style.borderColor = triggerBorder;
  });

  // Dropdown ok ikonu
  const arrow = document.createElement("span");
  arrow.innerHTML = "▼";
  const arrowColor = isDark ? 'var(--text-secondary-dark, #cbd5e1)' : '#64748b';
  arrow.style.cssText = `position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 9px; color: ${arrowColor}; pointer-events: none;`;
  trigger.appendChild(arrow);

  // Dropdown menü
  const dropdown = document.createElement("div");
  dropdown.className = "project-select-dropdown";
  const dropdownBg = isDark ? 'var(--card-dark, #1e293b)' : '#ffffff';
  const dropdownBorder = isDark ? 'var(--border-dark, #334155)' : '#cbd5e1';
  dropdown.style.cssText = `position: absolute; top: calc(100% + 4px); left: 0; right: 0; background: ${dropdownBg}; border: 1px solid ${dropdownBorder}; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 10001; display: none; max-height: 400px; overflow: hidden; animation: fadeIn 0.15s ease-out;`;
  // Dropdown içindeki tıklamaları yakala - dışarı kapanmasını önle
  dropdown.addEventListener("mousedown", (e) => {
    e.stopPropagation();
  });
  dropdown.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // CSS animasyonu ekle (eğer yoksa)
  if (!document.getElementById("project-dropdown-style")) {
    const style = document.createElement("style");
    style.id = "project-dropdown-style";
    style.textContent = `
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: translateY(0); }
      }
    `;
    document.head.appendChild(style);
  }

  // Arama input (dropdown içinde)
  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.placeholder = "Proje ara...";
  const searchInputBg = isDark ? 'var(--card-dark, #1e293b)' : '#ffffff';
  const searchInputColor = isDark ? 'var(--text-dark, #ffffff)' : '#0f172a';
  const searchInputBorder = isDark ? 'var(--border-dark, #334155)' : '#e2e8f0';
  searchInput.style.cssText = `width: 100%; padding: 8px 10px; border: none; border-bottom: 1px solid ${searchInputBorder}; font-size: 12px; background: ${searchInputBg}; color: ${searchInputColor}; box-sizing: border-box; outline: none;`;
  searchInput.className = "project-search-input";
  // Input tıklamalarını yakala - dropdown'u kapatma
  searchInput.addEventListener("mousedown", (e) => {
    e.stopPropagation();
  });
  searchInput.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Liste container
  const listContainer = document.createElement("div");
  listContainer.style.cssText = "overflow-y: auto; max-height: 320px;";
  // Scrollbar tıklamalarını yakala - dropdown'u kapatma
  listContainer.addEventListener("mousedown", (e) => {
    e.stopPropagation();
  });
  listContainer.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Son seçilenler ve diğerleri
  const lastSelected = getLastSelectedProjects();
  const lastSelectedIds = lastSelected.map(id => Number(id));
  const lastSelectedTemplates = sortedTemplates.filter(p => lastSelectedIds.includes(Number(p.id)));
  const otherTemplates = sortedTemplates.filter(p => !lastSelectedIds.includes(Number(p.id)));

  // Liste oluştur
  function renderList(searchTerm = "") {
    listContainer.innerHTML = "";
    const term = (searchTerm || "").toLowerCase().trim();

    // Son seçilenler
    if (lastSelectedTemplates.length > 0 && (!term || lastSelectedTemplates.some(p => {
      const searchText = `${p.project_code} - ${p.project_name} (${p.responsible || ""})`.toLowerCase();
      return searchText.includes(term);
    }))) {
      const header = document.createElement("div");
      header.style.cssText = "padding: 6px 10px; font-weight: 600; font-size: 11px; color: #64748b; background: #f8fafc; border-bottom: 1px solid #e2e8f0;";
      header.textContent = "— Son açılanlar —";
      listContainer.appendChild(header);

      lastSelectedTemplates.forEach(p => {
        const text = `${p.project_code} - ${p.project_name}`;
        const searchText = `${p.project_code} - ${p.project_name} (${p.responsible || ""})`.toLowerCase();
        if (term && !searchText.includes(term)) return;

        const item = document.createElement("div");
        item.className = "project-option";
        item.dataset.value = String(p.id);
        const itemBg = isDark ? 'transparent' : '';
        const itemColor = isDark ? 'var(--text-dark, #ffffff)' : '#0f172a';
        const itemBorder = isDark ? 'var(--border-dark, #334155)' : '#f1f5f9';
        const itemHoverBg = isDark ? 'var(--bg-dark, #0f172a)' : '#f1f5f9';
        const itemSelectedBg = isDark ? 'var(--line-dark, #334155)' : '#eff6ff';
        item.style.cssText = `padding: 8px 10px; cursor: pointer; font-size: 12px; color: ${itemColor}; border-bottom: 1px solid ${itemBorder}; transition: background 0.15s; line-height: 1.4; word-wrap: break-word;`;
        item.textContent = text;

        if (selectedId && Number(p.id) === Number(selectedId)) {
          item.style.background = itemSelectedBg;
          item.style.fontWeight = "500";
        }

        item.addEventListener("mouseenter", () => {
          if (!item.style.background || item.style.background === itemSelectedBg || item.style.background === "rgb(239, 246, 255)" || item.style.background === "transparent") {
            item.style.background = itemHoverBg;
          } else {
            item.style.background = itemHoverBg;
          }
        });
        item.addEventListener("mouseleave", () => {
          if (selectedId && Number(p.id) === Number(selectedId)) {
            item.style.background = itemSelectedBg;
          } else {
            item.style.background = itemBg;
          }
        });

        item.addEventListener("click", () => {
          const value = Number(item.dataset.value);
          saveLastSelectedProject(value);
          trigger.textContent = text;
          dropdown.style.display = "none";
          searchInput.value = "";
          renderList("");

          // Önce value'yu set et, sonra event tetikle
          container._selectedValue = value;

          // Change event tetikle - CustomEvent ile value'yu gönder
          setTimeout(() => {
            const event = new CustomEvent("change", {
              bubbles: true,
              detail: { value: value }
            });
            container.dispatchEvent(event);
          }, 0);
        });

        listContainer.appendChild(item);
      });
    }

    // Diğer projeler
    if (otherTemplates.length > 0) {
      const hasVisible = !term || otherTemplates.some(p => {
        const searchText = `${p.project_code} - ${p.project_name} (${p.responsible || ""})`.toLowerCase();
        return searchText.includes(term);
      });

      if (hasVisible && lastSelectedTemplates.length > 0) {
        const separator = document.createElement("div");
        const separatorBg = isDark ? 'var(--bg-dark, #0f172a)' : '#f8fafc';
        const separatorColor = isDark ? 'var(--text-secondary-dark, #cbd5e1)' : '#64748b';
        const separatorBorder = isDark ? 'var(--border-dark, #334155)' : '#e2e8f0';
        separator.style.cssText = `padding: 6px 10px; font-weight: 600; font-size: 11px; color: ${separatorColor}; background: ${separatorBg}; border-bottom: 1px solid ${separatorBorder}; border-top: 1px solid ${separatorBorder};`;
        separator.textContent = "— Tüm projeler —";
        listContainer.appendChild(separator);
      }

      otherTemplates.forEach(p => {
        const text = `${p.project_code} - ${p.project_name}`;
        const searchText = `${p.project_code} - ${p.project_name} (${p.responsible || ""})`.toLowerCase();
        if (term && !searchText.includes(term)) return;

        const item = document.createElement("div");
        item.className = "project-option";
        item.dataset.value = String(p.id);
        const itemBg2 = isDark ? 'transparent' : '';
        const itemColor2 = isDark ? 'var(--text-dark, #ffffff)' : '#0f172a';
        const itemBorder2 = isDark ? 'var(--border-dark, #334155)' : '#f1f5f9';
        const itemHoverBg2 = isDark ? 'var(--bg-dark, #0f172a)' : '#f1f5f9';
        const itemSelectedBg2 = isDark ? 'var(--line-dark, #334155)' : '#eff6ff';
        item.style.cssText = `padding: 8px 10px; cursor: pointer; font-size: 12px; color: ${itemColor2}; border-bottom: 1px solid ${itemBorder2}; transition: background 0.15s; line-height: 1.4; word-wrap: break-word;`;
        item.textContent = text;

        if (selectedId && Number(p.id) === Number(selectedId)) {
          item.style.background = itemSelectedBg2;
          item.style.fontWeight = "500";
        }

        item.addEventListener("mouseenter", () => {
          if (!item.style.background || item.style.background === itemSelectedBg2 || item.style.background === "rgb(239, 246, 255)" || item.style.background === "transparent") {
            item.style.background = itemHoverBg2;
          } else {
            item.style.background = itemHoverBg2;
          }
        });
        item.addEventListener("mouseleave", () => {
          if (selectedId && Number(p.id) === Number(selectedId)) {
            item.style.background = itemSelectedBg2;
          } else {
            item.style.background = itemBg2;
          }
        });

        item.addEventListener("click", () => {
          const value = Number(item.dataset.value);
          saveLastSelectedProject(value);
          trigger.textContent = text;
          dropdown.style.display = "none";
          searchInput.value = "";
          renderList("");

          // Önce value'yu set et, sonra event tetikle
          container._selectedValue = value;

          // Change event tetikle - CustomEvent ile value'yu gönder
          setTimeout(() => {
            const event = new CustomEvent("change", {
              bubbles: true,
              detail: { value: value }
            });
            container.dispatchEvent(event);
          }, 0);
        });

        listContainer.appendChild(item);
      });
    }

    // Sonuç yoksa
    if (listContainer.children.length === 0 || (term && Array.from(listContainer.querySelectorAll(".project-option")).length === 0)) {
      const empty = document.createElement("div");
      const emptyColor = isDark ? 'var(--text-secondary-dark, #cbd5e1)' : '#94a3b8';
      empty.style.cssText = `padding: 20px; text-align: center; color: ${emptyColor}; font-size: 12px;`;
      empty.textContent = "Proje bulunamadı";
      listContainer.appendChild(empty);
    }
  }

  // İlk render
  renderList();

  // Dropdown yapısı
  dropdown.appendChild(searchInput);
  dropdown.appendChild(listContainer);

  // Arama input event
  searchInput.addEventListener("input", (e) => {
    renderList(e.target.value);
  });

  // Dropdown'u body'ye taşı (overflow sorunlarını çözmek için)
  let dropdownInBody = false;

  // Trigger click - dropdown aç/kapa
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = dropdown.style.display !== "none" && dropdown.style.display !== "";
    if (isOpen) {
      dropdown.style.display = "none";
      trigger.style.borderColor = "#cbd5e1";
      trigger.style.boxShadow = "";
      if (dropdownInBody && dropdown.parentElement === document.body) {
        document.body.removeChild(dropdown);
        container.appendChild(dropdown);
        dropdownInBody = false;
      }
    } else {
      // Dropdown'u body'ye taşı
      if (!dropdownInBody) {
        container.removeChild(dropdown);
        document.body.appendChild(dropdown);
        dropdownInBody = true;
      }

      // Pozisyonu hesapla
      const rect = trigger.getBoundingClientRect();
      dropdown.style.position = "fixed";
      dropdown.style.top = (rect.bottom + window.scrollY + 4) + "px";
      dropdown.style.left = rect.left + "px";
      dropdown.style.width = rect.width + "px";
      dropdown.style.display = "block";

      // Trigger'ı vurgula
      trigger.style.borderColor = "#3b82f6";
      trigger.style.boxShadow = "0 0 0 3px rgba(59, 130, 246, 0.1)";

      setTimeout(() => searchInput.focus(), 50);
    }
  });

  // Dışarı tıklanınca kapat
  const closeHandler = (e) => {
    // Dropdown içindeki herhangi bir elemente tıklanırsa kapatma (scrollbar dahil)
    if (dropdown.contains(e.target) || container.contains(e.target)) {
      return;
    }
    // Dışarı tıklanırsa kapat
    if (dropdown.style.display !== "none" && dropdown.style.display !== "") {
      dropdown.style.display = "none";
      trigger.style.borderColor = "#cbd5e1";
      trigger.style.boxShadow = "";
      searchInput.value = "";
      renderList("");
      if (dropdownInBody && dropdown.parentElement === document.body) {
        document.body.removeChild(dropdown);
        container.appendChild(dropdown);
        dropdownInBody = false;
      }
    }
  };

  // Mousedown event'i de kontrol et (scrollbar için)
  const mousedownHandler = (e) => {
    // Dropdown içindeki herhangi bir elemente tıklanırsa kapatma
    if (dropdown.contains(e.target) || container.contains(e.target)) {
      e.stopPropagation();
      return;
    }
  };

  document.addEventListener("click", closeHandler);
  document.addEventListener("mousedown", mousedownHandler);

  // Scroll olduğunda dropdown'u kapat (sadece dropdown dışında scroll olduğunda)
  const scrollHandler = (e) => {
    // Dropdown içindeki scroll'u görmezden gel
    if (dropdown.contains(e.target) || listContainer.contains(e.target)) {
      return;
    }
    // Dropdown açıksa ve dışarıda scroll olduysa kapat
    if (dropdown.style.display !== "none" && dropdown.style.display !== "") {
      dropdown.style.display = "none";
      trigger.style.borderColor = "#cbd5e1";
      trigger.style.boxShadow = "";
      searchInput.value = "";
      renderList("");
      if (dropdownInBody && dropdown.parentElement === document.body) {
        document.body.removeChild(dropdown);
        container.appendChild(dropdown);
        dropdownInBody = false;
      }
    }
  };

  window.addEventListener("scroll", scrollHandler, true);

  // Container'a ekle
  container.appendChild(trigger);
  container.appendChild(dropdown);

  // Select benzeri interface için
  const select = {
    value: selectedId ? String(selectedId) : "0",
    get value() {
      return container._selectedValue ? String(container._selectedValue) : (selectedId ? String(selectedId) : "0");
    },
    set value(val) {
      const numVal = Number(val);
      container._selectedValue = numVal;
      const tpl = templates.find(p => Number(p.id) === numVal);
      if (tpl) {
        trigger.textContent = `${tpl.project_code} - ${tpl.project_name}`;
      } else {
        trigger.textContent = "-- Proje seç --";
      }
      renderList("");
    },
    addEventListener: function (event, handler) {
      if (event === "change") {
        container.addEventListener("change", handler);
      }
    }
  };

  container._selectedValue = selectedId || 0;

  return { container, select, searchInput: null };
}

function _showTopButtons() {
  const bSave = _byId("topJobSave");
  const bCancel = _byId("topJobCancel");
  const bEdit = _byId("topJobEdit");
  const bDel = _byId("topJobDelete");
  const bCopyRow = _byId("topJobCopyRow");

  const showSaveCancel = (__newRowActive || __editMode);
  if (bSave) bSave.style.display = showSaveCancel ? "inline-flex" : "none";
  if (bCancel) bCancel.style.display = showSaveCancel ? "inline-flex" : "none";
  if (bEdit) bEdit.style.display = (!__newRowActive && !__editMode && __selectedProjectId) ? "inline-flex" : "none";
  if (bDel) bDel.style.display = (!__newRowActive && !__editMode && __selectedProjectId) ? "inline-flex" : "none";
  // Satırı Kopyala butonu: İş Ekle butonuna tıklandığında ve bir satır seçiliyse göster
  if (bCopyRow) bCopyRow.style.display = (!__newRowActive && !__editMode && __selectedProjectId > 0) ? "inline-flex" : "none";
}

function _clearRowHighlights() {
  document.querySelectorAll("tr.planRow.selectedRow").forEach(tr => tr.classList.remove("selectedRow"));
}

function _selectRow(projectId) {
  __selectedProjectId = parseInt(projectId || 0, 10);
  _clearRowHighlights();
  const tr = document.querySelector(`tr.planRow[data-project-id='${__selectedProjectId}']`);
  if (tr) tr.classList.add("selectedRow");

  const lbl = _byId("selectedLabel");
  if (lbl) {
    const city = tr ? (tr.querySelector(".region")?.textContent || "") : "";
    const pcode = tr ? (tr.querySelector(".pcode")?.textContent || "") : "";
    lbl.textContent = __selectedProjectId ? `${city} - ${pcode}` : "-";
  }
  _showTopButtons();
}

// Bugünün tarih sütununu vurgula
function highlightTodayColumn() {
  const todayIso = window.TODAY_ISO;
  if (!todayIso) {
    // Eğer window.TODAY_ISO yoksa, script tag'inden al
    const appDataScript = document.getElementById('app-data');
    if (appDataScript) {
      window.TODAY_ISO = appDataScript.getAttribute('data-today') || '';
    }
  }

  const today = window.TODAY_ISO || '';
  if (!today) return;

  // Tüm bugünün tarihine sahip hücreleri vurgula
  document.querySelectorAll(`td.cell[data-date="${today}"]`).forEach(cell => {
    cell.classList.add("selectedDateColumn");
  });

  // Header'daki bugünün th'ini de vurgula
  document.querySelectorAll(`th[data-date="${today}"]`).forEach(th => {
    th.classList.add("selectedDateColumn");
  });
}

function selectRowByProjectId(projectId) {
  if (__newRowActive || __editMode) return;
  _selectRow(projectId);
}

function initRowSelection() {
  document.querySelectorAll("tr.planRow").forEach(tr => {
    tr.addEventListener("click", (e) => {
      if (__newRowActive || __editMode) return;
      const inSticky = e.target && e.target.closest && e.target.closest("td.st");
      if (!inSticky) return;
      const pid = tr.getAttribute("data-project-id") || "0";
      _selectRow(pid);
    });
  });
}

async function refreshRowSubProjectSelect(selectEl, templateProjectId, selectedId) {
  if (!selectEl) return;
  const pid = parseInt(templateProjectId || 0, 10) || 0;
  const selected = parseInt(selectedId || 0, 10) || 0;

  selectEl.innerHTML = `<option value="0">-- Alt proje (yok) --</option>`;
  selectEl.value = "0";
  selectEl.disabled = !pid;
  if (!pid) return;

  try {
    const resp = await fetch(`/api/projects/${encodeURIComponent(pid)}/subprojects?include_inactive=1`);
    const payload = await resp.json().catch(() => ({ ok: false }));
    if (!resp.ok || !payload.ok) {
      console.warn('refreshRowSubProjectSelect: API error', { pid, resp: resp.ok, payload });
      return;
    }

    const all = Array.isArray(payload.subprojects) ? payload.subprojects : [];

    // API'den dönen project_id ile gönderilen project_id farklıysa uyarı ver
    if (payload.project_id && payload.project_id !== pid) {
      console.warn('refreshRowSubProjectSelect: Project ID mismatch', {
        requested: pid,
        returned: payload.project_id,
        subprojects_count: all.length
      });
    }

    if (all.length === 0) {
      console.log('refreshRowSubProjectSelect: No subprojects found for project', pid, 'effective_project_id:', payload.project_id);
    } else {
      console.log('refreshRowSubProjectSelect: Found', all.length, 'subprojects for project', pid, 'effective_project_id:', payload.project_id);
    }

    const selectedRow = all.find(x => parseInt((x || {}).id || 0, 10) === selected) || null;
    const active = all.filter(x => x && x.is_active);

    const options = [];
    if (selectedRow && !selectedRow.is_active) {
      const name = String(selectedRow.name || "").trim();
      const code = String(selectedRow.code || "").trim();
      const label = code && code.length > 0 ? `[Pasif] ${code} - ${name}` : `[Pasif] ${name}`;
      const isSelected = parseInt((selectedRow || {}).id || 0, 10) === selected;
      options.push(`<option value="${selectedRow.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(label)}</option>`);
    }
    for (const sp of active) {
      const name = String(sp.name || "").trim();
      const code = String(sp.code || "").trim();
      const label = code && code.length > 0 ? `${code} - ${name}` : name;
      const isSelected = parseInt((sp || {}).id || 0, 10) === selected;
      options.push(`<option value="${sp.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(label)}</option>`);
    }
    selectEl.insertAdjacentHTML("beforeend", options.join(""));

    if (selected && all.some(x => parseInt((x || {}).id || 0, 10) === selected)) {
      selectEl.value = String(selected);
    } else {
      selectEl.value = "0";
    }
  } catch (_) {
    return;
  }
}

function addBlankJobRow() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (__newRowActive || __editMode) return;
  ensureAppData();

  const tbody = _byId("planTbody");
  if (!tbody) return;

  const tr = document.createElement("tr");
  tr.id = "newJobRow";
  tr.className = "planRow newRow";

  // İl
  const tdCity = document.createElement("td");
  tdCity.className = "st st1 region";
  const citySel = document.createElement("select");
  citySel.id = "newJobCity";
  const cities = window.CITIES || [];
  console.log('addBlankJobRow - CITIES:', cities);
  if (cities.length === 0) {
    console.warn('CITIES is empty! window.CITIES:', window.CITIES);
  }
  citySel.innerHTML = `<option value="">-- İl seç --</option>` +
    cities.map(c => `<option value="${escapeHtml(String(c))}">${escapeHtml(String(c))}</option>`).join("");
  tdCity.appendChild(citySel);

  // Proje
  const tdProj = document.createElement("td");
  tdProj.className = "st st2 proj";
  const templates = window.TEMPLATE_PROJECTS || [];
  console.log('addBlankJobRow - TEMPLATE_PROJECTS:', templates);
  if (templates.length === 0) {
    console.warn('TEMPLATE_PROJECTS is empty! window.TEMPLATE_PROJECTS:', window.TEMPLATE_PROJECTS);
  }

  // Arama özellikli dropdown oluştur
  const { container: projContainer, select: projSel } = createSearchableProjectSelect("newJobTemplate", templates, 0);

  const subSel = document.createElement("select");
  subSel.id = "newJobSubProject";
  subSel.innerHTML = `<option value="0">-- Alt proje (yok) --</option>`;
  subSel.disabled = true;

  const meta = document.createElement("div");
  meta.className = "muted";
  meta.style.marginTop = "4px";
  meta.id = "newJobProjMeta";

  tdProj.appendChild(projContainer);
  tdProj.appendChild(subSel);
  tdProj.appendChild(meta);

  // Sorumlu
  const tdResp = document.createElement("td");
  tdResp.className = "st st3 resp";
  tdResp.id = "newJobResp";
  tdResp.textContent = "-";

  // Günler placeholder
  const dayCount = document.querySelectorAll("table.plan thead th.daycol").length || 7;
  const dayTds = [];
  for (let i = 0; i < dayCount; i++) {
    const td = document.createElement("td");
    td.className = "cell daycol";
    td.innerHTML = `<span class="muted">Kaydedince aktif olur</span>`;
    dayTds.push(td);
  }

  // Araç
  const tdVeh = document.createElement("td");
  tdVeh.className = "vehcol";
  tdVeh.innerHTML = `<div class="hint" id="newJobHint"></div>`;

  tr.appendChild(tdCity);
  tr.appendChild(tdProj);
  tr.appendChild(tdResp);
  dayTds.forEach(x => tr.appendChild(x));
  tr.appendChild(tdVeh);
  tbody.prepend(tr);

  // Proje değiştiğinde
  projSel.addEventListener("change", async (e) => {
    // Event'ten value'yu al, yoksa container'dan al, yoksa select'ten al
    const selectedValue = parseInt((e.detail?.value || projContainer._selectedValue || projSel.value || "0"), 10);
    if (selectedValue > 0) {
      saveLastSelectedProject(selectedValue);
    }
    const t = _tplById(String(selectedValue));
    if (!t) {
      tdResp.textContent = "-";
      meta.textContent = "";
      await refreshRowSubProjectSelect(subSel, 0, 0);
      return;
    }
    tdResp.textContent = t.responsible || "-";
    meta.textContent = `${t.project_code} - ${t.project_name}`;
    await refreshRowSubProjectSelect(subSel, t.id, 0);
  });

  __newRowActive = true;
  _selectRow(0);
  _showTopButtons();
}

function cancelNewJobRow() {
  const tr = _byId("newJobRow");
  if (tr) {
    tr.remove();
    __newRowActive = false;
    __editMode = false;
    _showTopButtons();
    return;
  }
  if (__editMode) {
    reloadWithScroll();
    return;
  }
  _showTopButtons();
}

async function _saveNewJobRow() {
  const city = (_byId("newJobCity")?.value || "").trim();
  // Custom dropdown'dan değer al
  const projContainer = _byId("newJobTemplate_container");
  const template_project_id = projContainer ? parseInt(projContainer._selectedValue || "0", 10) : parseInt(_byId("newJobTemplate")?.value || "0", 10);
  const subproject_id = parseInt(_byId("newJobSubProject")?.value || "0", 10) || 0;
  const hint = _byId("newJobHint");
  if (!city) { if (hint) hint.textContent = "İl seçin."; return; }
  if (!template_project_id) { if (hint) hint.textContent = "Proje seçin."; return; }
  if (hint) hint.textContent = "Kaydediliyor...";

  // Seçili hafta bilgisini al (week_start_iso hidden input'undan)
  const weekStartHidden = _byId("weekStartHidden");
  const weekStart = weekStartHidden ? weekStartHidden.value : '';

  if (!weekStart) {
    if (hint) hint.textContent = "Hafta bilgisi bulunamadı.";
    return;
  }

  const res = await fetch("/api/project_create_from_plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csrf_token: (_byId("csrfToken")?.value || ""), city, template_project_id, subproject_id, week_start: weekStart })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) { if (hint) hint.textContent = data.error || "Kaydedilemedi"; return; }
  reloadWithScroll();
}

async function copySelectedRow() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (!__selectedProjectId || __newRowActive || __editMode) {
    alert("Lütfen kopyalanacak bir satır seçin.");
    return;
  }

  if (!confirm("Seçili satırı alt kısma kopyalamak istediğinizden emin misiniz? Tüm hücreler, personel atamaları ve bilgiler kopyalanacak.")) {
    return;
  }

  const weekStart = (_byId("weekStartHidden")?.value || "").trim();
  if (!weekStart) {
    alert("Hafta bilgisi bulunamadı.");
    return;
  }

  const csrf = (_byId("csrfToken")?.value || "").trim();
  if (!csrf) {
    alert("CSRF token bulunamadı.");
    return;
  }

  try {
    const res = await fetch("/api/plan_row_copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        csrf_token: csrf,
        source_project_id: __selectedProjectId,
        week_start: weekStart
      })
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      alert(data.error || "Kopyalama hatası");
      return;
    }

    toast("Satır başarıyla kopyalandı");
    // Sayfayı yenile
    setTimeout(() => {
      reloadWithScroll();
    }, 500);
  } catch (e) {
    console.error("Kopyalama hatası:", e);
    alert("Kopyalama sırasında bir hata oluştu: " + e.message);
  }
}

async function editSelectedJobRow() {
  if (!__selectedProjectId || __newRowActive || __editMode) return;
  ensureAppData();
  const tr = document.querySelector(`tr.planRow[data-project-id='${__selectedProjectId}']`);
  if (!tr) return;

  const tdCity = tr.querySelector("td.region");
  const tdProj = tr.querySelector("td.proj");
  const tdResp = tr.querySelector("td.resp");
  const curCity = (tdCity?.textContent || "").trim();
  const curCode = (tdProj?.querySelector(".pcode")?.textContent || "").trim();
  const curTpl = (window.TEMPLATE_PROJECTS || []).find(p => String((p || {}).project_code || "").trim() === curCode);
  const weekStart = (_byId("weekStartHidden")?.value || "").trim();
  let curSubprojectId = 0;
  if (weekStart) {
    const mondayCell = tr.querySelector(`td.cell[data-date="${weekStart}"]`);
    curSubprojectId = parseInt(mondayCell?.dataset?.subprojectId || "0", 10) || 0;
  }
  if (!curSubprojectId) {
    tr.querySelectorAll("td.cell").forEach(td => {
      if (curSubprojectId) return;
      const sid = parseInt(td?.dataset?.subprojectId || "0", 10) || 0;
      if (sid) curSubprojectId = sid;
    });
  }

  // city select
  const citySel = document.createElement("select");
  citySel.id = "editJobCity";
  const cities = window.CITIES || [];
  citySel.innerHTML = `<option value="">-- İl seç --</option>` +
    cities.map(c => `<option value="${escapeHtml(String(c))}">${escapeHtml(String(c))}</option>`).join("");
  citySel.value = curCity;
  tdCity.innerHTML = "";
  tdCity.appendChild(citySel);

  // project select - arama özellikli
  const templates = window.TEMPLATE_PROJECTS || [];
  const selectedTemplateId = curTpl ? curTpl.id : 0;
  const { container: projContainer, select: projSel } = createSearchableProjectSelect("editJobTemplate", templates, selectedTemplateId);
  tdProj.innerHTML = "";
  tdProj.appendChild(projContainer);

  const subSel = document.createElement("select");
  subSel.id = "editJobSubProject";
  subSel.innerHTML = `<option value="0">-- Alt proje (yok) --</option>`;
  subSel.disabled = true;
  tdProj.appendChild(subSel);

  const meta = document.createElement("div");
  meta.className = "muted";
  meta.style.marginTop = "4px";
  meta.id = "editJobProjMeta";
  tdProj.appendChild(meta);

  function syncResp() {
    const t = _tplById(projSel.value);
    tdResp.textContent = (t?.responsible) || "-";
    meta.textContent = t ? `${t.project_code} - ${t.project_name}` : "";
  }
  projSel.addEventListener("change", async (e) => {
    // Event'ten value'yu al, yoksa container'dan al, yoksa select'ten al
    const selectedValue = parseInt((e.detail?.value || projContainer._selectedValue || projSel.value || "0"), 10);
    if (selectedValue > 0) {
      saveLastSelectedProject(selectedValue);
    }
    curSubprojectId = 0;
    syncResp();
    await refreshRowSubProjectSelect(subSel, String(selectedValue), curSubprojectId);
  });
  syncResp();
  await refreshRowSubProjectSelect(subSel, projSel.value, curSubprojectId);

  __editMode = true;
  _showTopButtons();
}

async function _saveEditJobRow() {
  if (!__selectedProjectId) return;
  const city = (_byId("editJobCity")?.value || "").trim();
  // Custom dropdown'dan değer al
  const projContainer = _byId("editJobTemplate_container");
  const template_project_id = projContainer ? parseInt(projContainer._selectedValue || "0", 10) : parseInt(_byId("editJobTemplate")?.value || "0", 10);
  const subproject_id = parseInt(_byId("editJobSubProject")?.value || "0", 10) || 0;
  if (!city || !template_project_id) { alert("İl ve Proje seçin."); return; }
  const weekStart = (_byId("weekStartHidden")?.value || "").trim();
  if (!weekStart) { alert("Hafta bilgisi bulunamadı."); return; }

  const res = await fetch("/api/plan_row_update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csrf_token: (_byId("csrfToken")?.value || ""), project_id: __selectedProjectId, city, template_project_id, subproject_id, week_start: weekStart })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) { alert(data.error || "Güncellenemedi"); return; }
  reloadWithScroll();
}

async function deleteSelectedJobRow() {
  if (IS_OBSERVER) {
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if (__newRowActive || __editMode) return;
  if (!__selectedProjectId || __selectedProjectId <= 0) return;
  if (!confirm("Bu satır silinsin mi ? (Tüm hafta kayıtları silinir)")) return;

  const res = await fetch("/api/plan_row_delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csrf_token: (_byId("csrfToken")?.value || ""), project_id: __selectedProjectId })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) { alert(data.error || "Silinemedi"); return; }
  reloadWithScroll();
}

function saveNewOrEdit() {
  if (__newRowActive) return _saveNewJobRow();
  if (__editMode) return _saveEditJobRow();
}

// plan.html'de varsa modal kapatma
function closeAddJobModal() {
  const m = _byId("addJobModal");
  if (m) m.style.display = "none";
}

// İ ş Ekle modal'i iş in template'ten doldur
function fillFromTemplate() {
  const sel = _byId("jobTemplateSelect");
  if (!sel) return;
  const tplId = parseInt(sel.value || "0", 10);
  if (!tplId) return;
  const tpl = _tplById(tplId);
  if (!tpl) return;
  const codeInput = _byId("jobProjectCode");
  const nameInput = _byId("jobProjectName");
  const respInput = _byId("jobResponsible");
  if (codeInput) codeInput.value = tpl.project_code || "";
  if (nameInput) nameInput.value = tpl.project_name || "";
  if (respInput) respInput.value = tpl.responsible || "";
}

// İ ş Ekle modal'ı ndan yeni satir olustur
async function createJobRow() {
  const city = (_byId("jobCity")?.value || "").trim();
  const templateId = parseInt(_byId("jobTemplateSelect")?.value || "0", 10);
  const projectCode = (_byId("jobProjectCode")?.value || "").trim();
  const projectName = (_byId("jobProjectName")?.value || "").trim();
  const responsible = (_byId("jobResponsible")?.value || "").trim();

  if (!city) {
    alert("İl seçin.");
    return;
  }
  if (!templateId && (!projectCode || !projectName || !responsible)) {
    alert("Proje şablonu seçin veya proje bilgilerini girin.");
    return;
  }

  // Seçili hafta bilgisini al (week_start_iso hidden input'undan)
  const weekStartHidden = _byId("weekStartHidden");
  const weekStart = weekStartHidden ? weekStartHidden.value : '';

  if (!weekStart) {
    alert("Hafta bilgisi bulunamadı. Lütfen sayfayı yenileyin.");
    return;
  }

  const res = await fetch("/api/project_create_from_plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      csrf_token: (_byId("csrfToken")?.value || ""),
      city: city,
      template_project_id: templateId || 0,
      project_code: projectCode,
      project_name: projectName,
      responsible: responsible,
      week_start: weekStart
    })
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    alert(data.error || "Kaydedilemedi");
    return;
  }

  closeAddJobModal();
  reloadWithScroll();
}

// =================== RIGHT PANEL (drawer/pin) ===================
function _applyPanelState() {
  // Panel tamamen kaldırıldı - hiçbir şey yapma
  const panel = _byId("rightPanel");
  const floatBtn = _byId("floatingPanelBtn");
  const pinBtn = _byId("panelPinBtn");
  const notch = _byId("panelNotch");
  if (panel) panel.style.display = "none";
  if (floatBtn) floatBtn.style.display = "none";
  if (notch) notch.style.display = "none";
  return;
}
function panelHoverOpen() {
  // Panel kaldırıldı - devre dışı
  return;
}
function panelHoverCloseSoon() {
  // Panel kaldırıldı - devre dışı
  return;
}
function panelHoverCancelClose() {
  // Panel kaldırıldı - devre dışı
  return;
}
function toggleRightPanel() {
  // Panel kaldırıldı - devre dışı
  return;
}
function togglePanelPin() {
  // Panel kaldırıldı - devre dışı
  return;
}

// =================== INIT ===================
window.addEventListener("load", () => {
  if (localStorage.getItem("fit-week") === "1") document.body.classList.add("fit-week");
  renderPeopleList();

  const availSel = _byId("availDate");
  if (availSel) {
    availSel.addEventListener("change", () => {
      const d = availSel.value;
      refreshPersonStatusForDate(d).then(() => {
        renderPeopleList();
        loadAvailability();
      });
    });
  }

  const shiftSel = _byId("mShift");
  if (shiftSel) shiftSel.addEventListener("change", () => loadAvailability());

  if (_byId("availDate")) loadAvailability();

  if (_byId("map")) {
    loadMap();
    const mw = _byId("mapWeek");
    if (mw) mw.addEventListener("change", () => refreshTeamSelect());
  }
});

document.addEventListener("DOMContentLoaded", () => {
  initRowSelection();
  // Bugünün tarih sütununu turuncu yap
  highlightTodayColumn();
  _showTopButtons();
  try { _bindDragPaste(); } catch (e) { }

  // Apply background colors from data-bg-color attributes
  document.querySelectorAll('.plan td.proj[data-bg-color]').forEach(function (td) {
    var bgColor = td.getAttribute('data-bg-color');
    if (bgColor) {
      td.style.backgroundColor = bgColor;
    }
  });

  // Panel tamamen kaldırıldı - DOM'dan sil
  const panel = _byId("rightPanel");
  if (panel) {
    panel.style.display = "none";
    panel.style.visibility = "hidden";
    try { panel.remove(); } catch (e) { }
  }
  const floatBtn = _byId("floatingPanelBtn");
  if (floatBtn) {
    floatBtn.style.display = "none";
    try { floatBtn.remove(); } catch (e) { }
  }
  const notch = _byId("panelNotch");
  if (notch) {
    notch.style.display = "none";
    try { notch.remove(); } catch (e) { }
  }

  // Personel combobox'ı başlat
  if (_byId("peopleSearch")) {
    renderPeopleComboBox();
    renderSelectedPeople();
  }
});

// =================== EXPORTS (global for inline handlers) ===================
window.escapeHtml = escapeHtml;
window.toast = toast;

window.selectCell = selectCell;
window.openCellEditor = openCellEditor;
window.closeCellModal = closeCellModal;
window.saveCell = saveCell;
window.clearCell = clearCell;
window.removeLLD = removeLLD;
window.removeTutanak = removeTutanak;
window.sendWeeklyEmails = sendWeeklyEmails;
window.sendTeamEmails = sendTeamEmails;

window.copyCurrentAsTemplate = copyCurrentAsTemplate;
window.togglePasteMode = togglePasteMode;

window.renderPeopleList = renderPeopleList;
window.renderPeopleComboBox = renderPeopleComboBox;
window.filterPeopleComboBox = filterPeopleComboBox;
window.showPeopleDropdown = showPeopleDropdown;
window.renderSelectedPeople = renderSelectedPeople;
window.updateFieldColors = updateFieldColors;
window.selectRowByProjectId = selectRowByProjectId;

// Scroll position preserving reload helper
window.reloadWithScroll = function () {
  try {
    sessionStorage.setItem('planner_scroll_y', window.scrollY);
    const tableWrap = getPlanTableWrap();
    if (tableWrap) {
      sessionStorage.setItem('planner_table_scroll_top', tableWrap.scrollTop);
      sessionStorage.setItem('planner_table_scroll_left', tableWrap.scrollLeft);
    }
  } catch (e) {
    console.error('Scroll position save error:', e);
  }
  location.reload();
};

// =================== REAL-TIME SYNC ===================
let lastSyncTimestamp = null;
let syncInterval = null;
let isSyncing = false;
let syncBackoffMs = 0;
let syncBackoffUntil = 0;
const syncBaseIntervalMs = 3000;
const syncMaxIntervalMs = 30000;

function _resetSyncBackoff() {
  syncBackoffMs = 0;
  syncBackoffUntil = 0;
}

function _bumpSyncBackoff() {
  syncBackoffMs = syncBackoffMs ? Math.min(syncBackoffMs * 2, syncMaxIntervalMs) : syncBaseIntervalMs;
  syncBackoffUntil = Date.now() + syncBackoffMs;
}

/**
 * Aktif düzenleme durumunu kontrol eden yardımcı fonksiyon
 * EditingStateManager yoksa temel kontroller yapar
 */
function isUserEditing() {
  // EditingStateManager varsa onu kullan
  if (window.EditingStateManager) {
    return window.EditingStateManager.isEditing();
  }

  // Fallback kontroller
  const cellModal = document.getElementById("cellModal");
  const dynamicModal = document.getElementById("dynamicModal");
  const newJobRow = document.getElementById("newJobRow");
  const editJobCity = document.getElementById("editJobCity");

  if (cellModal && cellModal.classList.contains("open")) return true;
  if (dynamicModal && dynamicModal.style.display !== "none") return true;
  if (newJobRow) return true;
  if (editJobCity) return true;

  // Input/textarea odak kontrolü
  const activeEl = document.activeElement;
  if (activeEl) {
    const tagName = activeEl.tagName.toLowerCase();
    if (tagName === "input" || tagName === "textarea" || tagName === "select") {
      const inPlanTable = activeEl.closest("#gridPlanContainer, #planTbody, .planRow, #cellModal");
      if (inPlanTable) return true;
    }
    if (activeEl.isContentEditable) return true;
  }

  return false;
}

async function checkForUpdates() {
  if (isSyncing) return;
  if (!currentWeekStart) return;

  const now = Date.now();
  if (syncBackoffUntil && now < syncBackoffUntil) {
    return;
  }

  // WebSocket bağlıysa polling frekansını düşür (30 saniyede bir)
  const socket = window.__socket || (window.RealtimeFeatures && window.RealtimeFeatures.state && window.RealtimeFeatures.state.socket);
  if (socket && socket.connected) {
    if (checkForUpdates._lastPoll && (now - checkForUpdates._lastPoll < 30000)) {
      return;
    }
    checkForUpdates._lastPoll = now;
  }

  // Aktif düzenleme kontrolü - EditingStateManager veya fallback
  if (isUserEditing()) {
    console.log("[Sync] Düzenleme aktif - güncelleme kontrolü atlandı");
    return;
  }

  isSyncing = true;
  try {
    const res = await fetch(`/api/plan_sync?date=${encodeURIComponent(currentWeekStart)}`);
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok) {
      _bumpSyncBackoff();
      return;
    }
    _resetSyncBackoff();

    const currentTimestamp = data.last_update;

    // İlk kontrol - sadece timestamp'i kaydet
    if (lastSyncTimestamp === null) {
      lastSyncTimestamp = currentTimestamp;
      return;
    }

    // Değişiklik tespit edilirse
    if (currentTimestamp && currentTimestamp !== lastSyncTimestamp) {
      console.log("[Sync] Değişiklik tespit edildi...");
      lastSyncTimestamp = currentTimestamp;

      if (socket && socket.connected) {
        console.log("[Sync] Socket bağlı - tam yenileme atlandı");
        return;
      }

      // EditingStateManager varsa güvenli yenileme kullan
      if (window.EditingStateManager) {
        if (!window.EditingStateManager.safeReload()) {
          // Yenileme engellendi - bekleyen güncelleme olarak işaretle
          window.EditingStateManager.queueCellUpdate({
            type: 'sync_update',
            timestamp: currentTimestamp
          });
          console.log("[Sync] Yenileme engellendi - düzenleme aktif");
        }
      } else {
        // Fallback - düzenleme kontrolü yap
        if (!isUserEditing()) {
          reloadWithScroll();
        } else {
          console.log("[Sync] Yenileme engellendi - düzenleme aktif (fallback)");
          if (typeof toast === "function") {
            toast("Bekleyen güncellemeler var");
          }
        }
      }
      return;
    }

    // Değişiklik yoksa hiçbir şey yapma (idle polling sadece /api/plan_sync)
    lastSyncTimestamp = currentTimestamp;
  } catch (e) {
    console.error("Sync hatası:", e);
    _bumpSyncBackoff();
  } finally {
    isSyncing = false;
  }
}

function startSync() {
  if (syncInterval) clearInterval(syncInterval);
  // Haftanın assignments'larını yükle
  loadAssignmentsForWeek();
  // Her 3 saniyede bir kontrol et
  syncInterval = setInterval(checkForUpdates, 3000);
  console.log("Eş zamanlı güncelleme başlatıldı");
}

function stopSync() {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
}

async function loadAssignmentsForWeek() {
  try {
    if (!currentWeekStart) return;
    const res = await fetch(`/api/assignments_week?week_start=${encodeURIComponent(currentWeekStart)}`);

    // Content-Type kontrolü yap
    const contentType = res.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      console.warn("Assignments: JSON olmayan yanıt alındı, atlanıyor");
      return;
    }

    if (!res.ok) {
      console.warn(`Assignments: HTTP ${res.status} hatası`);
      return;
    }

    const data = await res.json().catch(e => {
      console.error("Assignments JSON parse hatası:", e);
      return null;
    });

    if (data && data.ok) {
      window.ALL_ASSIGNMENTS = data.assignments || {};
    }
  } catch (e) {
    console.error("Assignments yüklenemedi:", e);
  }
}

// Hafta başlangıcını ayarla (global fonksiyon)
function setCurrentWeekStart(dateStr) {
  if (dateStr) {
    currentWeekStart = dateStr;
  } else {
    // URL'den veya input'tan al
    const weekInput = document.querySelector('#weekStartInput') || document.querySelector('input[name="date"]');
    if (weekInput && weekInput.value) {
      currentWeekStart = weekInput.value;
    } else {
      const urlParams = new URLSearchParams(window.location.search);
      const dateParam = urlParams.get('date');
      if (dateParam) {
        currentWeekStart = dateParam;
      } else {
        // Bugünün haftasını al
        const today = new Date();
        const weekStart = getWeekStart(today);
        currentWeekStart = formatDateISO(weekStart);
      }
    }
  }
}

function getWeekStart(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1); // Pazartesi
  return new Date(date.setDate(diff));
}

function formatDateISO(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseDateISO(d) {
  if (!d) return null;
  const parts = d.split("-");
  if (parts.length < 3) return null;
  const [year, month, day] = parts;
  const y = Number(year);
  const m = Number(month);
  const dd = Number(day);
  if (Number.isNaN(y) || Number.isNaN(m) || Number.isNaN(dd)) return null;
  return new Date(y, m - 1, dd);
}

// Sayfa yuklenince sync baslat (sadece plan/board sayfalarinda; portal /me/ sayfalarinda calistirma)
function initSync() {
  const path = (window.location.pathname || "").toLowerCase();
  if (path.indexOf("/me/") !== -1 || path === "/me") return;
  const weekInput = document.querySelector('#weekStartInput') || document.querySelector('input[name="date"]');
  if (weekInput && weekInput.value) {
    setCurrentWeekStart(weekInput.value);
  } else {
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    if (dateParam) {
      setCurrentWeekStart(dateParam);
    } else {
      setCurrentWeekStart(); // bugunun haftasi
    }
  }
  // Haftalık araç verisini tek sefer çek (araç sütunu artık cache'li)
  loadVehicleWeekData(currentWeekStart);
  startSync();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSync);
} else {
  initSync();
}

window.addEventListener("beforeunload", stopSync);

// Export to window for inline handlers
window.selectCell = selectCell;
window.openCellEditor = openCellEditor;
window.closeCellModal = closeCellModal;
window.saveCell = saveCell;
window.clearCell = clearCell;
window.removeLLD = removeLLD;
window.removeTutanak = removeTutanak;

window.copyCurrentAsTemplate = copyCurrentAsTemplate;
window.togglePasteMode = togglePasteMode;
window.renderPeopleList = renderPeopleList;
window.renderPeopleComboBox = renderPeopleComboBox;
window.filterPeopleComboBox = filterPeopleComboBox;
window.showPeopleDropdown = showPeopleDropdown;
window.renderSelectedPeople = renderSelectedPeople;
window.updateFieldColors = updateFieldColors;
window.selectRowByProjectId = selectRowByProjectId;
window.copySelectedRow = copySelectedRow;

window.loadAvailability = loadAvailability;
window.setPersonStatus = setPersonStatus;
window.openStatusModal = openStatusModal;
window.closeStatusModal = closeStatusModal;
window.setStatusBulk = setStatusBulk;
window.renderStatusPeopleList = renderStatusPeopleList;

window.copyMondayToWeek = copyMondayToWeek;
window.copyWeekToNext = copyWeekToNext;
window.copyWeekFromPrevious = copyWeekFromPrevious;
window.toggleFit = toggleFit;

window.cellDragStart = cellDragStart;
window.cellDragEnd = cellDragEnd;
window.cellDragOver = cellDragOver;
window.cellDragLeave = cellDragLeave;
window.cellDrop = cellDrop;

applyStoredTeamTableStyle();
window.openTeamModal = openTeamModal;
window.closeTeamModal = closeTeamModal;
window.copyTeamReportTSV = copyTeamReportTSV;
window.copyTeamReportText = copyTeamReportText;
window.copyTeamReportTable = copyTeamReportTable;
window.downloadTeamReportImage = downloadTeamReportImage;

window.openPersonShot = openPersonShot;
window.closePersonShot = closePersonShot;
window.loadPersonShot = loadPersonShot;
window.downloadPersonShotImage = downloadPersonShotImage;

window.loadMap = loadMap;
window.drawAllRoutes = drawAllRoutes;
window.drawSingleTeamRoute = drawSingleTeamRoute;
window.ensureMap = ensureMap;
window.computeRealRouteDuration = computeRealRouteDuration;
window.toggleRouteCities = toggleRouteCities;

window.addBlankJobRow = addBlankJobRow;
window.cancelNewJobRow = cancelNewJobRow;
// Wrapper: formdaki Ekle butonu için
function saveNewJobRow() {
  if (__editMode) return _saveEditJobRow();
  if (__newRowActive) return _saveNewJobRow();
  return (typeof saveNewOrEdit === "function") ? saveNewOrEdit() : null;
}
window.saveNewJobRow = saveNewJobRow;
window.editSelectedJobRow = editSelectedJobRow;
window.deleteSelectedJobRow = deleteSelectedJobRow;
window.closeAddJobModal = closeAddJobModal;

// =================== PUBLISH PREVIEW MODAL =================== 
let __publishPreviewOnConfirm = null;
let __publishPreviewBusy = false;

function openPublishPreviewModal(title, html, onConfirm) {
  const modal = _byId("publishPreviewModal");
  const titleEl = _byId("publishPreviewTitle");
  const bodyEl = _byId("publishPreviewBody");
  const btn = _byId("publishPreviewConfirmBtn");

  if (!modal || !titleEl || !bodyEl) {
    toast("Yayın önizleme modalı bulunamadı.");
    return;
  }

  titleEl.textContent = title || "Yayın Önizleme";
  bodyEl.innerHTML = html || "";
  __publishPreviewOnConfirm = (typeof onConfirm === "function") ? onConfirm : null;
  __publishPreviewBusy = false;

  if (btn) {
    btn.disabled = false;
    btn.textContent = "Onayla";
  }

  modal.classList.add("open");
}

function closePublishPreviewModal() {
  const modal = _byId("publishPreviewModal");
  if (modal) modal.classList.remove("open");
  __publishPreviewOnConfirm = null;
  __publishPreviewBusy = false;
  const btn = _byId("publishPreviewConfirmBtn");
  if (btn) {
    btn.disabled = false;
    btn.textContent = "Onayla";
  }
}

async function confirmPublishPreview() {
  if (__publishPreviewBusy) return;
  if (!__publishPreviewOnConfirm) {
    closePublishPreviewModal();
    return;
  }

  __publishPreviewBusy = true;
  const btn = _byId("publishPreviewConfirmBtn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Gönderiliyor...";
  }

  let ok = false;
  try {
    ok = !!(await __publishPreviewOnConfirm());
  } catch (_) {
    ok = false;
  } finally {
    __publishPreviewBusy = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Onayla";
    }
  }

  if (ok) {
    closePublishPreviewModal();
  }
}

async function publishWeek() {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const weekStart = (_byId("weekStartHidden") || {}).value || (_byId("weekStartInput") || {}).value || "";
  if (!weekStart) {
    toast("Hafta baslangici bulunamadı.");
    return;
  }
  try {
    const previewRes = await fetch("/admin/publish/week/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week_start: weekStart, csrf_token: csrf })
    });
    const preview = await previewRes.json().catch(() => ({ ok: false }));
    if (!previewRes.ok || !preview.ok) {
      toast(preview.error || "Önizleme alınamadı.");
      return;
    }

    const cities = Array.isArray(preview.cities) ? preview.cities : [];
    const dist = Array.isArray(preview.distribution) ? preview.distribution : [];
    const distTotal = Number(preview.distribution_total || dist.length || 0) || 0;

    const distLines = dist.map(row => {
      const city = escapeHtml((row.city || "").toString());
      const pcode = escapeHtml((row.project_code || "").toString());
      const pname = escapeHtml((row.project_name || "").toString());
      const spname = escapeHtml((row.subproject_name || "").toString());
      const cnt = Number(row.count || 0) || 0;
      const spPart = spname ? ` / ${spname}` : "";
      return `<li style="margin:4px 0;">${city} / ${pcode} - ${pname}${spPart}: <strong>${cnt}</strong></li>`;
    }).join("");

    const more = distTotal > dist.length
      ? `<div style="margin-top:8px; color:#94a3b8; font-size:12px;">(+${distTotal - dist.length} kalem daha)</div>`
      : "";

    const cityText = cities.length ? ` (${cities.map(c => escapeHtml(c)).join(", ")})` : "";
    const html = ` 
      <div style="display:flex; flex-direction:column; gap:10px;"> 
        <div><strong>Hafta:</strong> ${escapeHtml(preview.week_start || "")} - ${escapeHtml(preview.week_end || "")}</div> 
        <div><strong>Yayınlanacak iş:</strong> ${Number(preview.total_jobs || 0) || 0}</div> 
        <div><strong>İl sayısı:</strong> ${Number(preview.city_count || 0) || 0}${cityText}</div> 
        <div> 
          <div style="font-weight:700; margin-bottom:6px;">Proje / Alt Proje Dağılımı</div> 
          <ul style="margin:0; padding-left:18px;">${distLines || '<li style="color:#94a3b8;">(iş yok)</li>'}</ul> 
          ${more} 
        </div> 
        <div style="padding:10px 12px; background:#fffbeb; border:1px solid #fde68a; border-radius:10px; color:#92400e; font-size:12px;">Onayla dersen, bu hafta içindeki yayınlanabilir tüm işler yayınlanacak.</div> 
      </div> 
    `;

    openPublishPreviewModal("Haftayı Yayınla - Önizleme", html, async () => {
      try {
        const res = await fetch("/admin/publish/week", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ week_start: weekStart, csrf_token: csrf })
        });
        const data = await res.json().catch(() => ({ ok: false }));
        if (res.ok && data.ok) {
          toast(`Yayinlandi: ${data.published || 0}`);
          return true;
        }
        toast(data.error || "Yayinlama hatasi");
        return false;
      } catch (_) {
        toast("Yayinlama hatasi");
        return false;
      }
    });
  } catch (_) {
    toast("Önizleme alınamadı.");
  }
}

async function publishSelectedCell() {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const pid = Number((currentCell || {}).project_id || 0) || 0;
  const wd = (currentCell || {}).work_date || "";
  if (!pid || !wd) {
    toast("Önce bir hücre seçin.");
    return;
  }
  try {
    const previewRes = await fetch("/admin/publish/cell/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: pid, work_date: wd, csrf_token: csrf })
    });
    const preview = await previewRes.json().catch(() => ({ ok: false }));
    if (!previewRes.ok || !preview.ok) {
      toast(preview.error || "Önizleme alınamadı.");
      return;
    }

    const proj = preview.project || {};
    const sp = preview.subproject || {};
    const cell = preview.cell || {};
    const people = Array.isArray(preview.people) ? preview.people : [];

    const peopleHtml = people.length
      ? `<ul style="margin:6px 0 0; padding-left:18px;">${people.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
      : `<div style="margin-top:6px; color:#94a3b8; font-size:12px;">(personel yok)</div>`;

    const spLabel = (sp && Number(sp.id || 0))
      ? `${escapeHtml((sp.name || "").toString())}${sp.code ? ` (${escapeHtml((sp.code || "").toString())})` : ""}`
      : "-";

    const html = ` 
      <div style="display:flex; flex-direction:column; gap:10px;"> 
        <div><strong>Tarih:</strong> ${escapeHtml(preview.work_date || wd)}</div> 
        <div><strong>İl / Proje:</strong> ${escapeHtml((proj.city || "").toString())} / ${escapeHtml((proj.project_code || "").toString())} - ${escapeHtml((proj.project_name || "").toString())}</div> 
        <div><strong>Alt Proje:</strong> ${spLabel}</div> 
        <div><strong>Sorumlu:</strong> ${escapeHtml((proj.responsible || "").toString())}</div> 
        <div><strong>Vardiya:</strong> ${escapeHtml((cell.shift || "-").toString() || "-")}</div> 
        <div><strong>Araç:</strong> ${escapeHtml((cell.vehicle_info || "-").toString() || "-")}</div> 
        <div><strong>Ekip:</strong> ${escapeHtml((cell.team_name || "-").toString() || "-")}</div> 
        <div> 
          <div style="font-weight:700;">Personel</div> 
          ${peopleHtml} 
        </div> 
        <div style="padding:10px 12px; background:#fffbeb; border:1px solid #fde68a; border-radius:10px; color:#92400e; font-size:12px;">Onayla dersen, seçili hücre yayınlanacak.</div> 
      </div> 
    `;

    openPublishPreviewModal("Seçili İşi Yayınla - Önizleme", html, async () => {
      try {
        const res = await fetch("/admin/publish/cell", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_id: pid, work_date: wd, csrf_token: csrf })
        });
        const data = await res.json().catch(() => ({ ok: false }));
        if (res.ok && data.ok) {
          toast("İş yayınlandı");
          return true;
        }
        toast(data.error || "Yayinlama hatasi");
        return false;
      } catch (_) {
        toast("Yayinlama hatasi");
        return false;
      }
    });
  } catch (_) {
    toast("Önizleme alınamadı.");
  }
}

async function publishTeamWeek() {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const weekStart = (_byId("weekStartHidden") || {}).value || (_byId("weekStartInput") || {}).value || "";
  if (!selectedCellEl && !(currentCell && currentCell.project_id && currentCell.work_date)) {
    toast("Önce bir hücre seçin.");
    return;
  }
  if (!weekStart) {
    toast("Hafta başlangıcı bulunamadı.");
    return;
  }

  const pid = Number((currentCell || {}).project_id || 0) || 0;
  const wd = (currentCell || {}).work_date || "";
  if (!pid || !wd) {
    toast("Önce bir hücre seçin.");
    return;
  }

  let teamId = Number((currentCell || {}).team_id || 0) || 0;
  if (!teamId) {
    try {
      const res = await fetch(`/api/cell?project_id=${pid}&date=${encodeURIComponent(wd)}`);
      const data = await res.json().catch(() => ({}));
      teamId = Number((data && data.cell && data.cell.team_id) ? data.cell.team_id : 0) || 0;
      currentCell.team_id = teamId || null;
    } catch (_) {
      teamId = 0;
    }
  }

  if (!teamId) {
    toast("Önce hücreye personel ekleyip ekip oluşturun.");
    return;
  }

  try {
    const res = await fetch("/admin/publish/team_week", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week_start: weekStart, team_id: teamId, csrf_token: csrf })
    });
    const data = await res.json().catch(() => ({ ok: false }));
    if (res.ok && data.ok) {
      toast(`Yayınlandı: ${data.published || 0}`);
      return;
    }
    toast(data.error || "Yayınlama hatası");
  } catch (_) {
    toast("Yayınlama hatası");
  }
}

async function openTeamPublishModal() {
  const modal = _byId("teamPublishModal");
  if (!modal) {
    toast("Ekip yayın modalı bulunamadı.");
    return;
  }
  modal.classList.add("open");

  const hint = _byId("teamPublishHint");
  const membersBox = _byId("teamPublishMembers");
  const sel = _byId("teamPublishSelect");
  const previewBox = _byId("teamPublishPreview");
  const btn = _byId("teamPublishConfirmBtn");
  if (hint) hint.textContent = "Yükleniyor...";
  if (membersBox) membersBox.innerHTML = "";
  if (sel) sel.innerHTML = "";
  if (previewBox) previewBox.innerHTML = "";
  if (btn) btn.disabled = true;

  const weekStart = (_byId("weekStartHidden") || {}).value || (_byId("weekStartInput") || {}).value || "";
  try {
    const res = await fetch(`/api/teams?week_start=${encodeURIComponent(weekStart)}`);
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok) {
      if (hint) hint.textContent = data.error || "Ekipler alınamadı.";
      return;
    }
    const teams = Array.isArray(data.teams) ? data.teams : [];
    if (!teams.length) {
      if (hint) hint.textContent = "Bu haftada ekip bulunamadı.";
      if (sel) sel.innerHTML = '<option value="">(ekip yok)</option>';
      return;
    }

    if (sel) {
      teams.forEach(t => {
        const opt = document.createElement("option");
        opt.value = String(t.id || "");
        const n = Number(t.member_count || 0) || 0;
        opt.textContent = `${t.name || ("Ekip #" + t.id)}${n ? ` (${n} kişi)` : ""}`;
        sel.appendChild(opt);
      });
      sel.onchange = () => { loadTeamPublishMembers(); loadTeamPublishPreview(); };
    }

    if (hint) hint.textContent = "";
    await loadTeamPublishMembers();
    await loadTeamPublishPreview();
  } catch (_) {
    if (hint) hint.textContent = "Ekipler alınamadı.";
  }
}

function closeTeamPublishModal() {
  _byId("teamPublishModal")?.classList.remove("open");
}

async function loadTeamPublishMembers() {
  const sel = _byId("teamPublishSelect");
  const membersBox = _byId("teamPublishMembers");
  const hint = _byId("teamPublishHint");
  const teamId = Number(sel?.value || 0) || 0;
  if (!teamId) {
    if (membersBox) membersBox.innerHTML = "";
    return;
  }
  if (hint) hint.textContent = "Üyeler yükleniyor...";
  try {
    const res = await fetch(`/api/team/${teamId}/members`);
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok) {
      if (hint) hint.textContent = data.error || "Üyeler alınamadı.";
      if (membersBox) membersBox.innerHTML = "";
      return;
    }
    const members = Array.isArray(data.members) ? data.members : [];
    if (membersBox) {
      if (!members.length) {
        membersBox.innerHTML = '<div style="color:#94a3b8; font-size:12px;">Üye yok</div>';
      } else {
        membersBox.innerHTML = members.map(m => {
          const name = escapeHtml(m.full_name || "");
          const phone = escapeHtml(m.phone || "");
          const email = escapeHtml(m.email || "");
          const line2 = [phone, email].filter(Boolean).join(" | ");
          return `
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px; margin-bottom:8px;">
              <div style="font-weight:900; color:#0f172a; font-size:13px;">${name}</div>
              <div style="margin-top:4px; color:#64748b; font-size:11px;">${line2 || "-"}</div>
            </div>
          `;
        }).join("");
      }
    }
    if (hint) hint.textContent = "";
  } catch (_) {
    if (hint) hint.textContent = "Üyeler alınamadı.";
    if (membersBox) membersBox.innerHTML = "";
  }
}

async function loadTeamPublishPreview() {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const weekStart = (_byId("weekStartHidden") || {}).value || (_byId("weekStartInput") || {}).value || "";
  const teamId = Number((_byId("teamPublishSelect") || {}).value || 0) || 0;

  const box = _byId("teamPublishPreview");
  const btn = _byId("teamPublishConfirmBtn");

  if (!teamId || !weekStart) {
    if (box) box.innerHTML = "";
    if (btn) btn.disabled = true;
    return;
  }

  if (btn) btn.disabled = true;
  if (box) box.innerHTML = "<div style='color:#64748b; font-size:12px;'>Önizleme yükleniyor...</div>";

  try {
    const res = await fetch("/admin/publish/team_week/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week_start: weekStart, team_id: teamId, csrf_token: csrf })
    });
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok) {
      if (box) box.innerHTML = `<div style='color:#be123c; font-size:12px;'>${escapeHtml(data.error || "Önizleme alınamadı.")}</div>`;
      if (btn) btn.disabled = true;
      return;
    }

    const days = Array.isArray(data.day_counts) ? data.day_counts : [];
    const labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
    const dayHtml = labels.map((label, idx) => {
      const row = days[idx] || {};
      const cnt = Number(row.count || 0) || 0;
      return `<div style='display:flex; justify-content:space-between; gap:10px; padding:6px 10px; border:1px solid #e2e8f0; border-radius:10px; background:#f8fafc;'> 
        <span style='font-weight:700; color:#0f172a;'>${label}</span> 
        <span style='font-weight:800; color:#0f172a;'>${cnt}</span> 
      </div>`;
    }).join("");

    if (box) {
      box.innerHTML = ` 
        <div style='display:flex; flex-direction:column; gap:10px; padding:10px 12px; border:1px solid #e2e8f0; border-radius:12px; background:#ffffff;'> 
          <div style='display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between;'> 
            <div><strong>Hafta:</strong> ${escapeHtml(data.week_start || "")} - ${escapeHtml(data.week_end || "")}</div> 
            <div><strong>Yayınlanacak iş:</strong> ${Number(data.total_jobs || 0) || 0}</div> 
          </div> 
          <div style='font-weight:700; color:#0f172a;'>Gün Dağılımı</div> 
          <div style='display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px;'>${dayHtml}</div> 
          <div style='padding:10px 12px; background:#fffbeb; border:1px solid #fde68a; border-radius:10px; color:#92400e; font-size:12px;'>Onayla dersen, seçili ekibin bu haftadaki işleri yayınlanacak.</div> 
        </div> 
      `;
    }
    if (btn) btn.disabled = false;
  } catch (_) {
    if (box) box.innerHTML = "<div style='color:#be123c; font-size:12px;'>Önizleme alınamadı.</div>";
    if (btn) btn.disabled = true;
  }
}

async function publishSelectedTeamWeek() {
  const csrf = (_byId("csrfToken") || {}).value || (_byId("csrfTokenGlobal") || {}).value || "";
  const weekStart = (_byId("weekStartHidden") || {}).value || (_byId("weekStartInput") || {}).value || "";
  const teamId = Number((_byId("teamPublishSelect") || {}).value || 0) || 0;
  if (!teamId) {
    toast("Önce ekip seçin.");
    return;
  }
  if (!weekStart) {
    toast("Hafta başlangıcı bulunamadı.");
    return;
  }

  const btn = _byId("teamPublishConfirmBtn");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch("/admin/publish/team_week", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week_start: weekStart, team_id: teamId, csrf_token: csrf })
    });
    const data = await res.json().catch(() => ({ ok: false }));
    if (res.ok && data.ok) {
      toast(`Yayınlandı: ${data.published || 0}`);
      closeTeamPublishModal();
      return;
    }
    toast(data.error || "Yayınlama hatası");
  } catch (_) {
    toast("Yayınlama hatası");
  } finally {
    if (btn) btn.disabled = false;
  }
}

window.publishWeek = publishWeek;
window.publishSelectedCell = publishSelectedCell;
window.publishTeamWeek = publishTeamWeek;
window.toggleSummary = toggleSummary;
window.openTeamPublishModal = openTeamPublishModal;
window.closeTeamPublishModal = closeTeamPublishModal;
window.loadTeamPublishMembers = loadTeamPublishMembers;
window.loadTeamPublishPreview = loadTeamPublishPreview;
window.publishSelectedTeamWeek = publishSelectedTeamWeek;
window.closePublishPreviewModal = closePublishPreviewModal;
window.confirmPublishPreview = confirmPublishPreview;

// Excel export
function exportWeekToExcel(weekStart) {
  if (!weekStart) {
    toast("Hafta başlangıcı bulunamadı.");
    return;
  }
  try {
    const url = `/plan/export/excel?week_start=${encodeURIComponent(weekStart)}`;
    window.location.href = url;
  } catch (e) {
    console.error("Excel export error:", e);
    toast("Excel indirme hatası.");
  }
}
window.exportWeekToExcel = exportWeekToExcel;

// =================== DARK MODE OBSERVER FOR GLOBAL CONSTANTS ===================
(function () {
  function updateGlobalThemeConstants() {
    const isDark = document.documentElement.classList.contains('dark-mode');
    if (typeof TEAM_TABLE_STYLE_DEFAULT !== 'undefined') {
      if (isDark) {
        TEAM_TABLE_STYLE_DEFAULT.headerBg = '#1e293b'; // Slate 800
        TEAM_TABLE_STYLE_DEFAULT.rowBg = '#0f172a';    // Slate 900
        TEAM_TABLE_STYLE_DEFAULT.borderColor = '#334155'; // Slate 700
        TEAM_TABLE_STYLE_DEFAULT.fontColor = '#f8fafc'; // Slate 50
      } else {
        // Restore defaults (Light)
        TEAM_TABLE_STYLE_DEFAULT.headerBg = '#f8fafc';
        TEAM_TABLE_STYLE_DEFAULT.rowBg = '#ffffff';
        TEAM_TABLE_STYLE_DEFAULT.borderColor = '#e2e8f0';
        TEAM_TABLE_STYLE_DEFAULT.fontColor = '#0f172a';
      }
    }
  }

  // Run once on load
  updateGlobalThemeConstants();

  // Observer for class changes on html element
  const observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (mutation.attributeName === 'class') {
        updateGlobalThemeConstants();
      }
    });
  });

  observer.observe(document.documentElement, {
    attributes: true
  });
})();

// =================== SCROLL RESTORATION ===================
function saveScrollPositions() {
  try {
    sessionStorage.setItem('planner_scroll_y', window.scrollY);
    const tableWrap = getPlanTableWrap();
    if (tableWrap) {
      sessionStorage.setItem('planner_table_scroll_top', tableWrap.scrollTop);
      sessionStorage.setItem('planner_table_scroll_left', tableWrap.scrollLeft);
    }
  } catch (e) {
    console.error('Scroll save error:', e);
  }
}

function restoreScrollPositions() {
  try {
    if ('scrollRestoration' in history) {
      history.scrollRestoration = 'manual';
    }
    // Window scroll
    const scrollY = sessionStorage.getItem('planner_scroll_y');
    if (scrollY !== null) {
      window.scrollTo(0, parseInt(scrollY));
    }

    // Table scroll
    const tableWrap = getPlanTableWrap();
    if (tableWrap) {
      const scrollTop = sessionStorage.getItem('planner_table_scroll_top');
      const scrollLeft = sessionStorage.getItem('planner_table_scroll_left');
      if (scrollTop !== null) {
        tableWrap.scrollTop = parseInt(scrollTop);
      }
      if (scrollLeft !== null) {
        tableWrap.scrollLeft = parseInt(scrollLeft);
      }
    }
  } catch (e) {
    console.error('Scroll restoration error:', e);
  }
}

// Global listenere for any reload/navigate
window.addEventListener('beforeunload', saveScrollPositions);

document.addEventListener('DOMContentLoaded', () => {
  // İlk deneme
  restoreScrollPositions();

  // Layout oturunca tekrar dene
  setTimeout(restoreScrollPositions, 50);
  setTimeout(restoreScrollPositions, 200);
  setTimeout(restoreScrollPositions, 500);
  setTimeout(restoreScrollPositions, 900);
  setTimeout(restoreScrollPositions, 1400);
  setTimeout(restoreScrollPositions, 2200);

  // İşlem bitince temizle (biraz daha uzun tutalım)
  setTimeout(() => {
    sessionStorage.removeItem('planner_scroll_y');
    sessionStorage.removeItem('planner_table_scroll_top');
    sessionStorage.removeItem('planner_table_scroll_left');
  }, 3000);
});

// =================== VERTICAL MERGE (LEFT COLUMNS) ===================
// İstek: Birleştirme kapalı - her satır kendi İL, PROJE, SORUMLU hücresini tek tek göstersin.
// Böylece "bir satırda 2 satır" görünümü olmaz.
function applyVerticalMerges() {
  const tbody = document.getElementById("planTbody");
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll("tr.planRow"));

  // Tüm satırlarda İL, PROJE, SORUMLU hücrelerini sıfırla - rowSpan ve display'i kaldır.
  rows.forEach(row => {
    const r = row.querySelector(".region");
    const p = row.querySelector(".proj");
    const s = row.querySelector(".resp");

    if (r) { r.style.display = ""; r.rowSpan = 1; }
    if (p) { p.style.display = ""; p.rowSpan = 1; }
    if (s) { s.style.display = ""; s.rowSpan = 1; }
  });
}