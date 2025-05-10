from odoo import models, fields, api, _
from datetime import datetime, timedelta

class ITCustomer(models.Model):
    _name = 'it.customer'
    _description = 'Client IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nom du client', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partenaire associé', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    # Informations générales
    industry_id = fields.Many2one('res.partner.industry', string='Secteur d\'activité', tracking=True)
    company_size = fields.Selection([
        ('small', 'TPE (< 10 employés)'),
        ('medium', 'PME (10-250 employés)'),
        ('large', 'Grande Entreprise (> 250 employés)')
    ], string='Taille de l\'entreprise', tracking=True)
    strategic_importance = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
        ('critical', 'Critique')
    ], string='Importance stratégique', tracking=True)
    customer_since = fields.Date(string='Client depuis', tracking=True)
    
    # Contacts
    technical_contact_ids = fields.Many2many('res.partner', 'it_customer_technical_contact_rel', 
                                          string='Contacts techniques', domain="[('parent_id', '=', partner_id)]")
    administrative_contact_ids = fields.Many2many('res.partner', 'it_customer_administrative_contact_rel', 
                                               string='Contacts administratifs', domain="[('parent_id', '=', partner_id)]")
    management_contact_ids = fields.Many2many('res.partner', 'it_customer_management_contact_rel', 
                                           string='Contacts direction', domain="[('parent_id', '=', partner_id)]")
    accounting_contact_ids = fields.Many2many('res.partner', 'it_customer_accounting_contact_rel', 
                                           string='Contacts comptabilité', domain="[('parent_id', '=', partner_id)]")
    
    # SLA et heures d'intervention
    sla_response_time = fields.Float(string='Temps de réponse SLA (heures)', default=4.0, tracking=True)
    sla_resolution_time = fields.Float(string='Temps de résolution SLA (heures)', default=24.0, tracking=True)
    availability_rate = fields.Float(string='Taux de disponibilité (%)', default=99.9, tracking=True)
    
    business_hours_start = fields.Float(string='Heures d\'ouverture début', default=8.0, tracking=True)
    business_hours_end = fields.Float(string='Heures d\'ouverture fin', default=18.0, tracking=True)
    work_on_monday = fields.Boolean(string='Lundi', default=True)
    work_on_tuesday = fields.Boolean(string='Mardi', default=True)
    work_on_wednesday = fields.Boolean(string='Mercredi', default=True)
    work_on_thursday = fields.Boolean(string='Jeudi', default=True)
    work_on_friday = fields.Boolean(string='Vendredi', default=True)
    work_on_saturday = fields.Boolean(string='Samedi', default=False)
    work_on_sunday = fields.Boolean(string='Dimanche', default=False)
    
    # Environnement technique
    network_infrastructure = fields.Text(string='Infrastructure réseau', tracking=True)
    server_environment = fields.Text(string='Environnement serveurs', tracking=True)
    security_specifics = fields.Text(string='Spécificités sécurité', tracking=True)
    
    # Relations avec d'autres modèles
    asset_count = fields.Integer(string='Nombre d\'équipements', compute='_compute_counts')
    contract_count = fields.Integer(string='Nombre de contrats', compute='_compute_counts')
    ticket_count = fields.Integer(string='Nombre de tickets', compute='_compute_counts')
    intervention_count = fields.Integer(string='Nombre d\'interventions', compute='_compute_counts')
    
    # Documents
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    
    # KPIs
    last_interaction_date = fields.Date(string='Dernière interaction', compute='_compute_last_interaction', store=True)
    satisfaction_rate = fields.Float(string='Taux de satisfaction (%)', compute='_compute_satisfaction_rate', store=True)
    revenue_ytd = fields.Monetary(string='CA année en cours', currency_field='currency_id', compute='_compute_revenue', store=True)
    revenue_last_year = fields.Monetary(string='CA année précédente', currency_field='currency_id', compute='_compute_revenue', store=True)
    currency_id = fields.Many2one('res.currency', string='Devise', related='partner_id.currency_id')
    
    # Opportunités
    opportunity_ids = fields.One2many('it.customer.opportunity', 'customer_id', string='Opportunités détectées')
    
    # Alertes
    inactivity_alert = fields.Boolean(string='Alerte inactivité', compute='_compute_inactivity_alert', store=True)
    contract_renewal_alert = fields.Boolean(string='Alerte renouvellement contrat', compute='_compute_contract_renewal_alert', store=True)
    
    @api.depends('partner_id')
    def _compute_counts(self):
        for customer in self:
            customer.asset_count = self.env['it.asset'].search_count([('partner_id', '=', customer.partner_id.id)])
            customer.contract_count = self.env['it.contract'].search_count([('partner_id', '=', customer.partner_id.id)])
            customer.ticket_count = self.env['it.ticket'].search_count([('partner_id', '=', customer.partner_id.id)])
            customer.intervention_count = self.env['it.intervention'].search_count([('partner_id', '=', customer.partner_id.id)])
    
    @api.depends('partner_id')
    def _compute_last_interaction(self):
        for customer in self:
            # Rechercher la dernière interaction (ticket, intervention, etc.)
            latest_ticket = self.env['it.ticket'].search([
                ('partner_id', '=', customer.partner_id.id)
            ], order='date_created desc', limit=1)
            
            latest_intervention = self.env['it.intervention'].search([
                ('partner_id', '=', customer.partner_id.id)
            ], order='date_start desc', limit=1)
            
            dates = []
            if latest_ticket and latest_ticket.date_created:
                dates.append(latest_ticket.date_created.date())
            if latest_intervention and latest_intervention.date_start:
                dates.append(latest_intervention.date_start.date())
            
            customer.last_interaction_date = max(dates) if dates else False
    
    @api.depends('partner_id')
    def _compute_satisfaction_rate(self):
        for customer in self:
            # Vérifier si le champ existe dans le modèle
            if 'satisfaction_rating' in self.env['it.intervention']._fields:
                try:
                    # Calculer le taux de satisfaction basé sur les tickets et interventions
                    interventions = self.env['it.intervention'].search([
                        ('partner_id', '=', customer.partner_id.id),
                        ('satisfaction_rating', '!=', False)
                    ])
                    
                    if interventions:
                        total_rating = sum(intervention.satisfaction_rating for intervention in interventions)
                        customer.satisfaction_rate = (total_rating / len(interventions)) * 20  # Sur 100%
                    else:
                        customer.satisfaction_rate = 0
                except Exception:
                    # En cas d'erreur, utiliser une valeur par défaut
                    customer.satisfaction_rate = 0
            else:
                customer.satisfaction_rate = 0
    
    @api.depends('partner_id')
    def _compute_revenue(self):
        for customer in self:
            # Calculer le CA basé sur les factures
            current_year = datetime.now().year
            
            # Factures de l'année en cours
            current_year_invoices = self.env['account.move'].search([
                ('partner_id', '=', customer.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', 'in', ['posted']),
                ('invoice_date', '>=', f'{current_year}-01-01'),
                ('invoice_date', '<=', f'{current_year}-12-31')
            ])
            
            # Factures de l'année précédente
            last_year_invoices = self.env['account.move'].search([
                ('partner_id', '=', customer.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', 'in', ['posted']),
                ('invoice_date', '>=', f'{current_year-1}-01-01'),
                ('invoice_date', '<=', f'{current_year-1}-12-31')
            ])
            
            customer.revenue_ytd = sum(invoice.amount_total for invoice in current_year_invoices)
            customer.revenue_last_year = sum(invoice.amount_total for invoice in last_year_invoices)
    
    @api.depends('last_interaction_date')
    def _compute_inactivity_alert(self):
        for customer in self:
            if customer.last_interaction_date:
                # Alerte si aucune interaction depuis 60 jours
                threshold_date = fields.Date.today() - timedelta(days=60)
                customer.inactivity_alert = customer.last_interaction_date < threshold_date
            else:
                customer.inactivity_alert = False
    
    @api.depends('partner_id')
    def _compute_contract_renewal_alert(self):
        for customer in self:
            # Vérifier s'il y a des contrats qui expirent dans les 30 prochains jours
            threshold_date = fields.Date.today() + timedelta(days=30)
            soon_expiring_contracts = self.env['it.contract'].search([
                ('partner_id', '=', customer.partner_id.id),
                ('end_date', '<=', threshold_date),
                ('end_date', '>=', fields.Date.today()),
                ('state', '=', 'active')
            ])
            
            customer.contract_renewal_alert = bool(soon_expiring_contracts)

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Équipements',
            'res_model': 'it.asset',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
    
    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contrats',
            'res_model': 'it.contract',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
    
    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tickets',
            'res_model': 'it.ticket',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
    
    def action_view_interventions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Interventions',
            'res_model': 'it.intervention',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
    
    def action_send_satisfaction_survey(self):
        # TODO: Implémenter l'envoi d'une enquête de satisfaction
        return {
            'type': 'ir.actions.act_window',
            'name': 'Envoyer une enquête de satisfaction',
            'res_model': 'it.customer.satisfaction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_customer_id': self.id},
        }


class ITCustomerOpportunity(models.Model):
    _name = 'it.customer.opportunity'
    _description = 'Opportunité client IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Titre', required=True, tracking=True)
    customer_id = fields.Many2one('it.customer', string='Client', required=True, tracking=True)
    description = fields.Text(string='Description', tracking=True)
    estimated_revenue = fields.Monetary(string='CA estimé', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Devise', related='customer_id.currency_id')
    probability = fields.Float(string='Probabilité (%)', default=50.0, tracking=True)
    type = fields.Selection([
        ('upsell', 'Vente additionnelle'),
        ('renewal', 'Renouvellement'),
        ('new_service', 'Nouveau service'),
        ('hardware', 'Matériel')
    ], string='Type', tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('qualified', 'Qualifiée'),
        ('proposal', 'Proposition'),
        ('won', 'Gagnée'),
        ('lost', 'Perdue')
    ], string='État', default='draft', tracking=True)
    detection_date = fields.Date(string='Date de détection', default=fields.Date.today, tracking=True)
    expected_closing = fields.Date(string='Clôture prévue', tracking=True)
    
    def action_qualify(self):
        self.write({'state': 'qualified'})
    
    def action_create_proposal(self):
        self.write({'state': 'proposal'})
    
    def action_mark_won(self):
        self.write({'state': 'won'})
    
    def action_mark_lost(self):
        self.write({'state': 'lost'})
