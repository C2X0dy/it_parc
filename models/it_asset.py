# models/it_asset.py
import json
from odoo import api, fields, models, _
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class ITAsset(models.Model):
    _name = 'it.asset'
    _description = 'IT Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    asset_type = fields.Selection([
        ('computer', 'Computer'),
        ('printer', 'Printer'),
        ('network', 'Network Equipment'),
        ('other', 'Other')
    ], string='Type', required=True)
    serial_number = fields.Char(string='Serial Number')
    partner_id = fields.Many2one('res.partner', string='Customer')
    user_id = fields.Many2one('res.users', string='Assigned User')
    purchase_date = fields.Date(string='Purchase Date')
    warranty_end = fields.Date(string='Warranty End Date')
    notes = fields.Text(string='Notes')
    contract_id = fields.Many2one('it.contract', string='Maintenance Contract')
    software_ids = fields.Many2many('it.software', string='Installed Software')
    currency_id = fields.Many2one('res.currency', string='Devise',
        default=lambda self: self.env.company.currency_id.id)
    purchase_value = fields.Monetary(string='Purchase Value', currency_field='currency_id')
    current_value = fields.Monetary(string='Current Value', compute='_compute_current_value', currency_field='currency_id')
    warranty_type = fields.Selection([
        ('none', 'No Warranty'),
        ('standard', 'Standard'),
        ('extended', 'Extended')
    ], string='Warranty Type', default='none')
    location = fields.Char(string='Location')
    status = fields.Selection([
        ('active', 'Active'),
        ('maintenance', 'In Maintenance'),
        ('stock', 'In Stock'),
        ('retired', 'Retired')
    ], string='Status', default='active', tracking=True)
    maintenance_interval = fields.Integer(string='Intervalle de maintenance (mois)', 
                                     help="Nombre de mois entre les maintenances préventives", default=12)
    
    # Dates du cycle de vie
    commissioning_date = fields.Date(string='Date de mise en service', tracking=True, 
                                    help="Date à laquelle l'équipement a été déployé et mis en service")
    end_of_life_date = fields.Date(string='Fin de vie prévue', compute='_compute_end_of_life',
                                 store=True, help="Date à laquelle l'équipement atteindra sa fin de vie")
    
    # Indicateurs d'état de santé
    health_score = fields.Float(string='Score de santé', compute='_compute_health_score', store=True,
                              help="Score sur 100 indiquant l'état global de l'équipement")
    
    # Suivi matériel
    cpu_health = fields.Selection([
        ('good', 'Bon'),
        ('medium', 'Moyen'),
        ('poor', 'Faible')
    ], string="État CPU", tracking=True)
    ram_health = fields.Selection([
        ('good', 'Bon'),
        ('medium', 'Moyen'),
        ('poor', 'Faible')
    ], string="État RAM", tracking=True)
    disk_health = fields.Selection([
        ('good', 'Bon'),
        ('medium', 'Moyen'),
        ('poor', 'Faible')
    ], string="État disque", tracking=True)
    battery_health = fields.Selection([
        ('good', 'Bon'),
        ('medium', 'Moyen'),
        ('poor', 'Faible')
    ], string="État batterie", tracking=True)
    
    # Suivi des coûts
    lifecycle_cost = fields.Monetary(string="Coût total de possession", 
                                  compute='_compute_lifecycle_cost',
                                  currency_field='currency_id',
                                  help="Coût total incluant l'achat et les interventions")
    cost_per_month = fields.Monetary(string="Coût mensuel", 
                                  compute='_compute_lifecycle_cost',
                                  currency_field='currency_id')
    
    # Métriques de performance
    mttf = fields.Float(string="MTTF (jours)", compute='_compute_metrics',
                      help="Temps moyen jusqu'à défaillance")
    mttr = fields.Float(string="MTTR (heures)", compute='_compute_metrics',
                      help="Temps moyen de réparation")
    incident_count = fields.Integer(string="Nombre d'incidents", compute='_compute_metrics')
    
    # Ajouter ce champ manquant
    intervention_ids = fields.Many2many('it.intervention', 
                                      string='Interventions',
                                      compute='_compute_intervention_ids', 
                                      store=False)
    
    # Ajout du champ manquant
    lifecycle_timeline = fields.Text(string='Timeline du cycle de vie', compute='_compute_lifecycle_timeline')
    
    @api.depends('purchase_date', 'purchase_value')
    def _compute_current_value(self):
        for asset in self:
            if not asset.purchase_date or not asset.purchase_value:
                asset.current_value = 0.0
                continue
                
            # Simple linear depreciation over 3 years
            age_days = (fields.Date.today() - asset.purchase_date).days
            if age_days < 0:
                asset.current_value = asset.purchase_value
                continue
                
            # 3 years depreciation (1095 days)
            if age_days >= 1095:
                asset.current_value = 0.0
            else:
                asset.current_value = asset.purchase_value * (1 - (age_days / 1095))

    @api.depends('purchase_date', 'commissioning_date', 'depreciation_years')
    def _compute_end_of_life(self):
        for asset in self:
            start_date = asset.commissioning_date or asset.purchase_date
            if start_date and asset.depreciation_years:
                asset.end_of_life_date = fields.Date.from_string(start_date) + \
                                       relativedelta(years=asset.depreciation_years)
            else:
                asset.end_of_life_date = False
    
    @api.depends('cpu_health', 'ram_health', 'disk_health', 'battery_health', 'age_in_months')
    def _compute_health_score(self):
        for asset in self:
            score = 100.0
            
            # Réduction basée sur l'âge
            if asset.age_in_months:
                age_factor = min(1.0, asset.age_in_months / (asset.depreciation_years * 12 or 36))
                score -= 30 * age_factor  # 30% max pour l'âge
            
            # Réduction basée sur l'état des composants
            component_states = [asset.cpu_health, asset.ram_health, 
                              asset.disk_health, asset.battery_health]
            components_count = sum(1 for c in component_states if c)
            
            if components_count > 0:
                for state in component_states:
                    if state == 'poor':
                        score -= 70 / components_count  # Sévère impact
                    elif state == 'medium':
                        score -= 30 / components_count  # Impact modéré
            
            asset.health_score = max(0, min(score, 100))  # Limiter entre 0 et 100

    @api.depends('purchase_value', 'intervention_ids')
    def _compute_lifecycle_cost(self):
        for asset in self:
            # Coût d'achat
            total_cost = asset.purchase_value or 0
            
            # Ajout des coûts de maintenance
            interventions = self.env['it.intervention'].search([
                ('asset_ids', 'in', asset.id),
                ('billable', '=', True)
            ])
            
            for intervention in interventions:
                if intervention.invoice_id and intervention.invoice_id.amount_total:
                    # Si facturé, prendre le montant réel
                    total_cost += intervention.invoice_id.amount_total
                elif intervention.duration and intervention.hourly_rate:
                    # Sinon estimer selon taux horaire
                    total_cost += intervention.duration * intervention.hourly_rate
            
            asset.lifecycle_cost = total_cost
            
            # Calcul du coût mensuel
            months = asset.age_in_months or 1
            asset.cost_per_month = total_cost / months if months > 0 else total_cost

    @api.depends('intervention_ids')
    def _compute_metrics(self):
        for asset in self:
            # Incidents liés à cet équipement
            incidents = self.env['it.intervention'].search([
                ('asset_ids', 'in', asset.id),
                ('type', 'in', ['corrective', 'incident'])
            ])
            
            asset.incident_count = len(incidents)
            
            # MTTF - Temps moyen entre deux défaillances
            if len(incidents) > 1:
                incidents_sorted = incidents.sorted(key=lambda r: r.date_start)
                total_days = 0
                for i in range(1, len(incidents_sorted)):
                    if incidents_sorted[i].date_start and incidents_sorted[i-1].date_end:
                        delta = fields.Datetime.from_string(incidents_sorted[i].date_start) - \
                                fields.Datetime.from_string(incidents_sorted[i-1].date_end)
                        total_days += delta.total_seconds() / (24*3600)
                asset.mttf = total_days / (len(incidents) - 1) if len(incidents) > 1 else 0
            else:
                asset.mttf = 0
            
            # MTTR - Temps moyen de réparation
            total_repair_time = 0
            for incident in incidents:
                if incident.date_start and incident.date_end:
                    repair_time = fields.Datetime.from_string(incident.date_end) - \
                                fields.Datetime.from_string(incident.date_start)
                    total_repair_time += repair_time.total_seconds() / 3600  # En heures
            asset.mttr = total_repair_time / len(incidents) if incidents else 0

    # Ajouter cette méthode de calcul
    def _compute_intervention_ids(self):
        for asset in self:
            asset.intervention_ids = self.env['it.intervention'].search([
                ('asset_ids', 'in', asset.id)
            ])
    
    @api.depends('purchase_date', 'commissioning_date', 'warranty_end', 'end_of_life_date', 'recommended_renewal_date')
    def _compute_lifecycle_timeline(self):
        for asset in self:
            timeline_events = []
            
            # Événement d'achat
            if asset.purchase_date:
                timeline_events.append({
                    'date': asset.purchase_date.isoformat(),
                    'name': 'Achat',
                    'type': 'purchase',
                    'color': '#4e73df'  # Bleu
                })
                
            # Événement de mise en service
            if asset.commissioning_date:
                timeline_events.append({
                    'date': asset.commissioning_date.isoformat(),
                    'name': 'Mise en service',
                    'type': 'commissioning',
                    'color': '#1cc88a'  # Vert
                })
                
            # Événement de fin de garantie
            if asset.warranty_end:
                timeline_events.append({
                    'date': asset.warranty_end.isoformat(),
                    'name': 'Fin de garantie',
                    'type': 'warranty_end',
                    'color': '#f6c23e'  # Jaune
                })
                
            # Événement de renouvellement recommandé
            if asset.recommended_renewal_date:
                timeline_events.append({
                    'date': asset.recommended_renewal_date.isoformat(),
                    'name': 'Renouvellement recommandé',
                    'type': 'renewal',
                    'color': '#e74a3b'  # Rouge
                })
                
            # Événement de fin de vie
            if asset.end_of_life_date:
                timeline_events.append({
                    'date': asset.end_of_life_date.isoformat(),
                    'name': 'Fin de vie',
                    'type': 'end_of_life',
                    'color': '#e74a3b'  # Rouge
                })
                
            asset.lifecycle_timeline = json.dumps(timeline_events)

class ITAssetTest(models.Model):
    _name = 'it.asset.test'
    _description = 'IT Asset Test'

    name = fields.Char(string='Name', required=True)
    asset_type = fields.Selection([
        ('computer', 'Computer'),
        ('printer', 'Printer'),
    ], string='Type')