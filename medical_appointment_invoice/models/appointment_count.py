from openerp.osv import fields,osv
from openerp import models
from openerp import api

import logging

_logger = logging.getLogger(__name__)


class MedicalAppointment(osv.osv):
    _inherit = 'medical.patient'
    _inherits = { 'res.partner': 'partner_id'}

    def _appointment_count(self, cr, uid, ids, field_name, args, context=None):
        res = dict(map(lambda x: (x,0), ids))
       
        patient = self.pool.get('medical.patient').browse(cr, uid, ids, context=context)
        # apps = self.pool.get('medical.appointment').search([('patient_id', '=', patient.id)])
        apps = patient.env['medical.appointment'].search([('patient_id', '=', patient.id)])
        # _logger.debug(apps)
        # _logger.debug(envv)
        # _logger.debug(patient)
        try:
            for appointment in apps:
                _logger.debug(len(appointment.ids))
                res[patient.id] += len(appointment.ids)
        except:
            pass
        return res

    def _invoice_count(self, cr, uid, ids, field_name, args, context=None):
        res = dict(map(lambda x: (x,0), ids))
       
        patient = self.pool.get('medical.patient').browse(cr, uid, ids, context=context)
        # apps = self.pool.get('medical.appointment').search([('patient_id', '=', patient.id)])
        apps = patient.env['medical.appointment'].search([('patient_id', '=', patient.id), ('validity_status', '=', 'invoiced')])
        # _logger.debug(apps)
        # _logger.debug(envv)
        # context.update({'active_id': patient.id})
        _logger.debug(context.get('id'))
        try:
            for appointment in apps:
                # _logger.debug(len(appointment.invoice_id))
                res[patient.id] += len(appointment.invoice_id)
        except:
            pass
        return res

    _columns = {
        'appointment_count': fields.function(_appointment_count, string='appointments count', type='integer'),
        'appointment_ids': fields.one2many('medical.appointment','patient_id','Medical appointment'),
        'invoice_count': fields.function(_invoice_count, string='invoices count', type='integer'),
        'invoice_ids': fields.one2many('account.invoice','partner_id','Medical invoice',domain=[('active', '=', True)])
    }