/**
 * Editing State Manager
 * Aktif düzenleme durumunu izler ve sayfa yenileme kontrolü sağlar
 * 
 * Bu modül şunları yapar:
 * 1. Kullanıcının düzenleme yapıp yapmadığını izler
 * 2. Düzenleme sırasında gelen güncellemeleri sıraya alır
 * 3. Düzenleme bittiğinde bekleyen güncellemeleri uygular
 */

const EditingStateManager = (function () {
    'use strict';

    // ================ STATE ================
    const state = {
        isEditing: false,
        editingCellId: null,
        editingProjectId: null,
        editingWorkDate: null,
        editStartTime: null,
        hasPendingUpdates: false,
        pendingCellUpdates: [],  // Bekleyen hücre güncellemeleri
        lastUpdateTimestamp: null,
        refreshBlocked: false
    };

    // ================ EDITING DETECTION ================

    /**
     * Modal veya form düzenleme durumunu kontrol et
     */
    function detectActiveEditing() {
        // 1. Cell Modal açık mı?
        const cellModal = document.getElementById('cellModal');
        if (cellModal && cellModal.classList.contains('open')) {
            return { type: 'modal', element: cellModal };
        }

        // 2. Dynamic Modal açık mı? (context menu modals)
        const dynamicModal = document.getElementById('dynamicModal');
        if (dynamicModal && dynamicModal.style.display !== 'none') {
            return { type: 'dynamic_modal', element: dynamicModal };
        }

        // 3. Yeni satır ekleme aktif mi?
        const newJobRow = document.getElementById('newJobRow');
        if (newJobRow) {
            return { type: 'new_row', element: newJobRow };
        }

        // 4. Satır düzenleme modunda mı?
        const editJobCity = document.getElementById('editJobCity');
        if (editJobCity) {
            return { type: 'edit_row', element: editJobCity };
        }

        // 5. Input veya textarea içinde mi?
        const activeEl = document.activeElement;
        if (activeEl) {
            const tagName = activeEl.tagName.toLowerCase();
            if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
                // Plan tablosu içinde mi kontrol et
                const inPlanTable = activeEl.closest('#gridPlanContainer, #planTbody, .planRow, #cellModal');
                if (inPlanTable) {
                    return { type: 'input', element: activeEl };
                }
            }

            // Contenteditable
            if (activeEl.isContentEditable) {
                return { type: 'contenteditable', element: activeEl };
            }
        }

        return null;
    }

    /**
     * Aktif düzenleme durumunu güncelle
     */
    function updateEditingState() {
        const editing = detectActiveEditing();
        const wasEditing = state.isEditing;

        state.isEditing = !!editing;

        if (editing && !wasEditing) {
            // Düzenleme başladı
            state.editStartTime = Date.now();
            console.log('[EditingState] Düzenleme başladı:', editing.type);
        } else if (!editing && wasEditing) {
            // Düzenleme bitti
            console.log('[EditingState] Düzenleme bitti');
            state.editStartTime = null;

            // Bekleyen güncellemeler varsa uygula
            if (state.hasPendingUpdates) {
                applyPendingUpdates();
            }
        }

        return editing;
    }

    // ================ STATE GETTERS ================

    function isEditing() {
        updateEditingState();
        return state.isEditing;
    }

    function getEditingInfo() {
        const editing = detectActiveEditing();
        return {
            isEditing: !!editing,
            type: editing ? editing.type : null,
            element: editing ? editing.element : null,
            duration: state.editStartTime ? Date.now() - state.editStartTime : 0,
            hasPendingUpdates: state.hasPendingUpdates,
            pendingCount: state.pendingCellUpdates.length
        };
    }

    // ================ REFRESH CONTROL ================

    /**
     * Sayfa yenilemesi güvenli mi?
     */
    function canRefresh() {
        // Düzenleme durumu güncelle
        updateEditingState();

        // Düzenleme yapılıyorsa yenileme yapma
        if (state.isEditing) {
            console.log('[EditingState] Yenileme engellendi - düzenleme aktif');
            return false;
        }

        // Yenileme engeli var mı?
        if (state.refreshBlocked) {
            console.log('[EditingState] Yenileme engellendi - manuel blok');
            return false;
        }

        return true;
    }

    /**
     * Yenilemeyi manuel olarak engelle/aç
     */
    function blockRefresh(block = true) {
        state.refreshBlocked = block;
        console.log('[EditingState] Yenileme engeli:', block);
    }

    /**
     * Güvenli sayfa yenileme - düzenleme durumunu kontrol eder
     */
    function safeReload(force = false) {
        if (force || canRefresh()) {
            console.log('[EditingState] Sayfa yenileniyor...');
            window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload();
            return true;
        } else {
            // Yenileme bekletiliyor, pending update olarak işaretle
            state.hasPendingUpdates = true;
            console.log('[EditingState] Yenileme bekletiliyor - düzenleme aktif');
            showPendingUpdateIndicator();
            return false;
        }
    }

    // ================ PENDING UPDATES ================

    /**
     * Hücre güncellemesini sıraya ekle
     */
    function queueCellUpdate(updateData) {
        // Aynı hücre için eski güncellemeyi kaldır
        state.pendingCellUpdates = state.pendingCellUpdates.filter(
            u => !(u.project_id === updateData.project_id && u.work_date === updateData.work_date)
        );

        state.pendingCellUpdates.push({
            ...updateData,
            queuedAt: Date.now()
        });

        state.hasPendingUpdates = true;
        console.log('[EditingState] Güncelleme sıraya eklendi:', updateData);
        showPendingUpdateIndicator();
    }

    /**
     * Bekleyen güncellemeleri uygula
     */
    function applyPendingUpdates() {
        if (!state.hasPendingUpdates) return;

        console.log('[EditingState] Bekleyen güncellemeler uygulanıyor:', state.pendingCellUpdates.length);

        // Eğer çok fazla güncelleme varsa sayfa yenile
        if (state.pendingCellUpdates.length > 10 || state.hasPendingUpdates) {
            state.pendingCellUpdates = [];
            state.hasPendingUpdates = false;
            hidePendingUpdateIndicator();

            // Kısa bir gecikme ile yenile
            setTimeout(() => {
                console.log('[EditingState] Bekleyen güncellemeler için sayfa yenileniyor...');
                window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload();
            }, 500);
            return;
        }

        // Hücre bazında güncelleme yap
        state.pendingCellUpdates.forEach(update => {
            applySingleCellUpdate(update);
        });

        state.pendingCellUpdates = [];
        state.hasPendingUpdates = false;
        hidePendingUpdateIndicator();
    }

    /**
     * Tek bir hücreyi güncelle (DOM manipülasyonu)
     */
    function applySingleCellUpdate(update) {
        const cell = document.querySelector(
            `td.cell[data-project-id="${update.project_id}"][data-date="${update.work_date}"]`
        );

        if (!cell) {
            console.warn('[EditingState] Güncellenecek hücre bulunamadı:', update);
            return;
        }

        // Hücre içeriğini güncelle
        if (update.shift) {
            cell.setAttribute('data-shift', update.shift);
            const timeDiv = cell.querySelector('.cell-time');
            if (timeDiv) timeDiv.textContent = update.shift;
        }

        if (update.note !== undefined) {
            cell.setAttribute('data-note', update.note || '');
        }

        if (update.status) {
            cell.setAttribute('data-status', update.status);
            if (update.status === 'cancelled') {
                cell.classList.add('is-cancelled');
            } else {
                cell.classList.remove('is-cancelled');
            }
        }

        // Görsel geri bildirim
        cell.style.backgroundColor = '#fef08a';
        setTimeout(() => {
            cell.style.backgroundColor = '';
        }, 2000);

        console.log('[EditingState] Hücre güncellendi:', update);
    }

    // ================ UI INDICATORS ================

    /**
     * Bekleyen güncelleme göstergesi göster
     */
    function showPendingUpdateIndicator() {
        let indicator = document.getElementById('pendingUpdateIndicator');

        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'pendingUpdateIndicator';
            indicator.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: white;
                padding: 12px 20px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                z-index: 99999;
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 14px;
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 10px;
                cursor: pointer;
                animation: slideInRight 0.3s ease-out;
            `;
            indicator.innerHTML = `
                <span class="pulse-dot" style="
                    width: 10px;
                    height: 10px;
                    background: #fef3c7;
                    border-radius: 50%;
                    animation: pulse 1.5s infinite;
                "></span>
                <span>Bekleyen güncellemeler var</span>
                <button onclick="EditingStateManager.applyPendingUpdates()" style="
                    background: rgba(255,255,255,0.2);
                    border: none;
                    padding: 6px 12px;
                    border-radius: 6px;
                    color: white;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 600;
                ">Şimdi Güncelle</button>
            `;

            // Animasyonlar için stil ekle
            if (!document.getElementById('editingStateStyles')) {
                const style = document.createElement('style');
                style.id = 'editingStateStyles';
                style.textContent = `
                    @keyframes slideInRight {
                        from { transform: translateX(100%); opacity: 0; }
                        to { transform: translateX(0); opacity: 1; }
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; transform: scale(1); }
                        50% { opacity: 0.5; transform: scale(1.2); }
                    }
                `;
                document.head.appendChild(style);
            }

            document.body.appendChild(indicator);
        }

        indicator.style.display = 'flex';
    }

    /**
     * Bekleyen güncelleme göstergesini gizle
     */
    function hidePendingUpdateIndicator() {
        const indicator = document.getElementById('pendingUpdateIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    // ================ EVENT LISTENERS ================

    function setupEventListeners() {
        // Modal açılma/kapanma olaylarını izle
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                if (mutation.type === 'attributes' &&
                    (mutation.attributeName === 'class' || mutation.attributeName === 'style')) {
                    updateEditingState();
                }
            });
        });

        // Cell Modal'ı izle
        const cellModal = document.getElementById('cellModal');
        if (cellModal) {
            observer.observe(cellModal, { attributes: true });
        }

        // Dynamic Modal'ı izle
        const dynamicModal = document.getElementById('dynamicModal');
        if (dynamicModal) {
            observer.observe(dynamicModal, { attributes: true });
        }

        // DOM değişikliklerini izle (yeni satır ekleme vb.)
        const planTbody = document.getElementById('planTbody');
        if (planTbody) {
            const domObserver = new MutationObserver(() => {
                updateEditingState();
            });
            domObserver.observe(planTbody, { childList: true });
        }

        // Focus/blur olaylarını izle
        document.addEventListener('focusin', () => {
            setTimeout(updateEditingState, 100);
        });

        document.addEventListener('focusout', () => {
            setTimeout(updateEditingState, 100);
        });

        console.log('[EditingState] Event listeners kuruldu');
    }

    // ================ INITIALIZATION ================

    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupEventListeners);
        } else {
            setupEventListeners();
        }
        console.log('[EditingState] Manager başlatıldı');
    }

    // Otomatik başlat
    init();

    // ================ PUBLIC API ================
    return {
        // State
        isEditing,
        getEditingInfo,
        updateEditingState,

        // Refresh control
        canRefresh,
        blockRefresh,
        safeReload,

        // Pending updates
        queueCellUpdate,
        applyPendingUpdates,
        hasPendingUpdates: () => state.hasPendingUpdates,

        // UI
        showPendingUpdateIndicator,
        hidePendingUpdateIndicator,

        // Direct state access (for debugging)
        _state: state
    };
})();

// Global erişim için
window.EditingStateManager = EditingStateManager;
