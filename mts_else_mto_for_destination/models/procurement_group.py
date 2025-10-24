from odoo import models

class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    def _get_rule_domain(self, location_id, values):
        """
        Heredamos este método para añadir un filtro al dominio de búsqueda
        de reglas.
        
        Este método es llamado por Odoo (en _find_rule) cada vez que 
        busca una regla de stock para un producto/ubicación.
        """
        domain = super(ProcurementGroup, self)._get_rule_domain(location_id, values)
        
        # Verificamos si hay reglas para excluir en los 'values'
        # que pasamos desde stock_rule.py
        if values and values.get('rules_to_exclude'):
            rules_to_exclude = values['rules_to_exclude']
            
            # Añadimos la condición al dominio
            domain += [('id', 'not in', rules_to_exclude)]
        
        return domain