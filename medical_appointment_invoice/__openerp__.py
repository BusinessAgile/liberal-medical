# -*- coding: utf-8 -*-
{
    'name': "Medical Appointment Invoices",

    'summary': """
        Generate invoices from medical appointments when there are "done".
        """,

    'description': """
        This module generate automatic invoice for patient when an appointment is done.
    """,

    'author': "Business Agile, LasLabs",
    'website': "http://businessagile.eu/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Medical',
    'version': '0.2',

    # any module necessary for this one to work correctly
    'depends': ['base', 'medical', 'sale', 'account_voucher'],
    
    'data': [
        'views/medical_patient_view_button.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}