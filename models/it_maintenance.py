from odoo import api, fields, models, _

class ITMaintenance(models.Model):
    _name = 'it.maintenance'
    _description = 'Maintenance des équipements'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Référence', required=True, copy=False, 
                       default=lambda self: _('Nouveau'))
    asset_id = fields.Many2one('it.asset', string='Actif', required=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    description = fields.Text(string='Description')
    cost = fields.Float(string='Coût')
    state = fields.Selection([
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('done', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='État', default='planned', tracking=True)