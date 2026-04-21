/**
 * Theme Manager - Ana Tema Yöneticisi
 * Netmon Proje Takip - Theme System
 * 
 * Bu dosya tüm tema işlemlerini yöneten ana sınıfı içerir.
 */

import { THEMES, DEFAULT_THEME, getThemeById } from './theme-data.js';
import { ThemeStorage } from './theme-storage.js';
import { ThemeTransition } from './theme-transition.js';

/**
 * Theme Manager
 * Uygulamanın tema yönetimini sağlar
 */
export class ThemeManager {
    constructor() {
        this.currentTheme = null;
        this.customPrimaryColor = null;
        this.transitionManager = new ThemeTransition();
        this.listeners = new Set();
        this.initialized = false;

        // Otomatik başlatma
        this._init();
    }

    /**
     * Tema yöneticisini başlat
     * @private
     */
    _init() {
        if (this.initialized) return;

        // Kaydedilmiş temayı al ve uygula
        const savedTheme = ThemeStorage.getTheme();
        this.currentTheme = savedTheme || DEFAULT_THEME;

        // Özel accent rengini al
        this.customPrimaryColor = ThemeStorage.getCustomPrimaryColor();

        // DOM'a uygula
        this._applyTheme(this.currentTheme, false);
        this._applyCustomPrimaryColor();

        // Sistem tema değişikliğini dinle
        this._setupSystemThemeListener();

        this.initialized = true;

        console.log(`ThemeManager: Başlatıldı, aktif tema: ${this.currentTheme}`);
    }

