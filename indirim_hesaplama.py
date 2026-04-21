def yuzdelik_indirim(fiyat, yuzde):
    """
    Belirtilen fiyata yüzde indirimi uygular.
    Örnek: yuzdelik_indirim(100, 20) -> 80.0
    """
    indirim_tutari = fiyat * (yuzde / 100)
    yeni_fiyat = fiyat - indirim_tutari
    return yeni_fiyat

def sabit_indirim(fiyat, indirim_miktari):
    """
    Belirtilen fiyattan sabit miktarda indirim yapar.
    Örnek: sabit_indirim(100, 10) -> 90.0
    """
    yeni_fiyat = fiyat - indirim_miktari
    if yeni_fiyat < 0:
        return 0
    return yeni_fiyat

def toplu_alim_indirimi(adet, birim_fiyat):
    """
    Adet sayısına göre kademeli indirim uygular:
    - 10 adetten fazla: %10 indirim
    - 50 adetten fazla: %20 indirim
    - 100 adetten fazla: %30 indirim
    """
    toplam_fiyat = adet * birim_fiyat
    
    if adet > 100:
        indirim_orani = 30
    elif adet > 50:
        indirim_orani = 20
    elif adet > 10:
        indirim_orani = 10
    else:
        indirim_orani = 0
        
    yeni_fiyat = yuzdelik_indirim(toplam_fiyat, indirim_orani)
    return yeni_fiyat

def promosyon_kodu_kontrol(kod, sepet_toplami):
    """
    Promosyon kodlarını kontrol eder ve indirimi uygular.
    """
    kodlar = {
        "YAZ2024": 0.15,  # %15 indirim
        "YENIUEYE": 0.10, # %10 indirim
        "SUEPER50": 50    # 50 TL sabit indirim
    }
    
    if kod in kodlar:
        değer = kodlar[kod]
        # Eğer değer 1'den küçükse (0.15 gibi) yüzde indirimidir
        if değer < 1:
            return yuzdelik_indirim(sepet_toplami, değer * 100)
        # Değer 1'den büyükse sabit tutar indirimidir
        else:
            return sabit_indirim(sepet_toplami, değer)
    else:
        print(f"Hata: '{kod}' geçerli bir promosyon kodu değil.")
        return sepet_toplami

if __name__ == "__main__":
    # Testler
    urun_fiyati = 1000
    
    print(f"Orijinal Fiyat: {urun_fiyati} TL")
    
    # %20 İndirim
    indirimli1 = yuzdelik_indirim(urun_fiyati, 20)
    print(f"%20 İndirimli: {indirimli1} TL")
    
    # 150 TL İndirim
    indirimli2 = sabit_indirim(urun_fiyati, 150)
    print(f"150 TL İndirimli: {indirimli2} TL")
    
    # Toplu Alım (60 adet)
    adet = 60
    birim = 100
    toplu_fiyat = toplu_alim_indirimi(adet, birim)
    print(f"{adet} adet ürün (Birim: {birim} TL) - Toplu Alım İndirimli: {toplu_fiyat} TL")
    
    # Promosyon Kodu
    kod = "YAZ2024"
    sepet = 500
    kodlu_fiyat = promosyon_kodu_kontrol(kod, sepet)
    print(f"Kod: {kod}, Sepet: {sepet} TL -> İndirimli: {kodlu_fiyat} TL")
