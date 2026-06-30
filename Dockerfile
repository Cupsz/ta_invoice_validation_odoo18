FROM odoo:18.0

USER root

# Install Tesseract OCR + Poppler (untuk pdf2image)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages yang dibutuhkan modul invoice_validation
# --break-system-packages diperlukan karena image Odoo 18 pakai Debian/Ubuntu
# terbaru yang menerapkan PEP 668 (externally-managed-environment)
# --ignore-installed diperlukan karena PyPDF2 versi lama sudah terpasang
# lewat paket Debian (python3-pypdf2) dan pip tidak bisa uninstall paket Debian
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    pytesseract==0.3.10 \
    pdf2image==1.17.0 \
    Pillow==10.4.0 \
    fuzzywuzzy==0.18.0 \
    python-Levenshtein==0.25.1 \
    PyPDF2==3.0.1

USER odoo