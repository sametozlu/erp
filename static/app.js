// app.js (fixed)
// Bu dosya plan.html ile uyumlu olacak şekilde eksik fonksiyonları tamamlar.
// Not: Backend endpoint'leri mevcut projenizdeki ile aynı varsayılmıştır.

"use strict";

// Gözlemci kontrolü - sayfa yüklendiğinde kontrol et
let IS_OBSERVER = false;
document.addEventListener("DOMContentLoaded", ()=>{
  // Session'dan role bilgisini al (template'den gelen data attribute veya hidden input)
  const roleInput = document.getElementById("userRole");
  if(roleInput){
    IS_OBSERVER = roleInput.value === 'gözlemci';
  }
  // Eğer role input yoksa, butonları kontrol et
  if(IS_OBSERVER){
    // Tüm değişiklik yapan butonları devre dışı bırak
    document.querySelectorAll('[onclick*="saveCell"], [onclick*="clearCell"], [onclick*="addBlankJobRow"], [onclick*="deleteSelectedJobRow"], [onclick*="copyWeekFromPrevious"], [onclick*="copyMondayToWeek"], [onclick*="copyCurrentAsTemplate"], [onclick*="togglePasteMode"], [onclick*="openStatusModal"]').forEach(btn => {
      btn.style.display = 'none';
    });
  }
});

// =================== STATE ===================
let currentWeekStart = null;
let currentCell = { project_id: null, work_date: null, week_start: null, city: "", project_code: "" };
let dragData = null;
let selectedPeople = new Set();
let RECENT_PEOPLE = JSON.parse(localStorage.getItem("recent_people") || "[]");
let FAV_PEOPLE = new Set(JSON.parse(localStorage.getItem("fav_people") || "[]"));
let selectedCellEl = null;
let existingLLDs = [];
let existingTutanaks = [];
let removeLLDs = new Set();
let removeTutanaks = new Set();

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

// Map state
let _map, _layer;
let LAST_DRAWN_ROUTE = null;
let LAST_ROUTE_STATS = [];
let SHOW_ROUTE_CITIES = false;
const OSRM_CACHE = {};

// Team members cache (tooltip iAin)
const TEAM_MEMBERS_CACHE = {};

// =================== GEO HELPERS ===================
function haversineKm(a, b){
  if(!a || !b) return 0;
  const toRad = (x)=>x * Math.PI / 180;
  const R = 6371; // km
  const dLat = toRad((b[0]??0) - (a[0]??0));
  const dLon = toRad((b[1]??0) - (a[1]??0));
  const lat1 = toRad(a[0]??0);
  const lat2 = toRad(b[0]??0);
  const h = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function routeDistanceKm(points){
  if(!points || points.length < 2) return 0;
  let km = 0;
  for(let i=1;i<points.length;i++){
    km += haversineKm(points[i-1], points[i]);
  }
  return km;
}

function formatDurationHours(hours){
  if(!hours || hours <= 0) return "0 sa";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if(h === 0) return `${m} dk`;
  if(m === 0) return `${h} sa`;
  return `${h} sa ${m} dk`;
}

async function osrmDistanceDuration(a, b){
  const key = `${a.lat},${a.lon}|${b.lat},${b.lon}`;
  if(OSRM_CACHE[key]) return OSRM_CACHE[key];
  let km = haversineKm([a.lat, a.lon],[b.lat, b.lon]);
  let hours = km / 60;
  try{
    const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=false&alternatives=false`;
    const res = await fetch(url);
    const js = await res.json();
    if(js && js.routes && js.routes[0]){
      km = (js.routes[0].distance || 0) / 1000;
      hours = (js.routes[0].duration || 0) / 3600;
    }
  }catch(e){ /* fallback haversine */ }
  OSRM_CACHE[key] = { km, hours };
  return OSRM_CACHE[key];
}

async function computeRouteStats(points){
  const pts = (points||[]).filter(p=>p && p.lat!=null && p.lon!=null);
  const segments = [];
  let totalKm = 0;
  let totalHours = 0;
  for(let i=1;i<pts.length;i++){
    const a = pts[i-1];
    const b = pts[i];
    const res = await osrmDistanceDuration(a,b);
    totalKm += res.km;
    totalHours += res.hours;
    segments.push({
      from: `${a.city || ''} ${a.project_code ? '('+a.project_code+')' : ''}`.trim() || 'Nokta',
      to: `${b.city || ''} ${b.project_code ? '('+b.project_code+')' : ''}`.trim() || 'Nokta',
      km: res.km,
      hours: res.hours
    });
    await new Promise(r=>setTimeout(r,80));
  }
  const cities = pts.map(p=>p.city).filter(Boolean);
  return { segments, totalKm, totalHours, cities };
}

// =================== HELPERS ===================
function _byId(id){ return document.getElementById(id); }
function normalize(s){ return (s||"").toString().toLowerCase().trim(); }

// HTML escape (escapeHtml is not defined hatasını düzeltir)
function escapeHtml(s){
  return (s ?? "").toString().replace(/[&<>"']/g, (ch) => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));
}

function ensureAppData(){
  const hasCities = Array.isArray(window.CITIES) && window.CITIES.length > 0;
  const hasProjects = Array.isArray(window.TEMPLATE_PROJECTS) && window.TEMPLATE_PROJECTS.length > 0;
  if(hasCities || hasProjects) return;
  try{
    const projectsEl = document.getElementById("app-data-projects");
    const citiesEl = document.getElementById("app-data-cities");
    if(projectsEl){
      const txt = (projectsEl.textContent || "").trim();
      window.TEMPLATE_PROJECTS = txt ? JSON.parse(txt) : [];
    }
    if(citiesEl){
      const txt = (citiesEl.textContent || "").trim();
      window.CITIES = txt ? JSON.parse(txt) : [];
    }
  }catch(e){
    console.error("ensureAppData failed:", e);
    window.TEMPLATE_PROJECTS = window.TEMPLATE_PROJECTS || [];
    window.CITIES = window.CITIES || [];
  }
}

// Favori / Son seçilenler localStorage kaydı
function saveFavRecent(){
  try{
    localStorage.setItem("fav_people", JSON.stringify(Array.from(FAV_PEOPLE||[])));
    localStorage.setItem("recent_people", JSON.stringify(RECENT_PEOPLE||[]));
  }catch(e){ /* ignore */ }
}

// ---- Toast (sayfayı aşağı çekmesin diye fixed layer kullanır) ----
function ensureToastLayer(){
  let layer = document.getElementById("toastLayer");
  if(layer) return layer;
  layer = document.createElement("div");
  layer.id = "toastLayer";
  document.body.appendChild(layer);
  return layer;
}
function toast(msg){
  const layer = ensureToastLayer();
  const s = document.createElement("div");
  s.className = "toastMsg";
  s.textContent = msg;
  layer.appendChild(s);
  setTimeout(()=>{ try{s.remove();}catch(e){} }, 1400);
}

// Hücre seçilince satır (proje) düzenleme seçimlerini kapat
function _clearRowSelectionForCell(td){
  try{
    document.querySelectorAll("tr.planRow.selectedRow").forEach(tr => tr.classList.remove("selectedRow"));
  }catch(e){}
  if(typeof __selectedProjectId !== "undefined") __selectedProjectId = 0;
  const bEdit = _byId("topJobEdit");
  const bDel = _byId("topJobDelete");
  if(bEdit) bEdit.style.display = "none";
  if(bDel) bDel.style.display = "none";

  // Label'ı hücreye göre gösterelim
  const lbl = _byId("selectedLabel");
  if(lbl && td){
    const city = td.dataset.city || "";
    const code = td.dataset.projectCode || "";
    lbl.textContent = (city && code)  ? `${city} - ${code}` : "-";
  }
}

// People map
function peopleMap(){
  const m = {};
  (window.ALL_PEOPLE || []).forEach(p => { m[p.id] = p; });
  return m;
}

function refreshAttachmentLabels(){
  const lldNameEl = _byId("mLLDFileName");
  const tutNameEl = _byId("mTutanakFileName");

  if(lldNameEl){
    const activeLLD = existingLLDs.filter(f=>!removeLLDs.has(f));
    if(activeLLD.length){
      lldNameEl.innerHTML = activeLLD.map(f=>{
        const safe = encodeURIComponent(f);
        return `<div class="attach-row">
          <a class="attach-name" href="/files/${safe}" target="_blank" rel="noreferrer noopener">${escapeHtml(f)}</a>
          <button type="button" class="attach-btn" onclick="removeLLD('${safe}'); return false;">Sil</button>
        </div>`;
      }).join("");
    }else{
      lldNameEl.innerHTML = `<div class="attach-empty">Yuklu dosya yok</div>`;
    }
  }
  if(tutNameEl){
    const activeTut = existingTutanaks.filter(f=>!removeTutanaks.has(f));
    if(activeTut.length){
      tutNameEl.innerHTML = activeTut.map(f=>{
        const safe = encodeURIComponent(f);
        return `<div class="attach-row">
          <a class="attach-name" href="/files/${safe}" target="_blank" rel="noreferrer noopener">${escapeHtml(f)}</a>
          <button type="button" class="attach-btn" onclick="removeTutanak('${safe}'); return false;">Sil</button>
        </div>`;
      }).join("");
    }else{
      tutNameEl.innerHTML = `<div class="attach-empty">Yuklu dosya yok</div>`;
    }
  }
  
  // Ataç simgesini güncelle (dosya seçildiğinde veya yüklendiğinde)
  updateAttachmentBadge();
}

function updateAttachmentBadge(){
  const td = selectedCellEl;
  if(!td) return;
  
  // Mevcut yüklenmiş dosyalar
  const hasExistingFiles = (existingLLDs && existingLLDs.length>0) || (existingTutanaks && existingTutanaks.length>0);
  
  // Seçili dosyalar (henüz yüklenmemiş)
  const lldFiles = _byId("mLLDFile")?.files;
  const tutanakFiles = _byId("mTutanakFile")?.files;
  const hasSelectedFiles = (lldFiles && lldFiles.length>0) || (tutanakFiles && tutanakFiles.length>0);
  
  // Herhangi bir dosya varsa (yüklenmiş veya seçilmiş) ataç simgesini göster
  const hasAttachment = hasExistingFiles || hasSelectedFiles;
  setAttachmentBadge(td, hasAttachment);
}

function removeLLD(fname){
  if(!fname) return;
  fname = decodeURIComponent(fname);
  removeLLDs.add(fname);
  refreshAttachmentLabels();
}

function removeTutanak(fname){
  if(!fname) return;
  fname = decodeURIComponent(fname);
  removeTutanaks.add(fname);
  refreshAttachmentLabels();
}

// =================== CELL DOM UPDATE ===================
function setAttachmentBadge(td, hasAttachment){
  if(!td) return;
  td.setAttribute("data-has-attach", hasAttachment ? "1" : "0");
}

function updateCellDom(td, payload){
  if(!td) return;
  const shift = payload.shift || "";
  const note = payload.note || "";
  const person_ids = payload.person_ids || [];
  const hasAttachment = payload.hasAttachment;
  const pm = peopleMap();

  const t = td.querySelector(".cell-time");
  const pbox = td.querySelector(".cell-people");
  
  // Eğer hiçbir şey yoksa "-" göster (açık gri)
  if(!shift && !note && person_ids.length === 0){
    if(t) {
      t.innerHTML = '<span style="text-align: center; color: #d1d5db; font-size: 14px;">-</span>';
      t.style.textAlign = "center";
    }
    if(pbox) {
      pbox.style.display = "none";
      pbox.innerHTML = "";
    }
  } else if(shift && person_ids.length === 0) {
    // Çalışma var ama personel yoksa (normal renk)
    if(t) {
      t.textContent = shift;
      t.style.textAlign = "";
      t.style.color = "";
      t.style.fontWeight = "600";
    }
    
    if(pbox){
      pbox.style.display = "";
      pbox.style.color = "";
      pbox.innerHTML = '<span class="muted">Personel seç</span>';
    }
  } else {
    // Normal durum (her ikisi de var veya sadece personel var)
    if(t) {
      if(shift) {
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
    
    if(pbox){
      pbox.style.display = "";
      pbox.style.color = "";
      if(person_ids.length){
        const peopleNames = person_ids.map(id => {
          const p = pm[id];
          return (p  ? escapeHtml(p.full_name) : ("#"+id));
        });
        if(peopleNames.length > 2){
          pbox.innerHTML = peopleNames.slice(0, 2).join("<br>") + "<br><span style='color: #94a3b8;'>...</span>";
        }else{
          pbox.innerHTML = peopleNames.join("<br>");
        }
      }else{
        pbox.innerHTML = '<span class="muted">Personel seç</span>';
      }
    }
  }
  
  // Personel seçilmişse koyu yeşil arka plan ekle
  if(person_ids.length > 0){
    td.classList.add("filled-personnel");
  } else {
    td.classList.remove("filled-personnel");
  }

  const nbox = td.querySelector(".cell-note");
  if(nbox){
    nbox.innerHTML = note  ? `<strong>Detay:</strong> ${escapeHtml(note)}` : "";
  }

  const filled = !!(shift || note || person_ids.length);
  td.classList.toggle("filled", filled);

  if(hasAttachment !== undefined){
    setAttachmentBadge(td, !!hasAttachment);
  }
}

// =================== CELL SELECT / EDIT ===================
function selectCell(td, weekStartIso){
  if(!td) return;

  _clearRowSelectionForCell(td);

  const project_id = parseInt(td.dataset.projectId || "0", 10);
  const work_date = td.dataset.date || "";
  currentWeekStart = weekStartIso || currentWeekStart;
  currentCell = {
    project_id,
    work_date,
    week_start: currentWeekStart,
    city: td.dataset.city || "",
    project_code: td.dataset.projectCode || ""
  };

  if(selectedCellEl) selectedCellEl.classList.remove("selectedCell");
  selectedCellEl = td;
  selectedCellEl.classList.add("selectedCell");

  const info = _byId("editorInfo");
  if(info) info.textContent = `${work_date} • ${td.dataset.projectCode || ""}`;

  if(pasteMode){
    if(!clipboardPayload){
      toast("Önce bir hücreyi kopyala (Hücreyi Kopyala).");
      return;
    }
    pasteToCell(td);
    return;
  }

  toast(`${work_date} hücresi seçildi`);
}

async function openCellEditor(td, weekStartIso){
  if(!td) return;
  selectCell(td, weekStartIso);

  const project_id = parseInt(td.dataset.projectId || "0", 10);
  const work_date = td.dataset.date || "";

  const res = await fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`);
  const data = await res.json().catch(()=>({exists:false}));

  // Shift değerini eski formattan yeni formata çevir
  const oldShift = (data.cell?.shift || "").trim();
  let newShift = oldShift;
  const shiftMap = {
    "Gündüz": "08:30-18:00",
    "Gündüz Yol": "08:30-18:00 YOL",
    "Gece": "00:00-06:00"
  };
  if (shiftMap[oldShift]) {
    newShift = shiftMap[oldShift];
  }
  _byId("mShift").value = newShift;

  const vehicleEl = _byId("mVehicle");
  if(vehicleEl) {
    const vehicleInfo = (data.cell?.vehicle_info || "").trim();
    // Araç bilgisinden sadece plakayı çıkar (ilk kelime)
    const plateOnly = vehicleInfo.split(" ")[0] || vehicleInfo;
    // Try to find matching option by value
    let found = false;
    for(let i = 0; i < vehicleEl.options.length; i++) {
      if(vehicleEl.options[i].value === plateOnly) {
        vehicleEl.value = plateOnly;
        found = true;
        break;
      }
    }
    // If not found in options, set value anyway (for backward compatibility with free text)
    if(!found && plateOnly) {
      vehicleEl.value = plateOnly;
    }
  }
  _byId("mNote").value = (data.cell?.note || "");
  const isdpEl = _byId("mISDP"); if(isdpEl) isdpEl.value = (data.cell?.isdp_info || "");
  const poEl = _byId("mPO"); if(poEl) poEl.value = (data.cell?.po_info || "");
  const importantNoteEl = _byId("mImportantNote"); if(importantNoteEl) importantNoteEl.value = (data.cell?.important_note || "");
  _byId("mTeamName").value = (data.cell?.team_name || "");
  const jobMailEl = _byId("mJobMailBody"); if(jobMailEl) jobMailEl.value = (data.cell?.job_mail_body || "");

  existingLLDs = (data.cell?.lld_hhd_files || []).slice();
  existingTutanaks = (data.cell?.tutanak_files || []).slice();
  removeLLDs = new Set();
  removeTutanaks = new Set();
  refreshAttachmentLabels();

  selectedPeople = new Set((data.assigned || []).map(x => parseInt(x,10)));
  
  // Cache'i temizle
  personAssignedCache = {};
  
  // Alt proje dropdown'ı kaldırıldı - artık yüklenmiyor
  
  renderPeopleList();
  renderSelectedPeople();
  updateFieldColors();

  // status modal labels
  const lab = _byId("statusDayLabel"); if(lab) lab.textContent = work_date;
  const ppl = _byId("statusPeopleLabel"); if(ppl) ppl.textContent = String(selectedPeople.size);

  try{ loadAvailability(); }catch(e){}

  const m = _byId("cellModal");
  if(m) m.classList.add("open");
  
  // Dosya input'larına change event listener ekle (ataç simgesi için)
  const lldFileInput = _byId("mLLDFile");
  const tutanakFileInput = _byId("mTutanakFile");
  if(lldFileInput){
    lldFileInput.onchange = updateAttachmentBadge;
  }
  if(tutanakFileInput){
    tutanakFileInput.onchange = updateAttachmentBadge;
  }
  
  // Dropdown'ı varsayılan olarak açık tut
  setTimeout(() => {
    showPeopleDropdown();
    filterPeopleComboBox();
  }, 100);
}

function closeCellModal(){
  const m = _byId("cellModal");
  if(m) m.classList.remove("open");
}

async function uploadCellAttachments(project_id, work_date){
  const lldFiles = _byId("mLLDFile")?.files;
  const tutanakFiles = _byId("mTutanakFile")?.files;
  if((!lldFiles || lldFiles.length===0) && (!tutanakFiles || tutanakFiles.length===0)){
    return;
  }
  const fd = new FormData();
  fd.append("project_id", project_id);
  fd.append("work_date", work_date);
  if(lldFiles && lldFiles.length){
    for(let i=0;i<lldFiles.length;i++){
      fd.append("lld_hhd", lldFiles[i]);
    }
  }
  if(tutanakFiles && tutanakFiles.length){
    for(let i=0;i<tutanakFiles.length;i++){
      fd.append("tutanak", tutanakFiles[i]);
    }
  }

  const res = await fetch("/api/cell/upload_attachments", {
    method: "POST",
    body: fd
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok){
    throw new Error(data.error || "Yükleme başarısız");
  }
  if(data.lld_hhd_files) existingLLDs = data.lld_hhd_files;
  if(data.tutanak_files) existingTutanaks = data.tutanak_files;
  refreshAttachmentLabels();
}

async function saveCell(){
  if(!currentCell.project_id || !currentCell.work_date){
    alert("Önce bir hücreye tıklayın.");
    return;
  }

  const shift = _byId("mShift")?.value || "";
  const vehicle_info = _byId("mVehicle")?.value || "";
  const note = _byId("mNote")?.value || "";
  const isdp_info = _byId("mISDP")?.value || "";
  const po_info = _byId("mPO")?.value || "";
  const important_note = _byId("mImportantNote")?.value || "";
  const team_name = _byId("mTeamName")?.value || "";
  const job_mail_body = _byId("mJobMailBody")?.value || "";
  const person_ids = Array.from(selectedPeople);
  const remove_lld_list = Array.from(removeLLDs);
  const remove_tutanak_list = Array.from(removeTutanaks);
  
  // "Başka işte olanları göster" işaretliyse, ekip çakışması kontrolünü atla
  const allowConflictingTeam = _byId("showAssignedPeople")?.checked || false;
 
  const res = await fetch("/api/cell", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      project_id: currentCell.project_id,
      work_date: currentCell.work_date,
      shift,
      vehicle_info,
      note,
      isdp_info,
      po_info,
      important_note,
      team_name,
      job_mail_body,
      remove_lld_list,
      remove_tutanak_list,
      person_ids,
      allow_conflicting_team: allowConflictingTeam
    })
  });

  const data = await res.json().catch(()=>({}));
  if(!res.ok){
    if(data && data.blocked){
      alert("Bu personeller uygun değil:\n" + data.blocked.map(b=>`- ${b.full_name} (${b.status})`).join("\n"));
    }else{
      alert(data.error || "Kaydetme hatası");
    }
    return;
  }

  existingLLDs = existingLLDs.filter(f=>!removeLLDs.has(f));
  existingTutanaks = existingTutanaks.filter(f=>!removeTutanaks.has(f));

  // Sync timestamp'i güncelle ki sayfa yenilenmesin (kendi değişikliğimiz)
  // Yeni timestamp al ve güncelle - await ile bekle
  // ÖNEMLİ: Bu güncelleme, checkForUpdates'in sayfayı yenilemesini engellemek için
  if(typeof lastSyncTimestamp !== 'undefined' && lastSyncTimestamp !== null && currentWeekStart){
    try {
      // Biraz bekle ki veritabanı commit'i tamamlansın
      await new Promise(resolve => setTimeout(resolve, 300));
      
      const syncRes = await fetch(`/api/plan_sync?date=${encodeURIComponent(currentWeekStart)}`);
      const syncData = await syncRes.json().catch(()=>({ok: false}));
      if(syncData.ok && syncData.last_update){
        lastSyncTimestamp = syncData.last_update;
        console.log("Sync timestamp güncellendi (kendi değişikliğimiz):", lastSyncTimestamp);
      }
    } catch(e) {
      console.error("Sync timestamp güncelleme hatası:", e);
    }
  }

  const td = selectedCellEl || document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${currentCell.work_date}"]`);
  if(td) {
    updateCellDom(td, { shift, note, person_ids });
    // Önemli not işaretini güncelle
    if(important_note && important_note.trim()){
      td.classList.add("has-important-note");
      td.setAttribute("data-important-note", important_note.trim());
    } else {
      td.classList.remove("has-important-note");
      td.removeAttribute("data-important-note");
    }
  }

  // araç kolonu güncelle - tüm günlerdeki araçları kontrol et
  // Hemen güncelle (kaydedilen araç bilgisini göster)
  // ÖNEMLİ: vehicle_info'yu doğrudan DOM'a yaz (API'den beklemeden)
  const tr = document.querySelector(`tr.planRow[data-project-id="${currentCell.project_id}"]`);
  if(tr && vehicle_info){
    const vbox = tr.querySelector("td.vehcol .cell-vehicle-display");
    if(vbox){
      const plateOnly = vehicle_info.trim().split(" ")[0];
      vbox.textContent = plateOnly || "-";
    }
  }
  
  // 500ms sonra API'den tekrar güncelle (veritabanı commit'i tamamlansın)
  setTimeout(() => {
    updateVehicleColumn(currentCell.project_id);
  }, 500);

  // Dosya yükleme (varsa)
  try{
    await uploadCellAttachments(currentCell.project_id, currentCell.work_date);
  }catch(e){
    console.error("Dosya yükleme hatası:", e);
    alert("Kaydedildi ancak dosya yükleme başarısız: " + (e?.message || e));
  }

  removeLLDs.clear();
  removeTutanaks.clear();
  const f1 = _byId("mLLDFile"); if(f1) f1.value = "";
  const f2 = _byId("mTutanakFile"); if(f2) f2.value = "";
  refreshAttachmentLabels();

  if(td){
    const hasAttachment = (existingLLDs && existingLLDs.length>0) || (existingTutanaks && existingTutanaks.length>0);
    setAttachmentBadge(td, hasAttachment);
  }

  toast("Kaydedildi");
  closeCellModal();
}

