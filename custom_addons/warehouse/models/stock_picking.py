# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WarehouseStockPicking(models.Model):
    _inherit = 'stock.picking'

    gr_receive_date = fields.Date(
        string='Receive Date',
        default=fields.Date.context_today,
    )
    gr_condition = fields.Selection([
        ('good', 'Good'),
        ('damaged', 'Damaged'),
        ('rejected', 'Rejected'),
    ], string='Condition', default='good')

    gr_notes = fields.Text(string='Notes')

    gr_number = fields.Char(
        string='GR Number',
        compute='_compute_gr_number',
        store=True,
    )

    @api.depends('name')
    def _compute_gr_number(self):
        for rec in self:
            if rec.name and rec.picking_type_code == 'incoming':
                rec.gr_number = rec.name.replace('WH/IN/', 'GR/')
            else:
                rec.gr_number = rec.name

    def action_print_goods_receipt(self):
        return self.env.ref(
            'warehouse.action_report_goods_receipt'
        ).report_action(self)

    def button_validate_gr(self):
        # Auto-fill qty_done jika kosong
        for move in self.move_ids:
            if move.quantity == 0:
                move.quantity = move.product_uom_qty
        return self.button_validate()
