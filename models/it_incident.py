from odoo import api, fields, models, _

class ITIncident(models.Model):
    _name = 'it.incident'
    _description = 'Incidents informatiques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Référence', required=True, copy=False, 
                       default=lambda self: _('Nouveau'))
    asset_id = fields.Many2one('it.asset', string='Actif concerné')
    date_reported = fields.Datetime(string='Date de signalement', default=fields.Datetime.now)
    reported_by = fields.Many2one('res.users', string='Signalé par', default=lambda self: self.env.user)
    description = fields.Text(string='Description', required=True)
    priority = fields.Selection([
        ('0', 'Basse'),
        ('1', 'Normale'),
        ('2', 'Haute'),
        ('3', 'Critique')
    ], string='Priorité', default='1')
    state = fields.Selection([
        ('new', 'Nouveau'),
        ('in_progress', 'En cours'),
        ('resolved', 'Résolu'),
        ('closed', 'Clôturé')
    ], string='État', default='new', tracking=True)