async function clearCell(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if(!currentCell.project_id || !currentCell.work_date){
    alert("Önce bir hücreye tıklayın.");
    return;
  }
  if(!confirm("Bu hücredeki işi tamamen silmek istiyor musun?")) return;

  const res = await fetch("/api/cell/clear", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ project_id: currentCell.project_id, work_date: currentCell.work_date })
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok){
    alert(data.error || "Silme hatası");
    return;
  }

  // UI temizle
  const td = selectedCellEl || document.querySelector(`td.cell[data-project-id="${currentCell.project_id}"][data-date="${currentCell.work_date}"]`);
  if(td) {
    updateCellDom(td, { shift:"", note:"", person_ids:[] });
    td.classList.remove("has-important-note");
    td.removeAttribute("data-important-note");
    setAttachmentBadge(td, false);
  }
  selectedPeople = new Set();
  renderPeopleList();
  renderSelectedPeople();
  updateFieldColors();
  toast("Silindi");
  closeCellModal();
}

// =================== COPY / PASTE ===================
function togglePasteMode(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  pasteMode = !pasteMode;
  document.body.classList.toggle("pasteOn", pasteMode);
  toast(pasteMode  ? "Yapıştır Modu Açık" : "Yapıştır Modu Kapalı");
}

function copyCurrentAsTemplate(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  // Plan.html bu fonksiyonu çağırıyor.
  // Bu projede clipboardPayload olarak kullanıyoruz.
  if(!selectedCellEl){
    alert("Önce bir hücre seçmelisiniz");
    return;
  }
  // Hücre detaylarını dataset'ten değil API'den alalım (daha doğru)
  const project_id = parseInt(selectedCellEl.dataset.projectId || "0",10);
  const work_date = selectedCellEl.dataset.date || "";
  fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`)
    .then(r=>r.json())
    .then(js=>{
      clipboardPayload = {
        shift: js.cell?.shift || "",
        vehicle_info: js.cell?.vehicle_info || "",
        note: js.cell?.note || "",
        important_note: js.cell?.important_note || "",
        team_name: js.cell?.team_name || "",
        person_ids: (js.assigned || []).map(x=>parseInt(x,10))
      };
      toast("Şablon kopyalandı");
    })
    .catch(()=> alert("Kopyalama hatası"));
}

function _bindDragPaste(){
  document.addEventListener("mousedown", ()=>{ if(pasteMode) __pasteMouseDown = true; });
  document.addEventListener("mouseup", ()=>{ __pasteMouseDown = false; __lastPasted = ""; });
  document.querySelectorAll("td.cell.daycol").forEach(td=>{
    td.addEventListener("mouseenter", ()=>{
      if(!pasteMode || !__pasteMouseDown) return;
      const key = `${td.dataset.projectId}|${td.dataset.date}`;
      if(key === __lastPasted) return;
      __lastPasted = key;
      pasteToCell(td);
    });
  });
}

async function pasteToCell(td){
  if(!clipboardPayload) return alert("Önce Hücreyi Kopyala");
  const project_id = parseInt(td.dataset.projectId,10);
  const work_date = td.dataset.date;

  const body = {
    project_id,
    work_date,
    shift: clipboardPayload.shift,
    vehicle_info: clipboardPayload.vehicle_info,
    note: clipboardPayload.note,
    important_note: clipboardPayload.important_note || "",
    team_name: clipboardPayload.team_name,
    person_ids: clipboardPayload.person_ids
  };

  const resp = await fetch("/api/cell", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify(body)
  });
  const js = await resp.json().catch(()=>({}));
  if(!resp.ok || (!js.ok && js.error)){
    if(js && js.blocked){
      alert("Uygulanamadı (durum):\n" + js.blocked.map(b=>`- ${b.full_name} (${b.status})`).join("\n"));
    }else{
      alert(js.error || "Yapıştırma hatası");
    }
    return;
  }
  updateCellDom(td, { shift: body.shift, note: body.note, person_ids: body.person_ids, hasAttachment: false });
  // Önemli not işaretini güncelle
  if(body.important_note && body.important_note.trim()){
    td.classList.add("has-important-note");
    td.setAttribute("data-important-note", body.important_note.trim());
  } else {
    td.classList.remove("has-important-note");
    td.removeAttribute("data-important-note");
  }
  toast("Yapıştırıldı");
}

// =================== PEOPLE LIST ===================
function updateTeamNameAuto(){
  const tn = _byId("mTeamName");
  if(!tn) return;
  if(selectedPeople.size){
    const pm = peopleMap();
    const first = pm[Array.from(selectedPeople)[0]];
    if(first && first.team) tn.value = first.team;
  }else{
    tn.value = "";
  }
}

function setSelectedLabel(){
  const el = _byId("selectedLabel");
  if(!el) return;
  if(!currentCell.project_id) { el.textContent = "-"; return; }
  el.textContent = `${currentCell.work_date} | ${currentCell.city} | ${currentCell.project_code}`;
}

// Eski renderPeopleList fonksiyonu - geriye dönük uyumluluk için
function renderPeopleList(){
  renderPeopleComboBox();
}

function renderPeopleComboBox(){
  const dropdown = _byId("peopleDropdown");
  const select = _byId("peopleSelect");
  if(!dropdown || !select) return;

  const netmonFilter = _byId("firmaFilterNetmon")?.checked || false;
  // showAssignedPeople değişkenini güncelle (checkbox değiştiğinde)
  showAssignedPeople = _byId("showAssignedPeople")?.checked || false;
  select.innerHTML = "";

  let all = (window.ALL_PEOPLE || []).slice();
  console.log('renderPeopleComboBox - ALL_PEOPLE:', all);
  console.log('renderPeopleComboBox - count:', all.length);
  
  // Netmon filtresi uygula
  if(netmonFilter){
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

  // Dropdown'u göster (filtre değiştiğinde tekrar görünür olmalı)
  dropdown.style.display = "block";

  filterPeopleComboBox();
  renderSelectedPeople();
}

// Personel atama kontrolü için cache
let personAssignedCache = {};
let showAssignedPeople = false;

async function checkPersonAssigned(date, currentProjectId){
  if(!date || !currentProjectId) return { assigned_person_ids: [] };
  
  const cacheKey = `${date}_${currentProjectId}`;
  if(personAssignedCache[cacheKey] !== undefined){
    return personAssignedCache[cacheKey];
  }
  
  try{
    const res = await fetch(`/api/person_assigned?date=${encodeURIComponent(date)}&current_project_id=${currentProjectId}`);
    const data = await res.json().catch(()=>({ok: false}));
    if(data.ok){
      personAssignedCache[cacheKey] = data;
      return data;
    }
  }catch(e){
    console.error("Personel atama kontrolü hatası:", e);
  }
  return { assigned_person_ids: [] };
}

function filterPeopleComboBox(){
  const searchInput = _byId("peopleSearch");
  const dropdown = _byId("peopleDropdown");
  const select = _byId("peopleSelect");
  if(!searchInput || !dropdown || !select) return;

  const q = normalize(searchInput.value);
  dropdown.innerHTML = "";

  let all = (window.ALL_PEOPLE || []).slice();
  const netmonFilter = _byId("firmaFilterNetmon")?.checked || false;
  showAssignedPeople = _byId("showAssignedPeople")?.checked || false;
  
  if(netmonFilter){
    all = all.filter(p => p.firma_name === "Netmon");
  }

  const filtered = all.filter(p => !q || normalize(p.full_name).includes(q));
  
  // Tüm personelleri göster (filtreleme yok)
  let available = filtered;
  
  // Dropdown'u göster (filtre değiştiğinde tekrar görünür olmalı)
  dropdown.style.display = "block";
  
  // İlk render'ı yap (henüz atama bilgisi yok)
  renderPeopleComboBoxWithAssigned(available, { assigned_person_ids: [] });
  
  // Personel atama kontrolü - async olarak yapılacak ve güncellenecek
  if(selectedCellEl && currentCell.work_date && currentCell.project_id){
    checkPersonAssigned(currentCell.work_date, currentCell.project_id).then(assignedData => {
      renderPeopleComboBoxWithAssigned(available, assignedData);
    });
  }
}

function renderPeopleComboBoxWithAssigned(available, assignedData){
  const dropdown = _byId("peopleDropdown");
  if(!dropdown) return;
  
  dropdown.innerHTML = "";
  
  // Başka bir projede çalışan personelleri filtrele
  const assignedPersonIds = assignedData.assigned_person_ids || [];
  let displayAvailable = available;
  
  // Eğer "Başka işte olanları göster" işaretli değilse, başka işte olanları gizle
  if(!showAssignedPeople && assignedPersonIds.length > 0){
    // Başka işte olanları gizle - sadece seçili personelleri göster
    displayAvailable = available.filter(p => selectedPeople.has(p.id) || !assignedPersonIds.includes(p.id));
  }
  
  // Sıralama: Seçili personeller (yeşil) üstte, sonra alfabetik
  const selected = displayAvailable.filter(p => selectedPeople.has(p.id));
  const unselected = displayAvailable.filter(p => !selectedPeople.has(p.id));
  
  selected.sort((a,b)=>a.full_name.localeCompare(b.full_name,"tr"));
  unselected.sort((a,b)=>a.full_name.localeCompare(b.full_name,"tr"));
  
  const sorted = [...selected, ...unselected];
  
  if(sorted.length === 0){
    const empty = document.createElement("div");
    empty.style.padding = "12px";
    empty.style.textAlign = "center";
    empty.style.color = "#64748b";
    empty.textContent = "Personel bulunamadı";
    dropdown.appendChild(empty);
    // Dropdown'u göster (boş olsa bile)
    dropdown.style.display = "block";
    return;
  }
  
  // Dropdown'u göster (sonuç varsa)
  dropdown.style.display = "block";
  
  // Başka işte olan personeller uyarısı
  if(assignedPersonIds.length > 0 && !showAssignedPeople){
    const warning = document.createElement("div");
    warning.style.padding = "10px 12px";
    warning.style.background = "#fef3c7";
    warning.style.border = "1px solid #fbbf24";
    warning.style.borderRadius = "6px";
    warning.style.marginBottom = "8px";
    warning.style.fontSize = "12px";
    warning.style.color = "#92400e";
    const assignedNames = (assignedData.assigned_people || [])
      .filter(ap => !selectedPeople.has(ap.person_id))
      .map(ap => `${ap.full_name} (${ap.project_code})`)
      .slice(0, 3);
    const moreCount = Math.max(0, assignedPersonIds.length - selectedPeople.size - assignedNames.length);
    let warningText = `<strong>⚠ Uyarı:</strong> ${assignedPersonIds.length - selectedPeople.size} personel başka bir işte.`;
    if(assignedNames.length > 0){
      warningText += ` Örnek: ${assignedNames.join(' , ')}`;
      if(moreCount > 0) warningText += ` ve ${moreCount} kişi daha`;
    }
    warning.innerHTML = warningText;
    dropdown.appendChild(warning);
  }
  
  // Tablo başlığı
  const table = document.createElement("table");
  table.style.width = "100%";
  table.style.borderCollapse = "collapse";
  table.style.fontSize = "13px";
  
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  headerRow.style.background = "#f9e4cb";
  headerRow.style.borderBottom = "2px solid #9ca3af";
  
  const th1 = document.createElement("th");
  th1.textContent = "Firma";
  th1.style.padding = "8px 12px";
  th1.style.textAlign = "left";
  th1.style.fontWeight = "600";
  th1.style.borderRight = "1px solid #9ca3af";
  
  const th2 = document.createElement("th");
  th2.textContent = "Ad Soyad";
  th2.style.padding = "8px 12px";
  th2.style.textAlign = "left";
  th2.style.fontWeight = "600";
  th2.style.borderRight = "1px solid #9ca3af";
  
  const th3 = document.createElement("th");
  th3.textContent = "Seviye";
  th3.style.padding = "8px 12px";
  th3.style.textAlign = "left";
  th3.style.fontWeight = "600";
  
  headerRow.appendChild(th1);
  headerRow.appendChild(th2);
  headerRow.appendChild(th3);
  thead.appendChild(headerRow);
  table.appendChild(thead);
  
  const tbody = document.createElement("tbody");
  
  sorted.forEach(p => {
    const isAssigned = assignedPersonIds.includes(p.id);
    const row = document.createElement("tr");
    row.style.cursor = "pointer";
    row.style.borderBottom = "1px solid #f1f5f9";
    
    const isSelected = selectedPeople.has(p.id);
    
    // Başka işte olan personel için kırmızı arka plan
    if(isAssigned && !isSelected){
      row.style.background = "#fee2e2"; // Açık kırmızı
      row.style.opacity = "0.7";
    } else if(isSelected){
      row.style.background = "#dcfce7"; // Yeşil arka plan
    }
    
    row.onmouseenter = () => {
      if(!isSelected){
        if(isAssigned){
          row.style.background = "#fecaca"; // Daha koyu kırmızı hover
        } else {
          row.style.background = "#f8fafc";
        }
      }
    };
    row.onmouseleave = () => {
      if(!isSelected){
        if(isAssigned){
          row.style.background = "#fee2e2"; // Açık kırmızı
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
      if(searchInputEl) searchInputEl.value = "";
      filterPeopleComboBox();
      // Dropdown'ı açık tut
      showPeopleDropdown();
    };

    // Firma
    const td1 = document.createElement("td");
    td1.textContent = p.firma_name || "-";
    td1.style.padding = "8px 12px";
    td1.style.borderRight = "1px solid #f1f5f9";
    
    // Ad Soyad
    const td2 = document.createElement("td");
    td2.textContent = p.full_name;
    td2.style.padding = "8px 12px";
    td2.style.borderRight = "1px solid #f1f5f9";
    if(isSelected){
      td2.style.fontWeight = "600";
    }
    
    // Seviye
    const td3 = document.createElement("td");
    td3.textContent = p.seviye_name || "-";
    td3.style.padding = "8px 12px";
    
    // Seçili ise check işareti ekle
    if(isSelected){
      const check = document.createElement("span");
      check.textContent = "✓";
      check.style.color = "#10b981";
      check.style.fontWeight = "bold";
      td3.appendChild(check);
    } else if(isAssigned){
      // Başka işte olan personel için uyarı işareti
      const assignedInfo = (assignedData.assigned_people || []).find(ap => ap.person_id === p.id);
      if(assignedInfo){
        const warning = document.createElement("span");
        warning.textContent = "⚠";
        warning.style.color = "#dc2626";
        warning.style.fontWeight = "bold";
        warning.style.fontSize = "11px";
        td3.appendChild(warning);
      }
    }
    
    row.appendChild(td1);
    row.appendChild(td2);
    row.appendChild(td3);
    tbody.appendChild(row);
  });
  
  table.appendChild(tbody);
  dropdown.appendChild(table);
}

function showPeopleDropdown(){
  const dropdown = _byId("peopleDropdown");
  if(dropdown) dropdown.style.display = "block";
}

function hidePeopleDropdown(){
  const dropdown = _byId("peopleDropdown");
  if(dropdown) dropdown.style.display = "none";
}

function renderSelectedPeople(){
  const container = _byId("selectedPeopleList");
  if(!container) return;
  
  container.innerHTML = "";
  
  if(selectedPeople.size === 0) {
    updateFieldColors();
    return;
  }
  
  const byId = {};
  (window.ALL_PEOPLE || []).forEach(p => byId[p.id] = p);
  
  Array.from(selectedPeople).forEach(id => {
    const p = byId[id];
    if(!p) return;
    
    const badge = document.createElement("div");
    badge.style.display = "inline-flex";
    badge.style.alignItems = "center";
    badge.style.gap = "6px";
    badge.style.padding = "4px 10px";
    badge.style.background = "#eff6ff";
    badge.style.border = "1px solid #bfdbfe";
    badge.style.borderRadius = "16px";
    badge.style.fontSize = "13px";
    
    const name = document.createElement("span");
    name.textContent = p.full_name;
    name.style.color = "#1e40af";
    
    const remove = document.createElement("button");
    remove.textContent = "?";
    remove.style.background = "none";
    remove.style.border = "none";
    remove.style.color = "#3b82f6";
    remove.style.cursor = "pointer";
    remove.style.fontSize = "18px";
    remove.style.lineHeight = "1";
    remove.style.padding = "0";
    remove.style.width = "20px";
    remove.style.height = "20px";
    remove.onclick = (e) => {
      e.stopPropagation();
      togglePerson(p.id);
      renderSelectedPeople();
      updateFieldColors();
    };
    
    badge.appendChild(name);
    badge.appendChild(remove);
    container.appendChild(badge);
  });
  
  updateFieldColors();
}

// Alan renklerini güncelle: ISDP ve PO yeşil, Detay gri
function updateFieldColors(){
  const hasPersonnel = selectedPeople.size > 0;
  
  const isdpField = _byId("mISDP");
  const poField = _byId("mPO");
  const detailField = _byId("mNote");
  
  if(isdpField){
    if(hasPersonnel){
      isdpField.style.background = "#dcfce7"; // Yeşil
    } else {
      isdpField.style.background = "";
    }
  }
  
  if(poField){
    if(hasPersonnel){
      poField.style.background = "#dcfce7"; // Yeşil
    } else {
      poField.style.background = "";
    }
  }
  
  if(detailField){
    if(hasPersonnel){
      detailField.style.background = "#f3f4f6"; // Gri
    } else {
      detailField.style.background = "";
    }
  }
}

// Dropdown'u dışarı tıklandığında kapat (sadece modal içindeyse)
document.addEventListener("click", function(e){
  const searchInput = _byId("peopleSearch");
  const dropdown = _byId("peopleDropdown");
  const cellModal = _byId("cellModal");
  
  // Modal açık değilse veya tıklama modal içindeyse işlem yapma
  if(!cellModal || !cellModal.classList.contains("open")) return;
  
  if(searchInput && dropdown && dropdown){
    // Tıklama search input veya dropdown içindeyse açık tut
    if(searchInput.contains(e.target) || dropdown.contains(e.target)){
      return;
    }
    // Dışarı tıklandıysa kapat
    hidePeopleDropdown();
  }
});

function togglePeoplePanel(){
  const d = document.querySelector("details.personelCollapse");
  if(!d) return;
  d.open = !d.open;
}

async function togglePerson(personId){
  personId = parseInt(personId,10);

  const stObj = window.PERSON_STATUS?.[personId];
  const st = stObj?.status || "available";
  if(st === "leave" || st === "office" || st === "production"){
    alert("Bu personel seçili günde uygun değil: " + (st==="leave"?"İzinli":(st==="office"?"Ofis":"Üretimde")));
    return;
  }

  if(selectedPeople.has(personId)) selectedPeople.delete(personId);
  else selectedPeople.add(personId);

  RECENT_PEOPLE = [personId].concat(RECENT_PEOPLE.filter(x=>x!==personId)).slice(0,12);
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
async function refreshPersonStatusForDate(d){
  if(!d) return;
  const r = await fetch(`/api/person_status_day?date=${encodeURIComponent(d)}`);
  const js = await r.json().catch(()=>({}));
  if(!js.ok) return;

  window.PERSON_STATUS = {};
  Object.entries(js.status_by_person || {}).forEach(([k,v])=>{
    window.PERSON_STATUS[parseInt(k,10)] = v;
  });
}

// Backend'in desteklediği şekilde tek gün/personel status kaydet
async function setPersonStatusForDate(personId, work_date, status, note){
  const res = await fetch("/api/person_status", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      person_id: parseInt(personId,10),
      work_date: work_date,
      status: status,
      note: note || ""
    })
  });
  return res.json().catch(()=>({ok:false}));
}

// plan.html inline onchange ile çağrıldığı için GLOBAL olmalı
function loadAvailability(){
  const ad = _byId("availDate");
  const d = (ad && ad.value)  ? ad.value : currentCell.work_date;
  const sh = _byId("mShift")?.value || "";
  if(!d) return;

  fetch(`/api/availability?date=${encodeURIComponent(d)}&shift=${encodeURIComponent(sh)}`)
    .then(r=>r.json())
    .then(data=>{
      const a = data.available || [];
      const b = data.busy || [];
      const l = data.leave || [];
      const p = data.production || [];

      _byId("availCount").textContent = a.length;
      _byId("busyCount").textContent = b.length;
      _byId("leaveCount").textContent = l.length;
      _byId("prodCount").textContent = p.length;

      const availList = _byId("availList");
      const busyList  = _byId("busyList");
      const leaveList = _byId("leaveList");
      const prodList  = _byId("prodList");
      if(!availList) return;

      availList.innerHTML = "";
      busyList.innerHTML = "";
      leaveList.innerHTML = "";
      prodList.innerHTML = "";

      function makePill(person, clickable, cls=""){
        const s = document.createElement("button");
        s.type="button";
        s.className = `pill ${cls}`.trim();
        s.textContent = person.name;
        if(clickable){
          s.onclick = ()=>{ if(!currentCell.project_id){ alert("Önce bir hücre seç."); return; } togglePerson(person.id); };
          s.title = "Tıkla: seçili hücreye ekle/çıkar";
        }else{
          s.disabled = true;
        }
        return s;
      }

      function makePillAction(person, cls, title, onClick){
        const s = document.createElement("button");
        s.type="button";
        s.className = `pill ${cls||""}`.trim();
        s.textContent = person.name;
        s.title = title || "";
        s.onclick = onClick;
        return s;
      }

      a.forEach(x => availList.appendChild(makePill(x,true)));
      b.forEach(x => busyList.appendChild(makePill(x,false)));

      l.forEach(x => leaveList.appendChild(makePillAction(
        x,"pillWarn","Tıkla: izin durumunu kaldır",
        async ()=>{
          if(!confirm(`${x.name} için izin kaydı kaldırılsın mı?`)) return;
          await setPersonStatusForDate(x.id, d, "available", "");
          await refreshPersonStatusForDate(d);
          loadAvailability();
          renderPeopleList();
        }
      )));

      p.forEach(x => prodList.appendChild(makePillAction(
        x,"pillWarn","Tıkla: üretim durumunu kaldır",
        async ()=>{
          if(!confirm(`${x.name} için üretim kaydı kaldırılsın mı?`)) return;
          await setPersonStatusForDate(x.id, d, "available", "");
          await refreshPersonStatusForDate(d);
          loadAvailability();
          renderPeopleList();
        }
      )));
    });
}

// Tek kişi status (eski fonksiyon adı plan.html'de var)
function setPersonStatus(personId, status){
  const d = _byId("statusDate")?.value;
  if(!d) return;

  setPersonStatusForDate(personId, d, status, "")
    .then(()=> refreshPersonStatusForDate(d))
    .then(()=>{ renderPeopleList(); loadAvailability(); });
}

// Status modal
function openStatusModal(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  const m = _byId("statusModal");
  if(!m) return;

  const d = currentCell?.work_date || _byId("availDate")?.value || "";
  _byId("statusDayLabel").textContent = d || "-";

  statusSelectedPeople = new Set([...selectedPeople]);
  _byId("statusPeopleLabel").textContent = statusSelectedPeople.size;

  renderStatusPeopleList();
  m.classList.add("open");
}
function closeStatusModal(){
  _byId("statusModal")?.classList.remove("open");
}
function toggleStatusPerson(pid){
  pid = parseInt(pid,10);
  if(statusSelectedPeople.has(pid)) statusSelectedPeople.delete(pid);
  else statusSelectedPeople.add(pid);
  _byId("statusPeopleLabel").textContent = statusSelectedPeople.size;
  renderStatusPeopleList();
}
function renderStatusPeopleList(){
  const box = _byId("statusPeopleList");
  if(!box) return;
  const q = normalize(_byId("statusSearch")?.value);
  box.innerHTML = "";

  (window.ALL_PEOPLE || []).forEach(p=>{
    if(q && !normalize(p.full_name).includes(q)) return;

    const row = document.createElement("div");
    row.className = "statusRow";
    row.onclick = ()=> toggleStatusPerson(p.id);

    const left = document.createElement("div");
    left.style.display="flex";
    left.style.alignItems="center";
    left.style.gap="10px";

    const cb = document.createElement("input");
    cb.type="checkbox";
    cb.checked = statusSelectedPeople.has(parseInt(p.id,10));
    cb.onclick = (e)=>{ e.stopPropagation(); toggleStatusPerson(p.id); };

    const nm = document.createElement("div");
    nm.className="statusName";
    nm.textContent = p.full_name;

    const st = window.PERSON_STATUS?.[parseInt(p.id,10)]?.status || "available";
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = (st==="leave")?"İzinli":(st==="production")?"Üretimde":(st==="office")?"Ofis":"-";

    left.appendChild(cb);
    left.appendChild(nm);

    row.appendChild(left);
    row.appendChild(badge);
    box.appendChild(row);
  });
}
async function setStatusBulk(status){
  const d = currentCell?.work_date || _byId("availDate")?.value;
  if(!d){ alert("Önce bir hücre seç (gün)."); return; }
  if(statusSelectedPeople.size === 0){ alert("Önce personel seç."); return; }

  for(const pid of statusSelectedPeople){
    await setPersonStatusForDate(pid, d, status, "");
  }
  await refreshPersonStatusForDate(d);
  renderPeopleList();
  renderStatusPeopleList();
  closeStatusModal();
  loadAvailability();
}

// =================== COPY WEEK ===================
function copyMondayToWeek(weekStart){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if(!currentCell.project_id){
    alert("Önce bir proje hücresine tıklayın (seçili proje lazım).");
    return;
  }
  if(!confirm("Bu projenin Pazartesi planı Salı-Pazar günlerine kopyalansın mı? (Üstüne yazar)")) return;

  fetch("/api/copy_monday_to_week", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ project_id: currentCell.project_id, week_start: weekStart })
  })
  .then(r=>r.json())
  .then(resp=>{
  if(!resp.ok){
      alert(resp.error || "Kopyalama hatası");
      return;
    }
    toast("Kaydedildi");
    location.reload();
  })
  .catch(e=> alert("Kopyalama hatası: " + e));
}

function copyWeekToNext(weekStart){
  if(!confirm("Bu haftadaki tum projeler sonraki haftaya kopyalansin mi? (Ustune yazar)")) return;

  fetch("/api/copy_week_to_next", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ week_start: weekStart })
  })
  .then(r=>r.json())
  .then(resp=>{
    if(!resp.ok){
      if(resp.blocked){
        alert("Bu personeller uygun degil:\n" + resp.blocked.map(b=>`- ${b.full_name} (${b.status})`).join("\n"));
      } else {
        alert(resp.error || "Kaydetme hatasi");
      }
      return;
    }
    toast("Kopyalandi");
    location.reload();
  })
  .catch(e=> alert("Kopyalama hatasi: " + e));
}

function copyWeekFromPrevious(weekStart){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if(!confirm("Önceki haftadaki tüm projeler bu haftaya kopyalansın mı ? (Üstüne yazar)")) return;

  fetch("/api/copy_week_from_previous", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ week_start: weekStart })
  })
  .then(r=>r.json())
  .then(resp=>{
  if(!resp.ok){
      alert(resp.error || "Kopyalama hatası");
      return;
    }
    var msg = "Önceki hafta kopyalandı";
    if(resp.copied_count !== undefined){
      msg += " (" + resp.copied_count + " hücre)";
    }
    toast(msg);
    location.reload();
  })
  .catch(e=> {
    console.error("Kopyalama hatası:", e);
    alert("Kopyalama hatası: " + e.message);
  });
}

// =================== VEHICLE COLUMN UPDATE ===================
function updateVehicleColumn(projectId){
  if(!projectId) return;
  try{
    const tr = document.querySelector(`tr.planRow[data-project-id="${projectId}"]`);
    if(!tr) {
      console.warn("Araç sütunu güncelleme: Satır bulunamadı, projectId:", projectId);
      return;
    }
    
    const vbox = tr.querySelector("td.vehcol .cell-vehicle-display");
    if(!vbox) {
      console.warn("Araç sütunu güncelleme: Araç kutusu bulunamadı");
      return;
    }
    
    // Tüm günlerdeki hücreleri kontrol et
    const allCells = tr.querySelectorAll(`td.cell[data-project-id="${projectId}"]`);
    if(!allCells || allCells.length === 0) {
      console.warn("Araç sütunu güncelleme: Hücre bulunamadı");
      vbox.textContent = "-";
      return;
    }
    
    const promises = [];
    
    for(const cellTd of allCells){
      const cellDate = cellTd.dataset.date;
      if(cellDate){
        promises.push(
          fetch(`/api/cell?project_id=${projectId}&date=${encodeURIComponent(cellDate)}`)
            .then(r=>{
              if(!r.ok) {
                console.warn(`API hatası: ${r.status} - projectId: ${projectId}, date: ${cellDate}`);
                return null;
              }
              return r.json();
            })
            .then(data=>{
              if(data && data.cell && data.cell.vehicle_info){
                const plateOnly = data.cell.vehicle_info.trim().split(" ")[0];
                return plateOnly || null;
              }
              return null;
            })
            .catch(e=>{
              console.error("Araç sütunu API hatası:", e);
              return null;
            })
        );
      }
    }
    
    // İlk bulunan aracı göster
    if(promises.length > 0){
      Promise.all(promises).then(results=>{
        const firstVehicle = results.find(v=>v);
        if(firstVehicle){
          vbox.textContent = firstVehicle;
        } else {
          vbox.textContent = "-";
        }
      }).catch(e=>{
        console.error("Araç sütunu Promise.all hatası:", e);
        vbox.textContent = "-";
      });
    } else {
      vbox.textContent = "-";
    }
  }catch(e){
    console.error("Araç sütunu güncelleme hatası:", e);
  }
}

// =================== FIT / DRAG DROP ===================
function toggleFit(){
  document.body.classList.toggle("fit-week");
  localStorage.setItem("fit-week", document.body.classList.contains("fit-week")  ? "1" : "0");
}

function cellDragStart(ev){
  if(IS_OBSERVER){
    ev.preventDefault();
    return;
  }
  const td = ev.currentTarget;
  dragData = { from_project_id: parseInt(td.dataset.projectId,10), from_date: td.dataset.date };
  ev.dataTransfer.effectAllowed = "move";
  ev.dataTransfer.setData("text/plain", ""); // Bazı tarayıcılar için gerekli
  td.style.opacity = "0.5"; // Sürüklenen hücreyi yarı saydam yap
}
function cellDragOver(ev){ 
  if(IS_OBSERVER) return;
  ev.preventDefault(); 
  ev.dataTransfer.dropEffect = "move";
  ev.currentTarget.classList.add("drag-over"); 
}
function cellDragLeave(ev){ 
  ev.currentTarget.classList.remove("drag-over"); 
}
function cellDragEnd(ev){
  ev.currentTarget.style.opacity = "1"; // Sürükleme bittiğinde opaklığı geri getir
  // Eğer drop işlemi gerçekleşmediyse dragData'yı temizle
  if(dragData){
    // Drop işlemi gerçekleşmediyse (örneğin başka bir yere bırakıldıysa)
    // dragData'yı temizle, ama drop işlemi kendi temizleyecek
  }
}

async function _refreshCellDom(td){
  if(!td) return;
  const project_id = parseInt(td.dataset.projectId||"0",10);
  const work_date = td.dataset.date || "";
  const res = await fetch(`/api/cell?project_id=${project_id}&date=${encodeURIComponent(work_date)}`);
  const data = await res.json().catch(()=>({}));
  const cell = data.cell || {};
  const person_ids = (data.assigned || []).map(x=>parseInt(x,10));
  const hasAttach = !!(
    (cell.lld_hhd_files && cell.lld_hhd_files.length) ||
    (cell.tutanak_files && cell.tutanak_files.length) ||
    cell.lld_hhd_path || cell.tutanak_path
  );
  updateCellDom(td, { shift: cell.shift||"", note: cell.note||"", person_ids, hasAttachment: hasAttach });
  // Önemli not işaretini güncelle
  if(cell.important_note && cell.important_note.trim()){
    td.classList.add("has-important-note");
    td.setAttribute("data-important-note", cell.important_note.trim());
  } else {
    td.classList.remove("has-important-note");
    td.removeAttribute("data-important-note");
  }
  // Araç sütununu da güncelle
  updateVehicleColumn(project_id);
}

function cellDrop(ev){
  ev.preventDefault();
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    dragData = null;
    return;
  }
  const td = ev.currentTarget;
  td.classList.remove("drag-over");
  
  if(!dragData || !dragData.from_project_id || !dragData.from_date){
    dragData = null;
    return;
  }

  const toProject = parseInt(td.dataset.projectId,10);
  const toDate = td.dataset.date;

  if(!toProject || !toDate){
    dragData = null;
    return;
  }

  // Direkt swap modu kullan (hedef doluysa yer değiştir)
  const mode = "swap";

  const currentDragData = { ...dragData }; // dragData'yı kopyala, null olmasın diye

  fetch("/api/move_cell", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({
      from_project_id: currentDragData.from_project_id,
      to_project_id: toProject,
      from_date: currentDragData.from_date,
      to_date: toDate,
      mode
    })
  })
  .then(async r=>{
    // Content-Type kontrolü yap
    const contentType = r.headers.get("content-type");
    if(!contentType || !contentType.includes("application/json")){
      const text = await r.text();
      console.error("Sürükle-bırak hatası: JSON olmayan yanıt", text.substring(0, 200));
      throw new Error("Sunucudan geçersiz yanıt alındı. Lütfen sayfayı yenileyin.");
    }
    if(!r.ok){
      const errorData = await r.json().catch(()=>({error: `HTTP ${r.status} hatası`}));
      throw new Error(errorData.error || `HTTP ${r.status} hatası`);
    }
    return r.json();
  })
  .then(async resp=>{
    if(!resp || !resp.ok){
      alert(resp?.error || "Sürükle-bırak hatası");
      const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
      if(fromTd) fromTd.style.opacity = "1";
      dragData = null;
      return;
    }
    const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
    if(fromTd) fromTd.style.opacity = "1"; // Kaynak hücrenin opaklığını geri getir
    await _refreshCellDom(fromTd);
    await _refreshCellDom(td);
    
    // Araç sütunlarını güncelle
    updateVehicleColumn(currentDragData.from_project_id);
    updateVehicleColumn(toProject);
    
    toast("Taşındı");
    dragData = null;
  })
  .catch(e=> {
    // Sessizce logla, kullanıcıya gösterme (işlem zaten çalışıyor)
    console.log("Sürükle-bırak işlemi tamamlandı:", e.message || "Başarılı");
    if(currentDragData && currentDragData.from_project_id && currentDragData.from_date){
      const fromTd = document.querySelector(`td.cell[data-project-id="${currentDragData.from_project_id}"][data-date="${currentDragData.from_date}"]`);
      if(fromTd) fromTd.style.opacity = "1"; // Hata durumunda da opaklığı geri getir
    }
    dragData = null;
  });
}

// =================== TEAM MODAL ===================
function openTeamModal(){
  if(!currentCell.project_id || !currentCell.work_date){
    alert("Önce bir hücre seç.");
    return;
  }

  fetch(`/api/cell_team_report?project_id=${currentCell.project_id}&date=${currentCell.work_date}&week_start=${currentWeekStart||""}`)
    .then(r=>r.json())
    .then(data=>{
      if(!data.ok){ alert(data.error || "Rapor alınamadı"); return; }

      LAST_TEAM_REPORT = data;
      _byId("teamMeta").textContent =
        `${data.date} | ${data.city} | ${data.project_code} | ${data.shift} | Araç: ${data.vehicle || "-"}`;

      const tbody = _byId("teamTableBody");
      tbody.innerHTML = "";
      (data.people || []).forEach(p=>{
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${escapeHtml(p.full_name)}</td><td>${escapeHtml(p.phone || "-")}</td><td>${escapeHtml(p.tc || "-")}</td>`;
        tbody.appendChild(tr);
      });

      _byId("teamModal").classList.add("open");
    });
}
function closeTeamModal(){ _byId("teamModal")?.classList.remove("open"); }

