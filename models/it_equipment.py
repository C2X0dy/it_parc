from odoo import api, fields, models

class ITEquipment(models.Model):
    _name = 'it.equipment'
    _description = 'Équipement informatique'
    
    name = fields.Char(string='Nom', required=True)
    asset_id = fields.Many2one('it.asset', string='Catégorie d\'actif')
    model = fields.Char(string='Modèle')
    serial_number = fields.Char(string='Numéro de série')
    purchase_date = fields.Date(string='Date d\'achat')
    warranty_end_date = fields.Date(string='Fin de garantie')
    status = fields.Selection([
        ('operational', 'Opérationnel'),
        ('maintenance', 'En maintenance'),
        ('retired', 'Retiré')
    ], string='Statut', default='operational')
    notes = fields.Text(string='Notes')
    site_id = fields.Many2one('it.client.site', string='Site')
    client_id = fields.Many2one('res.partner', string='Client', related='site_id.client_id', store=True)
    
    # Champs d'amortissement
    purchase_value = fields.Monetary(string='Valeur d\'achat', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Devise')
    amortization_years = fields.Integer(string='Durée d\'amortissement (années)', default=3)
    current_value = fields.Monetary(string='Valeur actuelle', compute='_compute_current_value')
    
    @api.depends('purchase_value', 'purchase_date', 'amortization_years')
    def _compute_current_value(self):
        today = fields.Date.today()
        for record in self:
            if not record.purchase_date or not record.purchase_value:
                record.current_value = 0
                continue
                
            total_days = record.amortization_years * 365
            elapsed_days = (today - record.purchase_date).days
            
            if elapsed_days >= total_days:
                record.current_value = 0
            else:
                remaining_ratio = (total_days - elapsed_days) / total_days
                record.current_value = record.purchase_value * remaining_ratio