import time
from datetime import datetime

import datetime as dt


from openerp.osv import fields, orm
from openerp.tools.translate import _
from openerp import SUPERUSER_ID, models
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import api
import logging

_logger = logging.getLogger(__name__)


class ConsultationServicesCategories(orm.Model):
    _inherit = 'product.product'
    _columns = {
        'category': fields.boolean(string="By duration", help="Check if the product is sold by duration, else the product will be sold by a group of appointments.")
    }


class appointment_cluster(orm.Model):
    _name = "medical.appointment.cluster"
    _columns = {
        'name': fields.char('Cluster ID'),
        'appointment_ids': fields.one2many('medical.appointment',
                                            'appointment_cluster_id',
                                            required=True,
                                            ondelete="cascade"),
        'patient_id': fields.many2one('medical.patient',
                                        delegate=True,
                                        string="Patient ID"),
        'consultations': fields.many2one('product.product',
                                        delegate=True,
                                        string="Consultation Service",
                                        domain="[('type', '=','service')]"),
        'physician_id': fields.many2one('medical.physician', string="Physician"),
    }

    def onchange_patient_id(self, cr, uid, ids, patient_id, context=None):
        val = {}
        if patient_id:
            val['patient_id'] = patient_id
            physicians = self.pool.get('medical.physician').search(cr, uid, [['active', '=', 'True']], context=context)
            if len(physicians) == 1:
                val['physician_id'] = physicians[0]
                consultation = self.pool['product.product'].name_search(cr, uid, 'Consultation')
                for service in consultation:
                    if "Consultation (C1)" in service:
                        _logger.debug(service.index("Consultation (C1)"))
                        _logger.debug(service)
                        val['consultations'] = service
        return {'value':val}

appointment_cluster()

