from odoo import api, fields, models

class ITContractService(models.Model):
    _name = 'it.contract.service'
    _description = 'Services supplémentaires du contrat'
    
    name = fields.Char(string='Description')
    contract_id = fields.Many2one('it.contract', string='Contrat', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Service', domain=[('type', '=', 'service')])
    quantity = fields.Float(string='Quantité', default=1.0)
    price_unit = fields.Float(string='Prix unitaire')
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.list_price
            