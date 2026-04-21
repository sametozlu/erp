
/* Realtime.js - Plan Sayfası Gerçek Zamanlı Özellikler */

if (typeof io === 'undefined') {
    window.__socket = null;
}

const socket = typeof io !== 'undefined' ? io({
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: Infinity
}) : null;
window.__socket = socket;

const RealtimeState = {
    socket: socket,
    activeContextCell: null,
    clipboardData: null, // Çoklu yapıştırma için clipboard
    settings: {
        fullscreen_shortcut: 'F11',
        theme: 'light',
        notifications_enabled: true,
        sound_enabled: true,
        ptt_key: 'Space',
        auto_play_voice: true,
        ptt_start_message: '🎤 Konuşma başladı...',
        ptt_end_message: '✅ Mesaj gönderildi',
        show_message_notifications: true,
        show_voice_notifications: true
    },
    // PTT Kayıt Durumu
    ptt: {
        isRecording: false,
        mediaRecorder: null,
        audioChunks: [],
        stream: null
    }
};

// Bildirim sesi
let notificationSound = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!socket) return;
    initSocketEvents();
    initContextMenu();
    loadUserSettings();
    updateCellTitles();
    initTableFilters();
    initNotifications();
    initPTT();

    // Global fonksiyonlar
    window.RealtimeFeatures = {
        state: RealtimeState,
        saveSettings: saveSettings,
        showSettingsModal: showSettingsModal,
        toggleFullscreen: toggleFullscreen,
        handleContextAction: handleContextAction,
        refreshPage: () => window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload(),
        showCancelModal: showCancelModal,
        showMoveModal: showMoveModal,
        showOvertimeModal: showOvertimeModal,
        startPTT: startPTTRecording,
        stopPTT: stopPTTRecording,
        togglePTT: togglePTTRecording
    };

    // Mesai silme fonksiyonu global
    window.deleteOvertime = deleteOvertime;

    // PTT fonksiyonları global
    window.startPTTRecording = startPTTRecording;
    window.stopPTTRecording = stopPTTRecording;
    window.togglePTTRecording = togglePTTRecording;

    // Tıklama ile menü kapatma
    document.addEventListener('click', (e) => {
        const menu = document.getElementById('dynamicContextMenu');
        if (menu && !menu.contains(e.target)) {
            menu.style.display = 'none';
        }

        const modal = document.getElementById('dynamicModal');
        if (modal && e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // Global klavye olayları
    document.addEventListener('keydown', handleGlobalKeydown);
    document.addEventListener('keyup', handleGlobalKeyup);
});

// ================ BİLDİRİM SİSTEMİ ================

function initNotifications() {
    // Güvenli bağlam kontrolü
    const isSecureContext = window.isSecureContext;
    const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';

    if (!isSecureContext && !isLocalhost) {
        console.warn('⚠️ HTTP ortamında bildirimler kısıtlı olabilir. HTTPS veya tarayıcı ayarları gerekebilir.');
    }

    // Bildirim izni al
    if ('Notification' in window) {
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                console.log('Bildirim izni:', permission);
                if (permission === 'denied' && !isSecureContext && !isLocalhost) {
                    console.warn('HTTP ortamında bildirim izni alınamıyor. chrome://flags → "Insecure origins treated as secure" ayarını kontrol edin.');
                }
            }).catch(err => {
                console.warn('Bildirim izni istenemedi (HTTP ortamı olabilir):', err);
            });
        }
    } else {
        console.warn('Bu tarayıcı web bildirimlerini desteklemiyor');
    }

    // Bildirim sesi yükle (dosya yoksa Web Audio API ile beep oluştur)
    try {
        notificationSound = new Audio('/static/sounds/notification.mp3');
        notificationSound.volume = 0.5;
        notificationSound.preload = 'auto';

        // Preload kontrolü - dosya yoksa Web Audio API fallback
        notificationSound.addEventListener('error', () => {
            console.log('Bildirim ses dosyası yüklenemedi, Web Audio API ile beep kullanılacak');
            notificationSound = null;
            // Web Audio API fallback hazırla
            RealtimeState.useBeepFallback = true;
        });

        // Başarılı yükleme
        notificationSound.addEventListener('canplaythrough', () => {
            console.log('Bildirim sesi yüklendi');
            RealtimeState.useBeepFallback = false;
        });
    } catch (e) {
        notificationSound = null;
        RealtimeState.useBeepFallback = true;
    }
}

// Web Audio API ile beep sesi çal (fallback)
function playBeepSound(frequency = 800, duration = 150, volume = 0.3) {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.frequency.value = frequency;
        oscillator.type = 'sine';
        gainNode.gain.value = volume;

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + duration / 1000);

        // Cleanup
        oscillator.onended = () => {
            audioContext.close();
        };
    } catch (e) {
        console.warn('Beep sesi çalınamadı:', e);
    }
}

// Bildirim sesi çal (mp3 veya beep fallback)
function playNotificationSound() {
    if (notificationSound && !RealtimeState.useBeepFallback) {
        notificationSound.currentTime = 0;
        notificationSound.play().catch(() => {
            // MP3 çalmazsa beep kullan
            playBeepSound();
        });
    } else {
        playBeepSound();
    }
}


function showNotification(title, body, options = {}) {
    // Ayar kontrolü
    if (!RealtimeState.settings.notifications_enabled) return;

    // Tarayıcı bildirimi
    if ('Notification' in window && Notification.permission === 'granted') {
        const notification = new Notification(title, {
            body: body,
            icon: '/static/img/logo.png',
            badge: '/static/img/logo.png',
            tag: options.tag || 'saha-notification',
            requireInteraction: options.requireInteraction || false,
            ...options
        });

        // Tıklanınca odaklan
        notification.onclick = () => {
            window.focus();
            notification.close();
        };

        // Otomatik kapat
        setTimeout(() => notification.close(), 5000);
    }

    // Ses çal (mp3 veya beep fallback)
    if (RealtimeState.settings.sound_enabled) {
        playNotificationSound();
    }

    // Toast da göster
    showToast(`${title}: ${body}`, options.type || 'info');
}

// ================ BAS-KONUŞ (PTT) SİSTEMİ ================

function initPTT() {
    console.log('PTT sistemi başlatıldı');

    // Ayar kontrolü - Varsayılan: Kapalı (Kullanıcı açmalı)
    // localStorage'da 'pttEnabled' === 'true' ise açık.
    const isPttEnabled = localStorage.getItem('pttEnabled') === 'true';

    // State güncelle
    if (RealtimeState.settings) {
        RealtimeState.settings.ptt_enabled = isPttEnabled;
    }

    // Görünürlük ayarı
    const pttBtn = document.getElementById('pttButton');
    // Container'ı bulmaya çalış (genelde pttBtn'u saran div)
    // Eğer pttContainer id'li bir element varsa onu kullan, yoksa butonun kendisini gizle
    const pttContainer = document.getElementById('pttContainer') || (pttBtn ? pttBtn.parentElement : null);

    if (pttContainer && pttContainer.id === 'pttContainer') {
        pttContainer.style.display = isPttEnabled ? 'flex' : 'none'; // Genelde flex kullanılır
    } else if (pttBtn) {
        pttBtn.style.display = isPttEnabled ? 'inline-flex' : 'none';
        // Ses geçmişi vb varsa onları da gizlemeli (pttContainer kullanılması daha iyi)
    }

    // PTT butonu varsa event ekle
    if (pttBtn) {
        pttBtn.addEventListener('mousedown', startPTTRecording);
        pttBtn.addEventListener('mouseup', stopPTTRecording);
        pttBtn.addEventListener('mouseleave', stopPTTRecording);

        // Mobil için touch events
        pttBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startPTTRecording();
        });
        pttBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopPTTRecording();
        });
    }
}

async function startPTTRecording() {
    if (RealtimeState.ptt.isRecording) return;

    // Ayarlardan kontrol et
    const isPttEnabled = localStorage.getItem('pttEnabled') === 'true';
    if (!isPttEnabled) {
        // Sadece kullanıcıya bir kere veya konsola log düşebiliriz, 
        // ya da sessizce return edebiliriz. 
        // Kullanıcı butona bastıysa uyarı vermek mantıklı.
        console.log('PTT devre disi (Ayarlardan kapali)');
        // Opsiyonel: showToast('Bas Konuş özelliği ayarlardan kapalı.', 'info'); 
        // Kullanıcı sürekli Space'e basıyorsa toast spam olabilir, o yüzden sadece buton etkileşimi için toast verilebilir.
        // Ancak bu fonksiyon hem klavye hem buton için çağrılıyor.
        // Şimdilik sessizce return edelim veya sadece konsola yazalım.
        return;
    }

    // Güvenli bağlam kontrolü (HTTPS veya localhost gerekli)
    const isSecureContext = window.isSecureContext;
    const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';

    if (!isSecureContext && !isLocalhost) {
        console.warn('Güvenli bağlam değil - mikrofon erişimi engellenebilir');
        showToast('⚠️ HTTP üzerinden mikrofon erişimi kısıtlı olabilir. Tarayıcı ayarlarından izin vermeniz gerekebilir.', 'warning');
    }

    // mediaDevices API kontrolü
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('MediaDevices API desteklenmiyor');
        showToast('❌ Bu tarayıcı ses kaydını desteklemiyor. Chrome veya Firefox kullanın.', 'error');
        showNotification('Desteklenmeyen Tarayıcı',
            'Ses kaydı için Chrome, Firefox veya Edge kullanın.',
            { type: 'error' });
        return;
    }

    try {
        // Mikrofon izni al ve stream başlat
        console.log('Mikrofon izni isteniyor...');
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 44100
            }
        });
        console.log('Mikrofon izni alındı, stream aktif');

        RealtimeState.ptt.stream = stream;
        RealtimeState.ptt.audioChunks = [];

        // MediaRecorder oluştur - opus codec daha iyi uyumluluk
        let mimeType = 'audio/webm;codecs=opus';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = 'audio/webm';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/ogg;codecs=opus';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = ''; // Tarayıcı varsayılanı
                }
            }
        }

        const mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
        console.log('MediaRecorder mimeType:', mediaRecorder.mimeType);


        RealtimeState.ptt.mediaRecorder = mediaRecorder;

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                RealtimeState.ptt.audioChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = () => {
            sendVoiceMessage();
        };

        mediaRecorder.start(100); // Her 100ms'de data al
        RealtimeState.ptt.isRecording = true;

        // Görsel gösterge
        showPTTIndicator(RealtimeState.settings.ptt_start_message);

        // PTT butonunu güncelle
        const pttBtn = document.getElementById('pttButton');
        if (pttBtn) {
            pttBtn.classList.add('recording');
            pttBtn.innerHTML = '🔴 Kayıt...';
        }

        console.log('PTT kayıt başladı');

    } catch (err) {
        console.error('Mikrofon erişim hatası:', err);

        // HTTP kontrolü
        const isInsecure = !window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1';

        // Kullanıcıya yardımcı mesaj
        if (err.name === 'NotAllowedError') {
            if (isInsecure) {
                showToast('❌ HTTP üzerinden mikrofon izni verilemiyor. Tarayıcı ayarlarından bu siteyi "güvensiz kaynakları güvenli say" listesine ekleyin.', 'error');
                showNotification('HTTPS veya Tarayıcı Ayarı Gerekli',
                    `Chrome: chrome://flags → "Insecure origins treated as secure" → ${location.origin} ekleyin`,
                    { type: 'error', requireInteraction: true });
            } else {
                showToast('❌ Mikrofon izni verilmedi. Adres çubuğundaki 🔒 simgesine tıklayıp mikrofon iznini etkinleştirin.', 'error');
                showNotification('Mikrofon İzni Gerekli',
                    'Tarayıcı ayarlarından mikrofon iznini etkinleştirin.',
                    { type: 'error' });
            }
        } else if (err.name === 'NotFoundError') {
            showToast('❌ Mikrofon bulunamadı. Cihazınızda mikrofon bağlı ve çalışıyor mu?', 'error');
        } else if (err.name === 'NotReadableError') {
            showToast('❌ Mikrofona erişilemiyor. Başka bir uygulama kullanıyor olabilir.', 'error');
        } else if (err.name === 'TypeError') {
            showToast('❌ Güvenli bağlam (HTTPS) gerekli. HTTP üzerinde mikrofon desteklenmiyor.', 'error');
        } else {
            showToast('Mikrofon erişimi başarısız: ' + err.message, 'error');
        }
    }
}

