/**
 * Theme Data - Tema Tanımları
 * Netmon Proje Takip - Theme System
 * 
 * Bu dosya tüm tema tanımlarını ve renk paletlerini içerir.
 */

// Tema tanımları
export const THEMES = {
    light: {
        id: 'light',
        name: 'Açık',
        nameEn: 'Light',
        description: 'Temiz ve profesyonel açık tema',
        icon: 'sun',
        isDark: false,
        colors: {
            bgPrimary: '#f3f6fc',
            bgSecondary: '#ffffff',
            bgTertiary: '#f8fafc',
            textPrimary: '#1e293b',
            textSecondary: '#64748b',
            accentPrimary: '#3b82f6',
            accentSecondary: '#6366f1',
            border: '#e2e8f0',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(255, 255, 255, 0.5)'
        }
    },

    dark: {
        id: 'dark',
        name: 'Koyu',
        nameEn: 'Dark',
        description: 'Göz dostu koyu tema',
        icon: 'moon',
        isDark: true,
        colors: {
            bgPrimary: '#0f172a',
            bgSecondary: '#1e293b',
            bgTertiary: '#334155',
            textPrimary: '#f1f5f9',
            textSecondary: '#94a3b8',
            accentPrimary: '#60a5fa',
            accentSecondary: '#818cf8',
            border: '#334155',
            glassBg: 'rgba(30, 41, 59, 0.85)',
            glassBorder: 'rgba(255, 255, 255, 0.1)'
        }
    },

    'pure-black': {
        id: 'pure-black',
        name: 'Saf Siyah',
        nameEn: 'Pure Black',
        description: 'OLED ekranlar için saf siyah',
        icon: 'moon-stars',
        isDark: true,
        colors: {
            bgPrimary: '#000000',
            bgSecondary: '#0a0a0a',
            bgTertiary: '#171717',
            textPrimary: '#ffffff',
            textSecondary: '#a3a3a3',
            accentPrimary: '#3b82f6',
            accentSecondary: '#6366f1',
            border: '#262626',
            glassBg: 'rgba(0, 0, 0, 0.9)',
            glassBorder: 'rgba(255, 255, 255, 0.08)'
        }
    },

    'pure-white': {
        id: 'pure-white',
        name: 'Saf Beyaz',
        nameEn: 'Pure White',
        description: 'Yüksek kontrast beyaz tema',
        icon: 'sun-bright',
        isDark: false,
        colors: {
            bgPrimary: '#ffffff',
            bgSecondary: '#ffffff',
            bgTertiary: '#f5f5f5',
            textPrimary: '#171717',
            textSecondary: '#525252',
            accentPrimary: '#2563eb',
            accentSecondary: '#4f46e5',
            border: '#e5e5e5',
            glassBg: 'rgba(255, 255, 255, 0.95)',
            glassBorder: 'rgba(0, 0, 0, 0.05)'
        }
    },

    ocean: {
        id: 'ocean',
        name: 'Okyanus',
        nameEn: 'Ocean',
        description: 'Sakinleştirici mavi tonlar',
        icon: 'droplet',
        isDark: false,
        colors: {
            bgPrimary: '#f0f9ff',
            bgSecondary: '#ffffff',
            bgTertiary: '#e0f2fe',
            textPrimary: '#0c4a6e',
            textSecondary: '#0369a1',
            accentPrimary: '#0284c7',
            accentSecondary: '#0891b2',
            border: '#bae6fd',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(186, 230, 253, 0.5)'
        }
    },

    forest: {
        id: 'forest',
        name: 'Orman',
        nameEn: 'Forest',
        description: 'Doğal yeşil tonlar',
        icon: 'tree',
        isDark: false,
        colors: {
            bgPrimary: '#f0fdf4',
            bgSecondary: '#ffffff',
            bgTertiary: '#dcfce7',
            textPrimary: '#14532d',
            textSecondary: '#166534',
            accentPrimary: '#16a34a',
            accentSecondary: '#22c55e',
            border: '#bbf7d0',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(187, 247, 208, 0.5)'
        }
    },

    sunset: {
        id: 'sunset',
        name: 'Gün Batımı',
        nameEn: 'Sunset',
        description: 'Sıcak turuncu-pembe tonlar',
        icon: 'sunset',
        isDark: false,
        colors: {
            bgPrimary: '#fff7ed',
            bgSecondary: '#ffffff',
            bgTertiary: '#ffedd5',
            textPrimary: '#7c2d12',
            textSecondary: '#c2410c',
            accentPrimary: '#ea580c',
            accentSecondary: '#f97316',
            border: '#fed7aa',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(254, 215, 170, 0.5)'
        }
    },

    purple: {
        id: 'purple',
        name: 'Mor',
        nameEn: 'Purple',
        description: 'Modern mor vurgular',
        icon: 'sparkles',
        isDark: false,
        colors: {
            bgPrimary: '#faf5ff',
            bgSecondary: '#ffffff',
            bgTertiary: '#f3e8ff',
            textPrimary: '#581c87',
            textSecondary: '#7e22ce',
            accentPrimary: '#9333ea',
            accentSecondary: '#a855f7',
            border: '#e9d5ff',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(233, 213, 255, 0.5)'
        }
    },

    // ========== YENİ TEMALAR ==========

    red: {
        id: 'red',
        name: 'Kırmızı',
        nameEn: 'Red',
        description: 'Enerjik kırmızı tema',
        icon: 'flame',
        isDark: false,
        colors: {
            bgPrimary: '#fef2f2',
            bgSecondary: '#ffffff',
            bgTertiary: '#fee2e2',
            textPrimary: '#7f1d1d',
            textSecondary: '#b91c1c',
            accentPrimary: '#ef4444',
            accentSecondary: '#dc2626',
            border: '#fecaca',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(254, 202, 202, 0.5)'
        }
    },

    red_dark: {
        id: 'red_dark',
        name: 'Koyu Kırmızı',
        nameEn: 'Dark Red',
        description: 'Koyu kırmızı tema',
        icon: 'flame',
        isDark: true,
        colors: {
            bgPrimary: '#7f1d1d',
            bgSecondary: '#991b1b',
            bgTertiary: '#b91c1c',
            textPrimary: '#fef2f2',
            textSecondary: '#fecaca',
            accentPrimary: '#f87171',
            accentSecondary: '#ef4444',
            border: '#7f1d1d',
            glassBg: 'rgba(153, 27, 27, 0.85)',
            glassBorder: 'rgba(254, 202, 202, 0.1)'
        }
    },

    yellow: {
        id: 'yellow',
        name: 'Sarı',
        nameEn: 'Yellow',
        description: 'Enerjik sarı tema',
        icon: 'sun',
        isDark: false,
        colors: {
            bgPrimary: '#fefce8',
            bgSecondary: '#ffffff',
            bgTertiary: '#fef9c3',
            textPrimary: '#713f12',
            textSecondary: '#a16207',
            accentPrimary: '#eab308',
            accentSecondary: '#ca8a04',
            border: '#fde047',
            glassBg: 'rgba(255, 255, 255, 0.85)',
            glassBorder: 'rgba(253, 224, 71, 0.5)'
        }
    },

    navy: {
        id: 'navy',
        name: 'Lacivert',
        nameEn: 'Navy',
        description: 'Profesyonel lacivert tema',
        icon: 'anchor',
        isDark: true,
        colors: {
            bgPrimary: '#0f172a',
            bgSecondary: '#1e3a8a',
            bgTertiary: '#1e40af',
            textPrimary: '#eff6ff',
            textSecondary: '#bfdbfe',
            accentPrimary: '#3b82f6',
            accentSecondary: '#60a5fa',
            border: '#1e3a8a',
            glassBg: 'rgba(30, 58, 138, 0.85)',
            glassBorder: 'rgba(191, 219, 254, 0.1)'
        }
    }
};

