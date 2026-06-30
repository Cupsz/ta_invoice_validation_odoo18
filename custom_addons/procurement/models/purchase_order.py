# -*- coding: utf-8 -*-
from odoo import models


class ProcurementPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_print_po(self):
        return self.env.ref(
            'procurement.action_report_purchase_order_custom'
        ).report_action(self)
