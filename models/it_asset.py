from odoo import models, fields, api
from datetime import timedelta

class ITAsset(models.Model):
    _name = 'it.asset'
    _description = 'Actif IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Nom', required=True, tracking=True)
    asset_type = fields.Selection([
        ('hardware', 'Matériel'),
        ('software', 'Logiciel'),
        ('network', 'Équipement Réseau'),
        ('peripheral', 'Périphérique'),
        ('other', 'Autre')
    ], string='Type d\'actif', required=True, tracking=True)
    
    # Add company_id for multi-company support
    company_id = fields.Many2one('res.company', string='Société', 
                                default=lambda self: self.env.company,
                                required=True, index=True)
    
    reference = fields.Char('Référence', tracking=True)
    model = fields.Char('Modèle', tracking=True)
    manufacturer = fields.Char('Fabricant', tracking=True)
    serial_number = fields.Char('Numéro de série', tracking=True)
    
    client_id = fields.Many2one('res.partner', string='Client', tracking=True, 
                               domain=[('is_company', '=', True)])
    site_id = fields.Many2one('it.client.site', string='Site client', tracking=True)
    user_id = fields.Many2one('res.users', string='Utilisateur assigné', tracking=True)
    
    # Informations financières
    purchase_date = fields.Date('Date d\'achat', tracking=True)
    warranty_end_date = fields.Date('Fin de garantie', tracking=True)
    purchase_value = fields.Float('Valeur d\'achat', tracking=True)
    current_value = fields.Float('Valeur actuelle', compute='_compute_current_value', store=True)
    
    # Informations de contrat
    contract_id = fields.Many2one('it.service.contract', string='Contrat', tracking=True)
    
    # Informations techniques
    ip_address = fields.Char('Adresse IP', tracking=True)
    mac_address = fields.Char('Adresse MAC', tracking=True)
    operating_system = fields.Char('Système d\'exploitation', tracking=True)
    
    # Relations pour historique
    maintenance_ids = fields.One2many('it.maintenance', 'asset_id', string='Maintenances')
    incident_ids = fields.One2many('it.incident', 'asset_id', string='Incidents')
    
    # État de l'équipement
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('available', 'Disponible'),
        ('assigned', 'Assigné'),
        ('maintenance', 'En maintenance'),
        ('eol', 'Fin de vie')
    ], string='État', default='draft', tracking=True)
    
    # Champs de licence (pour les logiciels)
    is_software = fields.Boolean('Est un logiciel', compute='_compute_is_software')
    license_key = fields.Char('Clé de licence', tracking=True)
    license_expiry = fields.Date('Expiration de licence', tracking=True)
    license_seats = fields.Integer('Postes autorisés', default=1, tracking=True)
    
    # Note et descriptions
    description = fields.Text('Description', tracking=True)
    internal_notes = fields.Text('Notes internes')
    
    # Additional field for it.asset model
    license_id = fields.Many2one('it.license', string='Licence', tracking=True)
    
    warranty_expired = fields.Boolean(
        string='Garantie expirée', 
        compute='_compute_warranty_expired',
        store=False
    )
    
    @api.depends('asset_type')
    def _compute_is_software(self):
        for asset in self:
            asset.is_software = asset.asset_type == 'software'
    
    @api.depends('purchase_value', 'purchase_date')
    def _compute_current_value(self):
        for asset in self:
            if not asset.purchase_date or not asset.purchase_value:
                asset.current_value = asset.purchase_value
                continue
                
            # Calculer la dépréciation linéaire sur 3 ans (36 mois)
            today = fields.Date.today()
            months_diff = (today.year - asset.purchase_date.year) * 12 + (today.month - asset.purchase_date.month)
            
            if months_diff >= 36:
                asset.current_value = 0
            else:
                # Dépréciation linéaire
                depreciation_per_month = asset.purchase_value / 36
                asset.current_value = max(0, asset.purchase_value - (depreciation_per_month * months_diff))

    @api.onchange('purchase_date')
    def _onchange_purchase_date(self):
        if self.purchase_date:
            # Par défaut, garantie de 2 ans 
            self.warranty_end_date = self.purchase_date + timedelta(days=730)
            
    @api.onchange('client_id')
    def _onchange_client_id(self):
        # Réinitialiser le site si le client change
        if self.client_id:
            self.site_id = False
            return {'domain': {'site_id': [('client_id', '=', self.client_id.id)]}}
        else:
            return {'domain': {'site_id': []}}
    
    @api.depends('warranty_end_date')
    def _compute_warranty_expired(self):
        today = fields.Date.today()
        for record in self:
            record.warranty_expired = record.warranty_end_date and record.warranty_end_date < today

    def init(self):
        # Supprimez les anciennes vues s'il en existe
        self.env['ir.ui.view'].search([
            ('model', '=', 'it.asset'),
            ('type', 'in', ['list', 'form'])
        ]).unlink()
        
        # Créer les vues programmatiquement au lieu d'utiliser des fichiers XML
        self.env['ir.ui.view'].create({
            'name': 'it.asset.form',
            'model': 'it.asset',
            'type': 'form',
            'arch': '''
                <form>
                    <sheet>
                        <group>
                            <field name="name"/>
                        </group>
                    </sheet>
                </form>
            '''
        })
        
        self.env['ir.ui.view'].create({
            'name': 'it.asset.list',  # Changé de tree à list
            'model': 'it.asset',
            'type': 'list',
            'arch': '''
                <list>
                    <field name="name"/>
                </list>
            '''
        })
        
        # Vérifiez si l'action existe déjà
        existing_action = self.env['ir.actions.act_window'].search([
            ('res_model', '=', 'it.asset')
        ], limit=1)
        
        if not existing_action:
            self.env['ir.actions.act_window'].create({
                'name': 'Actifs IT',
                'res_model': 'it.asset',
                'view_mode': 'list,form',
            })