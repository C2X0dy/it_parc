from odoo import api, fields, models
from datetime import timedelta

class ITAlert(models.Model):
    _name = 'it.alert'
    _description = 'Alertes IT'
    
    name = fields.Char(string='Nom', required=True)
    equipment_id = fields.Many2one('it.equipment', string='Équipement')
    contract_id = fields.Many2one('it.service.contract', string='Contrat')
    alert_type = fields.Selection([
        ('warranty', 'Garantie'),
        ('license', 'Licence'),
        ('maintenance', 'Maintenance'),
    ], string='Type d\'alerte')
    due_date = fields.Date(string='Date d\'échéance')
    days_before = fields.Integer(string='Jours avant notification', default=30)
    active = fields.Boolean(default=True)
    