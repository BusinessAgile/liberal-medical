# -*- coding: utf-8 -*-
{
    'name': "Liber'Agile",

    'summary': """
        Packaging module for Medic'Agile. Installs dependancies
        """,

    'description': """
        
    """,

    'author': "Business Agile",
    'website': "http://businessagile.eu",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Medical',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'medical_appointment_invoice', 'purchase', 'account_accountant', 'sale', 'stock', 'account_voucher'],
}