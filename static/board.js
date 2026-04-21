(() => {
  const root = document.getElementById('boardRoot');
  if (!root) return;

  const els = (id) => document.getElementById(id);
  const csrfToken =
    ((els('csrfTokenGlobal') || {}).value || '') ||
    ((els('csrfTokenBoard') || {}).value || '');

  const apiJobs = root.dataset.apiJobs || '/api/board/jobs';
  const detailTemplate = root.dataset.detailTemplate || '/api/board/job/0/detail';
  const apiBulkPublish = root.dataset.bulkPublish || '/api/board/jobs/publish';
  const apiBulkClose = root.dataset.bulkClose || '/api/board/jobs/close';
  const apiBulkReassign = root.dataset.bulkReassign || '/api/board/jobs/reassign';
  const exportXlsx = root.dataset.exportXlsx || '/board/export.xlsx';
  const subprojectsApi = root.dataset.subprojectsApi || '/api/subprojects';

  const selected = new Set();
  let state = {
    page: 1,
    page_size: 50,
    total_count: 0,
    rows: [],
  };

  const fmtTime = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', '');
    } catch (_) {
      return isoStr;
    }
  };

  const esc = (s) => (s || '').toString().replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  const STATUS_TR = {
    PLANNED: 'Planlandı',
    ASSIGNED: 'Atandı',
    PUBLISHED: 'Sahada',
    REPORTED: 'Raporlandı',
    CLOSED: 'Kapandı',
  };
  const statusLabel = (st) => {
    const key = (st || '').toString().trim().toUpperCase();
    return STATUS_TR[key] || (st || '');
  };

  const buildUrlWithParams = (base, params) => {
    const u = new URL(base, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '' || v === false) return;
      u.searchParams.set(k, String(v));
    });
    return u.pathname + (u.search ? u.search : '');
  };

  const getFilters = () => {
    const q = (els('f_q') || {}).value || '';
    const start = (els('f_start') || {}).value || '';
    const end = (els('f_end') || {}).value || '';
    const status = (els('f_status') || {}).value || '';
    const project_id = (els('f_project') || {}).value || '';
    const subproject_id = (els('f_subproject') || {}).value || '';
    const city = (els('f_city') || {}).value || '';
    const assigned_user_id = (els('f_assigned_user') || {}).value || '';
    const assignee_q = (els('f_assignee_q') || {}).value || '';
    const overdue_only = !!(els('f_overdue_only') || {}).checked;
    const unassigned_only = !!(els('f_unassigned_only') || {}).checked;
    const published_only = !!(els('f_published_only') || {}).checked;
    const page_size = Number((els('f_page_size') || {}).value || 50) || 50;
    return {
      q: q.trim(),
      start,
      end,
      status,
      project_id,
      subproject_id,
      city,
      assigned_user_id,
      assignee_q: assignee_q.trim(),
      overdue_only: overdue_only ? '1' : '',
      unassigned_only: unassigned_only ? '1' : '',
      published_only: published_only ? '1' : '',
      page_size,
    };
  };

  const applyFiltersFromUrl = async () => {
    const sp = new URLSearchParams(window.location.search);
    const setVal = (id, key) => {
      const el = els(id);
      if (!el) return;
      const v = sp.get(key);
      if (v !== null) el.value = v;
    };
    setVal('f_q', 'q');
    setVal('f_start', 'start');
    setVal('f_end', 'end');
    setVal('f_status', 'status');
    setVal('f_project', 'project_id');
    setVal('f_city', 'city');
    setVal('f_assigned_user', 'assigned_user_id');
    setVal('f_assignee_q', 'assignee_q');
    setVal('f_page_size', 'page_size');

    const cb = (id, key) => {
      const el = els(id);
      if (!el) return;
      el.checked = (sp.get(key) || '') === '1';
    };
    cb('f_overdue_only', 'overdue_only');
    cb('f_unassigned_only', 'unassigned_only');
    cb('f_published_only', 'published_only');

    const pg = Number(sp.get('page') || 1) || 1;
    state.page = Math.max(1, pg);

    const projectId = (els('f_project') || {}).value || '';
    await loadSubprojects(projectId, sp.get('subproject_id') || '');
  };

  const pushUrlState = (filters, page) => {
    const params = {
      ...filters,
      page: page,
      page_size: filters.page_size,
    };
    const url = buildUrlWithParams(window.location.pathname, params);
    window.history.replaceState({}, '', url);
  };

  const loadSubprojects = async (projectId, selectedId) => {
    const sel = els('f_subproject');
    if (!sel) return;
    sel.innerHTML = `<option value="">Alt Proje (Hepsi)</option>`;
    if (!projectId) return;

    try {
      const res = await fetch(`${subprojectsApi}?project_id=${encodeURIComponent(projectId)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) return;
      const items = data.subprojects || data.items || [];
      items.forEach((it) => {
        const opt = document.createElement('option');
        opt.value = String(it.id || '');
        const code = (it.code || '').toString().trim();
        opt.textContent = code ? `${it.name} (${code})` : `${it.name}`;
        sel.appendChild(opt);
      });
      if (selectedId) sel.value = String(selectedId);
    } catch (_) {}
  };

  const renderBulkBar = () => {
    const bar = els('bulkBar');
    const cnt = els('selCount');
    if (!bar || !cnt) return;
    const n = selected.size;
    cnt.textContent = String(n);
    bar.style.display = n > 0 ? 'block' : 'none';
  };

  const renderTable = () => {
    const tbody = els('jobsTbody');
    const metaTotal = els('metaTotal');
    const metaPage = els('metaPage');
    const selAll = els('selAll');
    if (!tbody) return;

    if (metaTotal) metaTotal.textContent = String(state.total_count || 0);
    if (metaPage) metaPage.textContent = String(state.page || 1);

    const rows = state.rows || [];
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="10" style="padding:14px; color:#94a3b8;">Kayıt yok</td></tr>`;
      if (selAll) selAll.checked = false;
      renderBulkBar();
      return;
    }

    tbody.innerHTML = rows.map((r) => {
      const pid = Number(r.id || 0) || 0;
      const checked = selected.has(pid) ? 'checked' : '';
      const proj = `${esc(r.project_code || '')} / ${esc(r.project_name || '')}`;
      const sub = (r.subproject_name || '').toString().trim();
      const projLine = sub ? `${proj}<div style="color:#64748b; font-size:12px; margin-top:2px;">${esc(sub)}</div>` : proj;

      const st = esc(statusLabel(r.kanban_status || ''));
      const pillBg = r.is_overdue ? '#fee2e2' : '#f1f5f9';
      const pillColor = r.is_overdue ? '#991b1b' : '#0f172a';
      const published = r.is_published ? `<span style="color:#16a34a; font-weight:900;">Evet</span>` : `<span style="color:#94a3b8; font-weight:900;">Hayır</span>`;
      const lastReport = r.last_report_at ? fmtTime(r.last_report_at) : '-';
      const review = (r.review_status || '').toString().trim();
      const reviewHtml = review ? `<div style="color:#64748b; font-size:11px; margin-top:2px;">${esc(review)}</div>` : '';

      return `
        <tr data-job-id="${pid}" style="border-bottom:1px solid #e2e8f0; background:#fff;">
          <td style="padding:10px 10px;">
            <input class="rowSel" data-id="${pid}" type="checkbox" ${checked} style="width:16px; height:16px; margin:0; cursor:pointer;">
          </td>
          <td style="padding:10px 10px; white-space:nowrap;">
            ${r.is_merged && r.work_date_end && r.work_date_end !== r.work_date 
              ? `${esc(r.work_date || '')} - ${esc(r.work_date_end || '')}` 
              : esc(r.work_date || '')}
          </td>
          <td style="padding:10px 10px;">${esc(r.city || '')}</td>
          <td style="padding:10px 10px; min-width:320px;">
            <div style="font-weight:900; color:#0f172a; font-size:13px;">${projLine}</div>
            <div style="color:#64748b; font-size:11px; margin-top:2px;">
              ${r.is_merged && r.merged_job_ids && r.merged_job_ids.length > 1 
                ? `#${r.merged_job_ids.join(', #')}` 
                : `#${pid}`}
            </div>
          </td>
          <td style="padding:10px 10px;">${esc(r.team_name || '')}</td>
          <td style="padding:10px 10px;">${esc(r.assigned_user_name || '') || '-'}</td>
          <td style="padding:10px 10px;">
            <span style="display:inline-flex; padding:2px 8px; border-radius:999px; background:${pillBg}; color:${pillColor}; font-weight:900; font-size:12px;">${st}</span>
          </td>
          <td style="padding:10px 10px; white-space:nowrap;">${published}</td>
          <td style="padding:10px 10px; white-space:nowrap;">${esc(lastReport)}${reviewHtml}</td>
          <td style="padding:10px 10px; white-space:nowrap;">
            <button class="btnRow btn tiny secondary" data-act="detail" data-id="${pid}" type="button">Detay</button>
            <button class="btnRow btn tiny secondary" data-act="publish" data-id="${pid}" type="button">Yayınla</button>
            <button class="btnRow btn tiny secondary" data-act="close" data-id="${pid}" type="button">Kapat</button>
            <a class="btn tiny secondary" href="/assignment/${pid}" style="text-decoration:none;">Aç</a>
          </td>
        </tr>
      `;
    }).join('');

    tbody.querySelectorAll('.rowSel').forEach((cb) => {
      cb.addEventListener('change', () => {
        const id = Number(cb.getAttribute('data-id') || 0) || 0;
        if (!id) return;
        
        // Birleştirilmiş işler için tüm iş ID'lerini seç/seçimi kaldır
        const row = state.rows.find(r => r.id === id);
        const jobIds = (row && row.is_merged && row.merged_job_ids) ? row.merged_job_ids : [id];
        
        if (cb.checked) {
          jobIds.forEach(jid => selected.add(jid));
        } else {
          jobIds.forEach(jid => selected.delete(jid));
        }
        renderBulkBar();
      });
    });

    tbody.querySelectorAll('.btnRow').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const id = Number(btn.getAttribute('data-id') || 0) || 0;
        const act = btn.getAttribute('data-act') || '';
        if (!id || !act) return;
        
        // Birleştirilmiş işler için tüm iş ID'lerini bul
        const row = state.rows.find(r => r.id === id);
        const jobIds = (row && row.is_merged && row.merged_job_ids) ? row.merged_job_ids : [id];
        
        if (act === 'detail') {
          await openDrawer(id);
          return;
        }
        if (act === 'publish') {
          await doBulk(apiBulkPublish, jobIds);
          await load();
          return;
        }
        if (act === 'close') {
          await doBulk(apiBulkClose, jobIds);
          await load();
          return;
        }
      });
    });

    if (selAll) {
      // Birleştirilmiş işler için tüm iş ID'lerini dahil et
      const pageIds = [];
      rows.forEach((r) => {
        const mainId = Number(r.id || 0);
        if (mainId > 0) {
          pageIds.push(mainId);
          // Birleştirilmiş işler için tüm ID'leri de ekle
          if (r.is_merged && r.merged_job_ids) {
            r.merged_job_ids.forEach((jid) => {
              if (jid !== mainId && jid > 0) {
                pageIds.push(jid);
              }
            });
          }
        }
      });
      selAll.checked = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
      selAll.indeterminate = pageIds.some((id) => selected.has(id)) && !selAll.checked;
    }

    renderBulkBar();
  };

  const doBulk = async (url, jobIds, extraPayload) => {
    const ids = (jobIds || []).map((x) => Number(x || 0)).filter((x) => x > 0);
    if (!ids.length) return;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: ids, csrf_token: csrfToken, ...(extraPayload || {}) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        alert((data && data.error) ? data.error : 'İşlem başarısız.');
        return;
      }
    } catch (_) {
      alert('İşlem başarısız.');
    }
  };

  const load = async () => {
    const filters = getFilters();
    state.page_size = filters.page_size;
    pushUrlState(filters, state.page);

    const url = buildUrlWithParams(apiJobs, {
      ...filters,
      page: state.page,
      page_size: state.page_size,
    });

    const tbody = els('jobsTbody');
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="padding:14px; color:#94a3b8;">Yükleniyor...</td></tr>`;

    try {
      const res = await fetch(url);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="padding:14px; color:#dc2626;">Yüklenemedi</td></tr>`;
        return;
      }
      state.total_count = Number(data.total_count || 0) || 0;
      state.rows = data.rows || [];
      renderTable();
    } catch (_) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="10" style="padding:14px; color:#dc2626;">Yüklenemedi</td></tr>`;
    }
  };

  const openDrawer = async (jobId) => {
    const overlay = els('drawerOverlay');
    const drawer = els('drawer');
    const body = els('drawerBody');
    if (!overlay || !drawer || !body) return;

    overlay.style.display = 'block';
    drawer.style.display = 'block';
    body.innerHTML = `<div style="color:#64748b;">Yükleniyor...</div>`;

    const url = detailTemplate.replace('/0/', `/${jobId}/`);
    try {
      const res = await fetch(url);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        body.innerHTML = `<div style="color:#dc2626;">Yüklenemedi</div>`;
        return;
      }

      const job = data.job || {};
      const people = data.people || [];
      const atts = data.attachments || {};
      const rep = data.latest_report || null;
      const hist = data.status_history || [];

      const attHtml = (key, title) => {
        const arr = (atts[key] || []).map((x) => (x || '').toString()).filter(Boolean);
        if (!arr.length) return `<div style="color:#94a3b8; font-size:12px;">${title}: yok</div>`;
        return `
          <div style="margin-top:8px;">
            <div style="font-weight:900; color:#0f172a; font-size:12px;">${title}</div>
            <div style="margin-top:6px; display:grid; grid-template-columns: 1fr; gap:8px;">
              ${arr.map((fp) => {
                const safe = encodeURIComponent(fp).replace(/%2F/g, '/');
                const view = `/files/view/${safe}`;
                const dl = `/files/${safe}`;
                return `
                  <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px;">
                    <div style="font-weight:800; font-size:12px; color:#0f172a; word-break:break-word;">${esc(fp)}</div>
                    <div style="margin-top:8px; display:flex; gap:8px;">
                      <a class="btn tiny secondary" href="${view}" target="_blank" style="text-decoration:none;">Aç</a>
                      <a class="btn tiny secondary" href="${dl}" style="text-decoration:none;">İndir</a>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        `;
      };

      const repHtml = (() => {
        if (!rep) return `<div style="color:#94a3b8; font-size:12px;">Rapor yok</div>`;
        const media = rep.media || [];
        const mediaHtml = media.length ? media.map((m) => {
          const fp = (m.file_path || '').toString();
          const safe = encodeURIComponent(fp).replace(/%2F/g, '/');
          const view = `/files/view/${safe}`;
          const dl = `/files/${safe}`;
          const title = esc(m.original_name || fp);
          return `
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px;">
              <div style="font-weight:800; font-size:12px; color:#0f172a; word-break:break-word;">${title}</div>
              ${(m.file_type === 'image') ? `<img src="${view}" alt="" style="margin-top:8px; width:100%; border-radius:10px; border:1px solid #e2e8f0;">` : ''}
              <div style="margin-top:8px; display:flex; gap:8px;">
                <a class="btn tiny secondary" href="${view}" target="_blank" style="text-decoration:none;">Aç</a>
                <a class="btn tiny secondary" href="${dl}" style="text-decoration:none;">İndir</a>
              </div>
            </div>
          `;
        }).join('') : `<div style="color:#94a3b8; font-size:12px;">Ek yok</div>`;

        return `
          <div style="color:#475569; font-size:12px;">${esc(rep.outcome || '')} | ${esc(rep.review_status || '')} | ${fmtTime(rep.submitted_at)}</div>
          <div style="margin-top:8px;">
            <div style="font-weight:900; color:#0f172a; font-size:12px;">ISDP</div>
            <div style="margin-top:4px; white-space:pre-wrap; color:#334155; font-size:13px;">${esc(rep.isdp_status || '') || '-'}</div>
          </div>
          <div style="margin-top:8px;">
            <div style="font-weight:900; color:#0f172a; font-size:12px;">Ek Çalışma</div>
            <div style="margin-top:4px; white-space:pre-wrap; color:#334155; font-size:13px;">${esc(rep.extra_work_text || '') || '-'}</div>
          </div>
          <div style="margin-top:8px;">
            <div style="font-weight:900; color:#0f172a; font-size:12px;">Notlar</div>
            <div style="margin-top:4px; white-space:pre-wrap; color:#334155; font-size:13px;">${esc(rep.notes_text || '') || '-'}</div>
          </div>
          <div style="margin-top:10px; display:grid; grid-template-columns: 1fr; gap:10px;">
            ${mediaHtml}
          </div>
        `;
      })();

      const histHtml = hist.length ? hist.map((h) => {
        return `
          <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px; margin-top:8px;">
            <div style="display:flex; justify-content:space-between; gap:10px;">
              <div style="font-weight:900; color:#0f172a; font-size:12px;">${esc(statusLabel(h.from_status || ''))} → ${esc(statusLabel(h.to_status || ''))}</div>
              <div style="color:#64748b; font-size:11px; white-space:nowrap;">${fmtTime(h.changed_at)}</div>
            </div>
            ${(h.changed_by || '').trim() ? `<div style="color:#64748b; font-size:11px; margin-top:4px;">${esc(h.changed_by)}</div>` : ''}
            ${(h.note || '').trim() ? `<div style="color:#334155; font-size:12px; margin-top:6px; white-space:pre-wrap;">${esc(h.note)}</div>` : ''}
          </div>
        `;
      }).join('') : `<div style="color:#94a3b8; font-size:12px;">Kayıt yok</div>`;

      body.innerHTML = `
        <div class="card" style="border:1px solid #e2e8f0; border-radius:12px; padding:12px;">
          <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start;">
            <div style="font-weight:900; color:#0f172a; font-size:14px;">#${esc(job.id || '')} | ${esc(job.project_code || '')} / ${esc(job.project_name || '')}</div>
            <div style="font-weight:900; color:#0f172a; font-size:12px;">${esc(statusLabel(job.kanban_status || ''))}</div>
          </div>
          <div style="color:#64748b; font-size:12px; margin-top:6px;">${esc(job.city || '')} | ${esc(job.work_date || '')}</div>
          ${job.subproject_name ? `<div style="color:#475569; font-size:12px; margin-top:6px;">Alt Proje: ${esc(job.subproject_name)}</div>` : ''}
          <div style="margin-top:10px; display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px;">
              <div style="font-weight:900; color:#0f172a; font-size:12px;">Atanan</div>
              <div style="margin-top:4px; color:#334155; font-size:13px;">${esc(job.assigned_user || '') || '-'}</div>
            </div>
            <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px;">
              <div style="font-weight:900; color:#0f172a; font-size:12px;">Ekip</div>
              <div style="margin-top:4px; color:#334155; font-size:13px;">${esc(job.team_name || '') || '-'}</div>
            </div>
          </div>
          ${(job.note || '').trim() ? `<div style="margin-top:10px; border-top:1px dashed #e2e8f0; padding-top:10px; color:#334155; white-space:pre-wrap;">${esc(job.note)}</div>` : ''}
        </div>

        <div class="card" style="margin-top:12px; border:1px solid #e2e8f0; border-radius:12px; padding:12px;">
          <div style="font-weight:900; color:#0f172a;">Ekip (Personel)</div>
          ${people.length ? `
            <div style="margin-top:10px; display:grid; grid-template-columns: 1fr; gap:8px;">
              ${people.map((p) => `
                <div style="border:1px solid #e2e8f0; border-radius:12px; padding:10px;">
                  <div style="font-weight:900; color:#0f172a; font-size:12px;">${esc(p.full_name || '')}</div>
                  <div style="color:#64748b; font-size:11px; margin-top:4px;">${esc(p.phone || '')} ${p.email ? ' | ' + esc(p.email) : ''}</div>
                </div>
              `).join('')}
            </div>
          ` : `<div style="margin-top:8px; color:#94a3b8; font-size:12px;">Kayıt yok</div>`}
        </div>

        <div class="card" style="margin-top:12px; border:1px solid #e2e8f0; border-radius:12px; padding:12px;">
          <div style="font-weight:900; color:#0f172a;">Ekler</div>
          ${attHtml('lld_hhd', 'LLD/HHD')}
          ${attHtml('tutanak', 'Tutanak')}
          ${attHtml('photo', 'Foto')}
        </div>

        <div class="card" style="margin-top:12px; border:1px solid #e2e8f0; border-radius:12px; padding:12px;">
          <div style="font-weight:900; color:#0f172a;">Son Rapor</div>
          <div style="margin-top:10px;">${repHtml}</div>
        </div>

        <div class="card" style="margin-top:12px; border:1px solid #e2e8f0; border-radius:12px; padding:12px;">
          <div style="font-weight:900; color:#0f172a;">Durum Geçmişi</div>
          <div style="margin-top:8px;">${histHtml}</div>
        </div>
      `;
    } catch (_) {
      body.innerHTML = `<div style="color:#dc2626;">Yüklenemedi</div>`;
    }
  };

  const closeDrawer = () => {
    const overlay = els('drawerOverlay');
    const drawer = els('drawer');
    if (overlay) overlay.style.display = 'none';
    if (drawer) drawer.style.display = 'none';
  };

  let debounceTimer = null;
  const scheduleReload = (immediate) => {
    if (debounceTimer) clearTimeout(debounceTimer);
    const delay = immediate ? 0 : 350;
    debounceTimer = setTimeout(() => {
      state.page = 1;
      load();
    }, delay);
  };

  const initEvents = () => {
    const watch = ['f_start', 'f_end', 'f_status', 'f_city', 'f_assigned_user', 'f_overdue_only', 'f_unassigned_only', 'f_published_only', 'f_page_size'];
    watch.forEach((id) => {
      const el = els(id);
      if (!el) return;
      el.addEventListener('change', () => scheduleReload(true));
    });

    const q = els('f_q');
    if (q) q.addEventListener('input', () => scheduleReload(false));
    const aq = els('f_assignee_q');
    if (aq) aq.addEventListener('input', () => scheduleReload(false));

    const proj = els('f_project');
    if (proj) {
      proj.addEventListener('change', async () => {
        await loadSubprojects((proj.value || '').toString(), '');
        const spSel = els('f_subproject');
        if (spSel) spSel.value = '';
        scheduleReload(true);
      });
    }
    const spSel = els('f_subproject');
    if (spSel) spSel.addEventListener('change', () => scheduleReload(true));

    const btnPrev = els('btnPrev');
    const btnNext = els('btnNext');
    if (btnPrev) {
      btnPrev.addEventListener('click', () => {
        if (state.page <= 1) return;
        state.page -= 1;
        load();
      });
    }
    if (btnNext) {
      btnNext.addEventListener('click', () => {
        const maxPage = Math.max(1, Math.ceil((state.total_count || 0) / (state.page_size || 50)));
        if (state.page >= maxPage) return;
        state.page += 1;
        load();
      });
    }

    const selAll = els('selAll');
    if (selAll) {
      selAll.addEventListener('change', () => {
        const rows = state.rows || [];
        const pageIds = rows.map((r) => Number(r.id || 0)).filter((x) => x > 0);
        if (selAll.checked) pageIds.forEach((id) => selected.add(id));
        else pageIds.forEach((id) => selected.delete(id));
        renderTable();
      });
    }

    const exportBtn = els('btnExport');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        const filters = getFilters();
        const url = buildUrlWithParams(exportXlsx, { ...filters, page: '', page_size: '' });
        window.open(url, '_blank');
      });
    }

    const exportSelBtn = els('btnExportSelected');
    if (exportSelBtn) {
      exportSelBtn.addEventListener('click', () => {
        if (!selected.size) return;
        const filters = getFilters();
        const ids = Array.from(selected.values()).join(',');
        const url = buildUrlWithParams(exportXlsx, { ...filters, ids, page: '', page_size: '' });
        window.open(url, '_blank');
      });
    }

    const btnBulkPublish = els('btnBulkPublish');
    if (btnBulkPublish) {
      btnBulkPublish.addEventListener('click', async () => {
        await doBulk(apiBulkPublish, Array.from(selected.values()));
        selected.clear();
        renderBulkBar();
        await load();
      });
    }

    const btnBulkClose = els('btnBulkClose');
    if (btnBulkClose) {
      btnBulkClose.addEventListener('click', async () => {
        await doBulk(apiBulkClose, Array.from(selected.values()));
        selected.clear();
        renderBulkBar();
        await load();
      });
    }

    const btnBulkReassign = els('btnBulkReassign');
    if (btnBulkReassign) {
      btnBulkReassign.addEventListener('click', async () => {
        const userId = Number((els('bulkAssignee') || {}).value || 0) || 0;
        if (!userId) return alert('Kullanıcı seçin.');
        await doBulk(apiBulkReassign, Array.from(selected.values()), { assigned_user_id: userId });
        selected.clear();
        renderBulkBar();
        await load();
      });
    }

    const btnClearSel = els('btnClearSel');
    if (btnClearSel) btnClearSel.addEventListener('click', () => { selected.clear(); renderTable(); });

    const closeBtn = els('drawerClose');
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    const overlay = els('drawerOverlay');
    if (overlay) overlay.addEventListener('click', closeDrawer);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
  };

  (async () => {
    await applyFiltersFromUrl();
    initEvents();
    await load();
  })();
})();
