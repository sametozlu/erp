# Rapor Sistemi Geliştirme Görev Dokümanı

## 📋 Genel Bakış

**Proje:** V12 Rapor Sistemi Modernizasyonu  
**Tarih:** 2026-02-01  
**Durum:** Planlama Aşaması

---

## 🎯 Hedefler

1. **Daha Fazla İstatistik Görüntüleme** - AnalyticsRobot'un kapasitesini artırmak
2. **Daha İyi Grafikler** - Yeni görselleştirme türleri eklemek
3. **Veri Doğruluğu** - Hesaplamaların güvenilirliğini sağlamak

---

## 📊 Mevcut Sistem Analizi

### AnalyticsRobot Yapısı

| Bileşen | Dosya | İşlev |
|---------|-------|-------|
| [`AnalyticsRobot.query()`](services/analytics_service.py:295) | Ana sorgu motoru | Boyut × Metrik gruplama |
| [`AnalyticsRobot.get_tops()`](services/analytics_service.py:352) | Enler listesi | Ranking kartları |
| [`AnalyticsRobot.get_cancellation_overtime_stats()`](services/analytics_service.py:483) | İptal/Mesai | Özel istatistikler |
| [`_collect_jobs()`](services/analytics_service.py:215) | Veri toplama | Job filtering |
| [`_dim_values()`](services/analytics_service.py:165) | Boyut değerleri | Entity extraction |
| [`calculate_hours()`](services/analytics_helpers.py:5) | Saat hesabı | Çalışma süresi |
| [`get_job_km()`](services/analytics_helpers.py:32) | KM hesabı | Mesafe hesabı |

### Mevcut Desteklenen Boyutlar

```
project, sub_project, person, vehicle, city, bucket (zaman)
```

### Mevcut Metrikler

```
job_count, work_hours, km_total, usage_count
```

### Whitelist Kuralları (Kısıtlamalar)

```python
# Mevcut - sınırlı kombinasyonlar
("project",): {"work_hours", "job_count"}
("bucket", "person"): {"work_hours", "job_count"}
("person", "vehicle"): {"usage_count", "job_count", "km_total"}
# ... toplam 24 kombinasyon
```

---

## 📌 GÖREV 1: AnalyticsRobot Geliştirme

### 1.1 Yeni Boyutlar Ekleme

**Mevcut Sorun:** Sadece 6 boyut destekleniyor  
**Çözüm:** Daha fazla entity için boyut ekle

#### Eklenmesi Gereken Boyutlar

| Boyut | Açıklama | Kaynak Tablo |
|-------|----------|--------------|
| `team` | Ekip adı | `Team.name` |
| `firma` | Firma/Alt yüklenici | `Person.firma_id` |
| `status` | İş durumu | `Job.status` |
| `shift` | Vardiya | `Job.shift` |
| `seviye` | Personel seviye | `Person.seviye_id` |
| `feedback_outcome` | Geri bildirim sonucu | `JobFeedback.outcome` |

#### Kod Değişikliği

```python
# services/analytics_service.py

ALLOWED_DIMENSIONS = {
    "project", "sub_project", "person", "vehicle", "city", "bucket",
    "team", "firma", "status", "shift", "seviye", "feedback_outcome"  # YENİ
}
```

```python
# _dim_values() fonksiyonuna ekle

def _dim_values(job, dim: str, bucket: str):
    # ... mevcut kod ...
    
    if dim == "team":
        return [job.team_name or job.team.name if job.team else "Atanmamış"]
    
    if dim == "firma":
        # Personel firmasını bul
        firms = set()
        for ja in (job.assignments or []):
            if ja.person and ja.person.firma:
                firms.add(ja.person.firma.name)
        return list(firms) or ["Bilinmiyor"]
    
    if dim == "status":
        return [job.status or "bilinmiyor"]
    
    if dim == "shift":
        return [job.shift or "Belirtilmemiş"]
    
    if dim == "seviye":
        # Personel seviyelerini bul
        levels = set()
        for ja in (job.assignments or []):
            if ja.person and ja.person.seviye:
                levels.add(ja.person.seviye.name)
        return list(levels) or ["Seviyesiz"]
    
    if dim == "feedback_outcome":
        outcomes = set()
        for fb in (job.feedback_rows or []):
            if fb.outcome:
                outcomes.add(fb.outcome)
        return list(outcomes) or ["Yanıtsız"]
    
    return ["N/A"]
```

