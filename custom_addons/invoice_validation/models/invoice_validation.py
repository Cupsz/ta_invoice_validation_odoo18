# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
FUZZY_THRESHOLD = 70


class InvoiceValidation(models.Model):
    _name = 'invoice.validation'
    _description = 'Invoice Validation - Three-Way Matching'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Validation Number', readonly=True, default='New', copy=False)

    state = fields.Selection([
        ('draft', 'Waiting Validation'),
        ('incomplete', 'Data Tidak Lengkap'),
        ('duplicate', 'Duplikat'),
        ('validated', 'VALID'),
        ('INVALID', 'INVALID'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)

    invoice_file = fields.Binary(string='Invoice PDF', required=True)
    invoice_filename = fields.Char(string='Filename')
    file_checksum = fields.Char(string='File Checksum', compute='_compute_file_checksum', store=True)

    ocr_invoice_number = fields.Char(string='Invoice Number')
    ocr_vendor_name = fields.Char(string='Vendor (OCR)')
    ocr_invoice_date = fields.Char(string='Invoice Date (OCR)')
    invoice_date = fields.Date(string='Invoice Date')
    ocr_po_number = fields.Char(string='PO Number (OCR)')
    ocr_total = fields.Float(string='Total (OCR)', digits=(16, 0))
    ocr_raw_text = fields.Text(string='Raw OCR Text')

    duplicate_of_id = fields.Many2one('invoice.validation', string='Duplikat Dari', readonly=True)
    missing_fields = fields.Char(string='Field Yang Belum Lengkap', readonly=True)

    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    stock_picking_id = fields.Many2one('stock.picking', string='Goods Receipt')

    line_ids = fields.One2many('invoice.validation.line', 'validation_id', string='Invoice Lines')
    audit_log_ids = fields.One2many(
        'invoice.validation.audit.log', 'validation_id', string='Audit Log',
    )
    exception_ids = fields.One2many(
        'invoice.exception', 'validation_id', string='Exceptions',
    )
    has_open_exception = fields.Boolean(
        string='Ada Exception Aktif', compute='_compute_has_open_exception', store=True,
    )

    @api.depends('exception_ids.state')
    def _compute_has_open_exception(self):
        for rec in self:
            rec.has_open_exception = bool(rec.exception_ids.filtered(
                lambda e: e.state in ('open', 'in_progress', 'escalated')
            ))

    match_vendor = fields.Boolean(string='Vendor Match', readonly=True)
    match_po = fields.Boolean(string='PO Match', readonly=True)
    match_qty = fields.Boolean(string='Qty Match', readonly=True)
    match_price = fields.Boolean(string='Price Match', readonly=True)
    match_total = fields.Boolean(string='Total Match', readonly=True)

    mismatch_notes = fields.Text(string='Mismatch Notes')
    matching_summary = fields.Html(string='Matching Summary', compute='_compute_matching_summary', sanitize=True)

    validated_by = fields.Many2one('res.users', string='Validated By', readonly=True)
    validated_date = fields.Datetime(string='Validated Date', readonly=True)

    @api.depends('invoice_file')
    def _compute_file_checksum(self):
        for rec in self:
            if rec.invoice_file:
                try:
                    raw_bytes = base64.b64decode(rec.invoice_file)
                    rec.file_checksum = hashlib.md5(raw_bytes).hexdigest()
                except Exception:
                    rec.file_checksum = False
            else:
                rec.file_checksum = False

    def _compute_matching_summary(self):
        for rec in self:
            checks = [
                ('Vendor', rec.match_vendor), ('PO Number', rec.match_po),
                ('Quantity', rec.match_qty), ('Price', rec.match_price),
                ('Total', rec.match_total),
            ]
            rows = ''
            for label, ok in checks:
                icon = '✔' if ok else '✘'
                color = 'success' if ok else 'danger'
                rows += f'<tr><td>{label}</td><td class="text-{color}"><strong>{icon}</strong></td></tr>'

            if rec.state == 'validated':
                status_badge = '<span class="badge bg-success fs-6">VALID</span>'
            elif rec.state == 'INVALID':
                status_badge = '<span class="badge bg-danger fs-6">INVALID</span>'
            else:
                status_badge = '<span class="badge bg-secondary fs-6">PENDING</span>'

            rec.matching_summary = f"""
                <table class="table table-sm table-bordered">
                    <thead><tr><th>Check</th><th>Result</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                <div class="mt-2">{status_badge}</div>
            """

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('invoice.validation') or 'IV/NEW'
        records = super().create(vals_list)
        for rec in records:
            rec._log_audit(
                'upload',
                state_before=False,
                state_after=rec.state,
                description=_('Invoice diupload (%s).') % (rec.invoice_filename or rec.name),
            )
        return records

    def _log_audit(self, action_type, state_before, state_after, description):
        """Catat satu entri audit log untuk record ini.
        Dipanggil di setiap aksi utama (upload, OCR, validate, reset,
        cancel) sehingga tersedia jejak who/what/when + status
        sebelum-sesudah untuk keperluan audit dan kepatuhan.
        """
        self.ensure_one()
        self.env['invoice.validation.audit.log'].sudo().create({
            'validation_id': self.id,
            'user_id': self.env.user.id,
            'action_type': action_type,
            'state_before': state_before,
            'state_after': state_after,
            'description': description,
        })

    def _route_to_exception_queue(self, notes, checks):
        """FR-07: Faktur yang gagal validasi harus dialihkan ke antrian
        pengecualian. Dipanggil otomatis dari action_validate() saat hasil
        matching = mismatch. Kalau sudah ada exception aktif untuk invoice
        ini, tidak dibuat duplikat - cukup dianggap masih dalam
        penanganan yang sama.
        """
        self.ensure_one()
        active_exception = self.exception_ids.filtered(
            lambda e: e.state in ('open', 'in_progress', 'escalated')
        )
        if active_exception:
            return active_exception

        failed_categories = [label for label, ok in checks.items() if not ok]
        error_report_html = '<ul>' + ''.join(f'<li>{n}</li>' for n in notes) + '</ul>'

        exception = self.env['invoice.exception'].create({
            'validation_id': self.id,
            'error_categories': ', '.join(failed_categories) if failed_categories else 'Lainnya',
            'error_report': error_report_html,
            'priority': 'high' if len(failed_categories) >= 3 else 'normal',
        })

        self._log_audit(
            'exception_create', state_before='INVALID', state_after='INVALID',
            description=_('Invoice dialihkan ke Antrian Pengecualian (%s). Kategori: %s') % (
                exception.name, exception.error_categories
            ),
        )
        return exception

    def _auto_resolve_exceptions(self):
        """Kalau invoice di-validasi ulang dan hasilnya MATCH, exception
        yang masih aktif otomatis ditutup dengan catatan otomatis -
        supaya antrian pengecualian tidak menumpuk record yang sudah
        tidak relevan.
        """
        self.ensure_one()
        active_exception = self.exception_ids.filtered(
            lambda e: e.state in ('open', 'in_progress', 'escalated')
        )
        for exc in active_exception:
            exc.write({
                'state': 'resolved',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
                'resolution_notes': (exc.resolution_notes or '') +
                    _('\n[Otomatis] Invoice divalidasi ulang dan hasilnya MATCH.'),
            })

    @api.model
    def get_dashboard_data(self):
        """
        Kumpulkan data ringkasan untuk Finance Dashboard:
        - jumlah VALID / INVALID / Waiting
        - 10 riwayat validasi terbaru
        Dipanggil dari widget dashboard (OWL) di frontend.
        """
        match_count = self.search_count([('state', '=', 'validated')])
        mismatch_count = self.search_count([('state', '=', 'INVALID')])
        waiting_count = self.search_count([('state', '=', 'draft')])

        recent = self.search([], limit=10, order='create_date desc')
        recent_data = []
        for rec in recent:
            recent_data.append({
                'id': rec.id,
                'name': rec.name,
                'invoice_number': rec.ocr_invoice_number or '-',
                'vendor_name': rec.ocr_vendor_name or '-',
                'po_number': rec.purchase_order_id.name or '-',
                'state': rec.state,
                'state_label': dict(rec._fields['state'].selection).get(rec.state, rec.state),
                'validated_date': rec.validated_date.strftime('%d/%m/%Y') if rec.validated_date else (
                    rec.create_date.strftime('%d/%m/%Y') if rec.create_date else '-'
                ),
            })

        return {
            'match_count': match_count,
            'mismatch_count': mismatch_count,
            'waiting_count': waiting_count,
            'recent': recent_data,
        }

    @api.model
    def get_validation_detail(self, validation_id):
        """
        Data lengkap satu invoice (header + line items + hasil matching)
        untuk ditampilkan di layar 'Invoice Detail' dan 'Validation Result'
        pada dashboard OWL.
        """
        rec = self.browse(validation_id)
        if not rec.exists():
            return {}

        lines = []
        for line in rec.line_ids:
            lines.append({
                'id': line.id,
                'product_name': line.product_name,
                'invoice_qty': line.invoice_qty,
                'invoice_price': line.invoice_price,
                'invoice_subtotal': line.invoice_subtotal,
                'po_qty': line.po_qty,
                'po_price': line.po_price,
                'gr_qty': line.gr_qty,
                'match_qty': line.match_qty,
                'match_price': line.match_price,
                'match_status': line.match_status,
            })

        return {
            'id': rec.id,
            'name': rec.name,
            'state': rec.state,
            'state_label': dict(rec._fields['state'].selection).get(rec.state, rec.state),
            'can_validate': rec.state == 'draft',
            'invoice_number': rec.ocr_invoice_number or '-',
            'vendor_name': rec.ocr_vendor_name or '-',
            'po_vendor_name': rec.purchase_order_id.partner_id.name or '-',
            'invoice_date': rec.ocr_invoice_date or '-',
            'po_number_ocr': rec.ocr_po_number or '-',
            'po_number': rec.purchase_order_id.name or '-',
            'gr_number': rec.stock_picking_id.name or '-',
            'total': rec.ocr_total,
            'po_total': rec.purchase_order_id.amount_total,
            'lines': lines,
            'raw_text': rec.ocr_raw_text or '',
            'missing_fields': rec.missing_fields or '',
            'duplicate_of_id': rec.duplicate_of_id.id or False,
            'duplicate_of_name': rec.duplicate_of_id.name or '',
            'match_vendor': rec.match_vendor,
            'match_po': rec.match_po,
            'match_qty': rec.match_qty,
            'match_price': rec.match_price,
            'match_total': rec.match_total,
            'mismatch_notes': rec.mismatch_notes or '',
        }

    def action_run_ocr(self):
        self.ensure_one()
        if not self.invoice_file:
            raise UserError(_('Silakan upload file Invoice PDF terlebih dahulu.'))

        ocr = self.env['ocr.service']
        result = ocr.extract_from_pdf(self.invoice_file)

        if result.get('error'):
            raise UserError(_('OCR gagal: %s') % result['error'])

        vals = {
            'ocr_invoice_number': result.get('invoice_number', ''),
            'ocr_vendor_name': result.get('vendor_name', ''),
            'ocr_invoice_date': result.get('invoice_date', ''),
            'ocr_po_number': result.get('po_number', ''),
            'ocr_total': result.get('total', 0.0),
            'ocr_raw_text': result.get('raw_text', ''),
        }

        self.line_ids.unlink()
        line_vals = []
        for line in result.get('lines', []):
            line_vals.append({
                'validation_id': self.id,
                'product_name': line.get('product', ''),
                'invoice_qty': line.get('qty', 0.0),
                'invoice_price': line.get('price', 0.0),
            })

        self.write(vals)
        if line_vals:
            self.env['invoice.validation.line'].create(line_vals)

        self._find_purchase_order()
        self._find_goods_receipt()

        self._log_audit(
            'ocr_run',
            state_before=self.state,
            state_after=self.state,
            description=_(
                'OCR dijalankan. Invoice #: %s, Vendor: %s, PO: %s'
            ) % (
                self.ocr_invoice_number or '-',
                self.ocr_vendor_name or '-',
                self.purchase_order_id.name or (self.ocr_po_number or '-'),
            ),
        )

        # ------------------------------------------------------------
        # STEP 1: Cek duplikasi invoice.
        # Invoice yang sudah pernah diproses sebelumnya (baik file yang
        # sama persis, maupun kombinasi Nomor Invoice + Vendor yang sama)
        # TIDAK BOLEH lanjut ke proses Three-Way Matching.
        # ------------------------------------------------------------
        duplicate = self._check_duplicate_invoice()
        if duplicate:
            self.write({
                'state': 'duplicate',
                'duplicate_of_id': duplicate.id,
                'missing_fields': False,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invoice Duplikat Terdeteksi',
                    'message': _(
                        'Invoice ini terdeteksi sama dengan %s yang sudah pernah '
                        'diproses sebelumnya. Tidak dapat dilanjutkan ke validasi.'
                    ) % duplicate.name,
                    'type': 'danger',
                    'sticky': True,
                }
            }

        # ------------------------------------------------------------
        # STEP 2: Cek kelengkapan field wajib hasil OCR.
        # Kalau ada field wajib yang tidak terbaca, invoice TIDAK BOLEH
        # lanjut ke proses Three-Way Matching sampai datanya lengkap.
        # ------------------------------------------------------------
        missing = self._check_required_fields()
        if missing:
            self.write({
                'state': 'incomplete',
                'missing_fields': ', '.join(missing),
                'duplicate_of_id': False,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Data Invoice Tidak Lengkap',
                    'message': _('Field wajib berikut tidak terbaca dari OCR: %s') % ', '.join(missing),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        # STEP 3: Lolos semua pengecekan awal -> siap untuk divalidasi.
        self.write({'state': 'draft', 'missing_fields': False, 'duplicate_of_id': False})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'OCR Selesai',
                'message': 'Data invoice berhasil diekstrak dan lolos pengecekan awal. Silakan periksa dan klik Validate.',
                'type': 'success',
            }
        }

    def _check_duplicate_invoice(self):
        """
        Deteksi invoice duplikat dengan 2 cara:
        1. File checksum identik (PDF yang sama persis diunggah ulang).
        2. Kombinasi Nomor Invoice + Vendor (hasil OCR) sama dengan
           record lain yang sudah ada (bukan invoice baru, hanya
           diunggah ulang / discan ulang).
        """
        self.ensure_one()
        domain = [('id', '!=', self.id), ('state', '!=', 'cancelled')]

        duplicate = self.env['invoice.validation']
        if self.file_checksum:
            duplicate = self.search(domain + [('file_checksum', '=', self.file_checksum)], limit=1)

        if not duplicate and self.ocr_invoice_number and self.ocr_vendor_name:
            duplicate = self.search(domain + [
                ('ocr_invoice_number', '=ilike', self.ocr_invoice_number.strip()),
                ('ocr_vendor_name', '=ilike', self.ocr_vendor_name.strip()),
            ], limit=1)

        return duplicate

    def _check_required_fields(self):
        """
        Pastikan field wajib pada invoice sudah terbaca lengkap oleh OCR
        sebelum boleh lanjut ke proses Three-Way Matching.
        """
        self.ensure_one()
        missing = []

        if not self.ocr_invoice_number:
            missing.append('Nomor Invoice')
        if not self.ocr_vendor_name:
            missing.append('Nama Vendor')
        if not self.ocr_invoice_date:
            missing.append('Tanggal Invoice')
        if not self.ocr_po_number:
            missing.append('Nomor PO')
        if not self.ocr_total or self.ocr_total <= 0:
            missing.append('Total Invoice')

        if not self.line_ids:
            missing.append('Baris Item Produk')
        else:
            invalid_line = any(
                (not line.product_name) or line.invoice_qty <= 0
                for line in self.line_ids
            )
            if invalid_line:
                missing.append('Detail Item Produk (nama/qty tidak valid)')

        return missing

    def _find_purchase_order(self):
        self.ensure_one()
        po_number = self.ocr_po_number or ''
        if not po_number:
            return

        po = self.env['purchase.order'].search([
            ('name', '=', po_number), ('state', '=', 'purchase'),
        ], limit=1)

        if not po:
            po = self.env['purchase.order'].search([
                ('name', 'ilike', po_number.replace('PO', '').strip()),
                ('state', '=', 'purchase'),
            ], limit=1)

        if not po and self.ocr_vendor_name:
            pos = self.env['purchase.order'].search([('state', '=', 'purchase')])
            try:
                from fuzzywuzzy import fuzz
                best_score, best_po = 0, None
                for p in pos:
                    score = fuzz.ratio(self.ocr_vendor_name.lower(), p.partner_id.name.lower())
                    if score > best_score and score >= FUZZY_THRESHOLD:
                        best_score, best_po = score, p
                po = best_po
            except ImportError:
                _logger.warning("fuzzywuzzy not installed")

        if po:
            self.purchase_order_id = po.id
            for line in self.line_ids:
                for po_line in po.order_line:
                    try:
                        from fuzzywuzzy import fuzz
                        score = fuzz.ratio(line.product_name.lower(), po_line.product_id.name.lower())
                        if score >= FUZZY_THRESHOLD:
                            line.write({
                                'product_id': po_line.product_id.id,
                                'po_qty': po_line.product_qty,
                                'po_price': po_line.price_unit,
                            })
                            break
                    except ImportError:
                        if line.product_name.lower() in po_line.product_id.name.lower():
                            line.write({
                                'product_id': po_line.product_id.id,
                                'po_qty': po_line.product_qty,
                                'po_price': po_line.price_unit,
                            })
                            break

    def _find_goods_receipt(self):
        self.ensure_one()
        if not self.purchase_order_id:
            return

        gr = self.env['stock.picking'].search([
            ('origin', '=', self.purchase_order_id.name),
            ('picking_type_code', '=', 'incoming'),
            ('state', '=', 'done'),
        ], limit=1, order='date_done desc')

        if gr:
            self.stock_picking_id = gr.id
            for line in self.line_ids:
                if line.product_id:
                    for move in gr.move_ids:
                        if move.product_id == line.product_id:
                            line.gr_qty = move.quantity
                            break

    def action_validate(self):
        self.ensure_one()
        if self.state == 'duplicate':
            raise UserError(_('Invoice ini terdeteksi duplikat. Tidak dapat diproses ke validasi.'))
        if self.state == 'incomplete':
            raise UserError(_('Data invoice belum lengkap (%s). Lengkapi terlebih dahulu sebelum validasi.') % (self.missing_fields or ''))
        if not self.purchase_order_id:
            raise UserError(_('Purchase Order tidak ditemukan. Pastikan PO Number di invoice valid.'))

        notes = []

        vendor_match = False
        if self.purchase_order_id and self.ocr_vendor_name:
            po_vendor = self.purchase_order_id.partner_id.name or ''
            try:
                from fuzzywuzzy import fuzz
                score = fuzz.ratio(self.ocr_vendor_name.lower(), po_vendor.lower())
                vendor_match = score >= FUZZY_THRESHOLD
                if not vendor_match:
                    notes.append(f'❌ Vendor tidak cocok: Invoice="{self.ocr_vendor_name}" vs PO="{po_vendor}" ({score}%)')
            except ImportError:
                vendor_match = self.ocr_vendor_name.lower() in po_vendor.lower()
                if not vendor_match:
                    notes.append(f'❌ Vendor tidak cocok: Invoice="{self.ocr_vendor_name}" vs PO="{po_vendor}"')
        else:
            notes.append('❌ Vendor tidak bisa diverifikasi (data OCR kosong)')

        po_match = bool(self.purchase_order_id)
        if not po_match:
            notes.append(f'❌ PO Number tidak ditemukan: "{self.ocr_po_number}"')

        all_lines_match_qty = True
        all_lines_match_price = True
        if not self.line_ids:
            all_lines_match_qty = False
            all_lines_match_price = False
            notes.append('❌ Tidak ada baris item yang bisa diparsing dari invoice')
        else:
            for line in self.line_ids:
                if not line.match_qty:
                    all_lines_match_qty = False
                    ref_qty = line.gr_qty if line.gr_qty else line.po_qty
                    notes.append(f'❌ Qty tidak cocok "{line.product_name}": Invoice={line.invoice_qty} vs {ref_qty}')
                if not line.match_price:
                    all_lines_match_price = False
                    notes.append(f'❌ Harga tidak cocok "{line.product_name}": Invoice={line.invoice_price} vs PO={line.po_price}')

        total_match = False
        if self.purchase_order_id:
            po_total = self.purchase_order_id.amount_total
            if po_total > 0:
                diff_pct = abs(self.ocr_total - po_total) / po_total
                total_match = diff_pct <= 0.01
                if not total_match:
                    notes.append(f'❌ Total tidak cocok: Invoice={self.ocr_total:,.2f} vs PO={po_total:,.2f}')

        all_match = vendor_match and po_match and all_lines_match_qty and all_lines_match_price and total_match

        state_before = self.state
        new_state = 'validated' if all_match else 'INVALID'

        self.write({
            'match_vendor': vendor_match,
            'match_po': po_match,
            'match_qty': all_lines_match_qty,
            'match_price': all_lines_match_price,
            'match_total': total_match,
            'mismatch_notes': '\n'.join(notes) if notes else 'Semua pengecekan berhasil.',
            'state': new_state,
            'validated_by': self.env.user.id,
            'validated_date': fields.Datetime.now(),
        })

        self._log_audit(
            'validate',
            state_before=state_before,
            state_after=new_state,
            description=_('Validasi dijalankan: %s.') % (
                'MATCH - semua pengecekan berhasil' if all_match
                else 'MISMATCH - ' + '; '.join(notes)
            ),
        )

        # --- FR-07: Antrian Pengecualian -------------------------------
        if new_state == 'INVALID':
            self._route_to_exception_queue(notes, {
                'Vendor': vendor_match, 'PO Number': po_match,
                'Quantity': all_lines_match_qty, 'Price': all_lines_match_price,
                'Total': total_match,
            })
        elif new_state == 'validated':
            self._auto_resolve_exceptions()

        msg_type = 'success' if all_match else 'warning'
        msg = '✅ VALID - Invoice valid!' if all_match else '⚠️ INVALID - Dialihkan ke Antrian Pengecualian!'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Hasil Three-Way Matching', 'message': msg, 'type': msg_type, 'sticky': True}
        }

    def action_reset_draft(self):
        self.ensure_one()
        state_before = self.state
        self.write({
            'state': 'draft', 'match_vendor': False, 'match_po': False,
            'match_qty': False, 'match_price': False, 'match_total': False,
            'mismatch_notes': '', 'validated_by': False, 'validated_date': False,
        })
        self._log_audit(
            'reset', state_before=state_before, state_after='draft',
            description=_('Hasil validasi direset ke Waiting Validation oleh %s.') % self.env.user.name,
        )

    def action_cancel(self):
        self.ensure_one()
        state_before = self.state
        self.state = 'cancelled'
        self._log_audit(
            'cancel', state_before=state_before, state_after='cancelled',
            description=_('Invoice validation dibatalkan oleh %s.') % self.env.user.name,
        )
