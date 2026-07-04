# -*- coding: utf-8 -*-
{
    'name': 'Procurement - Purchase Order',
    'version': '18.0.1.0.0',
    'summary': 'Modul Procurement untuk membuat Purchase Order',
    'author': 'TA Invoice Validation',
    'category': 'Purchase',
    'depends': ['purchase'],
    'data': [
        'security/procurement_security.xml',
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/purchase_order_views.xml',
        'views/procurement_menu.xml',
        'report/purchase_order_report.xml',
        'report/purchase_order_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'procurement/static/src/js/qty_flexible_field.js',
            'procurement/static/src/js/price_idr_field.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
