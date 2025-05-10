from odoo import http
from odoo.http import request

class ITAssetController(http.Controller):
    @http.route(['/it-assets', '/it-assets/page/<int:page>'], type='http', auth="public", website=True)
    def list_assets(self, page=1, **kw):
        Asset = request.env['it.asset']
        
        # Comptage des assets
        assets_count = Asset.search_count([])
        pager = request.website.pager(
            url='/it-assets',
            total=assets_count,
            page=page,
            step=10,
        )
        
        # Récupération des assets pour la page courante
        assets = Asset.search([], limit=10, offset=pager['offset'])
        
        values = {
            'assets': assets,
            'pager': pager,
        }
        return request.render("it_parc.assets_list_template", values)
    
    @http.route(['/it-assets/<model("it.asset"):asset>'], type='http', auth="public", website=True)
    def asset_details(self, asset, **kw):
        return request.render("it_parc.asset_detail_template", {
            'asset': asset,
        })