### 1.2 Yeni Metrikler Ekleme

**Mevcut Sorun:** Sadece 4 metrik var  
**Çözüm:** Hesaplanmış metrikler ekle

#### Eklenmesi Gereken Metrikler

| Metrik | Formül | Açıklama |
|--------|--------|----------|
| `completion_rate` | `completed / total * 100` | Tamamlanma oranı |
| `avg_completion_hours` | `(closed_at - work_date).avg()` | Ortalama bitiş süresi |
| `efficiency_score` | `job_count / work_hours` | Verimlilik |
| `overtime_hours` | Mesai kayıtlarından | Toplam mesai |
| `cancellation_rate` | `cancelled / total * 100` | İptal oranı |
| `overtime_rate` | `overtime_hours / work_hours * 100` | Mesai oranı |

#### Kod Değişikliği

```python
# services/analytics_service.py

ALLOWED_METRICS = {
    "job_count", "work_hours", "km_total", "usage_count",
    "completion_rate", "avg_completion_hours", "efficiency_score",  # YENİ
    "overtime_hours", "cancellation_rate", "overtime_rate"          # YENİ
}
```

```python
# AnalyticsRobot.query() içinde hesaplama mantığı

def _calculate_metrics(grouped_jobs, metric):
    """Hesaplanmış metrikler için yardımcı fonksiyon"""
    if metric == "completion_rate":
        total = len(grouped_jobs)
        completed = sum(1 for j in grouped_jobs if j.status == 'completed')
        return (completed / total * 100) if total > 0 else 0
    
    if metric == "avg_completion_hours":
        completed = [j for j in grouped_jobs if j.closed_at and j.work_date]
        if not completed:
            return 0
        total_hours = sum(
            (j.closed_at - datetime.combine(j.work_date, datetime.min.time())).total_seconds() / 3600
            for j in completed
        )
        return round(total_hours / len(completed), 1)
    
    if metric == "efficiency_score":
        total_jobs = len(grouped_jobs)
        total_hours = sum(calculate_hours(j) for j in grouped_jobs)
        return round(total_jobs / total_hours, 3) if total_hours > 0 else 0
    
    if metric == "overtime_hours":
        # TeamOvertime tablosundan hesapla
        total_overtime = 0
        for j in grouped_jobs:
            if j.team:
                overtime = TeamOvertime.query.filter_by(team_id=j.team.id).first()
                if overtime:
                    total_overtime += overtime.hours or 0
        return round(total_overtime, 1)
    
    if metric == "cancellation_rate":
        total = len(grouped_jobs)
        cancelled = sum(1 for j in grouped_jobs if j.status == 'cancelled')
        return round(cancelled / total * 100, 1) if total > 0 else 0
    
    return 0
```

### 1.3 Whitelist Genişletme

```python
# services/analytics_service.py

WHITELIST = {
    # ... mevcut kurallar ...
    
    # YENİ - Firma bazlı
    ("firma",): {"job_count", "work_hours", "completion_rate"},
    ("firma", "project"): {"job_count", "work_hours"},
    ("bucket", "firma"): {"job_count", "work_hours"},
    
    # YENİ - Seviye bazlı
    ("seviye",): {"job_count", "efficiency_score"},
    ("seviye", "project"): {"job_count", "work_hours"},
    
    # YENİ - Ekip bazlı
    ("team",): {"job_count", "work_hours", "completion_rate"},
    ("team", "bucket"): {"job_count", "work_hours"},
    
    # YENİ - Vardiya bazlı
    ("shift",): {"job_count", "work_hours", "avg_completion_hours"},
    
    # YENİ - Geri bildirim bazlı
    ("feedback_outcome",): {"job_count"},
    ("project", "feedback_outcome"): {"job_count"},
    
    # YENİ - Çapraz analizler
    ("person", "firma"): {"job_count", "work_hours", "efficiency_score"},
    ("team", "person"): {"job_count", "work_hours"},
    ("city", "seviye"): {"job_count", "work_hours"},
}
```

---

## 📈 GÖREV 2: Yeni Grafik Türleri

### 2.1 Gauge Chart - Kullanım Oranları

**Kullanım Alanı:** Araç kullanım oranı, kapasite kullanımı, SLA uyumu

