# -*- coding: utf-8 -*-
from odoo import models, fields, api


class InvoiceValidationLine(models.Model):
    _name = 'invoice.validation.line'
    _description = 'Invoice Validation Line'

    validation_id = fields.Many2one(
        'invoice.validation', string='Invoice Validation',
        required=True, ondelete='cascade',
    )

    product_name = fields.Char(string='Product (Invoice)', required=True)
    product_id = fields.Many2one('product.product', string='Product (Odoo)')
    invoice_qty = fields.Float(string='Qty (Invoice)', digits=(16, 2))
    invoice_price = fields.Float(string='Unit Price (Invoice)', digits=(16, 2))
    invoice_subtotal = fields.Float(
        string='Subtotal (Invoice)', compute='_compute_invoice_subtotal', store=True,
    )

    po_qty = fields.Float(string='Qty (PO)', digits=(16, 2), readonly=True)
    po_price = fields.Float(string='Unit Price (PO)', digits=(16, 2), readonly=True)
    gr_qty = fields.Float(string='Qty Received (GR)', digits=(16, 2), readonly=True)

    match_qty = fields.Boolean(string='Qty Match?', compute='_compute_line_match', store=True)
    match_price = fields.Boolean(string='Price Match?', compute='_compute_line_match', store=True)
    match_status = fields.Selection([
        ('match', 'Match'), ('mismatch', 'Mismatch'), ('pending', 'Pending'),
    ], string='Line Status', default='pending', compute='_compute_line_match', store=True)

    TOLERANCE_PCT = 0.01

    @api.depends('invoice_qty', 'invoice_price')
    def _compute_invoice_subtotal(self):
        for rec in self:
            rec.invoice_subtotal = rec.invoice_qty * rec.invoice_price

    # PENTING: @api.depends wajib ada di sini. Baris invoice dibuat oleh
    # action_run_ocr() SEBELUM po_qty/po_price/gr_qty terisi (masih 0),
    # sehingga match_qty/match_price pertama kali dihitung saat data PO/GR
    # belum ada. Tanpa @api.depends, field 'store=True' ini TIDAK akan
    # dihitung ulang setelah po_qty/po_price/gr_qty di-set belakangan oleh
    # _find_purchase_order()/_find_goods_receipt() -> hasilnya nyangkut
    # (stale) di False walau nilai invoice vs PO sebenarnya sudah cocok.
    @api.depends('invoice_qty', 'invoice_price', 'po_qty', 'po_price', 'gr_qty')
    def _compute_line_match(self):
        for rec in self:
            if rec.po_qty == 0 and rec.po_price == 0:
                rec.match_qty = False
                rec.match_price = False
                rec.match_status = 'pending'
                continue

            if rec.gr_qty > 0:
                qty_diff = abs(rec.invoice_qty - rec.gr_qty) / max(rec.gr_qty, 1)
            else:
                qty_diff = abs(rec.invoice_qty - rec.po_qty) / max(rec.po_qty, 1)
            rec.match_qty = qty_diff <= self.TOLERANCE_PCT

            if rec.po_price > 0:
                price_diff = abs(rec.invoice_price - rec.po_price) / max(rec.po_price, 1)
                rec.match_price = price_diff <= self.TOLERANCE_PCT
            else:
                rec.match_price = False

            rec.match_status = 'match' if (rec.match_qty and rec.match_price) else 'mismatch'
