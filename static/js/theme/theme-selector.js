/**
 * Theme Selector - Tema Seçici UI Komponenti
 * Netmon Proje Takip - Theme System
 * 
 * Bu dosya tema seçici dropdown UI komponentini içerir.
 */

import { THEMES, COLOR_PRESETS } from './theme-data.js';
import { getThemeManager } from './theme-manager.js';

/**
 * Theme Selector
 * Tema seçimi için dropdown UI komponenti
 */
export class ThemeSelector {
    /**
     * @param {HTMLElement|string} container - Kapsayıcı element veya selector
     * @param {Object} options - Seçenekler
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;

        if (!this.container) {
            console.error('ThemeSelector: Container bulunamadı');
            return;
        }

        this.options = {
            showColorPicker: true,
            showPresets: true,
            compact: false,
            iconOnly: false,
            ...options
        };

        this.themeManager = getThemeManager();
        this.isOpen = false;
        this.dropdown = null;

        this._init();
    }

    /**
     * Komponenti başlat
     * @private
     */
    _init() {
        this.container.classList.add('theme-selector');
        if (this.options.compact) this.container.classList.add('compact');
        if (this.options.iconOnly) this.container.classList.add('icon-only');

        this._render();
        this._bindEvents();

        // Theme Manager'dan değişiklikleri dinle
        this.themeManager.addListener((event, data) => {
            if (event === 'themeChanged' || event === 'customColorChanged') {
                this._syncWithThemeManager();
            }
        });
    }

    /**
     * Komponenti render et
     * @private
     */
    _render() {
        const currentTheme = this.themeManager.getThemeData();

        this.container.innerHTML = `
      <button class="theme-selector-trigger" type="button" aria-label="Tema Seç" aria-expanded="false">
        <span class="theme-current-icon">
          ${this._getThemeIcon(currentTheme.id)}
        </span>
        <span class="theme-current-name">${currentTheme.name}</span>
        <svg class="theme-dropdown-arrow" width="12" height="12" viewBox="0 0 24 24">
          <path d="M7 10l5 5 5-5z" fill="currentColor"/>
        </svg>
      </button>
      ${this._renderDropdown()}
    `;

        this.dropdown = this.container.querySelector('.theme-dropdown-menu');
    }

    /**
     * Dropdown menüyü render et
     * @private
     * @returns {string} HTML
     */
    _renderDropdown() {
        const currentThemeId = this.themeManager.getTheme();
        let itemsHtml = '';

        // Tema öğelerini oluştur
        for (const [themeId, theme] of Object.entries(THEMES)) {
            const isActive = themeId === currentThemeId;
            itemsHtml += `
        <div class="theme-item ${isActive ? 'active' : ''}" 
             data-theme="${themeId}" 
             role="button" 
             tabindex="0"
             aria-label="${theme.name} - ${theme.description}">
          <div class="theme-preview">
            <div class="theme-preview-bar" style="background: ${theme.colors.bgPrimary}"></div>
            <div class="theme-preview-bar" style="background: ${theme.colors.bgSecondary}"></div>
            <div class="theme-preview-dot" style="background: ${theme.colors.accentPrimary}"></div>
          </div>
          <span class="theme-name">${theme.name}</span>
          <svg class="theme-check" width="16" height="16" viewBox="0 0 24 24">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="currentColor"/>
          </svg>
        </div>
      `;
        }

        // Özel renk bölümü
        let customColorHtml = '';
        if (this.options.showColorPicker) {
            const customColor = this.themeManager.getCustomPrimaryColor() || '#3b82f6';

            let presetsHtml = '';
            if (this.options.showPresets) {
                presetsHtml = `
          <div class="theme-color-presets">
            ${COLOR_PRESETS.map(preset => `
              <button class="theme-color-preset" 
                      style="background: ${preset.color}" 
                      data-color="${preset.color}"
                      title="${preset.name}"
                      type="button">
              </button>
            `).join('')}
          </div>
        `;
            }

            customColorHtml = `
        <div class="theme-divider"></div>
        <div class="theme-custom-section">
          <div class="theme-custom-header">
            <span>Özel Vurgu Rengi</span>
          </div>
          ${presetsHtml}
          <div class="theme-custom-color-picker">
            <input type="color" id="themeCustomColorPicker" value="${customColor}">
            <input type="text" id="themeCustomColorText" value="${customColor}" maxlength="7" placeholder="#RRGGBB">
          </div>
          <button class="theme-reset-btn" type="button">Varsayılana Sıfırla</button>
        </div>
      `;
        }

        return `
      <div class="theme-dropdown-menu" hidden>
        ${itemsHtml}
        ${customColorHtml}
      </div>
    `;
    }

    /**
     * Tema ikonu al
     * @param {string} themeId - Tema ID'si
     * @returns {string} SVG HTML
     * @private
     */
    _getThemeIcon(themeId) {
        const icons = {
            light: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="5"/>
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
      </svg>`,
            dark: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>`,
            'pure-black': `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="4" fill="currentColor"/>
      </svg>`,
            'pure-white': `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <circle cx="12" cy="12" r="4"/>
      </svg>`,
            ocean: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2">
        <path d="M2 12c2-2 4-3 6-3s4 1 6 3 4 3 6 3"/>
        <path d="M2 17c2-2 4-3 6-3s4 1 6 3 4 3 6 3"/>
        <path d="M2 7c2-2 4-3 6-3s4 1 6 3 4 3 6 3"/>
      </svg>`,
            forest: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2">
        <path d="M12 2L8 10h2v6H8l-2 6h4v-4h4v4h4l-2-6h-2v-6h2L12 2z"/>
      </svg>`,
            sunset: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2">
        <path d="M17 18a5 5 0 0 0-10 0"/>
        <circle cx="12" cy="9" r="4"/>
        <path d="M12 2v2M4 12H2M6.31 6.31L4.8 4.8M22 12h-2M17.69 6.31l1.51-1.51"/>
      </svg>`,
            purple: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9333ea" stroke-width="2">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
      </svg>`
        };

        return icons[themeId] || icons.light;
    }