```javascript
// templates/reports_analytics.html

function renderGaugeChart(containerId, value, max, label, thresholds = {}) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const option = {
        series: [{
            type: 'gauge',
            min: 0,
            max: max,
            axisLine: {
                lineStyle: {
                    width: 30,
                    color: [
                        [thresholds.danger || 0.3, '#ff4d4f'],
                        [thresholds.warning || 0.7, '#faad14'],
                        [1, '#52c41a']
                    ]
                }
            },
            pointer: { itemStyle: { color: 'auto' } },
            axisTick: { distance: -30, length: 8, lineStyle: { color: '#fff', width: 2 } },
            splitLine: { distance: -30, length: 30, lineStyle: { color: '#fff', width: 4 } },
            axisLabel: { color: 'auto', distance: 40, fontSize: 14 },
            detail: {
                valueAnimation: true,
                formatter: '{value}%',
                color: 'auto',
                fontSize: 20
            },
            data: [{ value: value, name: label }]
        }]
    };
    
    chart.setOption(option);
    return chart;
}

// Kullanım örneği
renderGaugeChart('vehicle-usage-gauge', 78, 100, 'Araç Kullanımı', {
    danger: 0.4,
    warning: 0.7
});
```

### 2.2 Radar Chart - Çok Boyutlu Karşılaştırma

**Kullanım Alanı:** Ekip performans karşılaştırması, personel yetkinlik analizi

```javascript
// templates/reports_analytics.html

function renderRadarChart(containerId, datasets, indicators) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const option = {
        color: ['#5470c6', '#91cc75', '#fac858', '#ee6666'],
        legend: { data: datasets.map(d => d.name) },
        radar: {
            indicator: indicators.map(ind => ({ name: ind.name, max: ind.max })),
            shape: 'polygon',
            splitArea: { areaStyle: { color: ['#f8f9fa', '#e9ecef', '#f8f9fa', '#e9ecef'] } }
        },
        series: [{
            type: 'radar',
            data: datasets.map(d => ({
                name: d.name,
                value: d.values,
                areaStyle: { opacity: 0.3 }
            }))
        }]
    };
    
    chart.setOption(option);
    return chart;
}

// Kullanım örneği
renderRadarChart('team-comparison-radar', [
    { name: 'A Ekipi', values: [85, 90, 78, 92, 88] },
    { name: 'B Ekipi', values: [78, 82, 95, 85, 90] }
], [
    { name: 'İş Sayısı', max: 100 },
    { name: 'Verimlilik', max: 100 },
    { name: 'Zamanında', max: 100 },
    { name: 'Kalite', max: 100 },
    { name: 'Memnuniyet', max: 100 }
]);
```

### 2.3 Gantt Chart - Proje Progresi

**Kullanım Alanı:** Proje zaman çizelgesi, plan vs gerçekleşme

```javascript
// templates/reports_analytics.html

function renderGanttChart(containerId, tasks) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const categories = tasks.map(t => t.name);
    const seriesData = tasks.map(t => ({
        name: t.name,
        type: 'custom',
        renderItem: function(params, api) {
            const categoryIndex = api.value(0);
            const start = api.coord([t.start, categoryIndex]);
            const end = api.coord([t.end, categoryIndex]);
            const height = api.size([0, 1])[1] * 0.6;
            
            return {
                type: 'rect',
                shape: {
                    x: start[0],
                    y: start[1] - height/2,
                    width: end[0] - start[0],
                    height: height
                },
                style: {
                    fill: t.completed ? '#52c41a' : '#1890ff',
                    stroke: '#fff'
                }
            };
        },
        encode: { x: [1, 2], y: 0 }
    }));
    
    const option = {
        tooltip: {
            formatter: function(params) {
                const task = tasks[params.value[0]];
                return `${task.name}: ${task.start} - ${task.end}`;
            }
        },
        grid: { height: 300, top: 40, bottom: 40 },
        xAxis: { type: 'time', min: 'dataMin', max: 'dataMax' },
        yAxis: { data: categories },
        series: seriesData
    };
    
    chart.setOption(option);
    return chart;
}
```

### 2.4 Word Cloud - Hata Nedenleri

**Kullanım Alanı:** En sık hata kategorileri, geri bildirim analizi

