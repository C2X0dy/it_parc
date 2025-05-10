from odoo import models, fields, api
from datetime import timedelta

class ITIntervention(models.Model):
    _name = 'it.intervention'
    _description = 'IT Intervention'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char(string='Référence', required=True, copy=False, readonly=True, default='New')
    description = fields.Text(string='Description', required=True)
    date_start = fields.Datetime(string='Date de début', required=True, tracking=True)
    date_end = fields.Datetime(string='Date de fin', required=True, tracking=True)
    duration = fields.Float(string='Durée (heures)', compute='_compute_duration', store=True)
    
    state = fields.Selection([
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('done', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='État', default='planned', tracking=True)
    
    type = fields.Selection([
        ('preventive', 'Maintenance préventive'),
        ('corrective', 'Maintenance corrective'),
        ('installation', 'Installation'),
        ('upgrade', 'Mise à niveau')
    ], string='Type d\'intervention', required=True)
    
    priority = fields.Selection([
        ('0', 'Basse'),
        ('1', 'Normale'),
        ('2', 'Haute'),
        ('3', 'Urgente')
    ], string='Priorité', default='1')
    
    technician_id = fields.Many2one('res.users', string='Technicien', 
                                  domain=[('share', '=', False)], required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    asset_ids = fields.Many2many('it.asset', string='Équipements concernés')
    
    ticket_id = fields.Many2one('it.ticket', string='Ticket associé')
    contract_id = fields.Many2one('it.contract', string='Contrat de maintenance')
    
    # Intégration Stock
    material_line_ids = fields.One2many('it.intervention.material', 'intervention_id', string='Matériel utilisé')
    stock_picking_ids = fields.Many2many('stock.picking', string='Transferts de stock')
    purchase_request_id = fields.Many2one('purchase.request', string='Demande d\'achat')
    
    notes = fields.Text(string='Notes')
    materials_used = fields.Text(string='Matériel utilisé')
    
    report = fields.Html(string='Rapport d\'intervention')
    signature = fields.Binary(string='Signature client')
    signature_name = fields.Char(string='Nom du signataire')
    signature_date = fields.Datetime(string='Date de signature')
    
    color = fields.Integer(string='Couleur')

    # Champs pour la facturation
    billable = fields.Boolean(string='Facturable', default=False)
    invoiced = fields.Boolean(string='Facturée', default=False)
    invoice_id = fields.Many2one('account.move', string='Facture')
    hourly_rate = fields.Float(string='Taux horaire')
    
    # Ajouter le champ satisfaction_rating
    satisfaction_rating = fields.Float(string='Note satisfaction', tracking=True, 
                                      help="Note de satisfaction du client (de 1 à 5)")
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('it.intervention') or 'New'
        return super(ITIntervention, self).create(vals)
    
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for intervention in self:
            if intervention.date_start and intervention.date_end:
                delta = intervention.date_end - intervention.date_start
                intervention.duration = delta.total_seconds() / 3600.0
            else:
                intervention.duration = 0.0
    
    def action_start(self):
        self.write({'state': 'in_progress'})
    
    def action_done(self):
        self.write({'state': 'done'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_plan(self):
        self.write({'state': 'planned'})
    
    # Planification des interventions
    @api.model
    def check_technician_availability(self, technician_id, date_start, date_end):
        """Vérifie si le technicien est disponible dans la plage horaire spécifiée"""
        domain = [
            ('technician_id', '=', technician_id),
            ('state', 'in', ['planned', 'in_progress']),
            '|',
            '&', ('date_start', '<=', date_start), ('date_end', '>=', date_start),
            '&', ('date_start', '<=', date_end), ('date_end', '>=', date_end),
        ]
        conflicting_interventions = self.search(domain)
        return not bool(conflicting_interventions)
    
    @api.model
    def get_available_technicians(self, date_start, date_end):
        """Retourne la liste des techniciens disponibles dans la plage horaire spécifiée"""
        all_technicians = self.env['res.users'].search([('share', '=', False)])
        available_technicians = self.env['res.users']
        
        for technician in all_technicians:
            if self.check_technician_availability(technician.id, date_start, date_end):
                available_technicians |= technician
                
        return available_technicians
    
    @api.model
    def get_technician_schedule(self, technician_id, date_from, date_to):
        """Retourne le planning d'un technicien sur une période donnée"""
        domain = [
            ('technician_id', '=', technician_id),
            ('date_start', '>=', date_from),
            ('date_start', '<=', date_to),
            ('state', 'in', ['planned', 'in_progress']),
        ]
        return self.search(domain)
    
    # Calcul automatique du caractère facturable
    @api.onchange('type', 'contract_id')
    def _onchange_billable_status(self):
        # Les interventions sont facturables par défaut sauf si:
        # - Liées à un contrat de maintenance (sauf demande explicite)
        # - Type d'intervention "maintenance préventive" (généralement incluse dans les contrats)
        if self.contract_id and self.type == 'preventive':
            self.billable = False
        elif not self.contract_id:
            self.billable = True