function stopPTTRecording() {
    if (!RealtimeState.ptt.isRecording) return;

    try {
        // Kaydı durdur
        if (RealtimeState.ptt.mediaRecorder && RealtimeState.ptt.mediaRecorder.state !== 'inactive') {
            RealtimeState.ptt.mediaRecorder.stop();
        }

        // Stream'i kapat
        if (RealtimeState.ptt.stream) {
            RealtimeState.ptt.stream.getTracks().forEach(track => track.stop());
            RealtimeState.ptt.stream = null;
        }

        RealtimeState.ptt.isRecording = false;

        // Görsel temizle
        hidePTTIndicator();

        // PTT butonunu güncelle
        const pttBtn = document.getElementById('pttButton');
        if (pttBtn) {
            pttBtn.classList.remove('recording');
            pttBtn.innerHTML = '🎤 Bas-Konuş';
        }

        console.log('PTT kayıt durdu');

    } catch (err) {
        console.error('PTT durdurma hatası:', err);
    }
}

function togglePTTRecording() {
    if (RealtimeState.ptt.isRecording) {
        stopPTTRecording();
    } else {
        startPTTRecording();
    }
}

async function sendVoiceMessage() {
    if (RealtimeState.ptt.audioChunks.length === 0) {
        console.log('Ses verisi yok');
        return;
    }

    try {
        const mimeType = RealtimeState.ptt.mediaRecorder?.mimeType || 'audio/webm';
        console.log('PTT: Audio chunks count:', RealtimeState.ptt.audioChunks.length);
        console.log('PTT: MIME type:', mimeType);

        // Audio blob oluştur
        const audioBlob = new Blob(RealtimeState.ptt.audioChunks, { type: mimeType });
        console.log('PTT: Blob size:', audioBlob.size, 'bytes');
        console.log('PTT: Blob type:', audioBlob.type);

        // Minimum süre kontrolü (500ms)
        if (audioBlob.size < 5000) {
            console.log('Ses çok kısa, gönderilmiyor');
            showToast('Ses çok kısa, lütfen daha uzun tutun', 'warning');
            return;
        }

        // ArrayBuffer kullanarak base64'e dönüştür (daha güvenilir)
        const arrayBuffer = await audioBlob.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);

        // WebM header kontrolü (ilk 4 byte: 1A 45 DF A3)
        const headerBytes = Array.from(uint8Array.slice(0, 4));
        console.log('PTT: First 4 bytes:', headerBytes.map(b => b.toString(16).padStart(2, '0')).join(' '));

        // Base64 encode
        let binary = '';
        const chunkSize = 8192;
        for (let i = 0; i < uint8Array.length; i += chunkSize) {
            const chunk = uint8Array.slice(i, i + chunkSize);
            binary += String.fromCharCode.apply(null, chunk);
        }
        const base64Audio = btoa(binary);

        console.log('PTT: Base64 length:', base64Audio.length);
        console.log('PTT: Base64 first 50 chars:', base64Audio.substring(0, 50));

        // Alıcı seçimini yeni yapıdan oku
        const recipient = window.currentPTTRecipient || { type: 'broadcast', id: 0, name: 'Herkese' };

        let toUserId = 0;
        let teamId = 0;

        if (recipient.type === 'user') {
            toUserId = recipient.id;
        }

        const response = await fetch('/api/voice/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                csrf_token: document.getElementById('csrfToken')?.value || '',
                audio_data: base64Audio,
                duration: audioBlob.size / 1000,
                to_user_id: toUserId,
                team_id: teamId
            })
        });

        const result = await response.json();
        console.log('PTT: Server response:', result);

        if (result.ok) {
            showPTTIndicator(RealtimeState.settings.ptt_end_message);
            setTimeout(hidePTTIndicator, 1500);
            showToast('Sesli mesaj gönderildi!', 'success');
        } else {
            showToast('Sesli mesaj gönderilemedi: ' + (result.error || 'Hata'), 'error');
        }

    } catch (err) {
        console.error('Ses gönderme hatası:', err);
        showToast('Sesli mesaj gönderilemedi: ' + err.message, 'error');
    }

    // Temizle
    RealtimeState.ptt.audioChunks = [];
}

// Sesli mesaj oynat (geliştirilmiş versiyon)
function playVoiceMessage(audioUrl) {
    if (!audioUrl) {
        console.error('Ses URL\'si boş');
        showToast('Ses dosyası bulunamadı', 'error');
        return;
    }

    console.log('Ses oynatılıyor:', audioUrl);

    const audio = new Audio(audioUrl);
    audio.volume = 0.8;
    audio.preload = 'auto';

    // Yükleme durumunu göster
    let loadingToastShown = false;
    const loadingTimeout = setTimeout(() => {
        loadingToastShown = true;
        showToast('Ses yükleniyor...', 'info');
    }, 500);

    // Yükleme hatası
    audio.addEventListener('error', (e) => {
        clearTimeout(loadingTimeout);
        console.error('Ses yüklenemedi:', e, audio.error);
        const errorMessage = audio.error ?
            `Kod: ${audio.error.code} - ${audio.error.message || 'Bilinmeyen hata'}` :
            'Ses dosyası yüklenemedi';
        showToast(`Ses oynatılamadı: ${errorMessage}`, 'error');
    });

    // Yükleme başarılı, oynat
    audio.addEventListener('canplaythrough', () => {
        clearTimeout(loadingTimeout);
        audio.play().then(() => {
            if (loadingToastShown) {
                showToast('Ses oynatılıyor...', 'success');
            }
        }).catch(err => {
            console.error('Ses oynatma hatası:', err);
            showToast('Ses oynatılamadı: Tarayıcı izni gerekli olabilir', 'error');
        });
    }, { once: true });

    // Ses bitti
    audio.addEventListener('ended', () => {
        console.log('Ses oynatma tamamlandı');
    });

    // Hemen yüklemeye başla
    audio.load();
}


// Klavye ile PTT
function handleGlobalKeyup(e) {
    // PTT tuşu bırakıldığında kayıt durdur
    const pttKey = RealtimeState.settings.ptt_key || 'Space';
    if (e.code === pttKey && RealtimeState.ptt.isRecording) {
        stopPTTRecording();
    }
}

// ================ KLAVYE OLAYLARI ================

function handleGlobalKeydown(e) {
    // PTT tuşu ile kayıt başlat
    const pttKey = RealtimeState.settings.ptt_key || 'Space';
    if (e.code === pttKey && !RealtimeState.ptt.isRecording) {
        // Input alanında değilse başlat
        const activeEl = document.activeElement;
        const isInputActive = activeEl && (
            activeEl.tagName === 'INPUT' ||
            activeEl.tagName === 'TEXTAREA' ||
            activeEl.isContentEditable
        );

        if (!isInputActive) {
            e.preventDefault();
            startPTTRecording();
        }
    }

    // ESC ile context menu kapat
    if (e.key === 'Escape') {
        const menu = document.getElementById('dynamicContextMenu');
        if (menu) {
            menu.style.display = 'none';
        }
        const modal = document.getElementById('dynamicModal');
        if (modal && modal.style.display !== 'none') {
            modal.style.display = 'none';
        }
    }

    // Tam ekran kısayolu
    const shortcut = RealtimeState.settings.fullscreen_shortcut || 'F11';
    if (e.key === shortcut || (shortcut === 'F11' && e.key === 'F11')) {
        if (shortcut !== 'F11') {
            e.preventDefault();
            toggleFullscreen();
        }
    }
}


// ================ TAM EKRAN (SADECE TABLO) ================

function toggleFullscreen() {
    toggleTableFullscreen();
}

