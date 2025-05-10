from odoo import models, fields, api, _
from odoo.tools import email_split, html2plaintext
from odoo.exceptions import UserError
import re

class ITTicket(models.Model):
    _name = 'it.ticket'
    _description = 'IT Support Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Subject', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    asset_id = fields.Many2one('it.asset', string='Related Asset')
    description = fields.Text(string='Description')
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1')
    
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', tracking=True)
    
    user_id = fields.Many2one('res.users', string='Assigned To')
    date_created = fields.Datetime(string='Date de création', default=fields.Datetime.now, tracking=True)
    date_resolved = fields.Datetime(string='Resolved On')
    
    resolution_details = fields.Text(string='Resolution Details')
    time_spent = fields.Float(string='Time Spent (Hours)')
    
    # Ajout des champs pour la facturation
    is_billed = fields.Boolean(string='Facturé', default=False, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Facture', copy=False, tracking=True)
    
    # Ajout de champs pour le suivi des emails
    email_from = fields.Char(string='Email de', tracking=True)
    email_cc = fields.Char(string='Email CC')
    channel_id = fields.Many2one('it.communication.channel', string='Canal')
    
    # Champ pour suivre si le ticket a été lu
    is_read = fields.Boolean(string='Lu', default=False, tracking=True)
    
    # Méthode pour la création de tickets via email
    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Méthode surchargée pour traiter les emails entrants et créer des tickets"""
        if custom_values is None:
            custom_values = {}
            
        # Extraire l'adresse email de l'expéditeur
        email_from = msg_dict.get('email_from', False)
        email_from_parsed = email_split(email_from)
        email = email_from_parsed[0] if email_from_parsed else False
        
        # Rechercher le partenaire associé à l'email
        partner = None
        if email:
            partner = self.env['res.partner'].search([('email', '=ilike', email)], limit=1)
        
        # Analyser le contenu pour identifier l'équipement concerné
        asset = None
        if msg_dict.get('body'):
            # Logique simplifiée - à améliorer avec NLP
            body = html2plaintext(msg_dict.get('body', ''))
            # Rechercher les numéros de série dans le corps du message
            serial_patterns = re.findall(r'[A-Z0-9]{8,}', body)
            if serial_patterns:
                for pattern in serial_patterns:
                    asset = self.env['it.asset'].search([('serial_number', '=ilike', pattern)], limit=1)
                    if asset:
                        break
        
        # Mettre à jour les valeurs personnalisées
        vals = {
            'name': msg_dict.get('subject') or _("Sans objet"),
            'email_from': email_from,
            'email_cc': msg_dict.get('cc', False),
            'partner_id': partner.id if partner else False,
            'asset_id': asset.id if asset else False,
            'description': html2plaintext(msg_dict.get('body', '')),
            'priority': self._get_priority_from_message(msg_dict),
            'state': 'new',
            'channel_id': self.env.ref('it_parc.communication_channel_email', False) and 
                          self.env.ref('it_parc.communication_channel_email', False).id or False,
        }
        
        custom_values.update(vals)
        return super(ITTicket, self).message_new(msg_dict, custom_values)

    def _check_billable_support(self):
        """Vérifie si le ticket est facturable hors contrat"""
        self.ensure_one()
        if not self.partner_id:
            return False
            
        # Vérifier si ce client a un contrat actif
        contract = self.env['it.contract'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'active'),
            ('end_date', '>=', fields.Date.today())
        ], limit=1)
        
        # Si pas de contrat, ou si problème non couvert par le contrat
        if not contract or not self._is_covered_by_contract(contract):
            return True
        return False
        
    def _is_covered_by_contract(self, contract):
        """Vérifie si le problème est couvert par le contrat"""
        # Logique simplifiée - à adapter selon vos besoins
        if not self.asset_id:
            return True  # Sans équipement lié, on suppose que c'est couvert
            
        # Vérifier si l'équipement est couvert par le contrat
        if self.asset_id.id in contract.asset_ids.ids:
            return True
        return False

    def action_create_invoice(self):
        """Crée une facture pour ce ticket"""
        self.ensure_one()
        
        if not self._check_billable_support():
            raise UserError(_("Ce ticket est déjà couvert par un contrat de maintenance."))
        
        # Créer une facture
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Produit par défaut pour intervention hors contrat
        product = self.env.ref('it_parc.product_support_service')
        
        # Calculer le temps passé (exemple simplifié)
        hours = 1.0  # Par défaut 1h
        
        # Créer la ligne de facture
        invoice_line = {
            'product_id': product.id,
            'name': f'Support technique pour {self.name}',
            'quantity': hours,
            'price_unit': product.list_price,
            'move_id': invoice.id,
        }
        
        self.env['account.move.line'].create(invoice_line)
        
        # Lier la facture au ticket
        self.write({
            'invoice_id': invoice.id,
            'is_billed': True
        })
        
        # Retourner une action pour voir la facture
        return {
            'name': _('Facture générée'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def _get_priority_from_message(self, msg_dict):
        """Détermine la priorité du ticket basée sur le contenu du message"""
        body = html2plaintext(msg_dict.get('body', '').lower()) if msg_dict.get('body') else ''
        subject = msg_dict.get('subject', '').lower() if msg_dict.get('subject') else ''
        
        # Liste de mots-clés pour priorisation
        urgent_keywords = ['urgent', 'urgence', 'immédiatement', 'critique', 'bloquant', 'emergency']
        high_keywords = ['important', 'prioritaire', 'rapidement', 'high priority', 'haute priorité']
        
        # Vérifier dans le sujet et le corps
        text_to_check = subject + ' ' + body
        
        if any(keyword in text_to_check for keyword in urgent_keywords):
            return '3'  # Urgent
        elif any(keyword in text_to_check for keyword in high_keywords):
            return '2'  # High
        else:
            return '1'  # Normal/Medium