// Varsayılan tema
export const DEFAULT_THEME = 'light';

// LocalStorage anahtarları
export const STORAGE_KEY = 'appTheme';
export const CUSTOM_COLOR_KEY = 'appCustomPrimary';
export const THEME_SETTINGS_KEY = 'themeSettings';

// Preset renk seçenekleri
export const COLOR_PRESETS = [
    { name: 'Mavi', color: '#3b82f6' },
    { name: 'İndigo', color: '#6366f1' },
    { name: 'Mor', color: '#8b5cf6' },
    { name: 'Pembe', color: '#ec4899' },
    { name: 'Kırmızı', color: '#ef4444' },
    { name: 'Turuncu', color: '#f97316' },
    { name: 'Sarı', color: '#eab308' },
    { name: 'Yeşil', color: '#22c55e' },
    { name: 'Turkuaz', color: '#14b8a6' },
    { name: 'Cyan', color: '#06b6d4' }
];

// Tema listesini dizi olarak al
export function getThemeList() {
    return Object.values(THEMES);
}

// Tema ID'sine göre tema al
export function getThemeById(themeId) {
    return THEMES[themeId] || THEMES[DEFAULT_THEME];
}

// Koyu temalar listesi
export function getDarkThemes() {
    return Object.values(THEMES).filter(theme => theme.isDark);
}

// Açık temalar listesi
export function getLightThemes() {
    return Object.values(THEMES).filter(theme => !theme.isDark);
}