function toggleTableFullscreen() {
    // Tablo wrapper elementini bul - birkaç fallback ile
    const tableWrap = document.querySelector('.jobTableWrapper') ||
        document.querySelector('.tablewrap') ||
        document.querySelector('#gridPlanContainer');
    if (!tableWrap) {
        showToast('Tablo bulunamadı', 'error');
        return;
    }

    if (!document.fullscreenElement) {
        // Tam ekrana girmeden önce stili kaydet
        tableWrap.dataset.prevMaxHeight = tableWrap.style.maxHeight || '';
        tableWrap.dataset.prevOverflow = tableWrap.style.overflow || '';
        tableWrap.dataset.prevBackground = tableWrap.style.background || '';

        tableWrap.requestFullscreen().then(() => {
            // Tam ekran stillerini uygula
            tableWrap.style.maxHeight = '100vh';
            tableWrap.style.overflow = 'auto';
            tableWrap.style.background = 'var(--card, #fff)';
            tableWrap.style.padding = '10px';
            showPTTIndicator('⛶ Tablo Tam Ekran - ESC ile çık');
        }).catch(err => {
            showToast('Tam ekran açılamadı: ' + err.message, 'error');
        });
    } else {
        document.exitFullscreen().then(() => {
            // Önceki stilleri geri yükle
            tableWrap.style.maxHeight = tableWrap.dataset.prevMaxHeight || '';
            tableWrap.style.overflow = tableWrap.dataset.prevOverflow || '';
            tableWrap.style.background = tableWrap.dataset.prevBackground || '';
            tableWrap.style.padding = '';
        });
    }
}

// Tam ekrandan çıkış dinleyicisi
document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
        const tableWrap = document.querySelector('.tablewrap');
        if (tableWrap) {
            tableWrap.style.maxHeight = tableWrap.dataset.prevMaxHeight || '';
            tableWrap.style.overflow = tableWrap.dataset.prevOverflow || '';
        }
        hidePTTIndicator();
    }
});


// Global erişim için
window.toggleTableFullscreen = toggleTableFullscreen;

// ================ PTT GÖSTERGESİ ================

