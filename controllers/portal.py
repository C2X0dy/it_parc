from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from datetime import datetime, timedelta
import json
import base64
import xlwt
from io import BytesIO

class ITPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if 'asset_count' in counters:
            asset_count = request.env['it.asset'].search_count([
                ('partner_id', '=', partner.id)
            ])
            values['asset_count'] = asset_count

        if 'ticket_count' in counters:
            ticket_count = request.env['it.ticket'].search_count([
                ('partner_id', '=', partner.id)
            ])
            values['ticket_count'] = ticket_count

        if 'contract_count' in counters:
            contract_count = request.env['it.contract'].search_count([
                ('partner_id', '=', partner.id)
            ])
            values['contract_count'] = contract_count
            
        # Ajout du nombre d'interventions
        if 'intervention_count' in counters:
            intervention_count = request.env['it.intervention'].search_count([
                ('partner_id', '=', partner.id)
            ])
            values['intervention_count'] = intervention_count

        return values

    @http.route(['/my/assets', '/my/assets/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_assets(self, page=1, sortby=None, filterby=None, search=None, search_in='all', **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Asset = request.env['it.asset']
        
        # Filtres
        domain = [('partner_id', '=', partner.id)]
        
        # Filtres spécifiques par type
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'computer': {'label': _('Computers'), 'domain': [('asset_type', '=', 'computer')]},
            'printer': {'label': _('Printers'), 'domain': [('asset_type', '=', 'printer')]},
            'network': {'label': _('Network'), 'domain': [('asset_type', '=', 'network')]},
            'other': {'label': _('Other'), 'domain': [('asset_type', '=', 'other')]},
        }
        
        # Tri
        searchbar_sortings = {
            'name': {'label': _('Name'), 'order': 'name'},
            'date': {'label': _('Purchase Date'), 'order': 'purchase_date desc'},
        }
        
        # Default sort by name
        if not sortby:
            sortby = 'name'
        order = searchbar_sortings[sortby]['order']
        
        # Default filter
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Recherche
        if search and search_in:
            search_domain = []
            if search_in in ('name', 'all'):
                search_domain = OR([search_domain, [('name', 'ilike', search)]])
            if search_in in ('serial', 'all'):
                search_domain = OR([search_domain, [('serial_number', 'ilike', search)]])
            domain += search_domain
        
        # Count pour pager
        asset_count = Asset.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/assets",
            url_args={'sortby': sortby, 'filterby': filterby, 'search': search, 'search_in': search_in},
            total=asset_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content according to pager
        assets = Asset.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        
        # Compteurs pour statistiques
        today_plus_30 = fields.Date.today() + timedelta(days=30)
        active_asset_count = Asset.search_count([
            ('partner_id', '=', partner.id),
            ('status', '=', 'active')
        ])
        warranty_expiring_count = Asset.search_count([
            ('partner_id', '=', partner.id),
            ('warranty_end', '!=', False),
            ('warranty_end', '<=', today_plus_30),
            ('warranty_end', '>=', fields.Date.today())
        ])
        
        values.update({
            'assets': assets,
            'page_name': 'assets',
            'pager': pager,
            'default_url': '/my/assets',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'search_in': search_in,
            'search': search,
            'asset_count': asset_count,
            'active_asset_count': active_asset_count,
            'warranty_expiring_count': warranty_expiring_count,
            'today_plus_30': today_plus_30,
        })
        
        return request.render("it_parc.portal_my_it_assets", values)
    
    # Vue détaillée d'un équipement
    @http.route(['/my/asset/<int:asset_id>'], type='http', auth="user", website=True)
    def portal_my_asset(self, asset_id=None, **kw):
        try:
            asset_sudo = self._document_check_access('it.asset', asset_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        # Récupérer les tickets récents liés à cet équipement
        recent_tickets = request.env['it.ticket'].search([
            ('asset_id', '=', asset_id),
        ], limit=5, order='date_created desc')
        
        today_plus_30 = fields.Date.today() + timedelta(days=30)
        
        values = {
            'asset': asset_sudo,
            'page_name': 'asset',
            'recent_tickets': recent_tickets,
            'today_plus_30': today_plus_30,
        }
        
        return request.render("it_parc.portal_asset_detail", values)

    # Formulaire de demande d'intervention
    @http.route(['/my/create/intervention'], type='http', auth="user", website=True)
    def portal_create_intervention(self, **kw):
        partner = request.env.user.partner_id
        Asset = request.env['it.asset']
        
        # Si c'est un POST, traiter la soumission du formulaire
        if request.httprequest.method == 'POST':
            # Extraire les données du formulaire
            values = {
                'partner_id': partner.id,
                'type': kw.get('intervention_type'),
                'description': kw.get('description'),
                'priority': kw.get('priority', '1'),
                'asset_ids': [(6, 0, [int(kw.get('asset_id'))])],
                'state': 'planned',
            }
            
            # Calculer les dates en fonction de la préférence
            preferred_date = kw.get('preferred_date')
            preferred_time = kw.get('preferred_time')
            
            if preferred_date:
                date_obj = fields.Date.from_string(preferred_date)
                time_start = '08:00:00'
                time_end = '17:00:00'
                
                if preferred_time == 'morning':
                    time_start = '08:00:00'
                    time_end = '12:00:00'
                elif preferred_time == 'afternoon':
                    time_start = '13:00:00'
                    time_end = '17:00:00'
                
                values.update({
                    'date_start': f"{preferred_date} {time_start}",
                    'date_end': f"{preferred_date} {time_end}",
                })
            
            # Créer l'intervention
            intervention = request.env['it.intervention'].sudo().create(values)
            
            # Gérer la pièce jointe si elle existe
            attachment = kw.get('attachment')
            if attachment:
                attachment_value = {
                    'name': attachment.filename,
                    'datas': base64.b64encode(attachment.read()),
                    'res_model': 'it.intervention',
                    'res_id': intervention.id,
                }
                request.env['ir.attachment'].sudo().create(attachment_value)
            
            # Rediriger vers la page de confirmation
            return request.render("it_parc.portal_intervention_created", {
                'intervention': intervention,
            })
        
        # Si c'est un GET, afficher le formulaire
        assets = Asset.search([
            ('partner_id', '=', partner.id),
            ('status', '=', 'active'),
        ])
        
        values = {
            'page_name': 'create_intervention',
            'assets': assets,
            'asset_id': kw.get('asset_id'),
            'today': fields.Date.today(),
        }
        
        return request.render("it_parc.portal_create_intervention", values)
    
    # Vue des contrats améliorée
    @http.route(['/my/contracts', '/my/contracts/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_contracts(self, page=1, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Contract = request.env['it.contract']
        
        # Filtres
        domain = [('partner_id', '=', partner.id)]
        
        # Filtres spécifiques
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'active': {'label': _('Active'), 'domain': [('state', '=', 'active')]},
            'expiring': {'label': _('Expiring Soon'), 'domain': [('expiry_alert', '=', True)]},
        }
        
        # Default filter
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Count pour pager
        contract_count = Contract.search_count(domain)
        
        # Compteurs pour statistiques
        active_contract_count = Contract.search_count([
            ('partner_id', '=', partner.id),
            ('state', '=', 'active')
        ])
        expiring_contract_count = Contract.search_count([
            ('partner_id', '=', partner.id),
            ('expiry_alert', '=', True)
        ])
        
        # Pager
        pager = portal_pager(
            url="/my/contracts",
            url_args={'filterby': filterby},
            total=contract_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content according to pager
        contracts = Contract.search(domain, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'contracts': contracts,
            'page_name': 'contracts',
            'pager': pager,
            'default_url': '/my/contracts',
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            'contract_count': contract_count,
            'active_contract_count': active_contract_count,
            'expiring_contract_count': expiring_contract_count,
        })
        
        return request.render("it_parc.portal_my_it_contracts", values)
    
    # Vue détaillée d'un contrat
    @http.route(['/my/contract/<int:contract_id>'], type='http', auth="user", website=True)
    def portal_my_contract(self, contract_id=None, **kw):
        try:
            contract_sudo = self._document_check_access('it.contract', contract_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        values = {
            'contract': contract_sudo,
            'page_name': 'contract',
        }
        
        return request.render("it_parc.portal_contract_detail", values)
    
    # Demande de renouvellement de contrat
    @http.route(['/my/contract/renew/<int:contract_id>'], type='http', auth="user", website=True)
    def portal_renew_contract(self, contract_id=None, **kw):
        try:
            contract_sudo = self._document_check_access('it.contract', contract_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
            
        # Créer une demande de renouvellement
        ticket = request.env['it.ticket'].sudo().create({
            'name': f"Demande de renouvellement du contrat {contract_sudo.name}",
            'partner_id': request.env.user.partner_id.id,
            'description': f"Le client souhaite renouveler son contrat de maintenance {contract_sudo.name}.",
            'priority': '1',
            'state': 'new',
        })
        
        # Message de confirmation
        message = f"Votre demande de renouvellement pour le contrat {contract_sudo.name} a été enregistrée. Notre équipe commerciale vous contactera prochainement."
        
        return request.render("it_parc.portal_simple_message", {
            'title': _("Demande de renouvellement"),
            'message': message,
            'back_url': f"/my/contract/{contract_id}",
        })
    
    # Template de message simple
    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tickets(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Ticket = request.env['it.ticket']
        
        domain = [('partner_id', '=', partner.id)]
        
        # Count for pager
        ticket_count = Ticket.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/tickets",
            total=ticket_count,
            page=page,
            step=self._items_per_page
        )
        
        # Content according to pager
        tickets = Ticket.search(domain, limit=self._items_per_page, offset=pager['offset'])
        
        values.update({
            'tickets': tickets,
            'page_name': 'tickets',
            'pager': pager,
            'default_url': '/my/tickets',
        })
        
        return request.render("it_parc.portal_my_it_tickets", values)
    
    @http.route(['/my/dashboard'], type='http', auth="user", website=True)
    def portal_it_dashboard(self, **kw):
        """Affiche le tableau de bord IT personnalisé"""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        
        # Compteurs pour statistiques
        asset_count = request.env['it.asset'].search_count([
            ('partner_id', '=', partner.id)
        ])
        
        active_count = request.env['it.asset'].search_count([
            ('partner_id', '=', partner.id),
            ('status', '=', 'active')
        ])
        
        ticket_count = request.env['it.ticket'].search_count([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['new', 'in_progress', 'waiting'])
        ])
        
        intervention_count = request.env['it.intervention'].search_count([
            ('partner_id', '=', partner.id),
            ('state', 'in', ['planned', 'in_progress'])
        ])
        
        today_plus_30 = fields.Date.today() + timedelta(days=30)
        
        # Alertes
        expiring_warranties = request.env['it.asset'].search_count([
            ('partner_id', '=', partner.id),
            ('warranty_end', '!=', False),
            ('warranty_end', '<=', today_plus_30),
            ('warranty_end', '>=', fields.Date.today())
        ])
        
        expiring_contracts = request.env['it.contract'].search_count([
            ('partner_id', '=', partner.id),
            ('expiry_alert', '=', True)
        ])
        
        # Activités récentes
        recent_activities = []
        
        # Tickets récents
        recent_tickets = request.env['it.ticket'].search([
            ('partner_id', '=', partner.id)
        ], limit=3, order='date_created desc')
        
        for ticket in recent_tickets:
            recent_activities.append({
                'name': f"Ticket: {ticket.name}",
                'date': ticket.date_created,
                'description': ticket.description[:100] + '...' if len(ticket.description) > 100 else ticket.description
            })
        
        # Interventions récentes
        recent_interventions = request.env['it.intervention'].search([
            ('partner_id', '=', partner.id)
        ], limit=3, order='date_start desc')
        
        for intervention in recent_interventions:
            recent_activities.append({
                'name': f"Intervention: {intervention.name}",
                'date': intervention.date_start,
                'description': intervention.description[:100] + '...' if len(intervention.description) > 100 else intervention.description
            })
        
        # Trier par date
        recent_activities = sorted(recent_activities, key=lambda x: x['date'], reverse=True)[:5]
        
        values.update({
            'asset_count': asset_count,
            'active_count': active_count,
            'ticket_count': ticket_count,
            'intervention_count': intervention_count,
            'expiring_warranties': expiring_warranties,
            'expiring_contracts': expiring_contracts,
            'recent_activities': recent_activities,
            'page_name': 'it_dashboard',
        })
        
        return request.render("it_parc.portal_it_dashboard", values)

    @http.route(['/my/asset/health/<int:asset_id>'], type='http', auth="user", website=True)
    def portal_asset_health(self, asset_id=None, **kw):
        """Affiche l'état de santé détaillé d'un équipement"""
        try:
            asset_sudo = self._document_check_access('it.asset', asset_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        # Récupérer les interventions pour cet équipement
        asset_interventions = request.env['it.intervention'].search([
            ('asset_ids', 'in', [asset_id]),
            ('state', '=', 'done')
        ], limit=5, order='date_end desc')
        
        values = {
            'asset': asset_sudo,
            'asset_interventions': asset_interventions,
            'page_name': 'asset_health',
        }
        
        return request.render("it_parc.portal_asset_health", values)

    @http.route(['/my/create/quote'], type='http', auth="user", website=True)
    def portal_create_quote(self, **kw):
        """Formulaire de demande de devis"""
        partner = request.env.user.partner_id
        Asset = request.env['it.asset']
        
        # Si c'est un POST, traiter la soumission du formulaire
        if request.httprequest.method == 'POST':
            # Créer une demande de devis (ticket spécial)
            values = {
                'name': f"Demande de devis: {kw.get('subject')}",
                'partner_id': partner.id,
                'description': kw.get('description'),
                'priority': '2' if kw.get('urgent') else '1',
                'state': 'new',
                'ticket_type': 'quote_request',
                'desired_date': kw.get('desired_date'),
                'budget': kw.get('budget'),
                'quote_type': kw.get('quote_type'),
            }
            
            # Associer l'équipement si spécifié
            asset_id = kw.get('asset_id')
            if asset_id:
                values['asset_id'] = int(asset_id)
            
            # Créer le ticket
            ticket = request.env['it.ticket'].sudo().create(values)
            
            # Gérer les pièces jointes
            attachment = kw.get('attachment')
            if attachment:
                if not isinstance(attachment, list):
                    attachment = [attachment]
                    
                for file in attachment:
                    attachment_value = {
                        'name': file.filename,
                        'datas': base64.b64encode(file.read()),
                        'res_model': 'it.ticket',
                        'res_id': ticket.id,
                    }
                    request.env['ir.attachment'].sudo().create(attachment_value)
        
        # Rediriger vers un message de confirmation
        return request.render("it_parc.portal_quote_created", {
            'ticket': ticket,
        })
    
    @http.route(['/my/reports', '/my/reports/page/<int:page>'], type='http', auth="user", website=True)
    def portal_reports(self, page=1, date_from=None, date_to=None, asset_type=None, report_type='inventory', **kw):
        """Page de rapports personnalisés"""
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        
        # Valeurs par défaut
        if not date_from:
            date_from = fields.Date.to_string(fields.Date.today() - timedelta(days=90))
        if not date_to:
            date_to = fields.Date.to_string(fields.Date.today())
        if not report_type:
            report_type = 'inventory'
        
        # Domaine pour les équipements
        domain = [('partner_id', '=', partner.id)]
        if asset_type:
            domain.append(('asset_type', '=', asset_type))
        
        # Récupérer les données selon le type de rapport
        if report_type == 'inventory':
            assets = request.env['it.asset'].search(domain)
            
            # Données pour les graphiques
            asset_types = {}
            asset_ages = [0, 0, 0, 0, 0]  # <1 an, 1-2 ans, 2-3 ans, 3-4 ans, +4 ans
            
            for asset in assets:
                # Comptage par type
                asset_type = asset.asset_type or 'Autre'
                asset_types[asset_type] = asset_types.get(asset_type, 0) + 1
                
                # Comptage par âge
                if asset.age_in_months:
                    if asset.age_in_months < 12:
                        asset_ages[0] += 1
                    elif asset.age_in_months < 24:
                        asset_ages[1] += 1
                    elif asset.age_in_months < 36:
                        asset_ages[2] += 1
                    elif asset.age_in_months < 48:
                        asset_ages[3] += 1
                    else:
                        asset_ages[4] += 1
            
            asset_type_labels = list(asset_types.keys())
            asset_type_data = list(asset_types.values())
            
        else:
            assets = []
            asset_type_labels = []
            asset_type_data = []
            asset_ages = [0, 0, 0, 0, 0]
        
        today_plus_30 = fields.Date.today() + timedelta(days=30)
        
        values.update({
            'assets': assets,
            'date_from': date_from,
            'date_to': date_to,
            'asset_type': asset_type,
            'report_type': report_type,
            'today_plus_30': today_plus_30,
            'asset_type_labels': json.dumps(asset_type_labels),
            'asset_type_data': json.dumps(asset_type_data),
            'asset_age_data': json.dumps(asset_ages),
            'page_name': 'it_reports',
        })
        
        return request.render("it_parc.portal_it_reports", values)

    @http.route(['/my/reports/export'], type='http', auth="user", website=True)
    def export_it_report(self, date_from=None, date_to=None, asset_type=None, report_type='inventory', **kw):
        """Export des rapports au format Excel"""
        partner = request.env.user.partner_id
        
        # Construire le domaine pour les données
        domain = [('partner_id', '=', partner.id)]
        if asset_type:
            domain.append(('asset_type', '=', asset_type))
            
        # Récupérer les données selon le type de rapport
        if report_type == 'inventory':
            assets = request.env['it.asset'].search(domain)
            
            # Créer un fichier Excel
            workbook = xlwt.Workbook()
            worksheet = workbook.add_sheet('Inventory Report')
            
            # Style pour les en-têtes
            header_style = xlwt.easyxf('font: bold on; align: horiz center;')
            
            # En-têtes des colonnes
            headers = ['Nom', 'Type', 'N° de série', 'Date d\'achat', 'Garantie jusqu\'au', 'Statut', 'Valeur actuelle']
            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_style)
                
            # Données
            row = 1
            for asset in assets:
                worksheet.write(row, 0, asset.name or '')
                worksheet.write(row, 1, asset.asset_type or '')
                worksheet.write(row, 2, asset.serial_number or '')
                worksheet.write(row, 3, asset.purchase_date and asset.purchase_date.strftime('%d/%m/%Y') or '')
                worksheet.write(row, 4, asset.warranty_end and asset.warranty_end.strftime('%d/%m/%Y') or '')
                worksheet.write(row, 5, asset.status or '')
                worksheet.write(row, 6, asset.current_value or 0)
                row += 1
                
            # Définir les largeurs des colonnes
            for col in range(len(headers)):
                worksheet.col(col).width = 256 * 20  # 20 caractères de large
                
            # Générer le fichier
            fp = BytesIO()
            workbook.save(fp)
            fp.seek(0)
            
            # Créer la réponse HTTP
            filename = f"IT_Inventory_Report_{fields.Date.today()}.xls"
            return request.make_response(fp.read(),
                                         [('Content-Type', 'application/vnd.ms-excel'),
                                          ('Content-Disposition', f'attachment; filename={filename}')])
        
        # Par défaut, retourner à la page des rapports
        return request.redirect('/my/reports')