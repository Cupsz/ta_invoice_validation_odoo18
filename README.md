# TA Invoice Validation — Setup Windows + VSCode + Docker

Project Odoo 18 dengan 3 modul: `procurement`, `warehouse`, `invoice_validation`.
Panduan ini untuk **Windows fresh install** (belum ada Docker/Odoo apapun).

---

## 0. Yang Harus Diinstall Dulu (sekali saja)

1. **Docker Desktop for Windows**
   https://www.docker.com/products/docker-desktop/
   - Saat instalasi, pilih opsi **WSL 2 backend** (default, biarkan saja)
   - Setelah install, restart Windows
   - Buka Docker Desktop, tunggu sampai status **"Engine running"** (ikon paus hijau di kanan bawah)

2. **VSCode**
   https://code.visualstudio.com/

3. Buka VSCode, install extension berikut (Ctrl+Shift+X):
   - **Docker** (ms-azuretools.vscode-docker)
   - **Dev Containers** (ms-vscode-remote.remote-containers) — opsional tapi membantu

---

## 1. Extract Project

Extract ZIP project ini ke folder, misalnya:
```
D:\ta-invoice-validation\
```

Buka folder itu di VSCode:
```
File > Open Folder > pilih D:\ta-invoice-validation
```

Struktur yang akan terlihat:
```
ta-invoice-validation/
├── custom_addons/
│   ├── procurement/
│   ├── warehouse/
│   └── invoice_validation/
├── Dockerfile
├── docker-compose.yml
├── odoo.conf
└── README.md
```

---

## 2. Jalankan Project