function showPTTIndicator(message) {
    // Mevcut göstergeyi kaldır
    hidePTTIndicator();

    const indicator = document.createElement('div');
    indicator.id = 'pttIndicator';
    indicator.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <div class="ptt-pulse" style="width: 16px; height: 16px; background: #ef4444; border-radius: 50%; animation: ptt-pulse 1s infinite;"></div>
            <span style="font-weight: 600; font-size: 15px;">${message || RealtimeState.settings.ptt_start_message}</span>
        </div>
    `;
    indicator.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: white;
        padding: 14px 24px;
        border-radius: 12px;
        z-index: 99999;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        font-family: system-ui, -apple-system, sans-serif;
        animation: slideDown 0.3s ease-out;
    `;

    // Animasyon stili ekle
    if (!document.getElementById('ptt-indicator-styles')) {
        const style = document.createElement('style');
        style.id = 'ptt-indicator-styles';
        style.textContent = `
            @keyframes ptt-pulse {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(1.2); }
            }
            @keyframes slideDown {
                from { transform: translateX(-50%) translateY(-100%); opacity: 0; }
                to { transform: translateX(-50%) translateY(0); opacity: 1; }
            }
            @keyframes slideUp {
                from { transform: translateX(-50%) translateY(0); opacity: 1; }
                to { transform: translateX(-50%) translateY(-100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(indicator);
}

function hidePTTIndicator() {
    const indicator = document.getElementById('pttIndicator');
    if (indicator) {
        indicator.style.animation = 'slideUp 0.3s ease-out';
        setTimeout(() => indicator.remove(), 300);
    }
}

// Global erişim
window.showPTTIndicator = showPTTIndicator;
window.hidePTTIndicator = hidePTTIndicator;

// ================ HÜCRE TOOLTIP'LARI ================

function updateCellTitles() {
    document.querySelectorAll('.cell').forEach(cell => {
        let titleParts = [];
        const note = cell.getAttribute('data-note');
        const reason = cell.getAttribute('data-cancellation-reason');
        const status = cell.getAttribute('data-status');

        if (status === 'cancelled' && reason) {
            titleParts.push(`❌ İPTAL NEDENİ: ${reason}`);
        }
        if (note) {
            titleParts.push(`📝 Not: ${note}`);
        }

        if (titleParts.length > 0) {
            cell.setAttribute('title', titleParts.join('\n'));
        }
    });
}

// ================ SOCKET OLAYLARI ================

function initSocketEvents() {
    if (!socket) return;
    socket.on('connect', () => {
        socket.emit('join_plan_updates');
        console.log('Socket bağlandı');
    });

    socket.on('disconnect', () => {
        showToast('Bağlantı koptu...', 'error');
    });

    socket.on('cell_locked', (data) => {
        if (data.locked_by_id === getCurrentUserId()) return;
        const cell = getCellEl(data.cell_id);
        if (cell) {
            cell.classList.add('locked-by-other');
            cell.setAttribute('title', `${data.locked_by} düzenliyor`);
        }
    });

    socket.on('cell_unlocked', (data) => {
        const cell = getCellEl(data.cell_id);
        if (cell) {
            cell.classList.remove('locked-by-other');
            updateCellTitles();
        }
    });

    socket.on('cell_updated', (data) => {
        if (data.updated_by_id !== getCurrentUserId()) {
            // EditingStateManager ile düzenleme durumu kontrolü
            if (window.EditingStateManager && window.EditingStateManager.isEditing()) {
                // Düzenleme aktif - güncellemeyi sıraya al
                window.EditingStateManager.queueCellUpdate({
                    project_id: data.project_id,
                    work_date: data.work_date,
                    shift: data.shift,
                    note: data.note,
                    vehicle_info: data.vehicle_info,
                    status: data.status
                });
                console.log('[Realtime] Hücre güncellemesi sıraya alındı:', data.cell_id);
            } else {
                // Düzenleme yok - hücreyi güncelle
                const cell = getCellEl(data.cell_id);
                if (cell) {
                    // Görsel geri bildirim
                    cell.style.backgroundColor = '#fef08a';
                    setTimeout(() => cell.style.backgroundColor = '', 1500);

                    // Global updateCellDOM (yeni) veya updateCellDom (eski) fonksiyonunu kullan
                    if (window.updateCellDOM) {
                        window.updateCellDOM(data.cell_id, data);
                    } else if (typeof window.updateCellDom === 'function') {
                        window.updateCellDom(cell, {
                            shift: data.shift,
                            note: data.note,
                            person_ids: data.person_ids,
                            vehicle_info: data.vehicle_info,
                            team_id: data.team_id,
                            subproject_id: data.subproject_id,
                            subproject_label: data.subproject_label,
                            hasAttachment: data.hasAttachment
                        });
                    }

                    // Ekstra status güncellemesi (updateCellDom status'u işlemeyebilir)
                    if (data.status) {
                        cell.setAttribute('data-status', data.status);
                    }
                }
            }
            // Bildirim göster
            // if (RealtimeState.settings.show_message_notifications) {
            //     showNotification('Hücre Güncellendi', `${data.updated_by} bir hücreyi güncelledi`);
            // }
        }
    });

    socket.on('cell_cancelled', (data) => {
        const cell = getCellEl(data.cell_id);
        if (cell) {
            cell.classList.add('is-cancelled');
            cell.setAttribute('data-cancellation-reason', data.reason);
            cell.setAttribute('data-status', 'cancelled');
            updateCellTitles();
            showToast(`${data.cancelled_by} işi iptal etti`, 'warning');
        }
    });

    socket.on('cell_restored', (data) => {
        const cell = getCellEl(data.cell_id);
        if (cell) {
            cell.classList.remove('is-cancelled');
            cell.removeAttribute('data-cancellation-reason');
            cell.setAttribute('data-status', 'active');
            updateCellTitles();
            showToast('İş geri yüklendi', 'success');
        }
    });

    socket.on('task_moved', (data) => {
        if (data.moved_by_id === getCurrentUserId()) return;

        if (window.moveTaskDOM && data.cell_data) {
            // DOM güncellemesi ile işi taşı
            window.moveTaskDOM(
                data.source_cell_id,
                data.target_cell_id,
                data.cell_data
            );
            showToast(`${data.moved_by} işi taşıdı`, 'info');
        } else {
            // Fallback
            console.log('Task moved DOM update fallback', data);
            setTimeout(() => window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload(), 500);
        }
    });

    socket.on('overtime_added', (data) => {
        showToast('Mesai eklendi', 'info');
        addOvertimeIndicator(data.cell_id);
    });

    socket.on('overtime_deleted', (data) => {
        if (data.remaining_count === 0) {
            const cell = getCellEl(data.cell_id);
            if (cell) {
                const b = cell.querySelector('.ot-badge');
                if (b) b.remove();
            }
        }
    });

    // Sesli mesaj bildirimi
    socket.on('voice_message', (data) => {
        if (RealtimeState.settings.show_voice_notifications) {
            showNotification('Sesli Mesaj', `${data.from_user_name} sesli mesaj gönderdi`);
        }
        if (RealtimeState.settings.auto_play_voice && RealtimeState.settings.sound_enabled) {
            playVoiceMessage(data.audio_url);
        }
    });
}

// ================ CONTEXT MENU ================

function initContextMenu() {
    const menuId = 'dynamicContextMenu';
    let menu = document.getElementById(menuId);
    if (!menu) {
        menu = document.createElement('div');
        menu.id = menuId;
        menu.style.cssText = `
            display: none; 
            position: fixed; 
            z-index: 10000; 
            background: white; 
            border-radius: 12px; 
            box-shadow: 0 8px 32px rgba(0,0,0,0.2); 
            border: 1px solid #e2e8f0; 
            width: 240px; 
            overflow: hidden; 
            padding: 6px 0; 
            font-family: system-ui, -apple-system, sans-serif;
        `;
        document.body.appendChild(menu);
    }

    document.addEventListener('contextmenu', (e) => {
        const cell = e.target.closest('.cell');
        if (cell) {
            e.preventDefault();
            if (window.selectCell) window.selectCell(cell, '');
            showContextMenu(e.clientX, e.clientY, cell);
        }
    });
}

function showContextMenu(x, y, cell) {
    const menu = document.getElementById('dynamicContextMenu');
    const isCancelled = cell.classList.contains('is-cancelled') || cell.getAttribute('data-status') === 'cancelled';
    const isFilled = cell.classList.contains('filled');

    RealtimeState.activeContextCell = {
        id: cell.getAttribute('data-cell-id'),
        date: cell.getAttribute('data-date'),
        projectId: cell.getAttribute('data-project-id'),
        status: cell.getAttribute('data-status'),
        element: cell
    };

    let items = [];

    if (isCancelled) {
        items.push({ icon: '↩️', label: 'Geri Yükle', action: 'restore', color: '#059669' });
        // İptal nedenini göster
        const reason = cell.getAttribute('data-cancellation-reason');
        if (reason) {
            items.push({ icon: '📋', label: 'İptal Nedenini Göster', action: 'show_cancel_reason', color: '#6366f1' });
        }
    } else if (isFilled) {

        items.push({ icon: '↪️', label: 'İşi Taşı', action: 'move', color: '#2563eb' });
        items.push({ icon: '⏰', label: 'Mesai (Ekle/Sil)', action: 'overtime', color: '#d97706' });
        items.push({ icon: '⏭️', label: 'İşi kalan güne ata', action: 'copy_remaining', color: '#475569' });
        items.push({ separator: true });
        items.push({ icon: '📋', label: 'Kopyala', action: 'copy', color: '#475569' });
    }

    // Clipboard'da veri varsa yapıştır seçeneği göster
    const clipboardData = localStorage.getItem('cell_clipboard');
    if (clipboardData && !isCancelled) {
        items.push({ icon: '📥', label: 'Yapıştır', action: 'paste', color: '#10b981' });
    }

    if (items.length === 0) {
        items.push({ icon: 'ℹ️', label: 'Boş hücre', action: null, color: '#94a3b8' });
    }

    menu.innerHTML = '';
    items.forEach(item => {
        if (item.separator) {
            const sep = document.createElement('div');
            sep.style.cssText = 'height: 1px; background: #f1f5f9; margin: 6px 0;';
            menu.appendChild(sep);
        } else {
            const el = document.createElement('div');
            el.className = 'ctx-item';
            el.style.cssText = `
                padding: 12px 16px; 
                cursor: ${item.action ? 'pointer' : 'default'}; 
                display: flex; 
                align-items: center; 
                gap: 12px; 
                font-size: 14px; 
                color: ${item.color}; 
                transition: background 0.15s;
                font-weight: 500;
            `;
            el.innerHTML = `
                <span style="font-size: 18px; width: 24px; text-align: center;">${item.icon}</span>
                <span>${item.label}</span>
            `;
            if (item.action) {
                el.onclick = (e) => {
                    e.stopPropagation();
                    handleContextAction(item.action);
                };
                el.onmouseenter = () => el.style.background = '#f8fafc';
                el.onmouseleave = () => el.style.background = 'white';
            }
            menu.appendChild(el);
        }
    });

    menu.style.display = 'block';

    // Pozisyon ayarla
    const winW = window.innerWidth;
    const winH = window.innerHeight;
    const r = menu.getBoundingClientRect();
    let posX = x;
    let posY = y;
    if (x + r.width > winW) posX = x - r.width;
    if (y + r.height > winH) posY = y - r.height;
    if (posX < 0) posX = 10;
    if (posY < 0) posY = 10;
    menu.style.left = posX + 'px';
    menu.style.top = posY + 'px';
}

function handleContextAction(action) {
    const active = RealtimeState.activeContextCell;
    document.getElementById('dynamicContextMenu').style.display = 'none';
    if (!active) return;

    switch (action) {
        case 'cancel':
            showCancelModal(active.id);
            break;
        case 'restore':
            restoreCell(active.id);
            break;
        case 'move':
            showMoveModal(active.id, active.date);
            break;
        case 'overtime':
            showOvertimeModal(active.id);
            break;
        case 'copy':
            copyCell(active.id);
            break;
        case 'paste':
            pasteCell(active);
            break;
        case 'copy_remaining':
            if (window.copyJobToFriday) window.copyJobToFriday();
            break;
        case 'show_cancel_reason':
            showCancelReason(active.element);
            break;
    }
}

// ================ İPTAL NEDENİ GÖSTER ================

function showCancelReason(cell) {
    const reason = cell.getAttribute('data-cancellation-reason') || 'Neden belirtilmedi';
    const modal = getOrCreateModal();
    modal.innerHTML = `
        <div style="background: white; width: 420px; padding: 28px; border-radius: 16px; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
            <h3 style="margin: 0 0 16px 0; color: #dc2626; font-size: 20px;">İş İptal Edildi</h3>
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 16px; text-align: left;">
                <div style="font-weight: 600; color: #991b1b; margin-bottom: 8px;">İptal Nedeni:</div>
                <div style="color: #7f1d1d; line-height: 1.6;">${escapeHtml(reason)}</div>
            </div>
            <button onclick="document.getElementById('dynamicModal').style.display='none'" 
                style="margin-top: 20px; background: #dc2626; color: white; border: none; padding: 12px 32px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 14px;">
                Kapat
            </button>
        </div>`;
    modal.style.display = 'flex';
}

// ================ MODAL YARDIMCISI ================

function getOrCreateModal() {
    let modal = document.getElementById('dynamicModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dynamicModal';
        modal.style.cssText = `
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(0,0,0,0.5); 
            backdrop-filter: blur(4px);
            z-index: 10001; 
            align-items: center; 
            justify-content: center;
        `;
        document.body.appendChild(modal);
    }
    return modal;
}

// ================ HÜCRE KOPYALA / YAPIŞTIR ================

async function copyCell(cellId) {
    showToast('Kopyalanıyor...', 'info');
    try {
        const res = await fetch(`/api/cell/details/${cellId}`);
        const data = await res.json();
        if (data.ok && data.cell) {
            const domEl = getCellEl(cellId);
            const copyData = {
                shift: domEl?.getAttribute('data-shift') || '',
                note: domEl?.getAttribute('data-note') || '',
                vehicle: domEl?.getAttribute('data-vehicle') || '',
                team_id: domEl?.getAttribute('data-team-id') || '',
                subproject_id: domEl?.getAttribute('data-subproject-id') || '',
                assignments: (data.cell.assignments || []).map(a => ({ id: a.id, name: a.name, color: a.color })),
                copied_at: new Date().toISOString()
            };
            localStorage.setItem('cell_clipboard', JSON.stringify(copyData));
            RealtimeState.clipboardData = copyData; // Yerel state'te de sakla
            showToast('✅ Kopyalandı! İstediğiniz kadar yapıştırabilirsiniz.', 'success');
        } else {
            showToast('Veri alınamadı', 'error');
        }
    } catch (e) {
        showToast('Kopyalama hatası', 'error');
        console.error(e);
    }
}

async function pasteCell(target) {
    const clipboard = localStorage.getItem('cell_clipboard');
    if (!clipboard) {
        showToast('Kopyalanmış veri yok', 'warning');
        return;
    }

    showToast('Yapıştırılıyor...', 'info');
    try {
        const data = JSON.parse(clipboard);
        const res = await fetch('/api/cell/paste', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cell_id: target.id,
                project_id: target.projectId,
                work_date: target.date,
                csrf_token: getCSRFToken(),
                shift: data.shift,
                note: data.note,
                vehicle_info: data.vehicle,
                team_id: data.team_id,
                subproject_id: data.subproject_id,
                assignments: (data.assignments || []).map(a => (typeof a === 'object' ? a.id : a))
            })
        });
        const r = await res.json();
        if (r.ok) {
            showToast('✅ Yapıştırıldı! Tekrar yapıştırmak için sağ tık yapın.', 'success');

            // DOM'u güncelle - SAYFA YENİLEME YOK
            if (window.updateCellDOM) {
                window.updateCellDOM(target.id, {
                    shift: data.shift,
                    note: data.note,
                    vehicle_info: data.vehicle,
                    team_id: data.team_id,
                    subproject_id: data.subproject_id,
                    status: 'active',
                    assignments: (data.assignments || []).map(a => (typeof a === 'object' ? a : { id: a, name: '' }))
                });

                const cell = target.element;
                if (cell) {
                    cell.style.transition = 'background-color 0.5s';
                    cell.style.backgroundColor = '#d1fae5';
                    setTimeout(() => cell.style.backgroundColor = '', 1500);
                }
            } else {
                window.location.reload();
            }

            // Clipboard SİLİNMEZ - çoklu yapıştırma için
            // localStorage.removeItem('cell_clipboard'); // BU SATIR KALDIRILDI

        } else {
            showToast('Hata: ' + (r.error || 'Bilinmeyen hata'), 'error');
        }
    } catch (e) {
        showToast('Yapıştırma başarısız', 'error');
        console.error(e);
    }
}

// ================ MESAİ YÖNETİMİ ================

function showOvertimeModal(cellId) {
    const modal = getOrCreateModal();
    modal.innerHTML = `
        <div style="background: white; width: 520px; padding: 28px; border-radius: 16px; position: relative; max-height: 85vh; overflow-y: auto;">
            <div class="modal-close" style="position: absolute; right: 20px; top: 20px; cursor: pointer; font-size: 24px; color: #94a3b8; hover: #475569;">✕</div>
            <h3 style="margin: 0 0 20px 0; font-size: 20px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px;">⏰ Mesai Yönetimi</h3>
            <div id="otLoader" style="text-align: center; padding: 20px; color: #64748b;">Yükleniyor...</div>
            <div id="otContent" style="display: none;">
                
                <div id="existingOts" style="margin-bottom: 24px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <h4 style="margin: 0 0 12px 0; font-size: 15px; font-weight: 600; color: #475569;">📋 Mevcut Mesailer</h4>
                    <div id="otListContainer"></div>
                </div>

                <div style="border-top: 2px solid #e2e8f0; padding-top: 20px;">
                    <h4 style="margin: 0 0 16px 0; font-size: 15px; font-weight: 600; color: #0f172a;">➕ Yeni Mesai Ekle</h4>
                    <div style="display: flex; gap: 12px; margin-bottom: 16px;">
                        <div style="flex: 0 0 100px;">
                            <label style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;">Saat</label>
                            <input type="number" id="otDuration" step="0.5" value="1" min="0.5" max="24" 
                                style="width: 100%; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; font-size: 14px;" placeholder="Saat">
                        </div>
                        <div style="flex: 1;">
                            <label style="font-size: 12px; color: #64748b; display: block; margin-bottom: 4px;">Açıklama</label>
                            <input type="text" id="otDesc" placeholder="Mesai açıklaması..." 
                                style="width: 100%; border: 1px solid #e2e8f0; padding: 10px; border-radius: 8px; font-size: 14px;">
                        </div>
                    </div>
                    <div style="margin-bottom: 16px;">
                        <label style="font-weight: 600; font-size: 13px; color: #475569; display: block; margin-bottom: 8px;">Personeller:</label>
                        <div id="otPersonList" style="max-height: 180px; overflow-y: auto; border: 1px solid #e2e8f0; padding: 8px; border-radius: 10px; background: white;"></div>
                    </div>
                    <button id="otAddBtn" style="width: 100%; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 14px; border-radius: 10px; border: none; cursor: pointer; font-weight: 600; font-size: 15px; transition: transform 0.2s;">
                        ⏰ Mesai Ekle
                    </button>
                </div>
            </div>
        </div>
    `;
    modal.style.display = 'flex';
    modal.querySelector('.modal-close').onclick = () => modal.style.display = 'none';

    fetch(`/api/cell/details/${cellId}`).then(r => r.json()).then(data => {
        document.getElementById('otLoader').style.display = 'none';
        document.getElementById('otContent').style.display = 'block';

        // Mevcut mesailer
        const otList = document.getElementById('otListContainer');
        if (data.cell.overtimes && data.cell.overtimes.length > 0) {
            otList.innerHTML = data.cell.overtimes.map(o => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: white; margin-bottom: 6px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 13px;">
                    <div>
                        <strong style="color: #0f172a;">${o.person_name}</strong>: 
                        <span style="color: #f59e0b; font-weight: 600;">${o.duration} saat</span>
                        <span style="color: #64748b;">(${o.description || 'Açıklama yok'})</span>
                    </div>
                    <button onclick="deleteOvertime(${o.id}, ${cellId})" 
                        style="color: #dc2626; background: #fef2f2; border: 1px solid #fecaca; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 500;">
                        🗑️ Sil
                    </button>
                </div>
            `).join('');
        } else {
            otList.innerHTML = '<div style="color: #94a3b8; font-size: 13px; text-align: center; padding: 12px;">Henüz mesai kaydı yok</div>';
        }

        // Personel listesi
        const pList = document.getElementById('otPersonList');
        if (data.cell.assignments && data.cell.assignments.length > 0) {
            pList.innerHTML = data.cell.assignments.map(p => `
                <div style="display: flex; align-items: center; padding: 8px 10px; border-bottom: 1px solid #f1f5f9;">
                    <input type="checkbox" class="ot-check" value="${p.id}" id="p_${p.id}" checked 
                        style="width: 18px; height: 18px; accent-color: #f59e0b;">
                    <label for="p_${p.id}" style="margin-left: 10px; flex: 1; cursor: pointer; font-size: 14px; color: #0f172a;">${p.name}</label>
                </div>
            `).join('');
        } else {
            pList.innerHTML = '<div style="color: #94a3b8; text-align: center; padding: 12px;">Bu hücrede personel yok</div>';
        }

        document.getElementById('otAddBtn').onclick = () => submitOvertime(cellId);
    }).catch(err => {
        console.error('Mesai modal hatası:', err);
        showToast('Mesai bilgileri yüklenemedi', 'error');
    });
}