```javascript
// Önce echarts-wordcloud extension'ı ekle
// <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>

function renderWordCloud(containerId, words) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const option = {
        series: [{
            type: 'wordCloud',
            shape: 'circle',
            sizeRange: [12, 60],
            rotationRange: [-90, 90],
            rotationStep: 45,
            gridSize: 8,
            textStyle: {
                fontFamily: 'sans-serif',
                fontWeight: 'bold',
                color: function() {
                    const colors = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de'];
                    return colors[Math.floor(Math.random() * colors.length)];
                }
            },
            data: words.map(w => ({ name: w.text, value: w.count }))
        }]
    };
    
    chart.setOption(option);
    return chart;
}

// Kullanım örneği
renderWordCloud('error-wordcloud', [
    { text: 'Ekipman Eksik', count: 45 },
    { text: 'Hava Koşulları', count: 38 },
    { text: 'İzin Gecikmesi', count: 32 },
    { text: 'Ulaşım Sorunu', count: 28 }
]);
```

### 2.5 Heatmap - Zaman × Entity

**Kullanım Alanı:** Gün × Proje yoğunluğu, Hafta × Personel aktivitesi

```javascript
// templates/reports_analytics.html

function renderHeatmap(containerId, xLabels, yLabels, dataMatrix) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const option = {
        tooltip: { position: 'top' },
        grid: { height: '70%', top: '10%' },
        xAxis: { type: 'category', data: xLabels, splitArea: { show: true } },
        yAxis: { type: 'category', data: yLabels, splitArea: { show: true } },
        visualMap: {
            min: 0,
            max: Math.max(...dataMatrix.flat()),
            calculable: true,
            orient: 'horizontal',
            left: 'center',
            bottom: '5%'
        },
        series: [{
            type: 'heatmap',
            data: dataMatrix.map((row, i) => row.map((val, j) => [j, i, val])),
            label: { show: true },
            emphasis: {
                itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' }
            }
        }]
    };
    
    chart.setOption(option);
    return chart;
}

// Kullanım örneği - Haftalık proje yoğunluğu
renderHeatmap('project-heatmap', 
    ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'],  // Günler
    ['Proje A', 'Proje B', 'Proje C', 'Proje D'],       // Projeler
    [[5, 8, 6, 7, 9, 3, 1], ...]                        // Veri matrisi
);
```

### 2.6 Sankey Diagram - İş Akışı

**Kullanım Alanı:** İl → Proje → Personel akışı, Kaynak dağılımı

```javascript
// templates/reports_analytics.html

function renderSankey(containerId, nodes, links) {
    const chart = echarts.init(document.getElementById(containerId));
    
    const option = {
        tooltip: { trigger: 'item', triggerOn: 'mousemove' },
        series: [{
            type: 'sankey',
            layout: 'none',
            emphasis: { focus: 'adjacency' },
            data: nodes,
            links: links,
            lineStyle: { color: 'source', curveness: 0.5 },
            label: { color: 'rgba(0,0,0,0.7)' }
        }]
    };
    
    chart.setOption(option);
    return chart;
}

// Kullanım örneği
renderSankey('resource-sankey',
    // Düğümler
    [
        { name: 'İstanbul' },
        { name: 'Ankara' },
        { name: 'Proje A' },
        { name: 'Proje B' },
        { name: 'Ekip 1' },
        { name: 'Ekip 2' }
    ],
    // Bağlantılar
    [
        { source: 'İstanbul', target: 'Proje A', value: 50 },
        { source: 'İstanbul', target: 'Proje B', value: 30 },
        { source: 'Ankara', target: 'Proje A', value: 20 },
        { source: 'Proje A', target: 'Ekip 1', value: 40 },
        { source: 'Proje A', target: 'Ekip 2', value: 30 },
        { source: 'Proje B', target: 'Ekip 2', value: 30 }
    ]
);
```

---

## ✅ GÖREV 3: Veri Doğruluğu

### 3.1 Veri Kalite Servisi

