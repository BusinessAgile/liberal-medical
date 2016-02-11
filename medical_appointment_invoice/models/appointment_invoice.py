import time
from datetime import datetime

# ODOO XML-RPC Interface
import oerplib

from openerp.osv import fields, orm
from openerp.tools.translate import _
from openerp import SUPERUSER_ID, models
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

import logging

_logger = logging.getLogger(__name__)


class appointment (orm.Model):
    _name = "medical.appointment"
    _inherit = "medical.appointment"

    def copy(self, cr, uid, id, default=None, context={}):
        default.update({'validity_status': 'tobe'})
        return super(appointment, self).copy(cr, uid, id, default, context)

    def onchange_appointment_date(self, cr, uid, ids, apt_date):
        if apt_date:
            validity_date = datetime.datetime.fromtimestamp(
                time.mktime(
                    time.strptime(
                        apt_date,
                        "%Y-%m-%d %H:%M:%S")))
            validity_date = validity_date + datetime.timedelta(days=7)
            v = {'appointment_validity_date': str(validity_date)}
            return {'value': v}
        return {}

    _columns = {
        'no_invoice': fields.boolean('Invoice exempt'),
        'appointment_validity_date': fields.datetime('Validity Date'),
        'validity_status': fields.selection(
            [
                ('invoiced',
                 'Invoiced'),
                ('tobe',
                 'To be Invoiced')],
            'Status'),
        'consultations': fields.many2one(
            'product.product',
            'Consultation Service',
            domain=[
                ('type',
                 '=',
                 "service")],
            help="Consultation Services",
            required=True),
    }
    _defaults = {
        'validity_status': lambda *a: 'tobe',
        'no_invoice': lambda *a: True
    }
appointment()

class patient_data (orm.Model):
    _name = "medical.patient"
    _inherit = "medical.patient"

    _columns = {
        'receivable': fields.related(
            'name',
            'credit',
            type='float',
            string='Receivable',
            help='Total amount this patient owes you',
            readonly=True),
}
patient_data()


class AppointmentInvoice(models.Model):
    # _name = "medical.appointment.invoice"
    _inherit = 'medical.appointment'

    def write(self, cr, uid, ids, values, context=None):
        if context is None:
            context = {}
        else:
            context = context.copy()

        parent_res = super(AppointmentInvoice, self).write(cr, uid, ids, values, context=context)
        appointment = self.browse(cr, uid, ids)

        if 'stage_id' in values:
            ait_obj = self.pool['medical.appointment.history']
            stage_proxy = self.pool['medical.appointment.stage']
            stage_name = stage_proxy.name_get(cr, uid, values['stage_id'],
                                              context=context)[0][1]
            if stage_name == 'Done':
                # update history and any other for stage_id.onchange....
                val_history = {
                    'action': "----  Creating Invoice for   ----",
                    'appointment_id_history': ids[0],
                    'name': uid,
                    'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                }
                ait_obj.create(cr, uid, val_history)

                # Get objects 
                invoice_obj = self.pool.get('account.invoice')
                appointment_obj = self.pool.get('medical.appointment')
                # apps = self.pool.get('medical.appointment').browse(cr, uid, appointment)
                apps = appointment
                # Retrieve current id
                # apps = context.get('ids')
                partner_id = appointment
                _logger.info(apps)
                pats = []

                for app_id in apps:
                    pats.append(
                        appointment_obj.browse(
                            cr,
                            uid,
                            ids).patient_id.id)
                    _logger.info(pats)
                # if pats.count(pats[0]) == len(pats):
                #     invoice_data = {}
                #     for app_id in apps:
                
                _logger.info(appointment)
                # Check if the appointment is invoice exempt, and stop the invoicing process
                # if appointment.no_invoice:
                #     raise orm.except_orm(
                #         _('UserError'),
                #         _('The appointment is invoice exempt'))

                # if appointment.validity_status == 'invoiced':
                #     if len(apps) > 1:
                #         raise orm.except_orm(
                #             _('UserError'),
                #             _('At least one of the selected appointments is already invoiced'))
                #     else:
                #         raise orm.except_orm(
                #             _('UserError'),
                #             _('Appointment already invoiced'))
                # if appointment.validity_status == 'no':
                #     if len(apps) > 1:
                #         raise orm.except_orm(
                #             _('UserError'),
                #             _('At least one of the selected appointments can not be invoiced'))
                #     else:
                #         raise orm.except_orm(
                #             _('UserError'),
                #             _('You can not invoice this appointment'))

                if appointment.patient_id.partner_id.id:
                    invoice_data = {}
                    invoice_data['partner_id'] = appointment.patient_id.partner_id.id
                    res = self.pool.get('res.partner').address_get(
                        cr, uid, [
                            appointment.patient_id.partner_id.id], [
                            'contact', 'invoice'])
                    invoice_data['address_contact_id'] = res['contact']
                    invoice_data['address_invoice_id'] = res['invoice']
                    invoice_data[
                        'account_id'] = appointment.patient_id.partner_id.property_account_receivable.id
                    invoice_data[
                        'fiscal_position'] = appointment.patient_id.partner_id.property_account_position and appointment.patient_id.partner_id.property_account_position.id or False
                    invoice_data[
                        'payment_term'] = appointment.patient_id.partner_id.property_payment_term and appointment.patient_id.partner_id.property_payment_term.id or False

                prods_data = {}
                for app_id in apps:
                    appointment = appointment_obj.browse(cr, uid, appointment.id)
                    if appointment.consultations:
                        _logger.debug(
                            'appointment.consultations = %s; appointment.consultations.id = %s',
                            appointment.consultations,
                            appointment.consultations.id)
                        if appointment.consultations.id in prods_data:
                            prods_data[
                                appointment.consultations.id]['quantity'] += 1
                        else:
                            a = appointment.consultations.product_tmpl_id.property_account_income.id
                            if not a:
                                a = appointment.consultations.categ_id.property_account_income_categ.id
                            prods_data[
                                appointment.consultations.id] = {
                                'product_id': appointment.consultations.id,
                                'name': appointment.consultations.name,
                                'quantity': 1,
                                'account_id': a,
                                'price_unit': appointment.consultations.lst_price}
                    else:
                        raise orm.except_orm(
                            _('UserError'),
                            _('No consultation service is connected with the selected appointments'))

                product_lines = []
                for prod_id, prod_data in prods_data.items():
                    product_lines.append((0,
                                          0,
                                          {'product_id': prod_data['product_id'],
                                           'name': prod_data['name'],
                                              'quantity': prod_data['quantity'],
                                              'account_id': prod_data['account_id'],
                                              'price_unit': prod_data['price_unit']}))

                invoice_data['invoice_line'] = product_lines
                invoice_id = invoice_obj.create(cr, uid, invoice_data)

                # appointment_obj.write(
                #     cr, uid, apps, {
                #         'validity_status': 'invoiced'})
                           
        return parent_res