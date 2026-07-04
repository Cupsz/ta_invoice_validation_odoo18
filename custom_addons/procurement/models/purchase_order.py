# -*- coding: utf-8 -*-
from odoo import models, fields


class ProcurementPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_print_po(self):
        return self.env.ref(
            'procurement.action_report_purchase_order_custom'
        ).report_action(self)


class ProcurementPurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # ------------------------------------------------------------
    # Odoo standar menghitung ulang price_unit secara OTOMATIS dari
    # Vendor Pricelist (supplierinfo) setiap kali field lain di baris
    # berubah (mis. Quantity, atau menambah baris baru). Karena modul
    # procurement ini dipakai untuk input manual tanpa setup Vendor
    # Pricelist per produk, hasil hitung ulangnya selalu jatuh ke 0
    # dan MENIMPA harga yang sudah diketik user secara manual.
    #
    # PENTING: field yang di-inherit di Odoo digabung (merge) atribut-
    # nya dengan definisi asli. Kalau parameter `compute` tidak disebut
    # ulang di sini, Odoo TETAP memakai compute method bawaan modul
    # `purchase` (`_compute_price_unit`) karena atribut yang tidak
    # ditulis ulang akan diwarisi dari definisi induknya. Itu sebabnya
    # harga tetap ter-reset ke 0 walau field sudah "didefinisikan
    # ulang" di sini tanpa `compute=...`.
    #
    # Solusinya: matikan compute-nya secara EKSPLISIT dengan
    # `compute=None` supaya field ini benar-benar jadi field manual
    # biasa, tidak lagi dihitung ulang otomatis dari Supplier Info.
    # ------------------------------------------------------------
    price_unit = fields.Float(
        string='Unit Price',
        compute=None,
        readonly=False,
        digits='Product Price',
    )