```python
# services/data_quality_service.py

from extensions import db
from models import Job, JobAssignment, Person, Project
from datetime import datetime

class DataQualityService:
    
    def __init__(self):
        self.issues = []
    
    def check_all(self):
        """Tüm kontrolleri çalıştır"""
        self.check_missing_completion_times()
        self.check_duplicate_assignments()
        self.check_negative_km()
        self.check_time_consistency()
        self.check_orphan_projects()
        self.check_missing_personnel()
        return self.issues
    
    def check_missing_completion_times(self):
        """Kapanış zamanı olmayan tamamlanmış işler"""
        jobs = Job.query.filter(
            Job.status == 'completed',
            Job.closed_at == None
        ).all()
        
        for job in jobs:
            self.issues.append({
                'type': 'missing_closed_at',
                'job_id': job.id,
                'severity': 'high',
                'description': f"İş #{job.id} tamamlanmış ama closed_at yok",
                'auto_fix': True
            })
    
    def check_duplicate_assignments(self):
        """Çift atama kontrolü"""
        # Personel bazlı çift atama kontrolü
        from sqlalchemy import func
        
        duplicates = db.session.query(
            JobAssignment.job_id,
            JobAssignment.person_id,
            func.count('*').label('count')
        ).group_by(
            JobAssignment.job_id,
            JobAssignment.person_id
        ).having(func.count('*') > 1).all()
        
        for job_id, person_id, count in duplicates:
            self.issues.append({
                'type': 'duplicate_assignment',
                'job_id': job_id,
                'person_id': person_id,
                'severity': 'medium',
                'description': f"İş #{job_id} için {count} çift atama tespit edildi",
                'auto_fix': True
            })
    
    def check_negative_km(self):
        """Negatif KM kontrolü"""
        jobs = Job.query.filter(Job.km_total < 0).all()
        
        for job in jobs:
            self.issues.append({
                'type': 'negative_km',
                'job_id': job.id,
                'severity': 'high',
                'description': f"İş #{job.id} için negatif KM: {job.km_total}",
                'auto_fix': True
            })
    
    def check_time_consistency(self):
        """Zaman tutarlılığı: closed_at >= work_date"""
        jobs = Job.query.filter(
            Job.status == 'completed',
            Job.closed_at != None,
            Job.work_date != None
        ).all()
        
        for job in jobs:
            min_expected = datetime.combine(job.work_date, datetime.min.time())
            if job.closed_at < min_expected:
                self.issues.append({
                    'type': 'time_inconsistency',
                    'job_id': job.id,
                    'severity': 'high',
                    'description': f"İş #{job.id} için closed_at work_date'den önce",
                    'auto_fix': False
                })
    
    def check_orphan_projects(self):
        """Projesiz iş kontrolü"""
        jobs = Job.query.filter(Job.project_id == None).all()
        
        for job in jobs:
            self.issues.append({
                'type': 'orphan_job',
                'job_id': job.id,
                'severity': 'high',
                'description': f"İş #{job.id} için proje atanmamış",
                'auto_fix': False
            })
    
    def check_missing_personnel(self):
        """Personelsiz iş kontrolü"""
        jobs = Job.query.filter(
            Job.status.in_(['pending', 'in_progress']),
            ~Job.assignments.any()
        ).all()
        
        for job in jobs:
            self.issues.append({
                'type': 'missing_personnel',
                'job_id': job.id,
                'severity': 'medium',
                'description': f"İş #{job.id} için personel atanmamış",
                'auto_fix': False
            })
    
    def auto_fix_all(self):
        """Otomatik düzeltmeleri uygula"""
        fixed_count = 0
        
        for issue in self.issues:
            if issue['auto_fix']:
                if self._fix_issue(issue):
                    fixed_count += 1
        
        db.session.commit()
        return fixed_count
    
    def _fix_issue(self, issue):
        """Tek bir sorunu düzelt"""
        if issue['type'] == 'missing_closed_at':
            job = Job.query.get(issue['job_id'])
            if job:
                job.closed_at = job.updated_at
                return True
        
        if issue['type'] == 'negative_km':
            job = Job.query.get(issue['job_id'])
            if job:
                job.km_total = abs(job.km_total)
                return True
        
        if issue['type'] == 'duplicate_assignment':
            # En son atamayı tut, diğerlerini sil
            from models import JobAssignment
            assignments = JobAssignment.query.filter_by(
                job_id=issue['job_id'],
                person_id=issue['person_id']
            ).all()
            if len(assignments) > 1:
                for a in assignments[:-1]:
                    db.session.delete(a)
                return True
        
        return False
    
    def generate_report(self):
        """Kalite raporu oluştur"""
        total = len(self.issues)
        high = sum(1 for i in self.issues if i['severity'] == 'high')
        medium = sum(1 for i in self.issues if i['severity'] == 'medium')
        low = sum(1 for i in self.issues if i['severity'] == 'low')
        
        return {
            'total_issues': total,
            'high_severity': high,
            'medium_severity': medium,
            'low_severity': low,
            'quality_score': max(0, 100 - (high * 10 + medium * 5 + low * 1)),
            'issues': self.issues
        }
```

