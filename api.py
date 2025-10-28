from flask import Flask, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json
import io
import re
import os
app = Flask(__name__)

# Drive API ayarları
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FILE_ID = '1aeeOJVc4qff00rdRaLZZAg2PSbJbma0u'  # JSON dosyanın ID'si

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def read_json_from_drive():
    """Drive'dan JSON'u OKU (indirmeden)"""
    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=FILE_ID)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        file_stream.seek(0)
        json_content = file_stream.read().decode('utf-8')
        return json.loads(json_content)

    except Exception as e:
        print(f"❌ Drive okuma hatası: {e}")
        return []

# Cache
_ilac_data = None

def get_ilac_data():
    global _ilac_data
    if _ilac_data is None:
        _ilac_data = read_json_from_drive()
    return _ilac_data

def clean_price(price_str):
    """Fiyat temizleme"""
    if not price_str:
        return 0.0

    price_str = str(price_str).strip()

    if '.' in price_str and ',' in price_str:
        price_str = price_str.replace('.', '').replace(',', '.')
    elif ',' in price_str:
        price_str = price_str.replace(',', '.')

    price_str = re.sub(r'[^\d.]', '', price_str)

    try:
        return float(price_str)
    except ValueError:
        return 0.0

# API Routes
@app.route('/')
def home():
    data = get_ilac_data()
    return jsonify({
        "message": "🏥 Nabisystem İlaç API - Drive Edition",
        "status": "✅ Google Drive'dan OKUYOR",
        "total_ilaclar": len(data),
        "endpoints": {
            "/ilaclar": "Tüm ilaçları listele (sayfalı)",
            "/ilac/<barkod>": "Barkod ile ilaç ara",
            "/ara/<ilac_adi>": "İlaç adı ile ara",
            "/firma/<firma_adi>": "Firmaya göre ara",
            "/etkin-madde/<madde>": "Etkin maddeye göre ara",
            "/stats": "İstatistikler"
        }
    })

@app.route('/stats')
def stats():
    data = get_ilac_data()
    firmalar = set()

    for ilac in data:
        firmalar.add(ilac['Firma bilgileri']['Firma adı'])

    return jsonify({
        "toplam_ilac": len(data),
        "toplam_firma": len(firmalar),
        "status": "✅ Drive'dan canlı okuyor"
    })

# TÜM İLAÇLARI LİSTELE (YENİ)
@app.route('/ilaclar')
def get_ilaclar():
    data = get_ilac_data()

    # Sayfalama parametreleri
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)

    # Sayfalama hesaplama
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit

    ilaclar = []
    for ilac in data[start_idx:end_idx]:
        temiz_fiyat = clean_price(ilac['Fiyat bilgileri']['Etiket fiyatı'])

        ilaclar.append({
            "ilac_adi": ilac['İlaç adı'],
            "barkod": ilac['Kod bilgileri']['Barkod'],
            "firma_adi": ilac['Firma bilgileri']['Firma adı'],
            "etiket_fiyati": temiz_fiyat,
            "orjinal_fiyat": ilac['Fiyat bilgileri']['Etiket fiyatı'],
            "atc_kodu": ilac['Kod bilgileri']['ATC kodu']
        })

    return jsonify({
        "sayfa": page,
        "sayfa_basina": limit,
        "toplam_ilac": len(data),
        "gosterilen": len(ilaclar),
        "ilaclar": ilaclar
    })

# Barkod ile ara
@app.route('/ilac/<barkod>')
def get_ilac_by_barkod(barkod):
    data = get_ilac_data()

    for ilac in data:
        if ilac['Kod bilgileri']['Barkod'] == barkod:
            temiz_fiyat = clean_price(ilac['Fiyat bilgileri']['Etiket fiyatı'])

            return jsonify({
                "ilac_adi": ilac['İlaç adı'],
                "barkod": ilac['Kod bilgileri']['Barkod'],
                "atc_kodu": ilac['Kod bilgileri']['ATC kodu'],
                "firma_adi": ilac['Firma bilgileri']['Firma adı'],
                "etiket_fiyati": temiz_fiyat,
                "etkin_maddeler": ilac['Etkin maddeler'],
                "orjinal_fiyat": ilac['Fiyat bilgileri']['Etiket fiyatı']
            })

    return jsonify({"error": "İlaç bulunamadı"}), 404

# İlaç adı ile ara
@app.route('/ara/<ilac_adi>')
def ara_ilac(ilac_adi):
    data = get_ilac_data()
    results = []

    for ilac in data:
        if ilac_adi.lower() in ilac['İlaç adı'].lower():
            temiz_fiyat = clean_price(ilac['Fiyat bilgileri']['Etiket fiyatı'])

            results.append({
                "ilac_adi": ilac['İlaç adı'],
                "barkod": ilac['Kod bilgileri']['Barkod'],
                "firma_adi": ilac['Firma bilgileri']['Firma adı'],
                "etiket_fiyati": temiz_fiyat,
                "orjinal_fiyat": ilac['Fiyat bilgileri']['Etiket fiyatı']
            })

            if len(results) >= 20:
                break

    return jsonify({
        "aranan": ilac_adi,
        "bulunan": len(results),
        "sonuclar": results
    })

# Firma ile ara
@app.route('/firma/<firma_adi>')
def ara_firma(firma_adi):
    data = get_ilac_data()
    results = []

    for ilac in data:
        if firma_adi.lower() in ilac['Firma bilgileri']['Firma adı'].lower():
            temiz_fiyat = clean_price(ilac['Fiyat bilgileri']['Etiket fiyatı'])

            results.append({
                "ilac_adi": ilac['İlaç adı'],
                "barkod": ilac['Kod bilgileri']['Barkod'],
                "firma_adi": ilac['Firma bilgileri']['Firma adı'],
                "etiket_fiyati": temiz_fiyat
            })

            if len(results) >= 20:
                break

    return jsonify({
        "firma": firma_adi,
        "bulunan": len(results),
        "sonuclar": results
    })

# Etkin madde ile ara
@app.route('/etkin-madde/<madde>')
def ara_etkin_madde(madde):
    data = get_ilac_data()
    results = []

    for ilac in data:
        for etkin_madde in ilac['Etkin maddeler']:
            if madde.lower() in etkin_madde['Etkin madde'].lower():
                temiz_fiyat = clean_price(ilac['Fiyat bilgileri']['Etiket fiyatı'])

                results.append({
                    "ilac_adi": ilac['İlaç adı'],
                    "barkod": ilac['Kod bilgileri']['Barkod'],
                    "firma_adi": ilac['Firma bilgileri']['Firma adı'],
                    "etiket_fiyati": temiz_fiyat,
                    "etkin_madde": f"{etkin_madde['Etkin madde']} ({etkin_madde['Miktar']} {etkin_madde['Birim']})"
                })

                if len(results) >= 20:
                    break
                break

    return jsonify({
        "etkin_madde": madde,
        "bulunan": len(results),
        "sonuclar": results
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