function deleteOvertime(otId, cellId) {
    if (!confirm('Bu mesai kaydını silmek istediğinizden emin misiniz?')) return;
    fetch('/api/overtime/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ overtime_id: otId, csrf_token: getCSRFToken() })
    }).then(r => r.json()).then(d => {
        if (d.ok) {
            showToast('Mesai silindi', 'success');
            showOvertimeModal(cellId); // Modal'ı yenile

            // Personel seçme ekranını güncelle (mesai bilgisini güncelle)
            if (typeof selectedCellEl !== 'undefined' && selectedCellEl && typeof currentCell !== 'undefined' && currentCell.work_date && currentCell.project_id) {
                const cacheKey = `${currentCell.work_date}_${currentCell.project_id}_${cellId}`;
                if (window.personAssignedCache) {
                    delete window.personAssignedCache[cacheKey]; // Cache'i temizle
                }
                if (typeof checkPersonAssigned === 'function') {
                    checkPersonAssigned(currentCell.work_date, currentCell.project_id, cellId).then(assignedData => {
                        const searchInput = document.getElementById("peopleSearch");
                        const select = document.getElementById("peopleSelect");
                        if (searchInput && select && typeof filterPeopleComboBox === 'function') {
                            filterPeopleComboBox(); // Personel listesini yenile
                        }
                    });
                }
            }
        } else {
            showToast('Silme hatası', 'error');
        }
    });
}

async function submitOvertime(cellId) {
    const duration = parseFloat(document.getElementById('otDuration').value);
    const desc = document.getElementById('otDesc').value;
    const checks = document.querySelectorAll('.ot-check:checked');
    const cellEl = getCellEl(cellId);

    if (!checks.length) {
        showToast('En az bir personel seçin', 'warning');
        return;
    }

    if (duration <= 0 || duration > 24) {
        showToast('Geçerli bir saat girin (0.5-24)', 'warning');
        return;
    }

    const promises = Array.from(checks).map(chk =>
        fetch('/api/overtime/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cell_id: cellId,
                person_id: chk.value,
                work_date: cellEl?.getAttribute('data-date'),
                duration_hours: duration,
                description: desc,
                csrf_token: getCSRFToken()
            })
        })
    );

    await Promise.all(promises);
    showToast(`✅ ${checks.length} kişiye ${duration} saat mesai eklendi`, 'success');
    showOvertimeModal(cellId); // Modal'ı yenile
    addOvertimeIndicator(cellId);

    // Personel seçme ekranını güncelle (mesai bilgisini göster)
    if (typeof selectedCellEl !== 'undefined' && selectedCellEl && typeof currentCell !== 'undefined' && currentCell.work_date && currentCell.project_id) {
        const cacheKey = `${currentCell.work_date}_${currentCell.project_id}_${cellId}`;
        if (window.personAssignedCache) {
            delete window.personAssignedCache[cacheKey]; // Cache'i temizle
        }
        if (typeof checkPersonAssigned === 'function') {
            checkPersonAssigned(currentCell.work_date, currentCell.project_id, cellId).then(assignedData => {
                const searchInput = document.getElementById("peopleSearch");
                const select = document.getElementById("peopleSelect");
                if (searchInput && select && typeof filterPeopleComboBox === 'function') {
                    filterPeopleComboBox(); // Personel listesini yenile
                }
            });
        }
    }
}

// ================ İŞ İPTAL ================

function showCancelModal(cellId) {
    const modal = getOrCreateModal();
    modal.innerHTML = `
        <div style="background: white; width: 440px; padding: 28px; border-radius: 16px; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 12px;">⚠️</div>
            <h3 style="margin: 0 0 8px 0; color: #dc2626; font-size: 20px; font-weight: 700;">İşi İptal Et</h3>
            <p style="color: #64748b; margin: 0 0 20px 0; font-size: 14px;">Bu işlem geri alınabilir. İptal nedenini aşağıya yazın.</p>
            <textarea id="cancelReason" placeholder="İptal nedeni yazın... (zorunlu)" 
                style="width: 100%; padding: 14px; border: 2px solid #fecaca; border-radius: 10px; margin-bottom: 20px; min-height: 100px; font-size: 14px; resize: vertical;"></textarea>
            <div style="display: flex; gap: 12px;">
                <button onclick="document.getElementById('dynamicModal').style.display='none'" 
                    style="flex: 1; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; padding: 14px; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 14px;">
                    Vazgeç
                </button>
                <button id="doCancel" 
                    style="flex: 1; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); color: white; border: none; padding: 14px; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 14px;">
                    ❌ İptal Et
                </button>
            </div>
        </div>`;
    modal.style.display = 'flex';

    document.getElementById('doCancel').onclick = async () => {
        const reason = document.getElementById('cancelReason').value.trim();
        if (!reason) {
            showToast('İptal nedeni yazmalısınız', 'warning');
            document.getElementById('cancelReason').style.borderColor = '#dc2626';
            return;
        }

        try {
            const res = await fetch('/api/cell/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cell_id: cellId, reason: reason, csrf_token: getCSRFToken() })
            });
            const data = await res.json();

            if (data.ok) {
                showToast('İş iptal edildi', 'success');
                modal.style.display = 'none';

                // DOM'u güncelle
                const cell = getCellEl(cellId);
                if (cell) {
                    cell.classList.add('is-cancelled');
                    cell.setAttribute('data-status', 'cancelled');
                    cell.setAttribute('data-cancellation-reason', reason);
                    updateCellTitles();
                }
            } else {
                showToast('Hata: ' + (data.error || 'Bilinmeyen'), 'error');
            }
        } catch (e) {
            showToast('İptal işlemi başarısız', 'error');
            console.error(e);
        }
    };
}

function restoreCell(cellId) {
    if (!confirm('Bu işi geri yüklemek istiyor musunuz?')) return;
    fetch('/api/cell/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cell_id: cellId, csrf_token: getCSRFToken() })
    })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                showToast('İş geri yüklendi', 'success');
                const cell = getCellEl(cellId);
                if (cell) {
                    cell.classList.remove('is-cancelled');
                    cell.setAttribute('data-status', 'active');
                    cell.removeAttribute('data-cancellation-reason');
                    updateCellTitles();
                }
            }
        });
}

// ================ İŞ TAŞIMA ================

