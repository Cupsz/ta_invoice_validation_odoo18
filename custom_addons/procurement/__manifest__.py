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
        'views/purchase_order_views.xml',
        'views/procurement_menu.xml',
        'report/purchase_order_report.xml',
        'report/purchase_order_template.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
