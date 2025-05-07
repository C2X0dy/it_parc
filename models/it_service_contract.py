from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta

class ITServiceContract(models.Model):
    _name = 'it.service.contract'
    _description = 'Contrat de service IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    name = fields.Char('Référence', required=True, copy=False, 
                      default=lambda self: _('Nouveau'), tracking=True)
    
    # Informations client
    client_id = fields.Many2one('res.partner', string='Client', required=True, 
                               domain=[('is_company', '=', True)], tracking=True)
    partner_contact_id = fields.Many2one('res.partner', string='Contact principal', 
                                         domain="[('parent_id', '=', client_id), ('type', '=', 'contact')]")
    
    # Dates du contrat
    start_date = fields.Date('Date de début', required=True, default=fields.Date.today, tracking=True)
    end_date = fields.Date('Date de fin', tracking=True)
    duration = fields.Integer(string='Durée (mois)', tracking=True)
    
    # État du contrat
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)
    
    # Type de contrat
    contract_type = fields.Selection([
        ('maintenance', 'Maintenance'),
        ('support', 'Support IT'),
        ('hosting', 'Hébergement'),
        ('saas', 'SaaS'),
        ('full_service', 'Service complet'),
        ('other', 'Autre')
    ], string='Type de contrat', required=True, tracking=True)
    
    # Détails financiers
    contract_line_ids = fields.One2many('it.service.contract.line', 'contract_id', 
                                       string='Lignes de contrat')
    currency_id = fields.Many2one('res.currency', string='Devise', 
                                 default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary(string='Montant total', compute='_compute_total_amount', 
                                  store=True, currency_field='currency_id')
    
    # Facturation
    billing_frequency = fields.Selection([
        ('monthly', 'Mensuelle'),
        ('quarterly', 'Trimestrielle'),
        ('semi_annual', 'Semestrielle'),
        ('annual', 'Annuelle'),
    ], string='Fréquence de facturation', default='monthly', required=True, tracking=True)
    
    next_invoice_date = fields.Date(string='Prochaine facturation', tracking=True)
    
    # Équipements couverts
    asset_ids = fields.One2many('it.asset', 'contract_id', string='Actifs couverts')
    asset_count = fields.Integer(compute='_compute_asset_count', string='Nombre d\'actifs')
    
    # Notes
    description = fields.Text('Description', tracking=True)
    terms_conditions = fields.Text('Termes et conditions')
    
    @api.depends('contract_line_ids.subtotal')
    def _compute_total_amount(self):
        for contract in self:
            contract.total_amount = sum(contract.contract_line_ids.mapped('subtotal'))
    
    @api.depends('asset_ids')
    def _compute_asset_count(self):
        for contract in self:
            contract.asset_count = len(contract.asset_ids)
    
    @api.onchange('start_date', 'duration')
    def _onchange_duration(self):
        if self.start_date and self.duration:
            self.end_date = self.start_date + relativedelta(months=self.duration)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('it.service.contract') or _('Nouveau')
        return super().create(vals_list)
    
    def action_confirm(self):
        self.state = 'active'
        # Définir la prochaine date de facturation
        self._set_next_invoice_date()
    
    def _set_next_invoice_date(self):
        self.ensure_one()
        today = fields.Date.today()
        if self.billing_frequency == 'monthly':
            self.next_invoice_date = today + relativedelta(months=1)
        elif self.billing_frequency == 'quarterly':
            self.next_invoice_date = today + relativedelta(months=3)
        elif self.billing_frequency == 'semi_annual':
            self.next_invoice_date = today + relativedelta(months=6)
        elif self.billing_frequency == 'annual':
            self.next_invoice_date = today + relativedelta(years=1)

    def _cron_generate_invoices(self):
        """Tâche planifiée pour générer les factures des contrats"""
        today = fields.Date.today()
        contracts = self.env['it.service.contract'].search([
            ('state', '=', 'active'),
            ('next_invoice_date', '<=', today)
        ])
        for contract in contracts:
            contract._generate_invoice()
    
    def _generate_invoice(self):
        """Générer une facture pour le contrat"""
        AccountMove = self.env['account.move']
        lines = []
        
        for line in self.contract_line_ids:
            lines.append({
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
            })
        
        if not lines:
            return False
            
        values = {
            'partner_id': self.client_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
            'move_type': 'out_invoice',
            'invoice_line_ids': [(0, 0, line) for line in lines],
            'narration': _('Facturation contrat %s - %s') % (self.name, self.billing_frequency),
        }
        
        invoice = AccountMove.create(values)
        
        # Mettre à jour la prochaine date de facturation
        self._set_next_invoice_date()
        
        return invoice

    @api.model
    def _valid_field_parameter(self, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)

class ITServiceContractLine(models.Model):
    _name = 'it.service.contract.line'
    _description = 'Ligne de contrat de service IT'
    
    contract_id = fields.Many2one('it.service.contract', string='Contrat', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Produit', required=True)
    name = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantité', required=True, default=1.0)
    price_unit = fields.Float(string='Prix unitaire', required=True)
    subtotal = fields.Monetary(string='Sous-total', compute='_compute_subtotal', store=True, currency_field='currency_id')
    
    # Autres champs
    currency_id = fields.Many2one('res.currency', string='Devise', related='contract_id.currency_id', readonly=True)
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit