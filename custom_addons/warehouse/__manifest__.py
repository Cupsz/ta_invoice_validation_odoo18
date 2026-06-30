# -*- coding: utf-8 -*-
{
    'name': 'Warehouse - Goods Receipt',
    'version': '18.0.1.0.0',
    'summary': 'Modul Warehouse untuk penerimaan barang',
    'author': 'TA Invoice Validation',
    'category': 'Inventory',
    'depends': ['stock', 'purchase', 'procurement'],
    'data': [
        'security/warehouse_security.xml',
        'security/ir.model.access.csv',
        'views/goods_receipt_views.xml',
        'views/warehouse_menu.xml',
        'report/goods_receipt_report.xml',
        'report/goods_receipt_template.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