class appointment (orm.Model):
    _name = "medical.appointment"
    _inherit = "medical.appointment"

    def copy(self, cr, uid, id, default=None, context={}):
        default.update({'validity_status': 'tobe'})
        return super(appointment, self).copy(cr, uid, id, default, context)

    def _get_duration_human_readable(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for record in self.browse(cr, uid, ids, context):
            td = dt.timedelta(hours=record.duration)
            res[record.id] = 'h'.join(str(td).split(':')[:2])
        return res

    def _check_color(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for record in self.browse(cr, uid, ids, context):
            stage_id = record.consultations.categ_id.id
            color = None
            if stage_id == 3:
                color = 5
            elif stage_id == 4:
                color = 6
            res[record.id] = color
        return res

    def _get_patient_first_name(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for record in self.browse(cr, uid, ids, context):
            res[record.id] = record.patient_id.name.split(' ')[0]
        return res

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
        'invoice_id': fields.many2one('account.invoice', string='Related Invoice', readonly=True),
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
        'appointment_cluster_id': fields.many2one('medical.appointment.cluster', string="Appointment Cluster ID", ondelete='cascade'),
        'color': fields.function(_check_color, string='Couleur', type="integer", store=False),
        'duration_human_readable': fields.function(_get_duration_human_readable, string='Duree humaine', type="char", store=False),
        'patient_first_name': fields.function(_get_patient_first_name, string='Patient Firstname', type="char", store=False),
    }
    _defaults = {
        'validity_status': lambda *a: 'tobe',
        'no_invoice': lambda *a: False
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
    _inherit = 'medical.appointment'

    def onchange_patient_id(self, cr, uid, ids, patient_id, context=None):
        val = {}
        if patient_id:
            val['patient_id'] = patient_id
            physicians = self.pool.get('medical.physician').search(cr, uid, [['active', '=', 'True']], context=context)
            if len(physicians) == 1:
                val['physician_id'] = physicians[0]
                consultation = self.pool['product.product'].name_search(cr, uid, 'Consultation')
                for service in consultation:
                    if "Consultation (C1)" in service:
                        val['consultations'] = service
        return {'value': val}

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
                                              context=None)[0][1]
            _logger.info(stage_name)
            _logger.info(values['stage_id'])
            #FIXME: Getting stage_id instead of stage_name because of translations
            if stage_name in ['Done', 'Absent'] and appointment.validity_status != 'invoiced':
                # Get objects
                invoice_obj = self.pool.get('account.invoice')
                appointment_obj = self.pool.get('medical.appointment')

                apps = appointment
                pats = []

                for app_id in apps:
                    pats.append(
                        appointment_obj.browse(
                            cr,
                            uid,
                            ids).patient_id.id)
                    # _logger.info("pats : %s", pats)
                # if pats.count(pats[0]) == len(pats):
                #     invoice_data = {}
                #     for app_id in apps:

                # _logger.info("appointment : %s", appointment)
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
                quantity = 1
                by_duration = False
                if appointment.appointment_cluster_id:
                    app_cluster = {}
                    cluster_lines = {}
                    cluster_pool = self.pool.get('medical.appointment.cluster')
                    cluster_obj = cluster_pool.browse(cr, uid, appointment.appointment_cluster_id.id, context=context)
                    app_ids = cluster_pool.browse(cr, uid, cluster_obj.id).appointment_ids
                    _logger.debug("app_ids : %s", app_ids)

                else:
                    app_ids = []
                    app_ids.append(appointment.id)

                for app in app_ids:
                    _logger.debug(apps.consultations)


                for app_id in app_ids:
                    if isinstance(app_id, int):
                        appointment = appointment_obj.browse(cr, uid, app_id)
                    else:
                        appointment = app_id

                    if appointment.consultations.uom_id.id in [5]:
                        by_duration = True
                        _logger.debug("%s is by_duration with unit of sale : %s", appointment.consultations.name, appointment.consultations.uos_id.name)

                    if appointment.consultations:
                        _logger.debug("Price : %f", appointment.consultations.lst_price)
                        if appointment.consultations.id in prods_data and by_duration:
                            prods_data[
                                appointment.consultations.id]['quantity'] += appointment.duration
                            _logger.debug("Duration : %f",appointment.duration)
                        else:
                            a = appointment.consultations.product_tmpl_id.property_account_income.id
                            if not a:
                                a = appointment.consultations.categ_id.property_account_income_categ.id
                            if by_duration:
                                quantity = appointment.duration
                            prods_data[
                                appointment.consultations.id] = {
                                'product_id': appointment.consultations.id,
                                'name': appointment.consultations.name,
                                'quantity': quantity,
                                'account_id': a,
                                'uos_id': appointment.consultations.uom_id,
                                'price_unit': appointment.consultations.lst_price}
                            _logger.debug(prods_data)
                            if not by_duration:
                                break
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
                if appointment.validity_status != 'invoiced':
                    try:
                        _logger.debug(app_ids)
                        app_count = len(app_ids)
                        app_done = 0
                        for app_id in app_ids:
                            if isinstance(app_id, int):
                                app_id = appointment
                            _logger.debug(app_id.stage_id.name)
                            if app_id.stage_id.name in ['Done', 'Absent']:
                                app_done += 1
                                if app_done == app_count:
                                    invoice_id = invoice_obj.create(cr, uid, invoice_data)
                                    _logger.debug(invoice_id)
                        if app_done == app_count:
                            for app_id in app_ids:
                                if isinstance(app_id, int):
                                    app_id = appointment
                                app_id.write({'invoice_id': invoice_id, 'validity_status': 'invoiced'})
                                val_history = {
                                    'action': "----  Creating Invoice for {0}  ----".format(app_id.patient_id.partner_id.name.encode('utf-8')),
                                    'appointment_id_history': app_id.id,
                                    'name': uid,
                                    'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                }
                                ait_obj.create(cr, uid, val_history)
                    except Exception as e:
                        raise orm.except_orm(
                            _('UserError'),
                            _(e))

                else:
                    raise orm.except_orm(
                            _('UserError'),
                            _('Appointment already invoiced'))

        return parent_res
