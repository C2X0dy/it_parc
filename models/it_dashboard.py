from odoo import models, fields, api, tools
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

class ITDashboard(models.Model):
    _name = 'it.dashboard'
    _description = 'IT Dashboard'
    _auto = False  # Ne pas créer de table dans la base de données

    name = fields.Char(string='Nom', readonly=True)
    
    # KPIs calculés
    total_assets = fields.Integer(string='Total des équipements', compute='_compute_kpis')
    total_contracts = fields.Integer(string='Contrats de maintenance', compute='_compute_kpis')
    tickets_open = fields.Integer(string='Tickets ouverts', compute='_compute_kpis')
    interventions_planned = fields.Integer(string='Interventions prévues', compute='_compute_kpis')
    assets_without_contract = fields.Integer(string='Équipements sans contrat', compute='_compute_kpis')
    
    # Statistiques d'utilisation
    assets_by_type = fields.Char(string='Équipements par type', compute='_compute_stats')
    tickets_by_priority = fields.Char(string='Tickets par priorité', compute='_compute_stats')
    contracts_by_state = fields.Char(string='Contrats par état', compute='_compute_stats')
    
    # Alertes
    expiring_warranties = fields.Integer(string='Garanties expirant bientôt', compute='_compute_alerts')
    expiring_licenses = fields.Integer(string='Licences à renouveler', compute='_compute_alerts')
    expiring_contracts = fields.Integer(string='Contrats expirant bientôt', compute='_compute_alerts')
    critical_tickets = fields.Integer(string='Tickets critiques', compute='_compute_alerts')

    # Ajout d'indicateurs de conformité des licences
    license_compliance_status = fields.Text(string='Conformité des licences', compute='_compute_license_compliance')

    @api.model
    def init(self):
        query = """
        SELECT 1 as id, 'Dashboard' as name
        """
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"CREATE or REPLACE VIEW {self._table} AS ({query})")
    
    def _compute_kpis(self):
        for record in self:
            # Total des équipements
            record.total_assets = self.env['it.asset'].search_count([])
            
            # Contrats de maintenance
            record.total_contracts = self.env['it.contract'].search_count([('state', '=', 'active')])
            
            # Tickets ouverts
            record.tickets_open = self.env['it.ticket'].search_count([
                ('state', 'in', ['new', 'in_progress', 'waiting'])
            ])
            
            # Interventions prévues
            record.interventions_planned = self.env['it.intervention'].search_count([
                ('state', 'in', ['planned', 'in_progress'])
            ])
            
            # Équipements sans contrat
            record.assets_without_contract = self.env['it.asset'].search_count([
                ('contract_id', '=', False)
            ])
    
    def _compute_stats(self):
        for record in self:
            # Équipements par type
            assets_by_type = {}
            asset_types = self.env['it.asset'].read_group(
                [], fields=['asset_type'], groupby=['asset_type']
            )
            for asset_type in asset_types:
                type_key = asset_type['asset_type'] or 'Non spécifié'
                assets_by_type[type_key] = asset_type['asset_type_count']
            record.assets_by_type = str(assets_by_type)
            
            # Tickets par priorité
            tickets_by_priority = {}
            ticket_priorities = self.env['it.ticket'].read_group(
                [], fields=['priority'], groupby=['priority']
            )
            for priority in ticket_priorities:
                priority_key = priority['priority'] or 'Non spécifié'
                tickets_by_priority[priority_key] = priority['priority_count']
            record.tickets_by_priority = str(tickets_by_priority)
            
            # Contrats par état
            contracts_by_state = {}
            contract_states = self.env['it.contract'].read_group(
                [], fields=['state'], groupby=['state']
            )
            for state in contract_states:
                state_key = state['state'] or 'Non spécifié'
                contracts_by_state[state_key] = state['state_count']
            record.contracts_by_state = str(contracts_by_state)
    
    def _compute_alerts(self):
        for record in self:
            # Date future pour les alertes (30 jours)
            future_date = fields.Date.today() + relativedelta(days=30)
            
            # Garanties expirant bientôt
            record.expiring_warranties = self.env['it.asset'].search_count([
                ('warranty_end', '!=', False),
                ('warranty_end', '<=', future_date),
                ('warranty_end', '>=', fields.Date.today())
            ])
            
            # Licences expirant bientôt
            record.expiring_licenses = self.env['it.license'].search_count([
                ('state', '=', 'active'),
                ('expiration_date', '!=', False),
                ('expiration_date', '<=', future_date),
                ('expiration_date', '>=', fields.Date.today())
            ])
            
            # Contrats expirant bientôt
            record.expiring_contracts = self.env['it.contract'].search_count([
                ('state', '=', 'active'),
                ('end_date', '<=', future_date),
                ('end_date', '>=', fields.Date.today())
            ])
            
            # Tickets critiques
            record.critical_tickets = self.env['it.ticket'].search_count([
                ('state', 'in', ['new', 'in_progress']),
                ('priority', 'in', ['2', '3'])
            ])

    @api.depends()
    def _compute_license_compliance(self):
        for record in self:
            # Calculer les statistiques de conformité
            compliant = self.env['it.license'].search_count([
                ('state', '=', 'active'),
                ('compliance_status', '=', 'compliant')
            ])
            
            over_used = self.env['it.license'].search_count([
                ('state', '=', 'active'),
                ('compliance_status', '=', 'over_used')
            ])
            
            under_used = self.env['it.license'].search_count([
                ('state', '=', 'active'),
                ('compliance_status', '=', 'under_used')
            ])
            
            expired = self.env['it.license'].search_count([
                ('state', '=', 'active'),
                ('compliance_status', '=', 'expired')
            ])
            
            # Stocker les résultats
            record.license_compliance_status = json.dumps({
                'compliant': compliant,
                'over_used': over_used,
                'under_used': under_used,
                'expired': expired
            })

    @api.model
    def get_dashboard_data(self):
        """Méthode pour obtenir toutes les données du tableau de bord"""
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({})
        
        # Force le calcul des champs calculés
        dashboard._compute_kpis()
        dashboard._compute_stats()
        dashboard._compute_alerts()
        
        # Conversion des chaînes en dictionnaires pour les graphiques
        import ast
        assets_by_type = ast.literal_eval(dashboard.assets_by_type or '{}')
        tickets_by_priority = ast.literal_eval(dashboard.tickets_by_priority or '{}')
        contracts_by_state = ast.literal_eval(dashboard.contracts_by_state or '{}')
        
        return {
            'kpis': {
                'total_assets': dashboard.total_assets,
                'total_contracts': dashboard.total_contracts,
                'tickets_open': dashboard.tickets_open,
                'interventions_planned': dashboard.interventions_planned,
                'assets_without_contract': dashboard.assets_without_contract,
            },
            'stats': {
                'assets_by_type': assets_by_type,
                'tickets_by_priority': tickets_by_priority,
                'contracts_by_state': contracts_by_state,
            },
            'alerts': {
                'expiring_warranties': dashboard.expiring_warranties,
                'expiring_licenses': dashboard.expiring_licenses,
                'expiring_contracts': dashboard.expiring_contracts,
                'critical_tickets': dashboard.critical_tickets,
            }
        }