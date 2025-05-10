from odoo import models, fields, api

class ITCommunicationChannel(models.Model):
    _name = 'it.communication.channel'
    _description = 'Canal de communication'
    
    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    requires_response = fields.Boolean(string='Nécessite réponse', default=True)
    auto_response_template_id = fields.Many2one('mail.template', string='Modèle de réponse automatique')
    
class ITCommunicationTemplate(models.Model):
    _name = 'it.communication.template'
    _description = 'Modèle de communication'
    
    name = fields.Char(string='Nom', required=True)
    subject = fields.Char(string='Sujet')
    body_html = fields.Html(string='Corps du message', sanitize=False)
    category = fields.Selection([
        ('welcome', 'Accueil'),
        ('problem', 'Problème technique'),
        ('request', 'Demande de service'),
        ('followup', 'Suivi'),
        ('closing', 'Clôture'),
        ('other', 'Autre')
    ], string='Catégorie')
    keywords = fields.Char(string='Mots-clés', help='Mots-clés séparés par des virgules pour la recherche')
    attachment_ids = fields.Many2many('ir.attachment', string='Pièces jointes')