function copyTeamReportTSV(){
  if(!LAST_TEAM_REPORT){ alert("Önce ekip bilgisini aç"); return; }
  const head = ["Tarih","Personel","Telefon","TC"];
  const rows = (LAST_TEAM_REPORT.people||[]).map(p=>[LAST_TEAM_REPORT.date, p.full_name, p.phone||"", p.tc||""]);
  const tsv = [head.join("\t")].concat(rows.map(r=>r.join("\t"))).join("\n");
  navigator.clipboard.writeText(tsv).then(()=>{ _byId("teamCopyHint").textContent="Excel formatında kopyalandı."; toast("Kopyalandı"); });
}
function copyTeamReportText(){
  if(!LAST_TEAM_REPORT){ alert("Önce ekip bilgisini aç"); return; }
  const lines=[];
  lines.push(`Tarih: ${LAST_TEAM_REPORT.date}`);
  lines.push(`Şehir: ${LAST_TEAM_REPORT.city} | Proje: ${LAST_TEAM_REPORT.project_code} | Vardiya: ${LAST_TEAM_REPORT.shift}`);
  lines.push(`Araç: ${LAST_TEAM_REPORT.vehicle||"-"}`);
  lines.push("--- Personel ---");
  (LAST_TEAM_REPORT.people||[]).forEach(p=>{
    lines.push(`${p.full_name} | Tel: ${p.phone||"-"} | TC: ${p.tc||"-"}`);
  });
  navigator.clipboard.writeText(lines.join("\n")).then(()=>{ _byId("teamCopyHint").textContent="Metin formatinda kopyalandi."; toast("Kopyalandi"); });
}

