from odoo import api, fields, models
from dateutil.relativedelta import relativedelta

class ITBilling(models.Model):
    _name = 'it.billing'
    _description = 'Facturation récurrente IT'
    
    contract_id = fields.Many2one('it.service.contract', string='Contrat', required=True)
    next_invoice_date = fields.Date(string='Prochaine facturation')
    frequency = fields.Selection([
        ('monthly', 'Mensuelle'),
        ('quarterly', 'Trimestrielle'),
        ('semi_annual', 'Semestrielle'),
        ('annual', 'Annuelle')
    ], string='Fréquence', required=True)
    