from odoo import api, fields, models

class ITServiceContractLine(models.Model):
    _name = 'it.service.contract.line'
    _description = 'Ligne de contrat de service IT'
    
    contract_id = fields.Many2one('it.service.contract', string='Contrat', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Séquence', default=10)
    
    product_id = fields.Many2one('product.product', string='Service', required=True,
                                domain=[('type', '=', 'service')])
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantité', default=1.0, required=True)
    price_unit = fields.Float(string='Prix unitaire', required=True)
    
    # Montant calculé
    currency_id = fields.Many2one(related='contract_id.currency_id', string='Devise')
    subtotal = fields.Monetary(string='Sous-total', compute='_compute_subtotal', store=True, currency_field='currency_id')
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.list_price