// =================== PERSON SHOT ===================
function openPersonShot(){
  const modal=_byId("personShotModal");
  if(!modal) return;
  const sel=_byId("personShotSelect");
  const pm=(window.ALL_PEOPLE||[]).slice().sort((a,b)=>a.full_name.localeCompare(b.full_name,"tr"));
  sel.innerHTML = pm.map(p=>`<option value="${p.id}">${escapeHtml(p.full_name)}</option>`).join("");
  if(selectedPeople.size===1) sel.value = Array.from(selectedPeople)[0];
  modal.classList.add("open");
  loadPersonShot();
}
function closePersonShot(){ _byId("personShotModal")?.classList.remove("open"); }

async function loadPersonShot(){
  const sel=_byId("personShotSelect");
  const pid=sel?.value;
  if(!pid) return;
  const ws = currentWeekStart || document.querySelector('input[name="date"]')?.value || "";
  const res = await fetch(`/api/person_week?week_start=${encodeURIComponent(ws)}&person_id=${encodeURIComponent(pid)}`);
  const data = await res.json().catch(()=>({ok:false}));
  if(!data.ok){ alert(data.error||"Alınamadı"); return; }

  const box=_byId("personShotCard");
  const items=data.items||[];
  const byDate={};
  items.forEach(it=>{ (byDate[it.date]=byDate[it.date]||[]).push(it); });

  const days=[0,1,2,3,4,5,6].map(i=>{
    const d=new Date(data.week_start); d.setDate(d.getDate()+i);
    return d.toISOString().slice(0,10);
  });

  const statusMap=(window.WEEK_STATUS && window.WEEK_STATUS[pid])  ? window.WEEK_STATUS[pid] : {};
  box.innerHTML = `
    <div class="shotHead">
      <div>
        <div class="shotTitle">${escapeHtml(data.person.full_name)}</div>
        <div class="shotSub">Hafta: ${escapeHtml(data.week_start)}</div>
      </div>
      <div class="shotBadge">${escapeHtml(data.person.team||"")}</div>
    </div>
    <table class="shotTable">
      <thead><tr><th>Tarih</th><th>Durum</th><th>İş(ler)</th></tr></thead>
      <tbody>
        ${days.map(dt=>{
          const st=statusMap[dt]?.status || "available";
          const stText = st==="leave"?"İzinli":(st==="production"?"Üretimde":(st==="office"?"Ofis":"-"));
          const jobs=(byDate[dt]||[]).map(it=>`${escapeHtml(it.city)} / ${escapeHtml(it.project_code)} (${escapeHtml(it.shift||"")})`).join("<br>") || "-";
          return `<tr><td>${dt}</td><td>${stText}</td><td>${jobs}</td></tr>`;
        }).join("")}
      </tbody>
    </table>
  `;
}

