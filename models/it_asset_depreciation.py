from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import date

class ITAssetDepreciation(models.Model):
    _name = 'it.asset.depreciation'
    _description = 'IT Asset Depreciation Entry'
    _order = 'date desc, id desc'
    
    asset_id = fields.Many2one('it.asset', string='IT Asset', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True)
    amount = fields.Float(string='Amount', required=True)
    remaining_value = fields.Float(string='Remaining Value', required=True)
    depreciation_value = fields.Float(string='Depreciated Value')
    name = fields.Char(string='Description', required=True)
    move_id = fields.Many2one('account.move', string='Journal Entry')
    sequence = fields.Integer(string='Sequence', default=10)
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account')


class ITAsset(models.Model):
    _inherit = 'it.asset'
    
    # Champs d'amortissement
    depreciation_method = fields.Selection([
        ('linear', 'Linear'),
        ('degressive', 'Degressive'),
        ('none', 'Not Applicable')
    ], string='Depreciation Method', default='linear', required=True)
    
    depreciation_years = fields.Integer(string='Years of Depreciation', default=3)
    depreciation_rate = fields.Float(string='Depreciation Rate (%)', compute='_compute_depreciation_rate')
    depreciation_start_date = fields.Date(string='Depreciation Start Date')
    salvage_value = fields.Float(string='Salvage Value', help="Value at the end of depreciation")
    
    depreciation_line_ids = fields.One2many('it.asset.depreciation', 'asset_id', string='Depreciation Lines')
    depreciation_nb = fields.Integer(string='Number of Depreciations', compute='_compute_depreciation_nb')
    
    # Dates de renouvellement
    recommended_renewal_date = fields.Date(string='Recommended Renewal',
                                        compute='_compute_recommended_renewal')
    renewal_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Renewal Priority', compute='_compute_renewal_priority', store=True)
    
    renewal_planned = fields.Boolean(string='Renewal Planned')
    renewal_date = fields.Date(string='Planned Renewal Date')
    renewal_notes = fields.Text(string='Renewal Notes')
    
    # État de l'équipement
    age_in_months = fields.Integer(string='Age (Months)', compute='_compute_age')
    depreciation_value = fields.Float(string='Depreciated Value', compute='_compute_depreciation_value')
    depreciation_percentage = fields.Float(string='Depreciation %', compute='_compute_depreciation_percentage')
    
    # Comptabilité
    account_asset_id = fields.Many2one('account.account', string='Asset Account')
    account_depreciation_id = fields.Many2one('account.account', string='Depreciation Account')
    account_expense_id = fields.Many2one('account.account', string='Expense Account')
    journal_id = fields.Many2one('account.journal', string='Journal')
    
    @api.depends('purchase_date')
    def _compute_age(self):
        today = fields.Date.today()
        for asset in self:
            if asset.purchase_date:
                delta = relativedelta(today, asset.purchase_date)
                asset.age_in_months = delta.years * 12 + delta.months
            else:
                asset.age_in_months = 0
    
    @api.depends('depreciation_method', 'depreciation_years')
    def _compute_depreciation_rate(self):
        for asset in self:
            if asset.depreciation_method == 'linear':
                asset.depreciation_rate = 100.0 / asset.depreciation_years if asset.depreciation_years else 0
            elif asset.depreciation_method == 'degressive':
                asset.depreciation_rate = 200.0 / asset.depreciation_years if asset.depreciation_years else 0
            else:
                asset.depreciation_rate = 0
    
    @api.depends('depreciation_years')
    def _compute_depreciation_nb(self):
        for asset in self:
            asset.depreciation_nb = asset.depreciation_years * 12  # Mensuel
    
    @api.depends('purchase_date', 'depreciation_years')
    def _compute_recommended_renewal(self):
        for asset in self:
            if asset.purchase_date and asset.depreciation_years:
                asset.recommended_renewal_date = fields.Date.from_string(asset.purchase_date) + \
                                               relativedelta(years=asset.depreciation_years)
            else:
                asset.recommended_renewal_date = False
    
    @api.depends('recommended_renewal_date', 'purchase_value', 'current_value', 'health_score', 'incident_count')
    def _compute_renewal_priority(self):
        today = fields.Date.today()
        for asset in self:
            if not asset.recommended_renewal_date:
                asset.renewal_priority = 'low'
                continue
                
            # Facteurs pour la décision
            factors = {
                'age_factor': 0,
                'value_factor': 0,
                'health_factor': 0,
                'incidents_factor': 0
            }
            
            # 1. Facteur temporel/âge
            days_to_renewal = (asset.recommended_renewal_date - today).days
            if days_to_renewal < 0:
                factors['age_factor'] = 1.0  # Dépassé, importance maximale
            elif days_to_renewal < 90:
                factors['age_factor'] = 0.8  # Très proche
            elif days_to_renewal < 180:
                factors['age_factor'] = 0.5  # Modérément proche
            else:
                factors['age_factor'] = 0.2  # Éloigné
            
            # 2. Facteur valeur résiduelle
            value_ratio = asset.current_value / asset.purchase_value if asset.purchase_value else 1
            factors['value_factor'] = 1.0 - value_ratio
            
            # 3. Facteur santé
            health_score = asset.health_score or 100
            if health_score < 30:
                factors['health_factor'] = 1.0  # Critique
            elif health_score < 60:
                factors['health_factor'] = 0.7  # Préoccupant
            elif health_score < 80:
                factors['health_factor'] = 0.3  # À surveiller
            else:
                factors['health_factor'] = 0.0  # Bonne santé
            
            # 4. Facteur incidents
            incident_count = asset.incident_count or 0
            if incident_count > 3:
                factors['incidents_factor'] = 1.0  # Nombreux incidents
            elif incident_count > 1:
                factors['incidents_factor'] = 0.6  # Quelques incidents
            else:
                factors['incidents_factor'] = 0.0  # Pas/peu d'incidents
            
            # Calcul du score final (moyenne pondérée)
            weights = {
                'age_factor': 0.3,
                'value_factor': 0.2,
                'health_factor': 0.3,
                'incidents_factor': 0.2
            }
            
            total_score = sum(factors[k] * weights[k] for k in factors)
            
            # Détermination de la priorité
            if total_score > 0.75:
                asset.renewal_priority = 'critical'
            elif total_score > 0.5:
                asset.renewal_priority = 'high'
            elif total_score > 0.25:
                asset.renewal_priority = 'medium'
            else:
                asset.renewal_priority = 'low'
    
    @api.depends('depreciation_line_ids.amount', 'purchase_value')
    def _compute_depreciation_value(self):
        for asset in self:
            asset.depreciation_value = sum(line.amount for line in asset.depreciation_line_ids)
    
    @api.depends('depreciation_value', 'purchase_value')
    def _compute_depreciation_percentage(self):
        for asset in self:
            if asset.purchase_value:
                asset.depreciation_percentage = (asset.depreciation_value / asset.purchase_value) * 100
            else:
                asset.depreciation_percentage = 0
    
    def compute_depreciation_board(self):
        """Calcul du tableau d'amortissement"""
        self.ensure_one()
        depreciation_line_obj = self.env['it.asset.depreciation']
        
        # Suppression des lignes existantes
        depreciation_line_obj.search([('asset_id', '=', self.id)]).unlink()
        
        # Si pas d'amortissement ou pas de valeur d'achat
        if self.depreciation_method == 'none' or not self.purchase_value:
            return True
        
        # Vérification des données nécessaires
        if not self.purchase_date:
            raise UserError(_("Please set the purchase date for the asset."))
        
        # Date de début d'amortissement (par défaut la date d'achat)
        depreciation_start_date = self.depreciation_start_date or self.purchase_date
        
        # Valeur à amortir
        amount_to_depreciate = self.purchase_value - self.salvage_value
        residual_value = amount_to_depreciate
        
        # Pour une méthode linéaire
        if self.depreciation_method == 'linear':
            amount_per_period = amount_to_depreciate / (self.depreciation_years * 12)
            
            for i in range(1, self.depreciation_years * 12 + 1):
                depreciation_date = fields.Date.from_string(depreciation_start_date) + relativedelta(months=i)
                
                if i == self.depreciation_years * 12:  # Dernière entrée
                    amount = residual_value
                else:
                    amount = amount_per_period
                
                residual_value -= amount
                vals = {
                    'asset_id': self.id,
                    'sequence': i,
                    'name': _('Depreciation %s/%s') % (i, self.depreciation_years * 12),
                    'date': depreciation_date,
                    'amount': amount,
                    'depreciation_value': self.purchase_value - self.salvage_value - residual_value,
                    'remaining_value': residual_value + self.salvage_value,
                }
                depreciation_line_obj.create(vals)
        
        # Pour une méthode dégressive
        elif self.depreciation_method == 'degressive':
            rate = self.depreciation_rate / 100
            for i in range(1, self.depreciation_years * 12 + 1):
                depreciation_date = fields.Date.from_string(depreciation_start_date) + relativedelta(months=i)
                
                if i == self.depreciation_years * 12:  # Dernière entrée
                    amount = residual_value
                else:
                    amount = residual_value * rate / 12  # Calcul mensuel
                
                residual_value -= amount
                vals = {
                    'asset_id': self.id,
                    'sequence': i,
                    'name': _('Depreciation %s/%s') % (i, self.depreciation_years * 12),
                    'date': depreciation_date,
                    'amount': amount,
                    'depreciation_value': self.purchase_value - self.salvage_value - residual_value,
                    'remaining_value': residual_value + self.salvage_value,
                }
                depreciation_line_obj.create(vals)
        
        return True
    
    def open_depreciation_board(self):
        """Ouvre la vue du tableau d'amortissement"""
        self.ensure_one()
        return {
            'name': _('Depreciation Board'),
            'view_mode': 'tree,form',
            'res_model': 'it.asset.depreciation',
            'domain': [('asset_id', '=', self.id)],
            'type': 'ir.actions.act_window',
        }
    
    def action_generate_renewal_request(self):
        """Génère une demande de renouvellement"""
        self.ensure_one()
        # Créer un ticket de demande de renouvellement
        Ticket = self.env['it.ticket']
        ticket = Ticket.create({
            'name': _('Renewal Request for %s') % self.name,
            'partner_id': self.partner_id.id,
            'asset_id': self.id,
            'description': _('This is an automated renewal request for the IT asset: %s.\n\nRenewal Priority: %s\nRecommended Renewal Date: %s\nCurrent Value: %s\nPurchase Value: %s\nAge: %s months') % (
                self.name, dict(self._fields['renewal_priority'].selection).get(self.renewal_priority), 
                self.recommended_renewal_date, self.current_value, self.purchase_value, self.age_in_months
            ),
            'priority': '2' if self.renewal_priority in ['high', 'critical'] else '1',
            'state': 'new',
        })
        
        # Marquer comme planifié
        self.write({
            'renewal_planned': True,
            'renewal_date': self.recommended_renewal_date,
            'renewal_notes': _('Renewal request automatically generated on %s. Ticket: %s') % (
                fields.Date.today(), ticket.name)
        })
        
        # Retourner une action pour voir le ticket créé
        return {
            'name': _('Renewal Request'),
            'view_mode': 'form',
            'res_model': 'it.ticket',
            'res_id': ticket.id,
            'type': 'ir.actions.act_window',
        }