### 3.2 Saat Hesabı İyileştirme

```python
# services/analytics_helpers.py

def calculate_hours(job):
    """
    Çalışma süresini hesapla.
    Öncelik sırası:
    1. closed_at - published_at (en doğru)
    2. closed_at - work_date (tamamlanan işler)
    3. Shift string'den (regex)
    4. Default değer
    """
    # 1. En doğru yöntem: closed_at ve published_at varsa
    if job.closed_at and job.published_at:
        diff = (job.closed_at - job.published_at).total_seconds() / 3600.0
        if 0.5 <= diff <= 24:  # Makul aralık kontrolü
            return round(diff, 1)
    
    # 2. closed_at varsa work_date'den hesapla
    if job.closed_at and job.work_date:
        work_datetime = datetime.combine(job.work_date, datetime.min.time())
        diff = (job.closed_at - work_datetime).total_seconds() / 3600.0
        if 0.5 <= diff <= 48:  # 2 güne kadar kabul edilebilir
            return round(diff, 1)
    
    # 3. Shift string'den parse et
    if job.shift:
        return _parse_shift_hours(job.shift)
    
    # 4. Default değer
    return 0.0


def _parse_shift_hours(shift_str):
    """Shift string'inden saat çıkar"""
    if not shift_str:
        return 0.0
    
    s = shift_str.strip().lower()
    
    # Regex: "08:30-18:00" veya "8.30-18.00"
    match = re.search(r'(\d{1,2})[:.](\d{2})\s*[-–]\s*(\d{1,2})[:.](\d{2})', s)
    if match:
        h1, m1, h2, m2 = map(int, match.groups())
        start = h1 + m1 / 60.0
        end = h2 + m2 / 60.0
        if end < start:
            end += 24  # Gece vardiyası
        return round(end - start, 1)
    
    # Saat formatı: "8 saat" veya "8s"
    match = re.search(r'(\d+)\s*(?:saat|s|s)', s)
    if match:
        return float(match.group(1))
    
    # Anahtar kelimeler
    keywords = {
        'tam gün': 9.0,
        'tam': 9.0,
        'gece': 8.0,
        'yarım gün': 4.5,
        'yarım': 4.5,
        'yarim': 4.5,
        'sabah': 4.0,
        'öğlen': 4.0,
    }
    
    for key, value in keywords.items():
        if key in s:
            return value
    
    # Bilinmeyen format
    return 0.0
```

### 3.3 KM Hesabı İyileştirme

```python
# services/analytics_helpers.py

def get_job_km(job):
    """
    İş için KM hesapla.
    Öncelik sırası:
    1. PlanCell.lld_hhd_path (LLD/HHD dosyasından)
    2. Job.note alanından regex
    3. Vehicle tablosundan (varsayılan)
    4. 0
    """
    # 1. PlanCell'den (daha doğru)
    if job.cell and job.cell.lld_hhd_path:
        km = _extract_km_from_path(job.cell.lld_hhd_path)
        if km > 0:
            return km
    
    # 2. Job.note'dan
    if job.note:
        km = _extract_km_from_text(job.note)
        if km > 0:
            return km
    
    # 3. Vehicle'dan (varsayılan değil, günlük ortalama)
    if job.team and job.team.vehicle:
        # Araç bazlı ortalama KM kullanılabilir
        # Bu veritabanında tutulmalı
        return 0.0  # Şimdilik 0
    
    return 0.0


def _extract_km_from_text(text):
    """Metinden KM değerini çıkar"""
    if not text:
        return 0.0
    
    patterns = [
        r'(?:km|mesafe|kilometre)[:\s]+(\d+[,.]?\d*)',  # "KM: 150" veya "Mesafe 150.5"
        r'(\d+[,.]?\d*)\s*(?:km|kilometre)',             # "150 km"
        r'Gidiş\s*(\d+)',                                # "Gidiş 75"
        r'Dönüş\s*(\d+)',                                # "Dönüş 75"
    ]
    
    total_km = 0.0
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                km = float(match.replace(',', '.'))
                total_km += km
            except ValueError:
                continue
    
    return round(total_km, 1)


def _extract_km_from_path(path):
    """Dosya yolundan KM çıkar (varsayılan olarak 0)"""
    # Gelecekte: PDF/Excel dosyasından okuma
    return 0.0
```

