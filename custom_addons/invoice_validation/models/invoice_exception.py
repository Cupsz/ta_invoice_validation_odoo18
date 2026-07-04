# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class InvoiceException(models.Model):
    _name = 'invoice.exception'
    _description = 'Invoice Exception Queue (FR-07)'
    _order = 'exception_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Exception No.', readonly=True, default='New', copy=False)

    validation_id = fields.Many2one(
        'invoice.validation', string='Invoice Validation',
        required=True, ondelete='cascade', index=True,
    )

    exception_date = fields.Datetime(
        string='Tanggal Masuk Antrian', required=True, default=fields.Datetime.now, readonly=True,
    )

    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'Sedang Ditangani'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('rejected', 'Rejected'),
    ], string='Status', default='open', required=True, tracking=False)

    assigned_to = fields.Many2one('res.users', string='Ditugaskan Ke')

    # --- Laporan kesalahan (snapshot saat exception dibuat) -------------
    # Disimpan sebagai snapshot (bukan compute) supaya laporan tetap
    # akurat mencerminkan kondisi SAAT invoice gagal validasi, walau
    # datanya di invoice.validation berubah belakangan.
    error_categories = fields.Char(string='Kategori Kesalahan', readonly=True)
    error_report = fields.Html(string='Laporan Kesalahan', readonly=True)

    priority = fields.Selection([
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'),
    ], string='Priority', default='normal')

    resolution_notes = fields.Text(string='Catatan Penyelesaian')
    resolved_by = fields.Many2one('res.users', string='Diselesaikan Oleh', readonly=True)
    resolved_date = fields.Datetime(string='Tanggal Selesai', readonly=True)

    # --- Info bantu untuk list/kanban ------------------------------
    invoice_number = fields.Char(related='validation_id.ocr_invoice_number', string='Invoice Number', store=True)
    vendor_name = fields.Char(related='validation_id.ocr_vendor_name', string='Vendor', store=True)
    po_number = fields.Char(related='validation_id.ocr_po_number', string='PO Number', store=True)
    ocr_total = fields.Float(related='validation_id.ocr_total', string='Total', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('invoice.exception') or 'EXC/NEW'
        return super().create(vals_list)

    def action_assign_to_me(self):
        for rec in self:
            rec.write({'assigned_to': self.env.user.id, 'state': 'in_progress'})
            rec.validation_id._log_audit(
                'exception_assign', state_before=rec.validation_id.state, state_after=rec.validation_id.state,
                description=_('Exception %s ditugaskan ke %s.') % (rec.name, self.env.user.name),
            )

    def action_resolve(self):
        for rec in self:
            rec.write({
                'state': 'resolved',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
            })
            rec.validation_id._log_audit(
                'exception_resolve', state_before=rec.validation_id.state, state_after=rec.validation_id.state,
                description=_('Exception %s ditandai selesai oleh %s. Catatan: %s') % (
                    rec.name, self.env.user.name, rec.resolution_notes or '-'
                ),
            )

    def action_escalate(self):
        for rec in self:
            rec.write({'state': 'escalated', 'priority': 'high'})
            rec.validation_id._log_audit(
                'exception_escalate', state_before=rec.validation_id.state, state_after=rec.validation_id.state,
                description=_('Exception %s dieskalasi oleh %s.') % (rec.name, self.env.user.name),
            )

    def action_reject(self):
        for rec in self:
            rec.write({
                'state': 'rejected',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
            })
            rec.validation_id._log_audit(
                'exception_reject', state_before=rec.validation_id.state, state_after=rec.validation_id.state,
                description=_('Exception %s ditolak/invoice dianggap tidak valid oleh %s. Catatan: %s') % (
                    rec.name, self.env.user.name, rec.resolution_notes or '-'
                ),
            )

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'invoice.validation',
            'res_id': self.validation_id.id,
            'views': [[False, 'form']],
            'target': 'current',
        }
