# -*- coding: utf-8 -*-
{
    'name': 'Invoice Validation - OCR & Three-Way Matching',
    'version': '18.0.1.0.0',
    'summary': 'Validasi Invoice otomatis dengan OCR dan Three-Way Matching',
    'author': 'TA Invoice Validation',
    'category': 'Accounting',
    'depends': ['base', 'purchase', 'stock', 'procurement', 'warehouse'],
    'data': [
        'security/invoice_validation_security.xml',
        'security/ir.model.access.csv',
        'data/invoice_validation_sequence.xml',
        'views/invoice_validation_views.xml',
        'views/invoice_validation_dashboard.xml',
        'views/invoice_validation_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'invoice_validation/static/src/css/invoice_validation.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