---

## 📅 Uygulama Planı

### Sprint 1: Temel İyileştirmeler (1 hafta)

| Görev | Dosya | Süre |
|-------|-------|------|
| Whitelist genişletme | `services/analytics_service.py` | 2 saat |
| Yeni boyutlar (team, firma, status) | `services/analytics_service.py` | 4 saat |
| Saat hesabı iyileştirme | `services/analytics_helpers.py` | 2 saat |
| KM hesabı iyileştirme | `services/analytics_helpers.py` | 2 saat |
| DataQualityService | `services/data_quality_service.py` | 4 saat |

### Sprint 2: Yeni Metrikler (1 hafta)

| Görev | Dosya | Süre |
|-------|-------|------|
| completion_rate, efficiency_score | `services/analytics_service.py` | 4 saat |
| avg_completion_hours | `services/analytics_service.py` | 2 saat |
| overtime, cancellation metrikleri | `services/analytics_service.py` | 4 saat |
| Yeni whitelist kombinasyonları | `services/analytics_service.py` | 2 saat |

### Sprint 3: Grafik Geliştirmeleri (1 hafta)

| Görev | Dosya | Süre |
|-------|-------|------|
| Gauge Chart entegrasyonu | `templates/reports_analytics.html` | 2 saat |
| Radar Chart entegrasyonu | `templates/reports_analytics.html` | 2 saat |
| Word Cloud entegrasyonu | `templates/reports_analytics.html` | 2 saat |
| Heatmap iyileştirme | `templates/reports_analytics.html` | 2 saat |
| Sankey Diagram entegrasyonu | `templates/reports_analytics.html` | 2 saat |

### Sprint 4: Veri Kalite Dashboard (1 hafta)

| Görev | Dosya | Süre |
|-------|-------|------|
| Data Quality sekmesi | `templates/reports_analytics.html` | 4 saat |
| API endpoint'leri | `routes/analytics_routes.py` | 2 saat |
| Auto-fix fonksiyonları | `services/data_quality_service.py` | 4 saat |
| Raporlama | `routes/analytics_routes.py` | 2 saat |

---

## ✅ Başarı Kriterleri

### Teknik Metrikler

| Metrik | Hedef | Ölçüm Yöntemi |
|--------|-------|---------------|
| Desteklenen boyut sayısı | 12+ | Code review |
| Desteklenen metrik sayısı | 10+ | Code review |
| Whitelist kombinasyonu | 50+ | Code review |
| Veri kalite skoru | >95% | DataQualityService |
| Otomatik düzeltme oranı | >80% | Log analizi |

### Kullanıcı Deneyimi Metrikleri

| Metrik | Hedef | Ölçüm Yöntemi |
|--------|-------|---------------|
| Yeni grafik türleri | 6+ | Feature list |
| Dashboard yükleme süresi | <3s | Performance test |
| Export süresi (10K kayıt) | <10s | Performance test |
| Kullanıcı memnuniyeti | >4/5 | User feedback |

---

## 📁 İlgili Dosyalar

| Dosya | Açıklama |
|-------|----------|
| [`services/analytics_service.py`](services/analytics_service.py) | Ana robot mantığı |
| [`services/analytics_helpers.py`](services/analytics_helpers.py) | Yardımcı fonksiyonlar |
| [`services/data_quality_service.py`](services/data_quality_service.py) | Veri kalite servisi (yeni) |
| [`routes/analytics_routes.py`](routes/analytics_routes.py) | API route'ları |
| [`templates/reports_analytics.html`](templates/reports_analytics.html) | Frontend arayüzü |

---

## 🚀 Sonraki Adımlar

1. Bu dokümanı onaylayın
2. Sprint 1'i başlatın
3. Haftalık ilerleme toplantıları
4. Her sprint sonunda demo

---

**Doküman Sahibi:** V12 Geliştirme Ekibi  
**Son Güncelleme:** 2026-02-01