function showMoveModal(cellId, currentDate) {
    const modal = getOrCreateModal();
    modal.innerHTML = `
        <div style="background: white; width: 400px; padding: 28px; border-radius: 16px; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 12px;">↪️</div>
            <h3 style="margin: 0 0 16px 0; color: #2563eb; font-size: 20px; font-weight: 700;">İşi Taşı</h3>
            <p style="color: #64748b; margin: 0 0 20px 0; font-size: 14px;">Mevcut tarih: <strong>${currentDate}</strong></p>
            <input type="date" id="moveNewDate" value="${currentDate}" 
                style="width: 100%; padding: 14px; border: 2px solid #e2e8f0; border-radius: 10px; margin-bottom: 20px; font-size: 16px; text-align: center;">
            <div style="display: flex; gap: 12px;">
                <button onclick="document.getElementById('dynamicModal').style.display='none'" 
                    style="flex: 1; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; padding: 14px; border-radius: 10px; cursor: pointer; font-weight: 600;">
                    Vazgeç
                </button>
                <button id="doMove" 
                    style="flex: 1; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: white; border: none; padding: 14px; border-radius: 10px; cursor: pointer; font-weight: 600;">
                    ↪️ Taşı
                </button>
            </div>
        </div>`;
    modal.style.display = 'flex';

    document.getElementById('doMove').onclick = async () => {
        const newDate = document.getElementById('moveNewDate').value;
        if (!newDate || newDate === currentDate) {
            showToast('Farklı bir tarih seçin', 'warning');
            return;
        }

        try {
            const res = await fetch('/api/update-task-date', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cell_id: cellId, new_date: newDate, csrf_token: getCSRFToken() })
            });
            const data = await res.json();

            if (data.ok) {
                showToast('İş taşındı', 'success');
                modal.style.display = 'none';
                if (window.moveTaskDOM && data.cell_data) {
                    window.moveTaskDOM(data.source_cell_id, data.target_cell_id, data.cell_data);
                } else {
                    setTimeout(() => window.reloadWithScroll ? window.reloadWithScroll() : window.location.reload(), 800);
                }
            } else {
                showToast('Hata: ' + (data.error || data.message || 'Bilinmeyen'), 'error');
            }
        } catch (e) {
            showToast('Taşıma başarısız', 'error');
            console.error(e);
        }
    };
}

// ================ AYARLAR ================

function loadUserSettings() {
    fetch('/api/settings')
        .then(r => r.json())
        .then(data => {
            if (data.ok && data.settings) {
                RealtimeState.settings = { ...RealtimeState.settings, ...data.settings };
            }
        })
        .catch(() => { });
}

function showSettingsModal() {
    const modal = getOrCreateModal();
    const s = RealtimeState.settings;

    modal.innerHTML = `
        <div style="background: white; width: 520px; padding: 28px; border-radius: 16px; position: relative; max-height: 90vh; overflow-y: auto;">
            <div class="modal-close" style="position: absolute; right: 20px; top: 20px; cursor: pointer; font-size: 24px; color: #94a3b8;">✕</div>
            <h3 style="margin: 0 0 24px 0; font-size: 22px; font-weight: 700; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px;">
                ⚙️ Kullanıcı Ayarları
            </h3>
            
            <!-- Genel Ayarlar -->
            <div style="margin-bottom: 24px;">
                <h4 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #475569;">🎯 Genel Ayarlar</h4>
                
                <label style="display: flex; align-items: center; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                    <input type="checkbox" id="set_sound" ${s.sound_enabled ? 'checked' : ''} 
                        style="width: 20px; height: 20px; accent-color: #6366f1; margin-right: 12px;">
                    <div>
                        <div style="font-weight: 600; color: #0f172a;">🔊 Ses Efektleri</div>
                        <div style="font-size: 12px; color: #64748b;">Bildirim sesleri ve uyarı sesleri</div>
                    </div>
                </label>
                
                <label style="display: flex; align-items: center; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                    <input type="checkbox" id="set_notif" ${s.notifications_enabled ? 'checked' : ''} 
                        style="width: 20px; height: 20px; accent-color: #6366f1; margin-right: 12px;">
                    <div>
                        <div style="font-weight: 600; color: #0f172a;">🔔 Bildirimler</div>
                        <div style="font-size: 12px; color: #64748b;">Tarayıcı bildirimleri</div>
                    </div>
                </label>
                
                <div style="padding: 12px; background: #f8fafc; border-radius: 10px;">
                    <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #0f172a;">⌨️ Tam Ekran Kısayolu</label>
                    <input type="text" id="set_fs" value="${s.fullscreen_shortcut || 'F11'}" 
                        style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                    <div style="font-size: 11px; color: #64748b; margin-top: 6px;">Örn: F11, F5, Escape</div>
                </div>
            </div>
            
            <!-- Bildirim Ayarları -->
            <div style="margin-bottom: 24px;">
                <h4 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #475569;">📬 Bildirim Ayarları</h4>
                
                <label style="display: flex; align-items: center; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                    <input type="checkbox" id="set_msg_notif" ${s.show_message_notifications ? 'checked' : ''} 
                        style="width: 20px; height: 20px; accent-color: #10b981; margin-right: 12px;">
                    <div>
                        <div style="font-weight: 600; color: #0f172a;">💬 Mesaj Bildirimleri</div>
                        <div style="font-size: 12px; color: #64748b;">Yeni mesajlarda ekranda bildirim göster</div>
                    </div>
                </label>
                
                <label style="display: flex; align-items: center; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px;">
                    <input type="checkbox" id="set_voice_notif" ${s.show_voice_notifications ? 'checked' : ''} 
                        style="width: 20px; height: 20px; accent-color: #10b981; margin-right: 12px;">
                    <div>
                        <div style="font-weight: 600; color: #0f172a;">🎤 Sesli Mesaj Bildirimleri</div>
                        <div style="font-size: 12px; color: #64748b;">Sesli mesajlarda ekranda bildirim göster</div>
                    </div>
                </label>
            </div>
            
            <!-- Bas-Konuş Ayarları -->
            <div style="margin-bottom: 24px;">
                <h4 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #475569;">🎙️ Bas-Konuş (PTT) Ayarları</h4>
                
                <!-- 1. Ana Toggle -->
                <label style="display: flex; align-items: flex-start; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px; border: 1px solid #e2e8f0;">
                    <input type="checkbox" id="set_ptt_enabled" ${s.ptt_enabled !== false ? 'checked' : ''} 
                        style="width: 20px; height: 20px; accent-color: #f59e0b; margin-right: 12px; margin-top: 3px;">
                    <div>
                        <div style="font-weight: 600; color: #0f172a; margin-bottom:4px;">🎤 Bas-Konuş Özelliğini Etkinleştir</div>
                        <div style="font-size: 13px; color: #64748b; margin-bottom: 6px;">Bas konuş özelliğini etkinleştirmek için açın. Kapalı olduğunda sağ alt köşedeki mikrofon simgesi ve sesli komut özellikleri gizlenecektir.</div>
                        <div id="ptt_status_text" style="font-size: 13px; font-weight: 600; color: ${s.ptt_enabled !== false ? '#16a34a' : '#dc2626'};">
                            ${s.ptt_enabled !== false ? '✅ Bas-Konuş Aktif' : '⛔ Bas-Konuş Pasif'}
                        </div>
                        <div id="ptt_sub_text" style="font-size: 12px; color: #64748b; margin-top: 2px;">
                            ${s.ptt_enabled !== false ? 'Sesli komut özelliği etkindir. Ayarlar panelindeki PTT tuşunu kullanarak konuşabilirsiniz.' : 'Sesli komut özellikleri devre dışıdır. Mikrofon dinlemesi yapılmaz.'}
                        </div>
                    </div>
                </label>

                <!-- 6. Alt Ayarlar (Container) -->
                <div id="ptt_sub_settings" style="display: ${s.ptt_enabled !== false ? 'block' : 'none'}; padding-left: 10px; border-left: 3px solid #e2e8f0; margin-left: 10px;">
                    
                    <div style="padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #0f172a;">PTT Tuşu Seçimi</label>
                        <select id="set_ptt_key" style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="Space" ${s.ptt_key === 'Space' ? 'selected' : ''}>Space (Boşluk)</option>
                            <option value="Control" ${s.ptt_key === 'Control' ? 'selected' : ''}>Ctrl</option>
                            <option value="Shift" ${s.ptt_key === 'Shift' ? 'selected' : ''}>Shift</option>
                            <option value="Alt" ${s.ptt_key === 'Alt' ? 'selected' : ''}>Alt</option>
                        </select>
                    </div>
                    
                    <label style="display: flex; align-items: center; cursor: pointer; padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                        <input type="checkbox" id="set_auto_play" ${s.auto_play_voice ? 'checked' : ''} 
                            style="width: 20px; height: 20px; accent-color: #f59e0b; margin-right: 12px;">
                        <div>
                            <div style="font-weight: 600; color: #0f172a;">▶️ Otomatik Oynatma</div>
                            <div style="font-size: 12px; color: #64748b;">Gelen sesli mesajları otomatik çal</div>
                        </div>
                    </label>
                    
                    <div style="padding: 12px; background: #f8fafc; border-radius: 10px; margin-bottom: 10px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #0f172a;">🎤 Konuşma Başlangıç Mesajı</label>
                        <input type="text" id="set_ptt_start" value="${s.ptt_start_message || '🎤 Konuşma başladı...'}" 
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                    </div>
                    
                    <div style="padding: 12px; background: #f8fafc; border-radius: 10px;">
                        <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #0f172a;">✅ Konuşma Bitiş Mesajı</label>
                        <input type="text" id="set_ptt_end" value="${s.ptt_end_message || '✅ Mesaj gönderildi'}" 
                            style="width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                    </div>
                </div>
            </div>
            
            <!-- Tema -->
            <div style="margin-bottom: 24px;">
                <h4 style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #475569;">🎨 Tema</h4>
                <div style="display: flex; gap: 12px;">
                    <label style="flex: 1; display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 16px; background: ${s.theme === 'light' ? '#e0e7ff' : '#f8fafc'}; border: 2px solid ${s.theme === 'light' ? '#6366f1' : '#e2e8f0'}; border-radius: 10px;">
                        <input type="radio" name="theme" value="light" ${s.theme === 'light' ? 'checked' : ''} style="display: none;">
                        <span style="font-size: 24px; margin-right: 8px;">☀️</span>
                        <span style="font-weight: 600; color: #0f172a;">Açık</span>
                    </label>
                    <label style="flex: 1; display: flex; align-items: center; justify-content: center; cursor: pointer; padding: 16px; background: ${s.theme === 'dark' ? '#312e81' : '#f8fafc'}; border: 2px solid ${s.theme === 'dark' ? '#6366f1' : '#e2e8f0'}; border-radius: 10px;">
                        <input type="radio" name="theme" value="dark" ${s.theme === 'dark' ? 'checked' : ''} style="display: none;">
                        <span style="font-size: 24px; margin-right: 8px;">🌙</span>
                        <span style="font-weight: 600; color: ${s.theme === 'dark' ? 'white' : '#0f172a'};">Koyu</span>
                    </label>
                </div>
            </div>
            
            <button id="saveSetBtn" style="width: 100%; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 16px; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; font-size: 16px; transition: transform 0.2s;">
                💾 Ayarları Kaydet
            </button>
        </div>
    `;

    modal.style.display = 'flex';
    modal.querySelector('.modal-close').onclick = () => modal.style.display = 'none';

    // PTT Toggle Logic
    const pttToggle = document.getElementById('set_ptt_enabled');
    const pttSub = document.getElementById('ptt_sub_settings');
    const pttStatus = document.getElementById('ptt_status_text');
    const pttSubText = document.getElementById('ptt_sub_text');

    pttToggle.addEventListener('change', (e) => {
        const enabled = e.target.checked;
        pttSub.style.display = enabled ? 'block' : 'none';

        if (enabled) {
            pttStatus.textContent = '✅ Bas-Konuş Aktif';
            pttStatus.style.color = '#16a34a'; // Green
            pttSubText.textContent = 'Sesli komut özelliği etkindir. Ayarlar panelindeki PTT tuşunu kullanarak konuşabilirsiniz.';
        } else {
            pttStatus.textContent = '⛔ Bas-Konuş Pasif';
            pttStatus.style.color = '#dc2626'; // Red
            pttSubText.textContent = 'Sesli komut özellikleri devre dışıdır. Mikrofon dinlemesi yapılmaz.';
        }
    });

    // Tema seçimi
    document.querySelectorAll('input[name="theme"]').forEach(radio => {
        radio.addEventListener('change', function () {
            document.querySelectorAll('input[name="theme"]').forEach(r => {
                const label = r.closest('label');
                if (r.checked) {
                    label.style.background = r.value === 'dark' ? '#312e81' : '#e0e7ff';
                    label.style.borderColor = '#6366f1';
                } else {
                    label.style.background = '#f8fafc';
                    label.style.borderColor = '#e2e8f0';
                }
            });
        });
    });

    document.getElementById('saveSetBtn').onclick = async () => {
        const newSettings = {
            sound_enabled: document.getElementById('set_sound').checked,
            notifications_enabled: document.getElementById('set_notif').checked,
            fullscreen_shortcut: document.getElementById('set_fs').value,
            ptt_key: document.getElementById('set_ptt_key').value,
            ptt_enabled: document.getElementById('set_ptt_enabled').checked,
            auto_play_voice: document.getElementById('set_auto_play').checked,
            theme: document.querySelector('input[name="theme"]:checked')?.value || 'light',
            ptt_start_message: document.getElementById('set_ptt_start').value,
            ptt_end_message: document.getElementById('set_ptt_end').value,
            show_message_notifications: document.getElementById('set_msg_notif').checked,
            show_voice_notifications: document.getElementById('set_voice_notif').checked,
            csrf_token: getCSRFToken()
        };

        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newSettings)
            });

            // Ayarlar değişti mi kontrol
            const pttChanged = newSettings.ptt_enabled !== (RealtimeState.settings.ptt_enabled !== false);

            RealtimeState.settings = { ...RealtimeState.settings, ...newSettings };

            if (pttChanged) {
                if (newSettings.ptt_enabled) {
                    showNotification('Bas-Konuş Açıldı', 'Bas-Konuş özelliği başarıyla açıldı. Sağ alt köşedeki mikrofon simgesini görebilir ve PTT tuşu (varsayılan: Space) ile sesli komut gönderebilirsiniz. ⚠️ Mikrofon erişimi için tarayıcı izni gerekebilir.');
                } else {
                    showNotification('Bas-Konuş Kapatıldı', 'Bas-Konuş özelliği başarıyla kapatıldı. Sağ alt köşedeki mikrofon simgesi ve diğer sesli komut araçları gizlenmiştir. Mikrofon dinlemesi sonlandırılmıştır.');
                }

                // Toggle UI
                const pttContainer = document.getElementById('pttContainer');
                if (pttContainer) {
                    pttContainer.style.display = newSettings.ptt_enabled ? 'block' : 'none';
                }

                // Eğer kapatıldıysa ve recording açıksa durdur
                if (!newSettings.ptt_enabled && RealtimeState.ptt.isRecording) {
                    stopPTTRecording();
                }
            }

            // Sync with localStorage for quick access
            localStorage.setItem('pttEnabled', newSettings.ptt_enabled);

            showToast('✅ Ayarlar başarıyla kaydedildi. Bas-Konuş ayarları güncellenmişir.', 'success');
            modal.style.display = 'none';
        } catch (e) {
            showToast('Ayarlar kaydedilemedi', 'error');
        }
    };
}

