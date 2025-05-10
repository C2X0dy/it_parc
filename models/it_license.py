from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

class ITLicense(models.Model):
    _name = 'it.license'
    _description = 'License IT'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Nom', required=True, tracking=True)
    description = fields.Text(string='Description')
    
    # Informations clés de la licence
    software_id = fields.Many2one('it.software', string='Logiciel', required=True, tracking=True)
    license_key = fields.Char(string='Clé de licence', tracking=True)
    activation_date = fields.Date(string='Date d\'activation', tracking=True)
    expiration_date = fields.Date(string='Date d\'expiration', tracking=True)
    
    # Type de licence
    license_type = fields.Selection([
        ('perpetual', 'Perpétuelle'),
        ('subscription', 'Abonnement'),
        ('trial', 'Essai'),
        ('open_source', 'Open Source'),
        ('saas', 'SaaS')
    ], string='Type de licence', default='subscription', tracking=True)
    
    is_concurrent = fields.Boolean(string='Licence flottante', help='Licence partagée entre plusieurs utilisateurs', tracking=True)
    purchased_seats = fields.Integer(string='Nombre de licences achetées', default=1, tracking=True)
    used_seats = fields.Integer(string='Licences utilisées', compute='_compute_used_seats', store=True)
    available_seats = fields.Integer(string='Licences disponibles', compute='_compute_available_seats', store=True)
    
    # Associations
    asset_ids = fields.Many2many('it.asset', string='Équipements', tracking=True)
    user_ids = fields.Many2many('res.users', string='Utilisateurs', tracking=True)
    
    # Informations financières et contractuelles
    purchase_date = fields.Date(string='Date d\'achat', tracking=True)
    purchase_value = fields.Monetary(string='Valeur d\'achat', currency_field='currency_id', tracking=True)
    renewal_cost = fields.Monetary(string='Coût de renouvellement', currency_field='currency_id', tracking=True)
    renewal_term = fields.Integer(string='Durée (mois)', default=12, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id.id)
    
    # Documents associés
    vendor_id = fields.Many2one('res.partner', string='Fournisseur', tracking=True)
    contract_reference = fields.Char(string='Référence contrat', tracking=True)
    agreement_document = fields.Binary(string='Contrat de licence', attachment=True)
    agreement_filename = fields.Char(string='Nom du fichier')
    
    # Conformité et audit
    last_audit_date = fields.Date(string='Dernier audit', tracking=True)
    compliance_status = fields.Selection([
        ('compliant', 'Conforme'),
        ('over_used', 'Sur-utilisé'),
        ('under_used', 'Sous-utilisé'),
        ('expired', 'Expiré'),
        ('to_review', 'À vérifier')
    ], string='Statut de conformité', compute='_compute_compliance_status', store=True, tracking=True)
    
    # État de la licence
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('terminated', 'Résiliée')
    ], string='État', default='draft', tracking=True)
    
    # Tags pour classification
    tag_ids = fields.Many2many('it.license.tag', string='Tags')
    
    # Fields pour le processus de renouvellement
    renewal_planned = fields.Boolean(string='Renouvellement planifié', default=False, tracking=True)
    renewal_quote_id = fields.Many2one('sale.order', string='Devis de renouvellement', tracking=True)
    reminder_sent = fields.Boolean(string='Rappel envoyé', default=False, tracking=True)
    
    @api.depends('user_ids', 'asset_ids', 'is_concurrent')
    def _compute_used_seats(self):
        for license in self:
            if license.is_concurrent:
                # Pour les licences flottantes, on compte le nombre d'utilisateurs
                license.used_seats = len(license.user_ids)
            else:
                # Pour les licences dédiées, on compte le nombre d'équipements
                license.used_seats = len(license.asset_ids)
    
    @api.depends('purchased_seats', 'used_seats')
    def _compute_available_seats(self):
        for license in self:
            license.available_seats = license.purchased_seats - license.used_seats
    
    @api.depends('expiration_date', 'purchased_seats', 'used_seats', 'state')
    def _compute_compliance_status(self):
        today = fields.Date.today()
        for license in self:
            if license.state != 'active':
                if license.state == 'expired':
                    license.compliance_status = 'expired'
                else:
                    license.compliance_status = 'to_review'
                continue
                
            if license.expiration_date and license.expiration_date < today:
                license.compliance_status = 'expired'
            elif license.used_seats > license.purchased_seats:
                license.compliance_status = 'over_used'
            elif license.used_seats < license.purchased_seats * 0.8:  # Moins de 80% utilisé
                license.compliance_status = 'under_used'
            else:
                license.compliance_status = 'compliant'
    
    @api.constrains('purchased_seats')
    def _check_purchased_seats(self):
        for license in self:
            if license.purchased_seats <= 0:
                raise ValidationError(_("Le nombre de licences achetées doit être supérieur à zéro."))
    
    @api.model
    def create(self, vals):
        # Affecter automatiquement un nom basé sur le logiciel si non fourni
        if not vals.get('name') and vals.get('software_id'):
            software = self.env['it.software'].browse(vals.get('software_id'))
            vals['name'] = f"{software.name} - Licence {fields.Date.today()}"
        return super(ITLicense, self).create(vals)
    
    def action_activate(self):
        self.write({'state': 'active'})
    
    def action_expire(self):
        self.write({'state': 'expired'})
    
    def action_terminate(self):
        self.write({'state': 'terminated'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
    
    def action_create_renewal_quote(self):
        """Crée un devis pour le renouvellement de licence"""
        self.ensure_one()
        
        if not self.vendor_id:
            raise UserError(_("Veuillez définir un fournisseur pour cette licence avant de créer un devis."))
        
        # Créer un devis
        SaleOrder = self.env['sale.order']
        order_lines = []
        
        # Ajouter la ligne principale pour le renouvellement
        line_name = f"Renouvellement {self.software_id.name}"
        if self.license_type == 'subscription':
            line_name += f" pour {self.renewal_term} mois"
        
        product = self.env.ref('it_parc.product_software_license', raise_if_not_found=False)
        if not product:
            raise UserError(_("Produit pour licences logicielles non trouvé. Veuillez configurer les produits de base."))
        
        order_lines.append((0, 0, {
            'product_id': product.id,
            'name': line_name,
            'product_uom_qty': self.purchased_seats,
            'price_unit': self.renewal_cost or self.purchase_value,
        }))
        
        # Créer le devis
        quote = SaleOrder.create({
            'partner_id': self.vendor_id.id,
            'order_line': order_lines,
            'note': f"Renouvellement de la licence pour {self.software_id.name}.\nRéférence: {self.contract_reference or 'N/A'}",
        })
        
        # Mettre à jour la référence du devis
        self.write({
            'renewal_quote_id': quote.id,
            'renewal_planned': True
        })
        
        return {
            'name': _('Devis de renouvellement'),
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': quote.id,
            'type': 'ir.actions.act_window',
        }
    
    def action_audit_license(self):
        """Effectue un audit de la licence"""
        self.ensure_one()
        
        # Mettre à jour la date d'audit
        self.write({'last_audit_date': fields.Date.today()})
        
        # Logique d'audit supplémentaire
        # ...
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Audit effectué"),
                'message': _("L'audit de la licence a été effectué."),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_quotations(self):
        """Afficher les devis associés au fournisseur de cette licence"""
        self.ensure_one()
        
        # Vérifier si le module sale est installé
        sale_installed = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'sale'), ('state', '=', 'installed')], limit=1)
        
        if not sale_installed:
            # Si le module sale n'est pas installé, utilisez une action générique
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Module de vente manquant"),
                    'message': _("Le module de vente n'est pas installé. Veuillez l'installer pour accéder aux devis."),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        try:
            # Essayer de récupérer l'action avec sa référence externe
            action = self.env.ref('sale.action_quotations').read()[0]
        except ValueError:
            # Fallback si la référence n'existe pas
            action = {
                'name': _('Devis'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'tree,form',
            }
        
        # Ajouter le domaine et le contexte
        action['domain'] = [('partner_id', '=', self.vendor_id.id)]
        action['context'] = {
            'default_partner_id': self.vendor_id.id,
            'search_default_draft_quotations': 1,
        }
        
        return action

class ITLicenseTag(models.Model):
    _name = 'it.license.tag'
    _description = 'License Tag'
    
    name = fields.Char(string='Nom', required=True)
    color = fields.Integer(string='Couleur')