    /**
     * Event listener'ları bağla
     * @private
     */
    _bindEvents() {
        const trigger = this.container.querySelector('.theme-selector-trigger');

        // Trigger click
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        // Tema öğe click'leri
        this.container.querySelectorAll('.theme-item[data-theme]').forEach(item => {
            item.addEventListener('click', () => {
                this.setTheme(item.dataset.theme);
            });

            // Klavye navigasyonu
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.setTheme(item.dataset.theme);
                }
            });
        });

        // Renk seçici
        const colorPicker = this.container.querySelector('#themeCustomColorPicker');
        const colorText = this.container.querySelector('#themeCustomColorText');

        if (colorPicker) {
            colorPicker.addEventListener('input', (e) => {
                const color = e.target.value;
                if (colorText) colorText.value = color;
                this.setCustomColor(color);
            });
        }

        if (colorText) {
            colorText.addEventListener('change', (e) => {
                let color = e.target.value.trim();
                if (!color.startsWith('#')) color = '#' + color;

                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (colorPicker) colorPicker.value = color;
                    this.setCustomColor(color);
                }
            });
        }

        // Preset renk butonları
        this.container.querySelectorAll('.theme-color-preset').forEach(preset => {
            preset.addEventListener('click', () => {
                const color = preset.dataset.color;
                if (colorPicker) colorPicker.value = color;
                if (colorText) colorText.value = color;
                this.setCustomColor(color);
            });
        });

        // Sıfırla butonu
        const resetBtn = this.container.querySelector('.theme-reset-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.resetToDefaults();
            });
        }

        // Dışarı tıklama - dropdown kapat
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.close();
            }
        });

        // ESC tuşu - dropdown kapat
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }

    /**
     * Theme Manager ile senkronize et
     * @private
     */
    _syncWithThemeManager() {
        const currentTheme = this.themeManager.getThemeData();
        const customColor = this.themeManager.getCustomPrimaryColor();

        // Trigger güncelle
        const trigger = this.container.querySelector('.theme-selector-trigger');
        if (trigger) {
            trigger.querySelector('.theme-current-icon').innerHTML = this._getThemeIcon(currentTheme.id);
            trigger.querySelector('.theme-current-name').textContent = currentTheme.name;
        }

        // Aktif durumu güncelle
        this.container.querySelectorAll('.theme-item').forEach(item => {
            if (item.dataset.theme === currentTheme.id) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Renk picker güncelle
        if (customColor) {
            const colorPicker = this.container.querySelector('#themeCustomColorPicker');
            const colorText = this.container.querySelector('#themeCustomColorText');
            if (colorPicker) colorPicker.value = customColor;
            if (colorText) colorText.value = customColor;
        }
    }

    // ===== PUBLIC API =====

    /**
     * Dropdown'ı aç/kapat
     */
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    /**
     * Dropdown'ı aç
     */
    open() {
        this.isOpen = true;
        this.dropdown.hidden = false;
        this.container.classList.add('open');
        this.container.querySelector('.theme-selector-trigger').setAttribute('aria-expanded', 'true');
    }

    /**
     * Dropdown'ı kapat
     */
    close() {
        this.isOpen = false;
        if (this.dropdown) this.dropdown.hidden = true;
        this.container.classList.remove('open');
        const trigger = this.container.querySelector('.theme-selector-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
    }

    /**
     * Tema ayarla
     * @param {string} themeId - Tema ID'si
     */
    setTheme(themeId) {
        this.themeManager.setTheme(themeId);
        this.close();
    }

    /**
     * Özel renk ayarla
     * @param {string} color - Hex renk kodu
     */
    setCustomColor(color) {
        this.themeManager.setCustomPrimaryColor(color);
    }

    /**
     * Varsayılana sıfırla
     */
    resetToDefaults() {
        this.themeManager.resetToDefaults();
        this._syncWithThemeManager();

        // Renk picker'ı varsayılana döndür
        const colorPicker = this.container.querySelector('#themeCustomColorPicker');
        const colorText = this.container.querySelector('#themeCustomColorText');
        if (colorPicker) colorPicker.value = '#3b82f6';
        if (colorText) colorText.value = '#3b82f6';
    }

    /**
     * Komponenti yok et
     */
    destroy() {
        this.container.innerHTML = '';
        this.container.classList.remove('theme-selector', 'compact', 'icon-only', 'open');
    }
}

/**
 * Tema seçiciyi otomatik başlat
 * @param {string} selector - Container selector
 * @param {Object} options - Seçenekler
 * @returns {ThemeSelector|null}
 */
export function initThemeSelector(selector = '#themeSelector', options = {}) {
    const container = document.querySelector(selector);
    if (container) {
        return new ThemeSelector(container, options);
    }
    return null;
}
