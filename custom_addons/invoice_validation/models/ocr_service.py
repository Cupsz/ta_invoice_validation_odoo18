# -*- coding: utf-8 -*-
import base64
import io
import logging
import re

from odoo import models, api

_logger = logging.getLogger(__name__)

HEADER_LABELS = {
    'product', 'produk', 'qty', 'quantity', 'jumlah', 'unit', 'unit price',
    'harga', 'harga satuan', 'subtotal', 'sub total', 'total', '#', 'no',
    'item', 'nama produk', 'nama barang',
}


class OcrService(models.AbstractModel):
    _name = 'ocr.service'
    _description = 'OCR Service - Invoice Data Extraction'

    @api.model
    def extract_from_pdf(self, pdf_base64):
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            raw_text = self._pdf_to_text(pdf_bytes)
            extracted = self._parse_invoice_text(raw_text)
            extracted['raw_text'] = raw_text
            return extracted
        except Exception as e:
            _logger.error("OCR extraction failed: %s", str(e))
            return {
                'invoice_number': '', 'vendor_name': '', 'invoice_date': '',
                'po_number': '', 'lines': [], 'total': 0.0,
                'raw_text': '', 'error': str(e),
            }

    def _pdf_to_text(self, pdf_bytes):
        text = ''
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                page_text = page.extract_text() or ''
                text += page_text
                if page_text and not page_text.endswith('\n'):
                    text += '\n'
            if text.strip():
                return text
        except Exception as e:
            _logger.warning("Direct PDF text extraction failed: %s", e)

        try:
            from pdf2image import convert_from_bytes
            import pytesseract

            images = convert_from_bytes(pdf_bytes, dpi=300)
            for image in images:
                text += pytesseract.image_to_string(
                    image, lang='ind+eng', config='--psm 6'
                ) + '\n'
            return text
        except Exception as e:
            _logger.error("pytesseract OCR failed: %s", e)
            raise

    # ----------------------------------------------------------------
    # Number parsing
    # ----------------------------------------------------------------
    @staticmethod
    def _parse_number(token):
        """
        Parse a numeric string yang formatnya bisa bermacam-macam:
          - '10.00'          -> 10.0      (titik = desimal, gaya default Odoo/Inggris)
          - '100,50'         -> 100.5     (koma = desimal)
          - '45.000'         -> 45000.0   (titik = pemisah ribuan, gaya Indonesia)
          - '1.234.567,89'   -> 1234567.89 (gabungan gaya Indonesia)
          - '1500'           -> 1500.0
        Heuristik: kalau hanya ada SATU titik dan digit di belakangnya
        cuma 1-2 angka, dianggap titik desimal. Kalau lebih dari itu
        (atau ada banyak titik), dianggap pemisah ribuan.
        """
        if token is None:
            return None
        token = re.sub(r'(?i)^\s*(rp\.?|idr)\s*', '', token.strip()).strip()
        if not token or not re.fullmatch(r'[\d.,]+', token):
            return None

        has_comma = ',' in token
        has_dot = '.' in token
        try:
            if has_comma and has_dot:
                return float(token.replace('.', '').replace(',', '.'))
            if has_comma and not has_dot:
                return float(token.replace(',', '.'))
            if has_dot and not has_comma:
                parts = token.split('.')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    return float(token)
                return float(token.replace('.', ''))
            return float(token)
        except ValueError:
            return None

    def _parse_invoice_text(self, text):
        result = {
            'invoice_number': '', 'vendor_name': '', 'invoice_date': '',
            'po_number': '', 'lines': [], 'total': 0.0,
        }

        for pattern in [
            r'(?i)invoice\s*(?:no|number|#|num)[:\s]*([A-Z0-9\-/]+)',
            r'(?i)no\.?\s*invoice[:\s]*([A-Z0-9\-/]+)',
            r'(?i)INV[-/]?\d+',
        ]:
            m = re.search(pattern, text)
            if m:
                result['invoice_number'] = m.group(1).strip() if m.lastindex else m.group(0).strip()
                break

        for pattern in [
            r'(?i)from[:\s]+([^\n]+)',
            r'(?i)vendor[:\s]+([^\n]+)',
            r'(?i)supplier[:\s]+([^\n]+)',
            r'(?i)sold by[:\s]+([^\n]+)',
        ]:
            m = re.search(pattern, text)
            if m:
                result['vendor_name'] = m.group(1).strip()
                break

        # PENTING: harus eksplisit cari label "Invoice Date" / "Tanggal"
        # dulu (bukan cuma kata generik "date"), supaya tidak ketipu oleh
        # baris "Due Date: ..." yang formatnya mirip tapi beda arti.
        # Ambil apa adanya sisa baris setelah label (tanpa memaksa format
        # angka dd/mm/yyyy) karena banyak invoice menulis tanggal dengan
        # nama bulan, mis. "03 July 2026" atau "3 Juli 2026".
        for pattern in [
            r'(?i)invoice\s*date[:\s]+([^\n]+)',
            r'(?i)tanggal\s*invoice[:\s]+([^\n]+)',
            r'(?i)\btanggal\b[:\s]+([^\n]+)',
        ]:
            m = re.search(pattern, text)
            if m:
                result['invoice_date'] = m.group(1).strip()
                break

        for pattern in [
            r'(?i)(?:purchase\s*order|PO)\s*(?:no|number|#|num)?[:\s]*([A-Z0-9\-/]+)',
            r'(?i)no\.?\s*po[:\s]*([A-Z0-9\-/]+)',
            r'(?i)PO[-/]?\d+',
        ]:
            m = re.search(pattern, text)
            if m:
                result['po_number'] = m.group(1).strip() if m.lastindex else m.group(0).strip()
                break

        # IMPORTANT: pakai \b di depan 'total' supaya tidak ke-trigger
        # oleh kata 'Subtotal' (header kolom tabel) yang muncul lebih dulu.
        for pattern in [
            r'(?i)\b(?:grand\s*)?total\b[:\s]*(?:Rp\.?|IDR)?\s*([\d.,]+)',
            r'(?i)\bjumlah\b[:\s]*(?:Rp\.?|IDR)?\s*([\d.,]+)',
        ]:
            m = re.search(pattern, text)
            if m:
                parsed = self._parse_number(m.group(1))
                if parsed is not None:
                    result['total'] = parsed
                break

        result['lines'] = self._parse_line_items(text)
        return result

    def _parse_line_items(self, text):
        """
        Parser baris item berbasis 'penanda nomor urut baris' (1, 2, 3, ...)
        yang biasanya muncul sebagai baris tersendiri pada hasil ekstraksi
        PDF tabel (tiap sel jadi baris sendiri). Jauh lebih tahan banting
        dibanding satu regex raksasa karena tidak terganggu oleh kata-kata
        header tabel seperti 'Product', 'Qty', 'Subtotal', dsb.
        """
        raw_lines = [l.strip() for l in text.split('\n') if l.strip()]
        n = len(raw_lines)
        unit_words = {
            'units', 'unit', 'pcs', 'pc', 'box', 'dus', 'buah',
            'kg', 'gram', 'liter', 'ltr', 'set', 'lembar', 'roll',
        }

        # Cari posisi baris yang berisi PERSIS '1', '2', '3', ... berurutan
        # -> ini penanda kolom '#' / nomor item.
        # Supaya tidak ketipu oleh nilai qty yang KEBETULAN sama dengan
        # nomor urut baris (mis. baris ke-2 qty-nya juga "2"), penanda baru
        # dianggap valid kalau baris SETELAHNYA adalah teks nama produk
        # (bukan angka, bukan header, bukan kata satuan seperti 'Units').
        row_starts = []
        expected = 1
        for idx, l in enumerate(raw_lines):
            if l != str(expected):
                continue
            nxt = raw_lines[idx + 1] if idx + 1 < n else ''
            if not nxt or nxt.lower() in HEADER_LABELS or nxt.lower() in unit_words:
                continue
            if self._parse_number(nxt) is not None:
                continue
            if not re.search(r'[A-Za-z]', nxt):
                continue
            row_starts.append(idx)
            expected += 1

        if not row_starts:
            return []

        items = []
        for k, start in enumerate(row_starts):
            if k + 1 < len(row_starts):
                block = raw_lines[start + 1:row_starts[k + 1]]
            else:
                # baris terakhir: ambil beberapa baris ke depan,
                # berhenti begitu ketemu 'TOTAL' / 'GRAND TOTAL' persis
                lookahead = raw_lines[start + 1:start + 1 + 10]
                block = []
                for l in lookahead:
                    if re.fullmatch(r'(?i)(grand\s*)?total', l):
                        break
                    block.append(l)

            product_name = None
            numeric_tokens = []
            for l in block:
                if l.lower() in HEADER_LABELS:
                    continue
                num = self._parse_number(l)
                if num is not None:
                    numeric_tokens.append(num)
                elif product_name is None and re.search(r'[A-Za-z]', l):
                    product_name = l

            if not product_name or not numeric_tokens:
                continue

            qty = numeric_tokens[0]
            price = numeric_tokens[1] if len(numeric_tokens) >= 2 else 0.0

            items.append({
                'product': product_name,
                'qty': qty,
                'price': price,
            })

        return items
