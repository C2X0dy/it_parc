from odoo import models, fields, api

class ITInterventionMaterial(models.Model):
    _name = 'it.intervention.material'
    _description = 'Material Used in IT Intervention'
    
    intervention_id = fields.Many2one('it.intervention', string='Intervention', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Article', required=True)
    quantity = fields.Float(string='Quantité', default=1.0, required=True)
    unit_price = fields.Float(related='product_id.lst_price', string='Prix unitaire')
    total_price = fields.Float(compute='_compute_total_price', string='Prix total')
    
    stock_available = fields.Float(compute='_compute_stock_available', string='Stock disponible')
    stock_location_id = fields.Many2one('stock.location', string='Emplacement')
    stock_move_id = fields.Many2one('stock.move', string='Mouvement de stock')
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('allocated', 'Alloué'),
        ('used', 'Utilisé'),
        ('returned', 'Retourné')
    ], string='État', default='draft')
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price
    
    @api.depends('product_id')
    def _compute_stock_available(self):
        for line in self:
            if not line.product_id:
                line.stock_available = 0.0
                continue
            
            # Récupère le stock disponible pour ce produit
            stock_quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.usage', '=', 'internal')
            ])
            line.stock_available = sum(quant.quantity for quant in stock_quant)
    
    def action_allocate_stock(self):
        """Allouer le stock pour cette ligne"""
        for line in self:
            if line.product_id and line.quantity > 0 and line.stock_available >= line.quantity:
                # Créer un transfert de stock pour cette ligne
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal')
                ], limit=1)
                
                if not picking_type:
                    continue
                
                # Créer un transfert de stock
                picking = self.env['stock.picking'].create({
                    'picking_type_id': picking_type.id,
                    'location_id': line.stock_location_id.id or picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                    'origin': line.intervention_id.name,
                })
                
                # Créer la ligne de mouvement
                move_vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'picking_id': picking.id,
                    'location_id': line.stock_location_id.id or picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                }
                move = self.env['stock.move'].create(move_vals)
                
                # Lier le mouvement à la ligne
                line.stock_move_id = move.id
                
                # Ajouter le transfert à l'intervention
                if picking not in line.intervention_id.stock_picking_ids:
                    line.intervention_id.stock_picking_ids = [(4, picking.id)]
                
                line.state = 'allocated'
    
    def action_request_purchase(self):
        """Créer une demande d'achat si le stock est insuffisant"""
        for line in self:
            if line.product_id and line.quantity > line.stock_available:
                # Vérifier si une demande d'achat existe déjà
                if not line.intervention_id.purchase_request_id:
                    request = self.env['purchase.request'].create({
                        'name': f"Demande pour {line.intervention_id.name}",
                        'description': f"Matériel nécessaire pour l'intervention {line.intervention_id.name}",
                        'requested_by': self.env.user.id,
                    })
                    line.intervention_id.purchase_request_id = request.id
                else:
                    request = line.intervention_id.purchase_request_id
                
                # Ajouter une ligne à la demande
                self.env['purchase.request.line'].create({
                    'request_id': request.id,
                    'product_id': line.product_id.id,
                    'product_qty': line.quantity - line.stock_available,
                    'product_uom_id': line.product_id.uom_id.id,
                    'estimated_cost': line.unit_price * (line.quantity - line.stock_available),
                })