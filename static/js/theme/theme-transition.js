/**
 * Theme Transition Manager - Yumuşak Geçiş Yönetimi
 * Netmon Proje Takip - Theme System
 * 
 * Bu dosya tema değişikliklerinde yumuşak geçişleri yönetir.
 */

/**
 * Theme Transition Manager
 * Tema değişikliklerinde yumuşak animasyonlar sağlar
 */
export class ThemeTransition {
    constructor() {
        this.isTransitioning = false;
        this.transitionDuration = 300; // ms
    }

    /**
     * Geçiş için hazırlık yap (geçişleri devre dışı bırak)
     * @param {HTMLElement} element - Hedef element (varsayılan: html)
     */
    prepareTransition(element = document.documentElement) {
        this.isTransitioning = true;
        element.classList.add('theme-transitioning');
    }

    /**
     * Geçişi uygula (geçişleri yeniden aktif et)
     * @param {HTMLElement} element - Hedef element (varsayılan: html)
     * @returns {Promise} Geçiş tamamlandığında resolve olur
     */
    async applyTransition(element = document.documentElement) {
        return new Promise((resolve) => {
            // Reflow zorla
            void element.offsetWidth;

            // Geçişleri aktif et
            element.classList.remove('theme-transitioning');

            // Geçiş tamamlanınca
            setTimeout(() => {
                this.isTransitioning = false;
                resolve();
            }, this.transitionDuration);
        });
    }

    /**
     * Geçişleri devre dışı bırak
     * @param {HTMLElement} element - Hedef element (varsayılan: html)
     */
    disableTransitions(element = document.documentElement) {
        element.classList.add('theme-transition-disabled');
    }

    /**
     * Geçişleri aktif et
     * @param {HTMLElement} element - Hedef element (varsayılan: html)
     */
    enableTransitions(element = document.documentElement) {
        element.classList.remove('theme-transition-disabled');
    }

    /**
     * Geçiş süresini ayarla
     * @param {number} duration - Süre (ms)
     */
    setDuration(duration) {
        this.transitionDuration = duration;
        document.documentElement.style.setProperty('--theme-transition-duration', `${duration}ms`);
    }

    /**
     * Geçiş devam ediyor mu?
     * @returns {boolean}
     */
    isInProgress() {
        return this.isTransitioning;
    }

    /**
     * Sayfa yüklenirken FOUC (Flash of Unstyled Content) önle
     * Bu fonksiyon inline script olarak head'de çağrılmalı
     */
    static preventFOUC() {
        try {
            // LocalStorage'dan tema ve özel rengi al
            const savedTheme = localStorage.getItem('netmon_theme_appTheme');
            const customColor = localStorage.getItem('netmon_theme_appCustomPrimary');

            // Eski darkMode anahtarını kontrol et
            const oldDarkMode = localStorage.getItem('darkMode');

            // Temayı belirle
            let theme = savedTheme;
            if (!theme && oldDarkMode === 'true') {
                theme = 'dark';
            }

            // Tema varsa uygula
            if (theme) {
                document.documentElement.setAttribute('data-theme', theme);

                // Geriye dönük uyumluluk için dark-mode class'ını da ekle
                if (theme === 'dark' || theme === 'pure-black') {
                    document.documentElement.classList.add('dark-mode');
                }
            }

            // Özel renk varsa uygula
            if (customColor) {
                document.documentElement.style.setProperty('--custom-primary-color', customColor);
                document.documentElement.style.setProperty('--custom-primary', customColor);
            }
        } catch (e) {
            // Sessizce hata yut - kritik değil
            console.warn('Theme FOUC prevention failed:', e);
        }
    }

    /**
     * FOUC önleme script'ini string olarak al (inline script için)
     * @returns {string} Inline script kodu
     */
    static getFOUCPreventionScript() {
        return `(function(){try{var t=localStorage.getItem('netmon_theme_appTheme'),d=localStorage.getItem('darkMode'),c=localStorage.getItem('netmon_theme_appCustomPrimary');if(!t&&d==='true')t='dark';if(t){document.documentElement.setAttribute('data-theme',t);if(t==='dark'||t==='pure-black')document.documentElement.classList.add('dark-mode');}if(c){document.documentElement.style.setProperty('--custom-primary-color',c);document.documentElement.style.setProperty('--custom-primary',c);}}catch(e){}})();`;
    }
}
