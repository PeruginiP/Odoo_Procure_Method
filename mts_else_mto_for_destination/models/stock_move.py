from odoo import models, fields

class StockMove(models.Model):
    _inherit = 'stock.move'

    procure_method = fields.Selection(
        selection_add=[
            ('mts_transfer_need', 'Tomar de stock, si no, transferir necesidad')
        ], ondelete={'mts_transfer_need': 'cascade'}
    )