    /**
     * Sistem tema tercihini dinle
     * @private
     */
    _setupSystemThemeListener() {
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                // Sadece kullanıcı tercih belirlemediyse otomatik değiştir
                if (!ThemeStorage.getTheme()) {
                    this.setTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    /**
     * Temayı DOM'a uygula
     * @param {string} themeId - Tema ID'si
     * @param {boolean} animate - Animasyonlu geçiş yapılsın mı
     * @private
     */
    _applyTheme(themeId, animate = true) {
        let theme = THEMES[themeId];
        if (!theme) {
            console.warn(`ThemeManager: Bilinmeyen tema "${themeId}", varsayılana dönülüyor`);
            themeId = DEFAULT_THEME;
            theme = THEMES[themeId];
        }

        const root = document.documentElement;
        const colors = theme.colors;

        // Animasyonlu geçiş hazırlığı
        if (animate) {
            this.transitionManager.prepareTransition(root);
        }

        // Data attribute uygula
        root.setAttribute('data-theme', themeId);

        // =============================================
        // ESKİ CSS DEĞİŞKENLERİNİ GÜNCELLE (style.css uyumluluğu)
        // =============================================

        // Arka plan değişkenleri
        root.style.setProperty('--bg', colors.bgPrimary);
        root.style.setProperty('--card', colors.bgSecondary);
        root.style.setProperty('--surface', colors.bgSecondary);
        root.style.setProperty('--bg-soft', colors.bgTertiary);
        root.style.setProperty('--bg-soft-2', colors.bgTertiary);

        // Yazı değişkenleri
        root.style.setProperty('--text', colors.textPrimary);
        root.style.setProperty('--text-strong', colors.textPrimary);
        root.style.setProperty('--text-secondary', colors.textSecondary);
        root.style.setProperty('--text-light', colors.textSecondary);
        root.style.setProperty('--muted', colors.textSecondary);
        root.style.setProperty('--text-muted', colors.textSecondary);
        root.style.setProperty('--text-subtle', colors.textSecondary);

        // Kenarlık değişkenleri
        root.style.setProperty('--border', colors.border);
        root.style.setProperty('--line', colors.border);
        root.style.setProperty('--line-light', colors.bgTertiary);
        root.style.setProperty('--border-soft', colors.bgTertiary);
        root.style.setProperty('--border-glass', colors.glassBorder);

        // Cam efekti değişkenleri
        root.style.setProperty('--glass-bg', colors.glassBg);
        root.style.setProperty('--glass-border', colors.glassBorder);

        // Vurgu rengi
        root.style.setProperty('--primary', colors.accentPrimary);
        root.style.setProperty('--primary-hover', this._adjustColor(colors.accentPrimary, -10));
        root.style.setProperty('--accent', colors.accentPrimary);
        root.style.setProperty('--secondary', colors.accentSecondary);

        // RGB değerleri (buton shadow'ları için)
        const rgb = this._hexToRgb(colors.accentPrimary);
        root.style.setProperty('--primary-rgb', `${rgb.r}, ${rgb.g}, ${rgb.b}`);
        const rgbSecondary = this._hexToRgb(colors.accentSecondary);
        root.style.setProperty('--secondary-rgb', `${rgbSecondary.r}, ${rgbSecondary.g}, ${rgbSecondary.b}`);

        // Status renkleri (tema bazlı)
        if (theme.isDark) {
            root.style.setProperty('--success-bg', 'rgba(16, 185, 129, 0.2)');
            root.style.setProperty('--success-text', '#6ee7b7');
            root.style.setProperty('--warning-bg', 'rgba(245, 158, 11, 0.2)');
            root.style.setProperty('--warning-text', '#fcd34d');
            root.style.setProperty('--danger-bg', 'rgba(239, 68, 68, 0.2)');
            root.style.setProperty('--danger-text', '#fca5a5');
            root.style.setProperty('--info-bg', 'rgba(59, 130, 246, 0.2)');
            root.style.setProperty('--info-text', '#93c5fd');
            root.style.setProperty('--status-success-bg', 'rgba(16, 185, 129, 0.2)');
            root.style.setProperty('--status-success-text', '#6ee7b7');
            root.style.setProperty('--status-warning-bg', 'rgba(245, 158, 11, 0.2)');
            root.style.setProperty('--status-warning-text', '#fcd34d');
            root.style.setProperty('--status-danger-bg', 'rgba(239, 68, 68, 0.2)');
            root.style.setProperty('--status-danger-text', '#fca5a5');
            root.style.setProperty('--status-info-bg', 'rgba(59, 130, 246, 0.2)');
            root.style.setProperty('--status-info-text', '#93c5fd');
        } else {
            root.style.setProperty('--success-bg', '#ecfdf5');
            root.style.setProperty('--success-text', '#065f46');
            root.style.setProperty('--warning-bg', '#fffbeb');
            root.style.setProperty('--warning-text', '#92400e');
            root.style.setProperty('--danger-bg', '#fef2f2');
            root.style.setProperty('--danger-text', '#b91c1c');
            root.style.setProperty('--info-bg', '#eff6ff');
            root.style.setProperty('--info-text', '#1e40af');
            root.style.setProperty('--status-success-bg', '#dcfce7');
            root.style.setProperty('--status-success-text', '#14532d');
            root.style.setProperty('--status-warning-bg', '#fffbeb');
            root.style.setProperty('--status-warning-text', '#92400e');
            root.style.setProperty('--status-danger-bg', '#fee2e2');
            root.style.setProperty('--status-danger-text', '#7f1d1d');
            root.style.setProperty('--status-info-bg', '#dbeafe');
            root.style.setProperty('--status-info-text', '#1e3a8a');
        }

        // Geriye dönük uyumluluk: dark-mode class'ını yönet
        if (theme.isDark) {
            root.classList.add('dark-mode');
        } else {
            root.classList.remove('dark-mode');
        }

        // Logo için tema class'ı
        this._updateLogoForTheme(themeId);

        this.currentTheme = themeId;

        // Animasyonlu geçişi tamamla
        if (animate) {
            this.transitionManager.applyTransition(root);
        }

        // Dinleyicileri bilgilendir
        this._notifyListeners('themeChanged', { themeId, theme });
    }

    /**
     * Özel accent rengini uygula
     * @private
     */
    _applyCustomPrimaryColor() {
        if (!this.customPrimaryColor) return;

        const root = document.documentElement;
        root.style.setProperty('--custom-primary-color', this.customPrimaryColor);
        root.style.setProperty('--custom-primary', this.customPrimaryColor);

        // Hover ve active renkleri oluştur
        const hoverColor = this._adjustColor(this.customPrimaryColor, -10);
        const activeColor = this._adjustColor(this.customPrimaryColor, -20);

        root.style.setProperty('--custom-primary-hover', hoverColor);
        root.style.setProperty('--custom-primary-active', activeColor);
    }

    /**
     * Rengi koyulaştır veya açıklaştır
     * @param {string} color - Hex renk
     * @param {number} percent - Yüzde (negatif = koyulaştır)
     * @returns {string} Yeni renk
     * @private
     */
    _adjustColor(color, percent) {
        const num = parseInt(color.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = Math.max(0, Math.min(255, (num >> 16) + amt));
        const G = Math.max(0, Math.min(255, ((num >> 8) & 0x00FF) + amt));
        const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
        return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
    }

    /**
     * Hex renkten RGB değerlerini çıkar
     * @param {string} hex - Hex renk
     * @returns {Object} {r, g, b}
     * @private
     */
    _hexToRgb(hex) {
        if (!hex || typeof hex !== 'string') return { r: 59, g: 130, b: 246 }; // default blue

        // Short form (#fff) destekle
        let hexStr = hex.replace('#', '');
        if (hexStr.length === 3) {
            hexStr = hexStr[0] + hexStr[0] + hexStr[1] + hexStr[1] + hexStr[2] + hexStr[2];
        }

        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hexStr);
        if (result) {
            return {
                r: parseInt(result[1], 16),
                g: parseInt(result[2], 16),
                b: parseInt(result[3], 16)
            };
        }

        return { r: 59, g: 130, b: 246 }; // default blue
    }

    /**
     * Logo görünümünü tema için güncelle
     * @param {string} themeId - Tema ID'si
     * @private
     */
    _updateLogoForTheme(themeId) {
        const theme = THEMES[themeId];
        const logo = document.querySelector('.brandLogo');

        if (logo) {
            if (theme && theme.isDark) {
                logo.classList.add('theme-dark-logo');
            } else {
                logo.classList.remove('theme-dark-logo');
            }
        }
    }

    /**
     * Dinleyicileri bilgilendir
     * @param {string} event - Olay adı
     * @param {Object} data - Olay verisi
     * @private
     */
    _notifyListeners(event, data) {
        this.listeners.forEach(callback => {
            try {
                callback(event, data);
            } catch (e) {
                console.warn('ThemeManager: Dinleyici hatası', e);
            }
        });
    }

    // ===== PUBLIC API =====

    /**
     * Temayı değiştir
     * @param {string} themeId - Tema ID'si
     * @returns {boolean} Başarılı mı
     */
    setTheme(themeId) {
        if (!THEMES[themeId]) {
            console.warn(`ThemeManager: Geçersiz tema "${themeId}"`);
            return false;
        }

        ThemeStorage.setTheme(themeId);
        this._applyTheme(themeId);

        console.log(`ThemeManager: Tema değiştirildi: ${themeId}`);
        return true;
    }

    /**
     * Aktif temayı al
     * @returns {string} Tema ID'si
     */
    getTheme() {
        return this.currentTheme;
    }

    /**
     * Aktif temanın verilerini al
     * @returns {Object} Tema verisi
     */
    getThemeData() {
        return THEMES[this.currentTheme] || THEMES[DEFAULT_THEME];
    }

    /**
     * Tüm temaları al
     * @returns {Object} Tema sözlüğü
     */
    getAllThemes() {
        return THEMES;
    }

    /**
     * Özel accent rengini ayarla
     * @param {string} color - Hex renk kodu (#RRGGBB)
     * @returns {boolean} Başarılı mı
     */
    setCustomPrimaryColor(color) {
        // Renk formatını doğrula
        if (!/^#[0-9A-Fa-f]{6}$/.test(color)) {
            console.warn('ThemeManager: Geçersiz renk formatı');
            return false;
        }

        this.customPrimaryColor = color;
        ThemeStorage.setCustomPrimaryColor(color);
        this._applyCustomPrimaryColor();

        this._notifyListeners('customColorChanged', { color });

        return true;
    }

    /**
     * Özel accent rengini al
     * @returns {string|null} Hex renk kodu veya null
     */
    getCustomPrimaryColor() {
        return this.customPrimaryColor;
    }

    /**
     * Özel accent rengini sıfırla
     */
    resetCustomPrimaryColor() {
        this.customPrimaryColor = null;
        ThemeStorage.removeCustomPrimaryColor();

        const root = document.documentElement;
        root.style.removeProperty('--custom-primary-color');
        root.style.removeProperty('--custom-primary');
        root.style.removeProperty('--custom-primary-hover');
        root.style.removeProperty('--custom-primary-active');

        this._notifyListeners('customColorReset', {});
    }

    /**
     * Varsayılanlara sıfırla
     */
    resetToDefaults() {
        ThemeStorage.clearTheme();
        this.currentTheme = DEFAULT_THEME;
        this.customPrimaryColor = null;
        this._applyTheme(DEFAULT_THEME);

        // Özel renk özelliklerini kaldır
        const root = document.documentElement;
        root.style.removeProperty('--custom-primary-color');
        root.style.removeProperty('--custom-primary');
        root.style.removeProperty('--custom-primary-hover');
        root.style.removeProperty('--custom-primary-active');

        this._notifyListeners('themeReset', {});
    }

    /**
     * Tema değişikliği dinleyicisi ekle
     * @param {Function} callback - Callback fonksiyonu (event, data)
     * @returns {Function} Dinleyiciyi kaldırma fonksiyonu
     */
    addListener(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }

    /**
     * Koyu mod açık mı? (Geriye dönük uyumluluk)
     * @returns {boolean}
     */
    isDarkMode() {
        const theme = THEMES[this.currentTheme];
        return theme ? theme.isDark : false;
    }

    /**
     * Koyu modu aç/kapat (Geriye dönük uyumluluk)
     * @returns {boolean} Yeni durum
     */
    toggleDarkMode() {
        const newTheme = this.isDarkMode() ? 'light' : 'dark';
        this.setTheme(newTheme);
        return this.isDarkMode();
    }
}

// Singleton instance
let themeManagerInstance = null;

/**
 * Theme Manager singleton'ını al
 * @returns {ThemeManager}
 */
export function getThemeManager() {
    if (!themeManagerInstance) {
        themeManagerInstance = new ThemeManager();
    }
    return themeManagerInstance;
}

/**
 * Global erişim için window'a ekle (geriye dönük uyumluluk)
 */
if (typeof window !== 'undefined') {
    window.getThemeManager = getThemeManager;
}