Buka terminal di VSCode: **Terminal > New Terminal** (atau Ctrl+`)

Pastikan terminal pakai **PowerShell** atau **CMD** (bukan WSL), lalu jalankan:

```powershell
docker compose up --build
```

> Pertama kali build akan agak lama (5-10 menit) karena download image Odoo + install Tesseract OCR + Python packages. Tunggu sampai muncul log seperti ini di terminal:
```
ta_odoo  | ... HTTP service (werkzeug) running on 0.0.0.0:8069
```

**Biarkan terminal ini tetap terbuka** (jangan ditutup) selama mau pakai Odoo.

Kalau mau jalankan di background (biar terminal bisa dipakai lagi):
```powershell
docker compose up --build -d
```

---

## 3. Buka Odoo & Buat Database

1. Buka browser: **http://localhost:8069**
2. Isi form database baru:
   - **Master Password**: `admin`
   - **Database Name**: `ta_odoo`
   - **Email**: `admin@example.com`
   - **Password**: `admin`
   - **Language**: Indonesian (atau English)
   - **Demo data**: boleh dicentang biar ada data contoh (vendor, produk, dll)
3. Klik **Create Database** — tunggu 1-2 menit

---

## 4. Aktifkan Developer Mode

Buka URL: **http://localhost:8069/web?debug=1**

(ini supaya menu Apps menampilkan semua modul termasuk custom)

---

## 5. Update Apps List & Install Modul

1. Buka menu **Apps**
2. Klik tombol **Update Apps List** (pojok kiri atas, ada ikon ⋮ titik tiga kalau tidak terlihat)
3. Hilangkan filter default "Apps" di kotak pencarian (klik tanda **x** di filter)
4. Cari dan install **berurutan**:
   - Cari `Procurement` → klik **Install**
   - Cari `Warehouse` → klik **Install**
   - Cari `Invoice Validation` → klik **Install**

Setelah selesai, akan muncul 3 menu baru di sidebar kiri: **Procurement**, **Warehouse**, **Invoice Validation**.

---

## 6. Tes Alur Lengkap

### A. Procurement (Tim Procurement)
1. Menu **Procurement > Purchase Orders > New**
2. Isi Vendor, Order Date, Expected Receipt Date
3. Tambah baris produk (Product, Qty, Unit Price)
4. Klik **Confirm Order**
5. Klik **🖨 Print PO** untuk cek PDF

### B. Warehouse (Tim Gudang)
1. Menu **Warehouse > Goods Receipts**
2. GR akan otomatis muncul dari PO yang sudah confirmed
3. Buka GR, isi Receive Date, Condition, Qty Received
4. Klik **Validate Receipt**
5. Klik **🖨 Print GR**

### C. Invoice Validation (Tim Finance) ⭐
1. Menu **Invoice Validation > Dashboard > New**
2. Upload file invoice PDF
3. Klik **🔍 Jalankan OCR**
4. Periksa data hasil ekstraksi
5. Klik **✅ Validate** → hasil MATCH / MISMATCH muncul

---

## Perintah Harian (simpan untuk referensi)

Jalankan dari folder project, di terminal VSCode:

| Kebutuhan | Perintah |
|---|---|
| Jalankan project | `docker compose up -d` |
| Stop project | `docker compose down` |
| Lihat log Odoo | `docker compose logs -f odoo` |
| Restart Odoo saja | `docker compose restart odoo` |
| Masuk shell container | `docker exec -it ta_odoo bash` |
| **Update modul setelah edit kode** | `docker exec ta_odoo odoo -d ta_odoo -u invoice_validation --stop-after-init` |
| Update semua 3 modul | `docker exec ta_odoo odoo -d ta_odoo -u procurement,warehouse,invoice_validation --stop-after-init` |
| Reset total (hapus database) | `docker compose down -v` lalu `docker compose up --build` |

> **Catatan penting:** setiap kali kamu edit file Python (.py) atau XML di `custom_addons/`, kamu HARUS jalankan perintah **update modul** di atas supaya perubahan terbaca Odoo. Folder `custom_addons` sudah otomatis ter-mount ke container (live sync), tapi Odoo tetap perlu di-restart/update untuk reload kode.

Workflow paling praktis saat development:
```powershell
# 1. Edit file di VSCode
# 2. Jalankan ini setiap selesai edit:
docker exec ta_odoo odoo -d ta_odoo -u invoice_validation --stop-after-init
# 3. Refresh browser
```

---

## Troubleshooting

**Docker Desktop error "WSL 2 not installed":**
```powershell
wsl --install
```
Lalu restart Windows, buka Docker Desktop lagi.

**Port 8069 sudah dipakai aplikasi lain:**
Edit `docker-compose.yml`, ganti baris ports:
```yaml
ports:
  - "8070:8069"
```
Lalu akses via `http://localhost:8070`

**Container ta_odoo restart terus / crash:**
```powershell
docker compose logs odoo
```
Baca error di log, biasanya soal `odoo.conf` atau addons_path salah.

**Modul tidak muncul di Apps walau sudah Update Apps List:**
Cek apakah folder modul punya `__manifest__.py` (bukan `__manifest__.py.txt` — pastikan ekstensi benar saat extract di Windows).

**Error "ModuleNotFoundError: No module named 'fuzzywuzzy'" saat klik Validate:**
Berarti Dockerfile belum ter-build dengan benar. Jalankan:
```powershell
docker compose up --build --force-recreate
```

**Lupa password master database:**
Master password ada di `odoo.conf`, tambahkan baris:
```ini
admin_passwd = admin
```

**Mau lihat isi PDF invoice yang diupload untuk testing:**
Buat dummy invoice PDF sederhana berisi teks seperti:
```
Invoice Number: INV-001
Vendor: PT Contoh Sukses
PO Number: P00001
Invoice Date: 01/01/2026
Laptop Dell    2    15000000
Total: Rp 30.000.000
```
Simpan sebagai PDF (bisa dari Word/Google Docs export to PDF) lalu upload.

---

## Struktur Modul (ringkasan)

```
custom_addons/
├── procurement/          → Tim Procurement: buat & cetak PO
├── warehouse/             → Tim Gudang: terima barang & cetak GR
└── invoice_validation/    → Tim Finance: OCR + Three-Way Matching (INTI TA)
    ├── models/
    │   ├── ocr_service.py            → ekstrak PDF jadi data
    │   ├── invoice_validation.py     → logic matching
    │   └── invoice_validation_line.py
    └── views/             → Dashboard, Form, Menu
```
