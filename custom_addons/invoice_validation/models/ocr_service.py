# -*- coding: utf-8 -*-
import base64
import io
import logging
import re

from odoo import models, api

_logger = logging.getLogger(__name__)


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
                text += page.extract_text() or ''
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

        for pattern in [
            r'(?i)(?:invoice\s*)?date[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
            r'(?i)tanggal[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
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

        for pattern in [
            r'(?i)(?:grand\s*)?total[:\s]*(?:Rp\.?|IDR)?\s*([\d.,]+)',
            r'(?i)jumlah[:\s]*(?:Rp\.?|IDR)?\s*([\d.,]+)',
        ]:
            m = re.search(pattern, text)
            if m:
                total_str = m.group(1).replace('.', '').replace(',', '.')
                try:
                    result['total'] = float(total_str)
                except ValueError:
                    pass
                break

        result['lines'] = self._parse_line_items(text)
        return result

    def _parse_line_items(self, text):
        lines = []
        pattern = r'([A-Za-z][^\d\n]{2,40})\s+(\d+(?:[.,]\d+)?)\s+(?:[A-Za-z]+\s+)?([\d.,]+(?:\.\d{2})?)'
        skip_keywords = ['total', 'subtotal', 'tax', 'pajak', 'discount',
                         'grand', 'payment', 'invoice', 'purchase', 'date',
                         'vendor', 'address', 'phone']

        for m in re.finditer(pattern, text):
            product_name = m.group(1).strip()
            qty_str = m.group(2).replace(',', '.')
            price_str = m.group(3).replace('.', '').replace(',', '.')

            if any(kw in product_name.lower() for kw in skip_keywords):
                continue
            try:
                lines.append({
                    'product': product_name,
                    'qty': float(qty_str),
                    'price': float(price_str) if price_str else 0.0,
                })
            except ValueError:
                continue
        return lines
