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
    # Field bantu supaya bisa dicari langsung pakai nomor invoice hasil
    # OCR, tanpa harus tahu kode internal (IV/2026/07/xxxx).
    invoice_number = fields.Char(
        related='validation_id.ocr_invoice_number', string='No. Invoice',
        store=True, readonly=True,
    )

    # --- 1. Identitas pengguna -----------------------------------------
    user_id = fields.Many2one(
        'res.users', string='User', required=True,
        default=lambda self: self.env.user, readonly=True,
    )

    # --- 3. Jenis aktivitas ----------------------------------------
    # Disederhanakan hanya 2 aksi inti sesuai kebutuhan: siapa upload,
    # siapa validasi.
    action_type = fields.Selection([
        ('upload', 'Upload Invoice'),
        ('validate', 'Validasi (Three-Way Matching)'),
    ], string='Jenis Aktivitas', required=True, readonly=True)

    # --- 2. Waktu aktivitas ------------------------------------------
    action_date = fields.Datetime(
        string='Waktu Aktivitas', required=True,
        default=fields.Datetime.now, readonly=True,
    )

    # --- 5. Perubahan data yang terjadi (status invoice sebelum/sesudah)
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

    # --- 6. Hasil aktivitas ------------------------------------------
    # Kesimpulan singkat dari aksi tsb, mis. "Invoice diupload",
    # "Match", "Mismatch".
    result = fields.Char(string='Hasil Aktivitas', readonly=True)

    # --- 7. Status aktivitas -------------------------------------------
    # Apakah prosesnya berhasil dieksekusi sistem atau gagal di tengah
    # jalan (mis. file corrupt saat upload) - beda dengan `result` yang
    # menyimpan kesimpulan bisnisnya (match/mismatch).
    status = fields.Selection([
        ('success', 'Berhasil'),
        ('failed', 'Gagal'),
    ], string='Status Aktivitas', default='success', required=True, readonly=True)

    # --- 4. Data yang diproses ------------------------------------------
    description = fields.Text(string='Keterangan / Data Diproses', readonly=True)

    # Semua field di atas readonly + tidak ada tombol edit di UI (lihat
    # views), supaya log tidak bisa diubah oleh siapapun setelah dibuat -
    # ini penting untuk validitas audit trail.
