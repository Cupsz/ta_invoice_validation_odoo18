# -*- coding: utf-8 -*-
from odoo import models, fields


class InvoiceValidationAuditLog(models.Model):
    _name = 'invoice.validation.audit.log'
    _description = 'Invoice Validation - Audit Log'
    _order = 'action_date desc, id desc'
    _rec_name = 'description'

    validation_id = fields.Many2one(
        'invoice.validation', string='Invoice Validation',
        required=True, ondelete='cascade', index=True,
    )

    # --- Who ---------------------------------------------------------
    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        default=lambda self: self.env.user, readonly=True,
    )

    # --- What ----------------------------------------------------------
    action_type = fields.Selection([
        ('upload', 'Upload Invoice'),
        ('ocr_run', 'Jalankan OCR'),
        ('validate', 'Validasi (Three-Way Matching)'),
        ('reset', 'Reset ke Draft'),
        ('cancel', 'Cancel'),
        ('exception_create', 'Masuk Antrian Pengecualian'),
        ('exception_assign', 'Exception Ditugaskan'),
        ('exception_resolve', 'Exception Diselesaikan'),
        ('exception_escalate', 'Exception Dieskalasi'),
        ('exception_reject', 'Exception Ditolak'),
    ], string='Action', required=True, readonly=True)

    # --- When ------------------------------------------------------
    action_date = fields.Datetime(
        string='Date/Time', required=True,
        default=fields.Datetime.now, readonly=True,
    )

    # --- Impact / hasil ------------------------------------------------
    state_before = fields.Selection([
        ('draft', 'Waiting Validation'),
        ('validated', 'Match'),
        ('mismatch', 'Mismatch'),
        ('cancelled', 'Cancelled'),
    ], string='Status Sebelum', readonly=True)

    state_after = fields.Selection([
        ('draft', 'Waiting Validation'),
        ('validated', 'Match'),
        ('mismatch', 'Mismatch'),
        ('cancelled', 'Cancelled'),
    ], string='Status Sesudah', readonly=True)

    description = fields.Text(string='Description', readonly=True)

    # Semua field di atas readonly + tidak ada tombol edit di UI (lihat
    # views), supaya log tidak bisa diubah oleh siapapun setelah dibuat -
    # ini penting untuk validitas audit trail.