function saveSettings() { }

// ================ TABLO FİLTRELERİ ================

function initTableFilters() {
    // Filtre alanı oluştur
    const filterContainer = document.getElementById('tableFilters');
    if (!filterContainer) return;

    // Benzersiz değerleri topla
    const regions = new Set();
    const projects = new Set();
    const responsibles = new Set();

    document.querySelectorAll('#planTbody tr.planRow').forEach(row => {
        const region = row.querySelector('.region')?.textContent?.trim();
        const project = row.querySelector('.pcode')?.textContent?.trim();
        const responsible = row.querySelector('.respText')?.textContent?.trim();

        if (region) regions.add(region);
        if (project) projects.add(project);
        if (responsible) responsibles.add(responsible);
    });

    // Eğer değerler varsa, filtre butonlarını aktif et
    window.tableFilterData = {
        regions: Array.from(regions).sort(),
        projects: Array.from(projects).sort(),
        responsibles: Array.from(responsibles).sort()
    };
}

function filterTable(type, value) {
    const rows = document.querySelectorAll('#planTbody tr.planRow');

    if (!value) {
        // Tüm satırları göster
        rows.forEach(row => row.style.display = '');
        return;
    }

    rows.forEach(row => {
        let cellValue = '';
        if (type === 'region') {
            cellValue = row.querySelector('.region')?.textContent?.trim() || '';
        } else if (type === 'project') {
            cellValue = row.querySelector('.pcode')?.textContent?.trim() || '';
        } else if (type === 'responsible') {
            cellValue = row.querySelector('.respText')?.textContent?.trim() || '';
        }

        if (cellValue.toLowerCase().includes(value.toLowerCase())) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function clearTableFilters() {
    document.querySelectorAll('#planTbody tr.planRow').forEach(row => {
        row.style.display = '';
    });

    // Filtre inputlarını temizle
    const filterInputs = document.querySelectorAll('.table-filter-input');
    filterInputs.forEach(input => input.value = '');
}

// Global erişim
window.filterTable = filterTable;
window.clearTableFilters = clearTableFilters;

// ================ BİLDİRİMLER ================

function showNotification(title, body) {
    if (!RealtimeState.settings.notifications_enabled) return;

    // Toast bildirimi göster
    showToast(`${title}: ${body}`, 'info');

    // Tarayıcı bildirimi
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/static/favicon.ico' });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(title, { body, icon: '/static/favicon.ico' });
            }
        });
    }
}

function playVoiceMessage(audioUrl) {
    if (!RealtimeState.settings.sound_enabled) return;
    try {
        const audio = new Audio(audioUrl);
        audio.play();
    } catch (e) {
        console.error('Ses çalma hatası:', e);
    }
}

// ================ YARDIMCI FONKSİYONLAR ================

function getCellEl(id) {
    return document.querySelector(`.cell[data-cell-id="${id}"]`);
}

function getCurrentUserId() {
    return parseInt(document.getElementById('currentUserId')?.value || '0', 10);
}

function getCSRFToken() {
    return document.getElementById('csrfToken')?.value ||
        document.getElementById('csrfTokenGlobal')?.value || '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(msg, type = 'info') {
    // Mevcut toast'ları kaldır (max 3)
    const existingToasts = document.querySelectorAll('.realtime-toast');
    if (existingToasts.length >= 3) {
        existingToasts[0].remove();
    }

    const colors = {
        success: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        error: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        warning: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        info: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
    };

    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    const d = document.createElement('div');
    d.className = 'realtime-toast';
    d.innerHTML = `<span style="margin-right: 8px;">${icons[type] || 'ℹ️'}</span>${msg}`;
    d.style.cssText = `
        position: fixed; 
        bottom: ${20 + (existingToasts.length * 60)}px; 
        right: 20px; 
        padding: 14px 20px; 
        background: ${colors[type] || colors.info}; 
        color: white; 
        z-index: 99999; 
        border-radius: 12px; 
        font-weight: 500;
        font-size: 14px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        animation: slideInRight 0.3s ease-out;
        display: flex;
        align-items: center;
    `;

    // Animasyon için style ekle
    if (!document.getElementById('toast-animations')) {
        const style = document.createElement('style');
        style.id = 'toast-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(d);

    setTimeout(() => {
        d.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => d.remove(), 300);
    }, 4000);
}

function addOvertimeIndicator(cellId) {
    const c = getCellEl(cellId);
    if (c && !c.querySelector('.ot-badge')) {
        const b = document.createElement('div');
        b.className = 'ot-badge';
        b.innerText = '⏰';
        b.style.cssText = 'position: absolute; top: 4px; right: 4px; font-size: 12px; background: #fef3c7; padding: 2px 4px; border-radius: 4px; border: 1px solid #fcd34d;';
    }
}

// ================ DOM GÜNCELLEME YARDIMCILARI ================

// Global state için gerekli
if (!window.getCellEl) {
    window.getCellEl = function (cellId) {
        return document.querySelector(`.cell[data-cell-id="${cellId}"]`);
    };
}

