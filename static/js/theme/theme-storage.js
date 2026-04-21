/**
 * Theme Storage - LocalStorage Yönetimi
 * Netmon Proje Takip - Theme System
 * 
 * Bu dosya tema tercihlerinin tarayıcıda saklanmasını yönetir.
 */

import { STORAGE_KEY, CUSTOM_COLOR_KEY, THEME_SETTINGS_KEY, DEFAULT_THEME } from './theme-data.js';

// Storage namespace
const NAMESPACE = 'netmon_theme';

/**
 * Theme Storage Manager
 * Tema tercihlerini LocalStorage'da yönetir
 */
export class ThemeStorage {

    /**
     * Namespace ile anahtar oluştur
     * @param {string} key - Anahtar adı
     * @returns {string} Namespace'li anahtar
     */
    static _key(key) {
        return `${NAMESPACE}_${key}`;
    }

    /**
     * Kaydedilmiş temayı al
     * @returns {string|null} Tema ID'si veya null
     */
    static getTheme() {
        try {
            // Önce yeni namespace'li anahtarı kontrol et
            let theme = localStorage.getItem(this._key(STORAGE_KEY));

            // Yoksa eski anahtarı kontrol et (geriye dönük uyumluluk)
            if (!theme) {
                const oldDarkMode = localStorage.getItem('darkMode');
                if (oldDarkMode === 'true') {
                    theme = 'dark';
                    // Yeni formata migrate et
                    this.setTheme('dark');
                }
            }

            return theme || null;
        } catch (e) {
            console.warn('ThemeStorage: Tema okunurken hata', e);
            return null;
        }
    }

    /**
     * Temayı kaydet
     * @param {string} themeId - Tema ID'si
     * @returns {boolean} Başarılı mı
     */
    static setTheme(themeId) {
        try {
            localStorage.setItem(this._key(STORAGE_KEY), themeId);

            // Geriye dönük uyumluluk için eski anahtarı da güncelle
            if (themeId === 'dark' || themeId === 'pure-black') {
                localStorage.setItem('darkMode', 'true');
            } else {
                localStorage.setItem('darkMode', 'false');
            }

            return true;
        } catch (e) {
            console.warn('ThemeStorage: Tema kaydedilirken hata', e);
            return false;
        }
    }

    /**
     * Özel accent rengini al
     * @returns {string|null} Hex renk kodu veya null
     */
    static getCustomPrimaryColor() {
        try {
            return localStorage.getItem(this._key(CUSTOM_COLOR_KEY)) || null;
        } catch (e) {
            console.warn('ThemeStorage: Özel renk okunurken hata', e);
            return null;
        }
    }

    /**
     * Özel accent rengini kaydet
     * @param {string} color - Hex renk kodu
     * @returns {boolean} Başarılı mı
     */
    static setCustomPrimaryColor(color) {
        try {
            localStorage.setItem(this._key(CUSTOM_COLOR_KEY), color);
            return true;
        } catch (e) {
            console.warn('ThemeStorage: Özel renk kaydedilirken hata', e);
            return false;
        }
    }

    /**
     * Özel accent rengini sil
     * @returns {boolean} Başarılı mı
     */
    static removeCustomPrimaryColor() {
        try {
            localStorage.removeItem(this._key(CUSTOM_COLOR_KEY));
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Tüm tema ayarlarını al
     * @returns {Object|null} Ayarlar objesi veya null
     */
    static getSettings() {
        try {
            const data = localStorage.getItem(this._key(THEME_SETTINGS_KEY));
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.warn('ThemeStorage: Ayarlar okunurken hata', e);
            return null;
        }
    }

    /**
     * Tüm tema ayarlarını kaydet
     * @param {Object} settings - Ayarlar objesi
     * @returns {boolean} Başarılı mı
     */
    static setSettings(settings) {
        try {
            const settingsData = {
                ...settings,
                lastUpdated: new Date().toISOString()
            };
            localStorage.setItem(this._key(THEME_SETTINGS_KEY), JSON.stringify(settingsData));
            return true;
        } catch (e) {
            console.warn('ThemeStorage: Ayarlar kaydedilirken hata', e);
            return false;
        }
    }

    /**
     * Tüm tema ayarlarını temizle
     * @returns {boolean} Başarılı mı
     */
    static clearTheme() {
        try {
            localStorage.removeItem(this._key(STORAGE_KEY));
            localStorage.removeItem(this._key(CUSTOM_COLOR_KEY));
            localStorage.removeItem(this._key(THEME_SETTINGS_KEY));
            localStorage.removeItem('darkMode'); // Eski anahtar
            return true;
        } catch (e) {
            console.warn('ThemeStorage: Temizleme sırasında hata', e);
            return false;
        }
    }

    /**
     * Ayarları dışa aktar (yedekleme için)
     * @returns {Object} Dışa aktarılan ayarlar
     */
    static exportSettings() {
        return {
            theme: this.getTheme(),
            customPrimaryColor: this.getCustomPrimaryColor(),
            settings: this.getSettings(),
            exportedAt: new Date().toISOString()
        };
    }

    /**
     * Ayarları içe aktar (geri yükleme için)
     * @param {Object} data - İçe aktarılacak ayarlar
     * @returns {boolean} Başarılı mı
     */
    static importSettings(data) {
        try {
            if (data.theme) {
                this.setTheme(data.theme);
            }
            if (data.customPrimaryColor) {
                this.setCustomPrimaryColor(data.customPrimaryColor);
            }
            if (data.settings) {
                this.setSettings(data.settings);
            }
            return true;
        } catch (e) {
            console.warn('ThemeStorage: İçe aktarma sırasında hata', e);
            return false;
        }
    }

    /**
     * LocalStorage kullanılabilir mi kontrol et
     * @returns {boolean} Kullanılabilir mi
     */
    static isAvailable() {
        try {
            const testKey = `${NAMESPACE}_test`;
            localStorage.setItem(testKey, 'test');
            localStorage.removeItem(testKey);
            return true;
        } catch (e) {
            return false;
        }
    }
}
