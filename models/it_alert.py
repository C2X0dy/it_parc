from odoo import api, fields, models, _
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

class ITAlert(models.Model):
    _name = 'it.alert'
    _description = 'IT Alert'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, create_date desc'
    
    name = fields.Char(string='Titre', required=True)
    description = fields.Text(string='Description')
    date_deadline = fields.Date(string='Date limite', required=True)
    days_remaining = fields.Integer(string='Jours restants', compute='_compute_days_remaining', store=True)
    
    alert_type = fields.Selection([
        ('contract', 'Contrat'),
        ('warranty', 'Garantie matériel'),
        ('license', 'Licence logicielle'),
        ('maintenance', 'Maintenance préventive'),
    ], string='Type d\'alerte', required=True)
    
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Important'),
        ('2', 'Urgent'),
        ('3', 'Critique'),
    ], string='Priorité', default='0')
    
    state = fields.Selection([
        ('new', 'Nouvelle'),
        ('in_progress', 'En cours'),
        ('done', 'Traitée'),
        ('cancelled', 'Annulée'),
    ], string='Statut', default='new', tracking=True)
    
    assigned_to_id = fields.Many2one('res.users', string='Assigné à')
    treated_by_id = fields.Many2one('res.users', string='Traité par')
    treated_date = fields.Datetime(string='Date de traitement')
    
    color = fields.Integer(string='Couleur', compute='_compute_color')
    
    # Relations avec d'autres modèles
    contract_id = fields.Many2one('it.contract', string='Contrat')
    asset_id = fields.Many2one('it.asset', string='Équipement')
    software_id = fields.Many2one('it.software', string='Logiciel')
    partner_id = fields.Many2one('res.partner', string='Client')
    license_id = fields.Many2one('it.license', string='Licence')
    
    # Suivi des notifications
    email_sent = fields.Boolean(string='Email envoyé', default=False)
    email_sent_date = fields.Datetime(string='Date d\'envoi email')
    notification_sent = fields.Boolean(string='Notification envoyée', default=False)
    
    # Action de suivi associée
    action_taken = fields.Text(string='Action réalisée')
    resolution_notes = fields.Text(string='Notes de résolution')
    
    @api.depends('date_deadline')
    def _compute_days_remaining(self):
        today = fields.Date.today()
        for alert in self:
            if alert.date_deadline:
                alert.days_remaining = (alert.date_deadline - today).days
            else:
                alert.days_remaining = 999  # Valeur par défaut élevée
    
    @api.depends('priority', 'days_remaining', 'state')
    def _compute_color(self):
        for alert in self:
            if alert.state == 'done':
                alert.color = 10  # Vert
            elif alert.state == 'cancelled':
                alert.color = 0   # Gris
            elif alert.priority == '3' or alert.days_remaining <= 0:
                alert.color = 1   # Rouge
            elif alert.priority == '2' or alert.days_remaining <= 7:
                alert.color = 2   # Orange
            elif alert.priority == '1' or alert.days_remaining <= 15:
                alert.color = 4   # Jaune
            else:
                alert.color = 0   # Gris clair
    
    def action_mark_in_progress(self):
        self.write({
            'state': 'in_progress',
            'assigned_to_id': self.env.user.id,
        })
    
    def action_mark_done(self):
        self.write({
            'state': 'done',
            'treated_by_id': self.env.user.id,
            'treated_date': fields.Datetime.now(),
        })
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_reset_to_new(self):
        self.write({'state': 'new'})
    
    def action_send_email_notification(self):
        self.ensure_one()
        template = self.env.ref('it_parc.email_template_it_alert')
        if template:
            template.send_mail(self.id, force_send=True)
            self.write({
                'email_sent': True,
                'email_sent_date': fields.Datetime.now()
            })
    
    def action_create_followup_task(self):
        """Créer une activité de suivi pour cette alerte"""
        self.ensure_one()
        
        if not self.assigned_to_id:
            self.assigned_to_id = self.env.user.id
        
        self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': f"Traitement de l'alerte: {self.name}",
            'note': f"Cette alerte nécessite votre attention: {self.description}",
            'user_id': self.assigned_to_id.id,
            'res_id': self.id,
            'res_model_id': self.env['ir.model'].search([('model', '=', 'it.alert')], limit=1).id,
            'date_deadline': fields.Date.today() + timedelta(days=1),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Activité créée"),
                'message': _("Une activité de suivi a été créée et assignée."),
                'type': 'success',
                'sticky': False,
            }
        }
        
    @api.model
    def _cron_generate_contract_alerts(self):
        """Génère les alertes pour les contrats proches de l'expiration"""
        today = fields.Date.today()
        
        # Dates de référence pour les alertes (30, 15, 7 jours)
        date_30_days = today + timedelta(days=30)
        date_15_days = today + timedelta(days=15)
        date_7_days = today + timedelta(days=7)
        
        # Recherche des contrats actifs qui expirent dans les délais d'alerte
        contracts = self.env['it.contract'].search([
            ('state', '=', 'active'),
            ('end_date', '>=', today),
            ('end_date', '<=', date_30_days),
        ])
        
        for contract in contracts:
            # Déterminer la priorité en fonction de la proximité de l'expiration
            priority = '0'  # Normal par défaut
            if contract.end_date <= date_7_days:
                priority = '2'  # Urgent
            elif contract.end_date <= date_15_days:
                priority = '1'  # Important
            
            # Vérifier si une alerte pour ce contrat existe déjà
            existing_alert = self.search([
                ('contract_id', '=', contract.id),
                ('state', 'in', ['new', 'in_progress']),
                ('alert_type', '=', 'contract')
            ], limit=1)
            
            if not existing_alert:
                # Créer une nouvelle alerte
                days_to_expiry = (contract.end_date - today).days
                self.create({
                    'name': f"Contrat {contract.name} expire dans {days_to_expiry} jours",
                    'description': f"Le contrat {contract.name} pour {contract.partner_id.name} expire le {contract.end_date}.",
                    'date_deadline': contract.end_date,
                    'alert_type': 'contract',
                    'priority': priority,
                    'contract_id': contract.id,
                    'partner_id': contract.partner_id.id,
                })
    
    @api.model
    def _cron_generate_warranty_alerts(self):
        """Génère les alertes pour les équipements dont la garantie expire bientôt"""
        today = fields.Date.today()
        
        # Dates de référence pour les alertes (30, 15, 7 jours)
        date_30_days = today + timedelta(days=30)
        date_15_days = today + timedelta(days=15)
        date_7_days = today + timedelta(days=7)
        
        # Recherche des équipements avec garantie expirant dans les délais d'alerte
        assets = self.env['it.asset'].search([
            ('warranty_end', '>=', today),
            ('warranty_end', '<=', date_30_days),
        ])
        
        for asset in assets:
            # Déterminer la priorité en fonction de la proximité de l'expiration
            priority = '0'  # Normal par défaut
            if asset.warranty_end <= date_7_days:
                priority = '2'  # Urgent
            elif asset.warranty_end <= date_15_days:
                priority = '1'  # Important
            
            # Vérifier si une alerte pour cet équipement existe déjà
            existing_alert = self.search([
                ('asset_id', '=', asset.id),
                ('state', 'in', ['new', 'in_progress']),
                ('alert_type', '=', 'warranty')
            ], limit=1)
            
            if not existing_alert:
                # Créer une nouvelle alerte
                days_to_expiry = (asset.warranty_end - today).days
                self.create({
                    'name': f"Garantie pour {asset.name} expire dans {days_to_expiry} jours",
                    'description': f"La garantie de l'équipement {asset.name} ({asset.asset_type}) expire le {asset.warranty_end}.",
                    'date_deadline': asset.warranty_end,
                    'alert_type': 'warranty',
                    'priority': priority,
                    'asset_id': asset.id,
                    'partner_id': asset.partner_id.id,
                })
    
    @api.model
    def _cron_generate_license_alerts(self):
        """Génère les alertes pour les licences logicielles expirant bientôt"""
        today = fields.Date.today()
        
        # Dates de référence pour les alertes (30, 15, 7 jours)
        date_30_days = today + timedelta(days=30)
        date_15_days = today + timedelta(days=15)
        date_7_days = today + timedelta(days=7)
        
        # Recherche des licences logicielles expirant dans les délais d'alerte
        licenses = self.env['it.license'].search([
            ('state', '=', 'active'),
            ('expiration_date', '>=', today),
            ('expiration_date', '<=', date_30_days),
        ])
        
        for license in licenses:
            # Déterminer la priorité en fonction de la proximité de l'expiration
            priority = '0'  # Normal par défaut
            if license.expiration_date <= date_7_days:
                priority = '2'  # Urgent
            elif license.expiration_date <= date_15_days:
                priority = '1'  # Important
            
            # Vérifier si une alerte pour cette licence existe déjà
            existing_alert = self.search([
                ('license_id', '=', license.id),
                ('state', 'in', ['new', 'in_progress']),
                ('alert_type', '=', 'license')
            ], limit=1)
            
            if not existing_alert:
                # Créer une nouvelle alerte
                days_to_expiry = (license.expiration_date - today).days
                self.create({
                    'name': f"Licence {license.name} expire dans {days_to_expiry} jours",
                    'description': f"La licence {license.name} pour {license.software_id.name} expire le {license.expiration_date}.",
                    'date_deadline': license.expiration_date,
                    'alert_type': 'license',
                    'priority': priority,
                    'license_id': license.id,
                    'partner_id': license.vendor_id.id if license.vendor_id else False,
                })
    
    @api.model
    def _cron_generate_maintenance_alerts(self):
        """Génère les alertes pour les maintenances préventives à planifier"""
        today = fields.Date.today()
        
        # Pour les équipements nécessitant une maintenance préventive tous les X mois
        # (on suppose que vous avez un champ maintenance_interval sur it.asset)
        assets = self.env['it.asset'].search([
            ('maintenance_interval', '>', 0)
        ])
        
        for asset in assets:
            # Calculer la date de prochaine maintenance
            last_maintenance = self.env['it.intervention'].search([
                ('asset_id', '=', asset.id),
                ('intervention_type', '=', 'maintenance'),
                ('state', '=', 'done')
            ], limit=1, order='date_end desc')
            
            if last_maintenance:
                next_maintenance_date = fields.Date.from_string(last_maintenance.date_end) + relativedelta(months=asset.maintenance_interval)
            else:
                # Si aucune maintenance n'a été effectuée, utiliser la date d'achat + intervalle
                next_maintenance_date = fields.Date.from_string(asset.purchase_date) + relativedelta(months=asset.maintenance_interval)
            
            # Si la prochaine maintenance est due dans les 30 prochains jours
            if today <= next_maintenance_date <= (today + timedelta(days=30)):
                # Vérifier si une alerte existe déjà
                existing_alert = self.search([
                    ('asset_id', '=', asset.id),
                    ('state', 'in', ['new', 'in_progress']),
                    ('alert_type', '=', 'maintenance')
                ], limit=1)
                
                if not existing_alert:
                    # Déterminer la priorité
                    priority = '0'  # Normal par défaut
                    days_to_maintenance = (next_maintenance_date - today).days
                    if days_to_maintenance <= 7:
                        priority = '2'  # Urgent
                    elif days_to_maintenance <= 15:
                        priority = '1'  # Important
                    
                    # Créer une nouvelle alerte
                    self.create({
                        'name': f"Maintenance préventive pour {asset.name}",
                        'description': f"Une maintenance préventive est due pour {asset.name} ({asset.asset_type}) le {next_maintenance_date}.",
                        'date_deadline': next_maintenance_date,
                        'alert_type': 'maintenance',
                        'priority': priority,
                        'asset_id': asset.id,
                        'partner_id': asset.partner_id.id,
                    })
    
    @api.model
    def _cron_generate_license_compliance_alerts(self):
        """Génère les alertes pour les licences non conformes"""
        # Recherche des licences en sur-utilisation
        over_used_licenses = self.env['it.license'].search([
            ('state', '=', 'active'),
            ('compliance_status', '=', 'over_used')
        ])
        
        for license in over_used_licenses:
            # Vérifier si une alerte pour cette licence existe déjà
            existing_alert = self.search([
                ('license_id', '=', license.id),
                ('state', 'in', ['new', 'in_progress']),
                ('alert_type', '=', 'license_compliance')
            ], limit=1)
            
            if not existing_alert:
                # Créer une nouvelle alerte
                self.create({
                    'name': f"Licence {license.name} en sur-utilisation",
                    'description': f"La licence {license.name} pour {license.software_id.name} est utilisée sur {license.used_seats} équipements/utilisateurs alors que {license.purchased_seats} ont été achetés.",
                    'date_deadline': fields.Date.today() + timedelta(days=7),
                    'alert_type': 'license_compliance',
                    'priority': '2',
                    'license_id': license.id,
                    'partner_id': license.vendor_id.id if license.vendor_id else False,
                })