function _safeEscape(s) {
    if (!s) return '';
    return s.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function clearCellDOM(cell) {
    if (!cell) return;

    // Sınıfları temizle
    cell.classList.remove('filled', 'is-cancelled', 'locked-by-other');

    // Attribute'ları temizle
    cell.removeAttribute('data-shift');
    cell.removeAttribute('data-note');
    cell.removeAttribute('data-vehicle');
    cell.removeAttribute('data-team-id');
    cell.removeAttribute('data-team-name');
    cell.removeAttribute('data-subproject-id');
    cell.removeAttribute('data-cancellation-reason');
    cell.setAttribute('data-status', 'active');
    cell.setAttribute('title', '');
    cell.style.backgroundColor = '';

    // İçeriği temizle
    cell.innerHTML = '';
}

function updateCellDOM(cellId, data) {
    const cell = window.getCellEl(cellId);
    if (!cell) return false;

    // Mevcut assignmentları sakla (eğer yeni data içinde gelmediyse)
    let existingAssignmentsHtml = '';
    const assignmentsDiv = cell.querySelector('.cell-assignments');
    if (assignmentsDiv && !data.assignments) {
        existingAssignmentsHtml = assignmentsDiv.outerHTML;
    }

    // Hücreyi temizle (önceki verilerden arındır)
    clearCellDOM(cell);

    // Yeni verileri set et
    cell.setAttribute('data-status', data.status || 'active');
    if (data.status === 'cancelled') {
        cell.classList.add('is-cancelled');
        if (data.cancellation_reason) {
            cell.setAttribute('data-cancellation-reason', data.cancellation_reason);
        }
    }

    if (data.shift) cell.setAttribute('data-shift', data.shift);
    if (data.note) cell.setAttribute('data-note', data.note);
    if (data.vehicle_info) cell.setAttribute('data-vehicle', data.vehicle_info);
    if (data.team_id) cell.setAttribute('data-team-id', data.team_id);
    if (data.subproject_id) cell.setAttribute('data-subproject-id', data.subproject_id);

    // Dolu işareti
    cell.classList.add('filled');

    // İçerik HTML'i oluştur
    let contentHtml = '';

    // Shift - eğer varsa
    if (data.shift) {
        contentHtml += `<div class="cell-time">${_safeEscape(data.shift)}</div>`;
    }

    // Personeller
    if (data.assignments && data.assignments.length > 0) {
        contentHtml += '<div class="cell-assignments" style="display: flex; flex-wrap: wrap; gap: 4px; padding: 2px;">';
        data.assignments.forEach(p => {
            const color = p.color || '#3b82f6';
            contentHtml += `
               <div class="person-badge" style="background: ${color}; color: white; font-size: 10px; padding: 2px 6px; border-radius: 10px; white-space: nowrap;">
                   ${_safeEscape(p.name)}
               </div>
           `;
        });
        contentHtml += '</div>';
    } else if (existingAssignmentsHtml) {
        contentHtml += existingAssignmentsHtml;
    }

    // Not
    if (data.note) {
        contentHtml += `<div class="cell-note" style="font-size: 11px; color: #64748b; margin-top: 2px;">${_safeEscape(data.note)}</div>`;
    }

    // Araç
    if (data.vehicle_info) {
        contentHtml += `<div class="cell-vehicle" style="font-size: 11px; font-weight: 600; color: #0f172a; margin-top: 2px;">🚗 ${_safeEscape(data.vehicle_info)}</div>`;
    }

    cell.innerHTML = contentHtml;

    // Tooltip güncelle
    if (window.updateCellTitles) window.updateCellTitles();

    return true;
}

function moveTaskDOM(sourceCellId, targetCellId, data) {
    const sourceCell = window.getCellEl(sourceCellId);
    if (sourceCell) {
        clearCellDOM(sourceCell);
    }

    const targetCell = window.getCellEl(targetCellId);
    if (targetCell) {
        updateCellDOM(targetCellId, data);

        // Highlight effect
        targetCell.style.transition = 'background-color 0.5s';
        targetCell.style.backgroundColor = '#86efac';
        setTimeout(() => {
            targetCell.style.backgroundColor = '';
        }, 1500);
    }
}

// Window'a ata
window.updateCellDOM = updateCellDOM;
window.moveTaskDOM = moveTaskDOM;
window.clearCellDOM = clearCellDOM;


// =================== CANCELLATION HANDLERS (New) ===================

function updateModalCancellationUI(isCancelled, details) {
    const btnCancel = document.getElementById('btnCancelJob');
    const formSection = document.getElementById('cancelFormSection');
    const infoSection = document.getElementById('cancellationInfoSection');
    const btnSave = document.getElementById('btnSaveCell');
    const btnDelete = document.querySelector("#cellModal button[onclick='clearCell()']");

    // Reset UI
    if (btnCancel) btnCancel.style.display = 'none';
    if (formSection) formSection.style.display = 'none';
    if (infoSection) infoSection.style.display = 'none';
    if (btnSave) btnSave.style.display = 'block';
    if (btnDelete) btnDelete.style.display = 'block';

    if (isCancelled) {
        // İptal edilmiş
        if (infoSection) {
            infoSection.style.display = 'block';
            if (document.getElementById('canceledBy')) document.getElementById('canceledBy').textContent = details.cancelledBy || '-';
            if (document.getElementById('cancelDate')) document.getElementById('cancelDate').textContent = details.cancelledAt || '-';
            if (document.getElementById('cancelReasonDisplay')) document.getElementById('cancelReasonDisplay').textContent = details.reason || '-';

            const fileLink = document.getElementById('cancelFileLink');
            const fileContainer = document.getElementById('cancelFileContainer');
            if (details.file_path && fileLink && fileContainer) {
                fileLink.href = '/' + details.file_path;
                fileContainer.style.display = 'block';
            } else if (fileContainer) {
                fileContainer.style.display = 'none';
            }
        }
        if (btnSave) btnSave.style.display = 'none'; // İptal edilen işte kaydetme olmaz
        // if (btnDelete) btnDelete.style.display = 'none'; // Silme opsiyonel, kalabilir
    } else {
        // Aktif iş
        if (btnCancel) btnCancel.style.display = 'block';
    }
}

function showCancelForm() {
    const s = document.getElementById('cancelFormSection');
    const b = document.getElementById('btnCancelJob');
    if (s) s.style.display = 'block';
    if (b) b.style.display = 'none';
}

function hideCancelForm() {
    const s = document.getElementById('cancelFormSection');
    const b = document.getElementById('btnCancelJob');
    if (s) s.style.display = 'none';
    if (b) b.style.display = 'block';

    if (document.getElementById('cancelReason')) document.getElementById('cancelReason').value = '';
    if (document.getElementById('cancelFile')) document.getElementById('cancelFile').value = '';
}

async function submitCancel() {
    if (!currentCell || !currentCell.cell_id) {
        alert("Hücre seçili değil.");
        return;
    }

    const reason = document.getElementById('cancelReason').value.trim();
    if (!reason) {
        alert("Lütfen bir iptal nedeni giriniz.");
        return;
    }

    const fileInput = document.getElementById('cancelFile');
    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append('cell_id', currentCell.cell_id);
    formData.append('reason', reason);
    const csrf = (document.getElementById("csrfToken") || {}).value || (document.getElementById("csrfTokenGlobal") || {}).value || "";
    formData.append('csrf_token', csrf);

    if (file) {
        formData.append('file', file);
    }

    try {
        const res = await fetch('/api/cell/cancel', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (data.ok) {
            hideCancelForm();
            closeCellModal();
            // Toast will be shown by socket event
        } else {
            alert("İptal işlemi başarısız: " + (data.error || "Bilinmeyen hata"));
        }
    } catch (e) {
        alert("Hata oluştu: " + e);
    }
}

async function removeCancellation() {
    if (!currentCell || !currentCell.cell_id) {
        alert("Hücre seçili değil.");
        return;
    }

    if (!confirm("İptal durumunu kaldırmak (geri yüklemek) istediğinize emin misiniz?")) return;

    try {
        const csrf = (document.getElementById("csrfToken") || {}).value || (document.getElementById("csrfTokenGlobal") || {}).value || "";
        const res = await fetch('/api/cell/restore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                cell_id: currentCell.cell_id,
                csrf_token: csrf
            })
        });

        const data = await res.json();

        if (data.ok) {
            closeCellModal();
            // Toast will be shown by socket event
        } else {
            alert("Geri yükleme başarısız: " + (data.error || "Bilinmeyen hata"));
        }
    } catch (e) {
        alert("Hata oluştu: " + e);
    }
}

window.updateModalCancellationUI = updateModalCancellationUI;
window.submitCancel = submitCancel;
window.showCancelForm = showCancelForm;
window.hideCancelForm = hideCancelForm;
window.removeCancellation = removeCancellation;

// Observer to handle modal open code
document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById('cellModal');
    if (!modal) return;

    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            const isStyleOpen = m.attributeName === 'style' && modal.style.display !== 'none';
            const isClassOpen = m.attributeName === 'class' && modal.classList.contains('open');

            if (isStyleOpen || isClassOpen) {
                // Modal açıldı
                if (typeof currentCell !== 'undefined' && currentCell.cell_id) {
                    const cell = getCellEl(currentCell.cell_id);
                    if (cell) {
                        const isCancelled = cell.getAttribute('data-status') === 'cancelled';
                        const reason = cell.getAttribute('data-cancellation-reason');

                        // Varsayılan UI'ı ayarla (iptal butonu görünürlüğü vb.)
                        updateModalCancellationUI(isCancelled, {
                            reason: reason,
                            cancelledBy: '...',
                            cancelledAt: '...'
                        });

                        // Detayları çek
                        // Her durumda çekelim ki "İş İptal Et" butonu için doğru state olsun
                        // Veya sadece iptalse çekelim, çünkü aktifse zaten buton görünecek
                        if (isCancelled) {
                            fetch('/api/cell/details/' + currentCell.cell_id)
                                .then(r => r.json())
                                .then(d => {
                                    if (d.ok && d.cell && d.cell.cancellation) {
                                        updateModalCancellationUI(true, {
                                            reason: d.cell.cancellation.reason,
                                            cancelledBy: d.cell.cancellation.by,
                                            cancelledAt: d.cell.cancellation.at,
                                            file_path: d.cell.cancellation.file_path
                                        });
                                    }
                                }).catch(() => { });
                        }
                    }
                }
            }
        }
    });
    observer.observe(modal, { attributes: true, attributeFilter: ['style', 'class'] });
});