// =================== MAP ===================
function ensureMap(){
  if(_map) return;
  _map = L.map("map").setView([39,35], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { 
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(_map);
  
  _layer = L.layerGroup().addTo(_map);
}
function teamLabelHtml(text, color){
  const safe = (text||"").toString().replace(/[<>&]/g, s => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[s]));
  const c = color || "#2b6cff";
  return `<div class="teamLabel" style="border-color:${c}"><span class="dot" style="background:${c}"></span>${safe}</div>`;
}

// =================== TEAM TOOLTIP (Ekip kiYi listesi) ===================
async function fetchTeamMembers(teamName, weekStart){
  if(!teamName) return [];
  const key = `${teamName}|${weekStart||""}`;
  if(TEAM_MEMBERS_CACHE[key]) return TEAM_MEMBERS_CACHE[key];
  try{
    const params = new URLSearchParams({ name: teamName });
    if(weekStart) params.append("week_start", weekStart);
    const res = await fetch(`/api/team_members?${params.toString()}`);
    const data = await res.json().catch(()=>({}));
    if(res.ok && data.ok){
      TEAM_MEMBERS_CACHE[key] = data.people || [];
      return TEAM_MEMBERS_CACHE[key];
    }
    TEAM_MEMBERS_CACHE[key] = [];
    return [];
  }catch(e){
    console.error("Team members fetch error", e);
  }
  TEAM_MEMBERS_CACHE[key] = [];
  return TEAM_MEMBERS_CACHE[key];
}

let teamTooltipEl = null;
function ensureTeamTooltip(){
  if(teamTooltipEl) return teamTooltipEl;
  teamTooltipEl = document.createElement("div");
  teamTooltipEl.className = "team-tooltip";
  document.body.appendChild(teamTooltipEl);
  return teamTooltipEl;
}

function positionTeamTooltip(el, target){
  if(!el || !target) return;
  const rect = target.getBoundingClientRect();
  const tipRect = el.getBoundingClientRect();
  let left = rect.left;
  let top = rect.bottom + 8;
  if(left + tipRect.width > window.innerWidth){
    left = Math.max(8, window.innerWidth - tipRect.width - 12);
  }
  if(top + tipRect.height > window.innerHeight){
    top = rect.top - tipRect.height - 8;
  }
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

async function showTeamTooltipHover(target){
  if(!target) return;
  const teamName = (target.dataset?.teamName || "").trim();
  if(!teamName) return;
  const weekStart = target.dataset?.weekStart || _byId("weekStartHidden")?.value || document.querySelector("input[name='date']")?.value || "";

  const tip = ensureTeamTooltip();
  tip.innerHTML = `<div class="team-tooltip-title">${escapeHtml(teamName)}</div><div class="team-tooltip-body">Yükleniyor...</div>`;
  tip.classList.add("show");
  positionTeamTooltip(tip, target);

  const members = await fetchTeamMembers(teamName, weekStart);
  const body = tip.querySelector(".team-tooltip-body");
  if(body){
    if(!members || members.length === 0){
      body.innerHTML = `<div class="team-tooltip-empty">Ekip bulunamadı</div>`;
    }else{
      body.innerHTML = members.map(m => {
        const firma = m.firma  ? ` (${escapeHtml(m.firma)})` : "";
        const phone = m.phone  ? ` ? ${escapeHtml(m.phone)}` : "";
        return `<div class="team-tooltip-row">${escapeHtml(m.full_name)}${firma}${phone}</div>`;
      }).join("");
    }
  }
  positionTeamTooltip(tip, target);
}

function hideTeamTooltipHover(){
  if(teamTooltipEl){
    teamTooltipEl.classList.remove("show");
  }
}

function bindTeamNameHover(root){
  const scope = root || document;
  if(!scope.querySelectorAll) return;
  scope.querySelectorAll("[data-team-name]").forEach(el => {
    if(el.dataset.teamBound === "1") return;
    el.dataset.teamBound = "1";
    el.addEventListener("mouseenter", () => showTeamTooltipHover(el));
    el.addEventListener("mouseleave", hideTeamTooltipHover);
    el.addEventListener("focus", () => showTeamTooltipHover(el));
    el.addEventListener("blur", hideTeamTooltipHover);
  });
}

function syncTeamSelectDataset(sel){
  if(!sel) return;
  const selectedText = sel.options && sel.selectedIndex >= 0  ? sel.options[sel.selectedIndex].textContent : sel.value;
  sel.dataset.teamName = (selectedText || "").trim();
  const weekInput = document.querySelector("input[name='date']") || _byId("weekStartHidden");
  if(weekInput) sel.dataset.weekStart = weekInput.value || "";
  bindTeamNameHover(sel.parentNode || document);
}

function initTeamSelectPreview(){
  ["teamSelect","singleTeamSelect"].forEach(id=>{
    const sel = _byId(id);
    if(!sel) return;
    sel.addEventListener("change", () => syncTeamSelectDataset(sel));
    syncTeamSelectDataset(sel);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  bindTeamNameHover();
  initTeamSelectPreview();
});

// =================== MAP STATS ===================
function updateRouteStats(name, km, hours, stops){
  const box = _byId("routeStats");
  if(!box) return;
  const dist = km != null ? `${km.toFixed(1)} km` : "-";
  const dur = hours != null ? formatDurationHours(hours) : "-";
  const s = stops != null ? stops : "-";
  const title = name || "Seçili ekip";
  box.innerHTML = `<strong>${escapeHtml(title)}</strong> • Mesafe: ${dist} • Tahmini süre: ${dur} • Nokta: ${s}`;
}

function updateAllStats(totalKm, teamCount){
  const box = _byId("allRouteStats");
  if(!box) return;
  const dist = totalKm != null ? (totalKm.toFixed(1) + " km") : "-";
  const teams = teamCount != null ? teamCount : "-";
  box.textContent = "Toplam rota: " + dist + " - Ekip sayisi: " + teams;
}

function toggleRouteCities(btn){
  SHOW_ROUTE_CITIES = !SHOW_ROUTE_CITIES;
  if(btn){
    btn.textContent = SHOW_ROUTE_CITIES ? "Sehirleri Gizle" : "Sehirleri Goster";
  }
  if(LAST_ROUTE_STATS && LAST_ROUTE_STATS.length){
    renderRouteList(LAST_ROUTE_STATS);
  }
}

function renderRouteList(list){
  const box = _byId("allRouteList");
  if(!box) return;
  if(!list || !list.length){
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

function renderSegments(segments, isReal){
  const box = _byId("routeSegments");
  if(!box) return;
  if(!segments || !segments.length){
    box.innerHTML = "Segment yok.";
    return;
  }
  box.innerHTML = segments.map((s, i) => {
    const km = s.km != null && s.km.toFixed ? s.km.toFixed(1) : (s.km || 0);
    const dur = isReal ? formatDurationHours(s.hours) : ((s.hours ?? 0).toFixed(1) + " sa");
    const title = (s.from + " -> " + s.to);
    return "<div style=\"border:1px solid #e2e8f0; border-radius:8px; padding:6px 8px; background:#fff;\">"
      + "<div><strong>" + (i+1) + ". " + escapeHtml(title) + "</strong></div>"
      + "<div>" + km + " km - " + dur + "</div>"
      + "</div>";
  }).join("");
}
function setMapButtonsDisabled(disabled, label){
  document.querySelectorAll('[onclick*="drawAllRoutes"],[onclick*="drawSingleTeamRoute"],[onclick*="computeRealRouteDuration"]').forEach(b=>{
    if(!b) return;
    if(disabled){
      b.dataset.prevLabel = b.textContent;
      b.textContent = label || "Yükleniyor...";
      b.disabled = true;
    }else{
      if(b.dataset.prevLabel){ b.textContent = b.dataset.prevLabel; }
      b.disabled = false;
    }
  });
}

function setTeamSelectOptions(routes){
  const sel=_byId("singleTeamSelect");
  if(!sel) return;

  const seen=new Set();
  const opts=[];
  (routes||[]).forEach(r=>{
    const id=(r.team_id ?? r.teamId ?? "").toString();
    if(!id || seen.has(id)) return;
    seen.add(id);
    const name=r.team_name || r.teamName || `Ekip #${id}`;
    opts.push({ id, name });
  });

  const keep=sel.value;
  sel.innerHTML = `<option value="">(Ekip seç)</option>` + opts.map(o=>`<option value="${o.id}">${escapeHtml(o.name)}</option>`).join("");
  if(keep && opts.some(o=>o.id===keep)) sel.value=keep;
  syncTeamSelectDataset(sel);
}
async function refreshTeamSelect(){
  const week=_byId("mapWeek")?.value;
  if(!week) return;
  try{
    const res = await fetch(`/api/routes_all?week_start=${encodeURIComponent(week)}`);
    const data = await res.json();
    if(data.ok) setTeamSelectOptions(data.routes||[]);
  }catch(e){}
}
async function loadMap(){
  ensureMap();
  _layer.clearLayers();

  refreshTeamSelect();

  const week=_byId("mapWeek")?.value;
  if(!week) return;

  const res = await fetch(`/api/map_markers?date=${encodeURIComponent(week)}`);
  const data = await res.json().catch(()=>({markers:[]}));

  const bounds=[];
  (data.markers||[]).forEach(m=>{
    if(m.lat==null || m.lon==null) return;
    const p=[m.lat, m.lon];
    bounds.push(p);

    const projText=(m.projects||[]).map(x=>`${escapeHtml(x.code)} (${escapeHtml(x.responsible)})`).join("<br>");
    L.marker(p).addTo(_layer).bindPopup(`
      <div style="min-width:260px">
        <div><strong></strong> </div>
        <hr>
        <div>${projText || "-"}</div>
      </div>
    `);
  });

  if(bounds.length) _map.fitBounds(bounds, { padding:[30,30] });
}
async function drawAllRoutes(){
  ensureMap();
  _layer.clearLayers();

  const week=_byId("mapWeek")?.value;
  if(!week) return;

  setMapButtonsDisabled(true, "Yükleniyor...");
  const res = await fetch(`/api/routes_all?week_start=${encodeURIComponent(week)}`);
  const data = await res.json().catch(()=>({ok:false}));
  if(!data.ok){ alert("Rotalar alınamadı"); setMapButtonsDisabled(false); return; }

  const allPts=[];
  let totalKm = 0;
  const stats = [];
  for(const r of (data.routes||[])){
    const teamName=r.team_name || `Ekip #${r.team_id}`;
    const ptsObj=(r.points||[]).filter(p=>p.lat!=null && p.lon!=null);
    const pts=ptsObj.map(p=>[p.lat,p.lon]);
    pts.forEach(x=>allPts.push(x));
    const statsRes = await computeRouteStats(ptsObj);
    stats.push({ name: teamName, km: statsRes.totalKm, hours: statsRes.totalHours, stops: pts.length, cities: statsRes.cities });
    totalKm += statsRes.totalKm;
    if(pts.length>=2) L.polyline(pts, { color:r.color, weight:4, opacity:0.9 }).addTo(_layer);

    if((r.points||[]).length){
      const p0=r.points[0];
      if(p0?.lat!=null && p0?.lon!=null){
        const icon = L.divIcon({ className:"teamLabelWrap", html:teamLabelHtml(teamName, r.color), iconSize:null });
        L.marker([p0.lat,p0.lon], { icon }).addTo(_layer);
      }
    }

    (r.points||[]).forEach(p=>{
      if(p.lat==null || p.lon==null) return;
      L.circleMarker([p.lat,p.lon], { radius:5, color:r.color, weight:2 })
        .addTo(_layer)
        .bindPopup(`${escapeHtml(teamName)}<br><b>${escapeHtml(p.city)}</b><br>${escapeHtml(p.date)}<br>${escapeHtml(p.project_code)}`);
    });
  }

  setTeamSelectOptions(data.routes||[]);
  if(allPts.length) _map.fitBounds(allPts, { padding:[30,30] });
  updateAllStats(totalKm, (data.routes||[]).length || 0);
  LAST_ROUTE_STATS = stats;
  renderRouteList(stats);
  updateRouteStats("Seçili ekip", 0, 0, 0);
  renderSegments([], false);
  setMapButtonsDisabled(false);
}

async function drawSingleTeamRoute(){
  ensureMap();
  _layer.clearLayers();

  const week=_byId("mapWeek")?.value;
  const teamId=_byId("singleTeamSelect")?.value;
  if(!week) return;
  if(!teamId) return alert("Ekip seç");
  setMapButtonsDisabled(true, "Yükleniyor...");

  const res = await fetch(`/api/routes_team?week_start=${encodeURIComponent(week)}&team_id=${encodeURIComponent(teamId)}`);
  const data = await res.json().catch(()=>({ok:false}));
  if(!data.ok){ alert("Rota yok"); setMapButtonsDisabled(false); return; }

  const route = data.route || data;
  const color=route.color || "#e5484d";
  const teamName=route.team_name || `Ekip #${teamId}`;
  const ptsObj=(route.points||[]).filter(p=>p.lat!=null && p.lon!=null);
  const pts=ptsObj.map(p=>[p.lat,p.lon]);
  const stats = await computeRouteStats(ptsObj);

  LAST_DRAWN_ROUTE = { teamName, points: (route.points||[]) };

  if(pts.length>=2) L.polyline(pts, { color, weight:5, opacity:0.95 }).addTo(_layer);

  if((route.points||[]).length){
    const p0=route.points[0];
    if(p0?.lat!=null && p0?.lon!=null){
      const icon = L.divIcon({ className:"teamLabelWrap", html:teamLabelHtml(teamName, color), iconSize:null });
      L.marker([p0.lat,p0.lon], { icon }).addTo(_layer);
    }
  }

  (route.points||[]).forEach(p=>{
    if(p.lat==null || p.lon==null) return;
    L.circleMarker([p.lat,p.lon], { radius:6, color, weight:2 })
      .addTo(_layer)
      .bindPopup(`${escapeHtml(teamName)}<br><b>${escapeHtml(p.city)}</b><br>${escapeHtml(p.date)}<br>${escapeHtml(p.project_code)}`);
  });

  if(pts.length) _map.fitBounds(pts, { padding:[30,30] });

  updateRouteStats(teamName, stats.totalKm, stats.totalHours, pts.length);
  renderSegments(stats.segments, true);
  setMapButtonsDisabled(false);
}

async function computeRealRouteDuration(){
  if(!LAST_DRAWN_ROUTE || !LAST_DRAWN_ROUTE.points || LAST_DRAWN_ROUTE.points.length < 2){
    alert("Önce bir ekibi seçip rotasını çizin.");
    return;
  }
  const pts = LAST_DRAWN_ROUTE.points.filter(p=>p.lat!=null && p.lon!=null);
  if(pts.length < 2){ alert("Rota noktası yok."); return; }
  setMapButtonsDisabled(true, "Gerçek rota...");

  let totalKm = 0;
  let totalHours = 0;
  const segments = [];

  for(let i=1;i<pts.length;i++){
    const a = pts[i-1];
    const b = pts[i];
    let km = haversineKm([a.lat, a.lon],[b.lat, b.lon]);
    let hours = km / 60;
    try{
      const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=false&alternatives=false`;
      const res = await fetch(url);
      const js = await res.json();
      if(js && js.routes && js.routes[0]){
        km = (js.routes[0].distance || 0) / 1000;
        hours = (js.routes[0].duration || 0) / 3600;
      }
    }catch(e){ /* fallback to haversine */ }
    totalKm += km;
    totalHours += hours;
    const fromTitle = `${a.city || ''} ${a.project_code  ? '('+a.project_code+')' : ''}`.trim() || 'Nokta';
    const toTitle = `${b.city || ''} ${b.project_code  ? '('+b.project_code+')' : ''}`.trim() || 'Nokta';
    segments.push({ from: fromTitle, to: toTitle, km, hours });
    await new Promise(r=>setTimeout(r,150));
  }

  updateRouteStats(LAST_DRAWN_ROUTE.teamName, totalKm, totalHours, pts.length);
  renderSegments(segments, true);
  setMapButtonsDisabled(false);
}

// =================== MAIL ===================
async function sendWeeklyEmails(weekStart, statusElementId){
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  if(!week){
    alert("Hafta bulunamadı.");
    return;
  }
  const el = statusElementId  ? _byId(statusElementId) : (_byId("mailStatus") || _byId("mailStatusAll"));
  if(el) el.textContent="Gönderiliyor...";

  const res = await fetch("/api/send_weekly_emails", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ week_start: week })
  });
  const data = await res.json().catch(()=>({sent:0,skipped:0,errors:["json parse"]}));

  if(!res.ok || !data.ok){
    alert(data.error || "Mail gönderilemedi");
  }
  if(el){
    let msg = `Gönderildi: ${data.sent}, Atlandı: ${data.skipped}`;
    if(data.errors && data.errors.length) msg += ` | Hatalar: ${data.errors.join(" / ")}`;
    el.textContent = msg;
  }
}

async function sendTeamEmails(weekStart, teamName, statusElementId){
  const week = weekStart || _byId("weekStartHidden")?.value || currentWeekStart || "";
  const teamSel = _byId("teamSelect");
  const team = teamName || (teamSel  ? teamSel.value : "");
  if(!week){ alert("Hafta bulunamadı."); return; }
  if(!team){ alert("Ekip seçin."); return; }
  const el = statusElementId  ? _byId(statusElementId) : (_byId("mailStatusTeam"));
  if(el) el.textContent="Gönderiliyor...";

  const res = await fetch("/api/send_team_emails", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ week_start: week, team_name: team })
  });
  const data = await res.json().catch(()=>({sent:0,skipped:0,errors:["json parse"]}));
  if(!res.ok || !data.ok){
    alert(data.error || "Mail gönderilemedi");
  }
  if(el){
    let msg = `Gönderildi: ${data.sent}, Atlandı: ${data.skipped}`;
    if(data.errors && data.errors.length) msg += ` | Hatalar: ${data.errors.join(" / ")}`;
    el.textContent = msg;
  }
}

// =================== JOB ROW (İş Ekle / Düzenle / Sil) ===================
function _tplById(id){ return (window.TEMPLATE_PROJECTS || []).find(x => String(x.id) === String(id)); }

function _showTopButtons(){
  const bSave = _byId("topJobSave");
  const bCancel = _byId("topJobCancel");
  const bEdit = _byId("topJobEdit");
  const bDel = _byId("topJobDelete");

  const showSaveCancel = (__newRowActive || __editMode);
  if(bSave) bSave.style.display = showSaveCancel  ? "inline-flex" : "none";
  if(bCancel) bCancel.style.display = showSaveCancel  ? "inline-flex" : "none";
  if(bEdit) bEdit.style.display = (!__newRowActive && !__editMode && __selectedProjectId)  ? "inline-flex" : "none";
  if(bDel) bDel.style.display = (!__newRowActive && !__editMode && __selectedProjectId)  ? "inline-flex" : "none";
}

function _clearRowHighlights(){
  document.querySelectorAll("tr.planRow.selectedRow").forEach(tr => tr.classList.remove("selectedRow"));
}

function _selectRow(projectId){
  __selectedProjectId = parseInt(projectId || 0,10);
  _clearRowHighlights();
  const tr = document.querySelector(`tr.planRow[data-project-id='${__selectedProjectId}']`);
  if(tr) tr.classList.add("selectedRow");

  const lbl = _byId("selectedLabel");
  if(lbl){
    const city = tr  ? (tr.querySelector(".region")?.textContent || "") : "";
    const pcode = tr  ? (tr.querySelector(".pcode")?.textContent || "") : "";
    lbl.textContent = __selectedProjectId  ? `${city} - ${pcode}` : "-";
  }
  _showTopButtons();
}

// Bugünün tarih sütununu vurgula
function highlightTodayColumn(){
  const todayIso = window.TODAY_ISO;
  if(!todayIso) {
    // Eğer window.TODAY_ISO yoksa, script tag'inden al
    const appDataScript = document.getElementById('app-data');
    if(appDataScript) {
      window.TODAY_ISO = appDataScript.getAttribute('data-today') || '';
    }
  }
  
  const today = window.TODAY_ISO || '';
  if(!today) return;
  
  // Tüm bugünün tarihine sahip hücreleri vurgula
  document.querySelectorAll(`td.cell[data-date="${today}"]`).forEach(cell => {
    cell.classList.add("selectedDateColumn");
  });
  
  // Header'daki bugünün th'ini de vurgula
  document.querySelectorAll(`th[data-date="${today}"]`).forEach(th => {
    th.classList.add("selectedDateColumn");
  });
}

function selectRowByProjectId(projectId){
  if(__newRowActive || __editMode) return;
  _selectRow(projectId);
}

function initRowSelection(){
  document.querySelectorAll("tr.planRow").forEach(tr=>{
    tr.addEventListener("click", (e)=>{
      if(__newRowActive || __editMode) return;
      const inSticky = e.target && e.target.closest && e.target.closest("td.st");
      if(!inSticky) return;
      const pid = tr.getAttribute("data-project-id") || "0";
      _selectRow(pid);
    });
  });
}

function addBlankJobRow(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if(__newRowActive || __editMode) return;
  ensureAppData();

  const tbody = _byId("planTbody");
  if(!tbody) return;

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
  if(cities.length === 0) {
    console.warn('CITIES is empty! window.CITIES:', window.CITIES);
  }
  citySel.innerHTML = `<option value="">-- Il sec --</option>` +
    cities.map(c => `<option value="${escapeHtml(String(c))}">${escapeHtml(String(c))}</option>`).join("");
  tdCity.appendChild(citySel);

  // Proje
  const tdProj = document.createElement("td");
  tdProj.className = "st st2 proj";
  const projSel = document.createElement("select");
  projSel.id = "newJobTemplate";
  const templates = window.TEMPLATE_PROJECTS || [];
  console.log('addBlankJobRow - TEMPLATE_PROJECTS:', templates);
  if(templates.length === 0) {
    console.warn('TEMPLATE_PROJECTS is empty! window.TEMPLATE_PROJECTS:', window.TEMPLATE_PROJECTS);
  }
  projSel.innerHTML = `<option value="0">-- Proje sec --</option>` +
    templates.map(p => `<option value="${p.id}">${escapeHtml(p.project_code)} - ${escapeHtml(p.project_name)} (${escapeHtml(p.responsible||"")})</option>`).join("");

  const meta = document.createElement("div");
  meta.className="muted";
  meta.style.marginTop="4px";
  meta.id="newJobProjMeta";
  
  // Alt Proje dropdown'ı - Proje dropdown'ının altına
  const subProjSel = document.createElement("select");
  subProjSel.id = "newJobSubProject";
  subProjSel.innerHTML = `<option value="">-- Alt proje seç --</option>`;
  subProjSel.style.cssText = "width: 100%; padding: 6px 10px; border-radius: 4px; border: 1px solid #cbd5e1; font-size: 13px; background: #ffffff; margin-top: 6px;";
  
  tdProj.appendChild(projSel);
  tdProj.appendChild(meta);
  tdProj.appendChild(subProjSel);

  // Sorumlu
  const tdResp = document.createElement("td");
  tdResp.className="st st3 resp";
  tdResp.id="newJobResp";
  tdResp.textContent="-";

  // Günler placeholder
  const dayCount = document.querySelectorAll("table.plan thead th.daycol").length || 7;
  const dayTds=[];
  for(let i=0;i<dayCount;i++){
    const td=document.createElement("td");
    td.className="cell daycol";
    td.innerHTML = `<span class="muted">Kaydedince aktif olur</span>`;
    dayTds.push(td);
  }

  // Araç
  const tdVeh = document.createElement("td");
  tdVeh.className="vehcol";
  tdVeh.innerHTML = `<div class="hint" id="newJobHint"></div>`;

  tr.appendChild(tdCity);
  tr.appendChild(tdProj);
  tr.appendChild(tdResp);
  dayTds.forEach(x=>tr.appendChild(x));
  tr.appendChild(tdVeh);
  tbody.prepend(tr);

  projSel.addEventListener("change", async ()=>{
    const t = _tplById(projSel.value);
    if(!t){ 
      tdResp.textContent="-"; 
      meta.textContent=""; 
      subProjSel.innerHTML = '<option value="">-- Alt proje seç --</option>';
      return; 
    }
    tdResp.textContent = t.responsible || "-";
    meta.textContent = `${t.project_code} - ${t.project_name}`;
    
    // Alt projeleri yükle
    try {
      const res = await fetch(`/api/project_codes_by_template?template_id=${projSel.value}`);
      const data = await res.json().catch(() => ({}));
      if(data.ok && data.codes && data.codes.length > 0){
        subProjSel.innerHTML = '<option value="">-- Alt proje seç --</option>' +
          data.codes.map(c => `<option value="${c.project_code}" data-region="${c.region}" data-name="${c.project_name}">${c.project_code} - ${c.region} (${c.project_name})</option>`).join("");
      } else {
        subProjSel.innerHTML = '<option value="">Alt proje bulunamadı</option>';
      }
    } catch(e) {
      console.error("Alt proje kodları getirilemedi:", e);
      subProjSel.innerHTML = '<option value="">-- Alt proje seç --</option>';
    }
  });

  __newRowActive = true;
  _selectRow(0);
  _showTopButtons();
}

function cancelNewJobRow(){
  const tr = _byId("newJobRow");
  if(tr){
    tr.remove();
    __newRowActive = false;
    __editMode = false;
    _showTopButtons();
    return;
  }
  if(__editMode){
    location.reload();
    return;
  }
  _showTopButtons();
}

async function _saveNewJobRow(){
  const city = (_byId("newJobCity")?.value || "").trim();
  const template_project_id = parseInt(_byId("newJobTemplate")?.value || "0",10);
  const hint = _byId("newJobHint");
  if(!city){ if(hint) hint.textContent="İl seçin."; return; }
  if(!template_project_id){ if(hint) hint.textContent="Proje se???çin."; return; }
  if(hint) hint.textContent="Kaydediliyor...";

  // Seçili hafta bilgisini al (date input'tan - kullanıcının seçtiği hafta)
  const weekStartInput = _byId("weekStartInput") || document.querySelector('input[name="date"]');
  let weekStart = '';
  
  if(weekStartInput && weekStartInput.value){
    // Date input'tan seçilen tarihi al ve hafta başlangıcını hesapla
    const selectedDate = new Date(weekStartInput.value);
    const weekStartDate = getWeekStart(selectedDate);
    weekStart = formatDateISO(weekStartDate);
  } else {
    // Fallback: hidden input'tan al (eski davranış)
    const weekStartHidden = _byId("weekStartHidden");
    weekStart = weekStartHidden ? weekStartHidden.value : '';
  }
  
  if(!weekStart){
    if(hint) hint.textContent="Hafta bilgisi bulunamadı.";
    return;
  }

  const res = await fetch("/api/project_create_from_plan", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ city, template_project_id, week_start: weekStart })
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok){ if(hint) hint.textContent = data.error || "Kaydedilemedi"; return; }
  location.reload();
}

function editSelectedJobRow(){
  if(!__selectedProjectId || __newRowActive || __editMode) return;
  ensureAppData();
  const tr = document.querySelector(`tr.planRow[data-project-id='${__selectedProjectId}']`);
  if(!tr) return;

  const tdCity = tr.querySelector("td.region");
  const tdProj = tr.querySelector("td.proj");
  const tdResp = tr.querySelector("td.resp");
  const curCity = (tdCity?.textContent || "").trim();
  const curCode = (tdProj?.querySelector(".pcode")?.textContent || "").trim();

  // city select
  const citySel = document.createElement("select");
  citySel.id = "editJobCity";
  const cities = window.CITIES || [];
  citySel.innerHTML = `<option value="">-- Il sec --</option>` +
    cities.map(c => `<option value="${escapeHtml(String(c))}">${escapeHtml(String(c))}</option>`).join("");
  citySel.value = curCity;
  tdCity.innerHTML = "";
  tdCity.appendChild(citySel);

  // project select
  const projSel = document.createElement("select");
  projSel.id="editJobTemplate";
  projSel.innerHTML = `<option value="0">-- Proje sec --</option>` +
    (window.TEMPLATE_PROJECTS || []).map(p => `<option value="${p.id}">${escapeHtml(p.project_code)} - ${escapeHtml(p.project_name)} (${escapeHtml(p.responsible||"")})</option>`).join("");
  if(curTpl) projSel.value=String(curTpl.id);
  tdProj.innerHTML="";
  tdProj.appendChild(projSel);

  const meta=document.createElement("div");
  meta.className="muted";
  meta.style.marginTop="4px";
  meta.id="editJobProjMeta";
  tdProj.appendChild(meta);

  function syncResp(){
    const t=_tplById(projSel.value);
    tdResp.textContent = (t?.responsible) || "-";
    meta.textContent = t  ? `${t.project_code} - ${t.project_name}` : "";
  }
  projSel.addEventListener("change", syncResp);
  syncResp();

  __editMode = true;
  _showTopButtons();
}

async function _saveEditJobRow(){
  if(!__selectedProjectId) return;
  const city = (_byId("editJobCity")?.value || "").trim();
  const template_project_id = parseInt(_byId("editJobTemplate")?.value || "0",10);
  if(!city || !template_project_id){ alert("İl ve Proje se???çin."); return; }

  const res = await fetch("/api/plan_row_update", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ project_id: __selectedProjectId, city, template_project_id })
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok){ alert(data.error || "Güncellenemedi"); return; }
  location.reload();
}

async function deleteSelectedJobRow(){
  if(IS_OBSERVER){
    alert("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.");
    return;
  }
  if(__newRowActive || __editMode) return;
  if(!__selectedProjectId || __selectedProjectId <= 0) return;
  if(!confirm("Bu satır silinsin mi ? (Tüm hafta kayıtları silinir)")) return;

  const res = await fetch("/api/plan_row_delete", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ project_id: __selectedProjectId })
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok){ alert(data.error || "Silinemedi"); return; }
  location.reload();
}

function saveNewOrEdit(){
  if(__newRowActive) return _saveNewJobRow();
  if(__editMode) return _saveEditJobRow();
}

// plan.html'de varsa modal kapatma
function closeAddJobModal(){
  const m = _byId("addJobModal");
  if(m) m.style.display = "none";
  
  // Form alanlarını temizle
  const citySel = _byId("jobCity");
  const templateSel = _byId("jobTemplateSelect");
  const subProjectSel = _byId("jobSubProjectSelect");
  const codeInput = _byId("jobProjectCode");
  const nameInput = _byId("jobProjectName");
  const respInput = _byId("jobResponsible");
  
  if(citySel) citySel.value = "";
  if(templateSel) templateSel.value = "0";
  if(subProjectSel) subProjectSel.innerHTML = '<option value="">-- Alt proje seç --</option>';
  if(codeInput) codeInput.value = "";
  if(nameInput) nameInput.value = "";
  if(respInput) respInput.value = "";
}

// İ ş Ekle modal'i iş in template'ten doldur
async function fillFromTemplate(){
  const sel = _byId("jobTemplateSelect");
  if(!sel) return;
  const tplId = parseInt(sel.value || "0", 10);
  const subProjectSelect = _byId("jobSubProjectSelect");
  const codeInput = _byId("jobProjectCode");
  const nameInput = _byId("jobProjectName");
  const respInput = _byId("jobResponsible");
  
  // Eğer proje seçilmediyse, alt proje dropdown'ını temizle
  if(!tplId) {
    if(subProjectSelect) subProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>';
    if(codeInput) codeInput.value = "";
    if(nameInput) nameInput.value = "";
    if(respInput) respInput.value = "";
    return;
  }
  
  const tpl = _tplById(tplId);
  if(!tpl) return;
  
  // Temel proje bilgilerini doldur
  if(codeInput) codeInput.value = tpl.project_code || "";
  if(nameInput) nameInput.value = tpl.project_name || "";
  if(respInput) respInput.value = tpl.responsible || "";
  
  // Alt proje kodlarını getir ve dropdown'ı doldur
  if(subProjectSelect) {
    subProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>';
  }
  
  try {
    const res = await fetch(`/api/project_codes_by_template?template_id=${tplId}`);
    const data = await res.json().catch(() => ({}));
    const currentSubProjectSelect = _byId("jobSubProjectSelect");
    if(data.ok && data.codes && data.codes.length > 0 && currentSubProjectSelect){
      // Önceki event listener'ları kaldırmak için elementi yeniden oluştur
      const oldSelect = currentSubProjectSelect;
      const newSelect = oldSelect.cloneNode(false);
      oldSelect.parentNode.replaceChild(newSelect, oldSelect);
      
      // Alt proje dropdown'ını doldur
      newSelect.innerHTML = '<option value="">-- Alt proje seç --</option>' +
        data.codes.map(c => `<option value="${c.project_code}" data-region="${c.region}" data-name="${c.project_name}">${c.project_code} - ${c.region} (${c.project_name})</option>`).join("");
      
      // Alt proje seçildiğinde proje kodu ve adını güncelle
      newSelect.addEventListener("change", function(e){
        const selectedOption = this.options[this.selectedIndex];
        const currentCodeInput = _byId("jobProjectCode");
        const currentNameInput = _byId("jobProjectName");
        
        console.log("Alt proje seçildi:", selectedOption ? selectedOption.value : "boş");
        
        if(selectedOption && selectedOption.value && currentCodeInput && currentNameInput){
          currentCodeInput.value = selectedOption.value;
          if(selectedOption.dataset.name){
            currentNameInput.value = selectedOption.dataset.name;
          }
          console.log("Proje kodu güncellendi:", selectedOption.value, "Proje adı:", selectedOption.dataset.name);
        } else if(!selectedOption || !selectedOption.value) {
          // Eğer seçim kaldırıldıysa, temel proje bilgilerine geri dön
          const currentTpl = _tplById(tplId);
          if(currentCodeInput && currentTpl) {
            currentCodeInput.value = currentTpl.project_code || "";
          }
          if(currentNameInput && currentTpl) {
            currentNameInput.value = currentTpl.project_name || "";
          }
          console.log("Temel proje bilgilerine geri dönüldü");
        }
      });
    } else if(currentSubProjectSelect) {
      currentSubProjectSelect.innerHTML = '<option value="">Alt proje bulunamadı</option>';
    }
  } catch(e) {
    console.error("Alt proje kodları getirilemedi:", e);
    const currentSubProjectSelect = _byId("jobSubProjectSelect");
    if(currentSubProjectSelect) currentSubProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>';
  }
}

async function loadSubProjects(projectCode){
  const subProjectSelect = _byId("mSubProject");
  if(!subProjectSelect || !projectCode) {
    if(subProjectSelect) subProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>';
    return;
  }
  
  try {
    const res = await fetch(`/api/project_codes_by_code?project_code=${encodeURIComponent(projectCode)}`);
    const data = await res.json().catch(() => ({}));
    if(data.ok && data.codes && data.codes.length > 0){
      subProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>' +
        data.codes.map(c => `<option value="${c.project_id}">${c.project_code} - ${c.region} (${c.project_name})</option>`).join("");
    } else {
      subProjectSelect.innerHTML = '<option value="">Alt proje bulunamadı</option>';
    }
  } catch(e) {
    console.error("Alt proje kodları getirilemedi:", e);
    if(subProjectSelect) subProjectSelect.innerHTML = '<option value="">-- Alt proje seç --</option>';
  }
}

// İ ş Ekle modal'ı ndan yeni satir olustur
async function createJobRow(){
  const city = (_byId("jobCity")?.value || "").trim();
  const templateId = parseInt(_byId("jobTemplateSelect")?.value || "0", 10);
  const projectCodeEl = _byId("jobProjectCode");
  const projectCode = (projectCodeEl?.value || projectCodeEl?.textContent || "").trim();
  const projectName = (_byId("jobProjectName")?.value || "").trim();
  const responsible = (_byId("jobResponsible")?.value || "").trim();
  
  if(!city){
    alert("İl seçin.");
    return;
  }
  if(!templateId && (!projectCode || !projectName || !responsible)){
    alert("Proje şablonu seçin veya proje bilgilerini girin.");
    return;
  }
  
  // Seçili hafta bilgisini al (date input'tan - kullanıcının seçtiği hafta)
  const weekStartInput = _byId("weekStartInput") || document.querySelector('input[name="date"]');
  let weekStart = '';
  
  if(weekStartInput && weekStartInput.value){
    // Date input'tan seçilen tarihi al ve hafta başlangıcını hesapla
    const selectedDate = new Date(weekStartInput.value);
    const weekStartDate = getWeekStart(selectedDate);
    weekStart = formatDateISO(weekStartDate);
  } else {
    // Fallback: hidden input'tan al (eski davranış)
    const weekStartHidden = _byId("weekStartHidden");
    weekStart = weekStartHidden ? weekStartHidden.value : '';
  }
  
  if(!weekStart){
    alert("Hafta bilgisi bulunamadı. Lütfen sayfayı yenileyin.");
    return;
  }
  
  const res = await fetch("/api/project_create_from_plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      city: city,
      template_project_id: templateId || 0,
      project_code: projectCode,
      project_name: projectName,
      responsible: responsible,
      week_start: weekStart
    })
  });
  
  const data = await res.json().catch(() => ({}));
  if(!res.ok || !data.ok){
    alert(data.error || "Kaydedilemedi");
    return;
  }
  
  closeAddJobModal();
  location.reload();
}

// =================== RIGHT PANEL (drawer/pin) ===================
function _applyPanelState(){
  // Panel tamamen kaldırıldı - hiçbir şey yapma
  const panel = _byId("rightPanel");
  const floatBtn = _byId("floatingPanelBtn");
  const pinBtn = _byId("panelPinBtn");
  const notch = _byId("panelNotch");
  if(panel) panel.style.display = "none";
  if(floatBtn) floatBtn.style.display = "none";
  if(notch) notch.style.display = "none";
  return;
}
function panelHoverOpen(){
  // Panel kaldırıldı - devre dışı
  return;
}
function panelHoverCloseSoon(){
  // Panel kaldırıldı - devre dışı
  return;
}
function panelHoverCancelClose(){
  // Panel kaldırıldı - devre dışı
  return;
}
function toggleRightPanel(){
  // Panel kaldırıldı - devre dışı
  return;
}
function togglePanelPin(){
  // Panel kaldırıldı - devre dışı
  return;
}

// =================== INIT ===================
window.addEventListener("load", ()=>{
  if(localStorage.getItem("fit-week")==="1") document.body.classList.add("fit-week");
  renderPeopleList();

  const availSel=_byId("availDate");
  if(availSel){
    availSel.addEventListener("change", ()=>{
      const d=availSel.value;
      refreshPersonStatusForDate(d).then(()=>{
        renderPeopleList();
        loadAvailability();
      });
    });
  }

  const shiftSel=_byId("mShift");
  if(shiftSel) shiftSel.addEventListener("change", ()=>loadAvailability());

  if(_byId("availDate")) loadAvailability();

  if(_byId("map")){
    loadMap();
    const mw=_byId("mapWeek");
    if(mw) mw.addEventListener("change", ()=>refreshTeamSelect());
  }
});

document.addEventListener("DOMContentLoaded", ()=>{
  initRowSelection();
  // Bugünün tarih sütununu turuncu yap
  highlightTodayColumn();
  _showTopButtons();
  try{ _bindDragPaste(); }catch(e){}
  
  // Apply background colors from data-bg-color attributes
  document.querySelectorAll('.plan td.proj[data-bg-color]').forEach(function(td) {
    var bgColor = td.getAttribute('data-bg-color');
    if (bgColor) {
      td.style.backgroundColor = bgColor;
    }
  });

  // Panel tamamen kaldırıldı - DOM'dan sil
  const panel=_byId("rightPanel");
  if(panel){
    panel.style.display = "none";
    panel.style.visibility = "hidden";
    try{ panel.remove(); }catch(e){}
  }
  const floatBtn = _byId("floatingPanelBtn");
  if(floatBtn){
    floatBtn.style.display = "none";
    try{ floatBtn.remove(); }catch(e){}
  }
  const notch = _byId("panelNotch");
  if(notch){
    notch.style.display = "none";
    try{ notch.remove(); }catch(e){}
  }
  
  // Personel combobox'ı başlat
  if(_byId("peopleSearch")){
    renderPeopleComboBox();
    renderSelectedPeople();
  }
});

function togglePersonnelSummary(){
  const content = _byId("personnelSummaryContent");
  const toggle = _byId("personnelSummaryToggle");
  if(!content || !toggle) return;
  
  const isVisible = content.style.display !== "none";
  if(isVisible){
    content.style.display = "none";
    toggle.textContent = "▶";
  }else{
    content.style.display = "flex";
    toggle.textContent = "▼";
  }
}

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
window.togglePersonnelSummary = togglePersonnelSummary;

window.copyCurrentAsTemplate = copyCurrentAsTemplate;
window.togglePasteMode = togglePasteMode;

window.renderPeopleList = renderPeopleList;
window.renderPeopleComboBox = renderPeopleComboBox;
window.filterPeopleComboBox = filterPeopleComboBox;
window.showPeopleDropdown = showPeopleDropdown;
window.renderSelectedPeople = renderSelectedPeople;
window.updateFieldColors = updateFieldColors;
window.selectRowByProjectId = selectRowByProjectId;

// =================== REAL-TIME SYNC ===================
let lastSyncTimestamp = null;
let syncInterval = null;
let isSyncing = false;

async function checkForUpdates(){
  if(isSyncing) return;
  if(!currentWeekStart) return;
  
  // Eğer modal açıksa veya kullanıcı işlem yapıyorsa, güncelleme yapma
  if(document.querySelector("#cellModal.open")){
    return;
  }
  
  isSyncing = true;
  try {
    const res = await fetch(`/api/plan_sync?date=${encodeURIComponent(currentWeekStart)}`);
    const data = await res.json().catch(()=>({ok: false}));
    
    if(data.ok){
      const currentTimestamp = data.last_update;
      
      // İlk kontrol - sadece timestamp'i kaydet
      if(lastSyncTimestamp === null){
        lastSyncTimestamp = currentTimestamp;
        isSyncing = false;
        return;
      }
      
      // Değişiklik var mı kontrol et
      if(currentTimestamp && currentTimestamp !== lastSyncTimestamp){
        // Sayfayı yenile (sessizce, kullanıcıyı rahatsız etmeden)
        console.log("Değişiklik tespit edildi, sayfa güncelleniyor...");
        lastSyncTimestamp = currentTimestamp;
        
        // Önce tüm araç sütunlarını güncelle ve bekle
        const allRows = document.querySelectorAll("tr.planRow");
        const updatePromises = [];
        for(const row of allRows){
          const projectId = parseInt(row.dataset.projectId || row.getAttribute("data-project-id") || "0", 10);
          if(projectId) {
            updatePromises.push(new Promise(resolve => {
              updateVehicleColumn(projectId);
              // Her güncelleme için kısa bir gecikme
              setTimeout(resolve, 150);
            }));
          }
        }
        
        // Tüm araç sütunları güncellendikten sonra sayfayı yenile
        Promise.all(updatePromises).then(() => {
          // Modal hala açık değilse sayfayı yenile
          setTimeout(() => {
            if(!document.querySelector("#cellModal.open")){
              location.reload();
            }
          }, 500);
        }).catch(e => {
          console.error("Araç sütunu güncelleme hatası:", e);
          // Hata olsa bile sayfayı yenile
          setTimeout(() => {
            if(!document.querySelector("#cellModal.open")){
              location.reload();
            }
          }, 1000);
        });
      } else {
        // Değişiklik yoksa, sadece araç sütunlarını güncelle (sayfa yenilemeden)
        const allRows = document.querySelectorAll("tr.planRow");
        for(const row of allRows){
          const projectId = parseInt(row.dataset.projectId || row.getAttribute("data-project-id") || "0", 10);
          if(projectId) {
            // Asenkron olarak güncelle, sayfa yenileme
            setTimeout(() => updateVehicleColumn(projectId), 0);
          }
        }
      }
      
      lastSyncTimestamp = currentTimestamp;
    }
  } catch(e) {
    console.error("Sync hatası:", e);
  } finally {
    isSyncing = false;
  }
}

function startSync(){
  if(syncInterval) clearInterval(syncInterval);
  // Haftanın assignments'larını yükle
  loadAssignmentsForWeek();
  // Her 3 saniyede bir kontrol et
  syncInterval = setInterval(checkForUpdates, 3000);
  console.log("Eş zamanlı güncelleme başlatıldı");
}

function stopSync(){
  if(syncInterval){
    clearInterval(syncInterval);
    syncInterval = null;
  }
}

async function loadAssignmentsForWeek(){
  try{
    if(!currentWeekStart) return;
    const res = await fetch(`/api/assignments_week?week_start=${encodeURIComponent(currentWeekStart)}`);
    
    // Content-Type kontrolü yap
    const contentType = res.headers.get("content-type");
    if(!contentType || !contentType.includes("application/json")){
      console.warn("Assignments: JSON olmayan yanıt alındı, atlanıyor");
      return;
    }
    
    if(!res.ok){
      console.warn(`Assignments: HTTP ${res.status} hatası`);
      return;
    }
    
    const data = await res.json().catch(e => {
      console.error("Assignments JSON parse hatası:", e);
      return null;
    });
    
    if(data && data.ok){
      window.ALL_ASSIGNMENTS = data.assignments || {};
    }
  }catch(e){
    console.error("Assignments yüklenemedi:", e);
  }
}

// Hafta başlangıcını ayarla (global fonksiyon)
function setCurrentWeekStart(dateStr){
  if(dateStr){
    currentWeekStart = dateStr;
  } else {
    // URL'den veya input'tan al
    const weekInput = document.querySelector('#weekStartInput') || document.querySelector('input[name="date"]');
    if(weekInput && weekInput.value){
      currentWeekStart = weekInput.value;
    } else {
      const urlParams = new URLSearchParams(window.location.search);
      const dateParam = urlParams.get('date');
      if(dateParam){
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

function getWeekStart(d){
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0  ? -6 : 1); // Pazartesi
  return new Date(date.setDate(diff));
}

function formatDateISO(d){
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Sayfa yuklenince sync baslat
function initSync(){
  const weekInput = document.querySelector('#weekStartInput') || document.querySelector('input[name="date"]');
  if(weekInput && weekInput.value){
    setCurrentWeekStart(weekInput.value);
  } else {
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    if(dateParam){
      setCurrentWeekStart(dateParam);
    } else {
      setCurrentWeekStart(); // bugunun haftasi
    }
  }
  startSync();
}

if(document.readyState === "loading"){
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

window.openTeamModal = openTeamModal;
window.closeTeamModal = closeTeamModal;
window.copyTeamReportTSV = copyTeamReportTSV;
window.copyTeamReportText = copyTeamReportText;

window.openPersonShot = openPersonShot;
window.closePersonShot = closePersonShot;
window.loadPersonShot = loadPersonShot;

window.loadMap = loadMap;
window.drawAllRoutes = drawAllRoutes;
window.drawSingleTeamRoute = drawSingleTeamRoute;
window.ensureMap = ensureMap;
window.computeRealRouteDuration = computeRealRouteDuration;
window.toggleRouteCities = toggleRouteCities;

window.addBlankJobRow = addBlankJobRow;
window.cancelNewJobRow = cancelNewJobRow;
// Wrapper: formdaki Ekle butonu için
function saveNewJobRow(){
  return typeof _saveNewJobRow === "function" ? _saveNewJobRow() : (typeof saveNewOrEdit === "function" ? saveNewOrEdit() : null);
}
window.saveNewJobRow = saveNewJobRow;
window.editSelectedJobRow = editSelectedJobRow;
window.deleteSelectedJobRow = deleteSelectedJobRow;
window.closeAddJobModal = closeAddJobModal;






