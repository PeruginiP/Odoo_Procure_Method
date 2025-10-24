from odoo import models, fields, api
from odoo.tools import float_is_zero
# defaultdict es una herramienta genial para agrupar
# registros sin necesidad de comprobar si la clave ya existe.
from collections import defaultdict

class StockRule(models.Model):
    _inherit = 'stock.rule'

    # --- 1. Definición del Nuevo Método ---
    # Añadimos nuestro método a la lista de opciones de Odoo.
    # Esto permite seleccionarlo en la configuración de las reglas.
    procure_method = fields.Selection(
        selection_add=[
            ('mts_transfer_need', 'Tomar de stock, si no, transferir necesidad')
        ], ondelete={'mts_transfer_need': 'cascade'}
    )

    # --- 2. Sobrescritura del Método '_run_pull' ---
    # Este es el "cerebro" de las reglas de abastecimiento. Odoo lo llama
    # cada vez que necesita "traer" productos a una ubicación.
    # 'procurements' es una lista de tuplas [(procurement, rule), ...]
    def _run_pull(self, procurements):
        
        # --- 3. Separación de Lógicas ---
        # Primero, separamos las reglas que usan nuestro método custom
        # de las reglas estándar de Odoo (MTO, MTS, Comprar, etc.).
        procurements_custom_tuples = []
        procurements_standard = []
        
        for procurement, rule in procurements:
            if rule.procure_method == 'mts_transfer_need':
                procurements_custom_tuples.append((procurement, rule))
            else:
                procurements_standard.append((procurement, rule))

        # Dejamos que Odoo maneje las reglas estándar de forma normal.
        if procurements_standard:
            super(StockRule, self)._run_pull(procurements_standard)
        
        # Si no hay nada para nuestro método, terminamos.
        if not procurements_custom_tuples:
            return

        # 'moves_to_confirm' recolectará todos los movimientos de stock
        # que SÍ tomemos del disponible. Los confirmaremos todos al final.
        moves_to_confirm = self.env['stock.move']
        
        # --- 4. EL "TRACKER" GLOBAL (La Magia) ---
        #
        # PROBLEMA: Si hay 2+ rutas distintas, Odoo llama a '_run_pull'
        # varias veces (una por ruta) en la misma transacción.
        # Una variable local no sirve para compartir el stock consumido.
        #
        # SOLUCIÓN: Usamos el 'contexto' de Odoo (self.env.context)
        # como un "tracker" global que persiste durante toda la transacción.
        
        # Buscamos nuestro tracker en el contexto. Si no existe, lo creamos.
        stock_tracker = self.env.context.get('mts_need_tracker')
        if stock_tracker is None:
            stock_tracker = {} # Será un dict: {(prod_id, loc_id): qty}

        # Creamos un nuevo entorno 'this_env' que SIEMPRE lleve
        # nuestro tracker en su contexto.
        this_env = self.with_context(mts_need_tracker=stock_tracker)

        # --- 5. Agrupación por "Pool" de Stock ---
        # Agrupamos todas las líneas por lo que define un stock físico:
        # el Producto y la Ubicación de Origen (de dónde tomamos).
        grouped_procs = defaultdict(list)
        for procurement, rule in procurements_custom_tuples:
            key = (procurement.product_id, rule.location_src_id)
            grouped_procs[key].append((procurement, rule))

        # Obtenemos la precisión decimal (usando nuestro 'this_env').
        precision = this_env.env['decimal.precision'].precision_get('Product Unit of Measure')

        # --- 6. Iteración por "Pool" de Stock ---
        # Procesamos cada grupo (ej. "Todas las líneas que piden 'Producto A' de 'WHA'").
        for (product_id, location_src), procs_list in grouped_procs.items():
            
            # --- 6a. Ordenamiento Secuencial ---
            # ¡CRÍTICO! Ordenamos las líneas de este grupo (ej. por 'sale_line_id')
            # para asegurar que la primera línea de la SO consume primero.
            procs_sorted = sorted(
                procs_list,
                key=lambda pr: (
                    pr[0].values.get('sale_line_id', 0),
                    pr[0].values.get('stock_move_id', 0)
                )
            )

            # --- 6b. Consulta del Tracker ---
            # Creamos una clave única para nuestro tracker global.
            tracker_key = (product_id.id, location_src.id)

            # Si es la PRIMERA VEZ que vemos este pool (Producto/Ubicación)
            # en esta transacción, consultamos la BD UNA SOLA VEZ.
            if tracker_key not in stock_tracker:
                stock_tracker[tracker_key] = this_env.env['stock.quant']._get_available_quantity(
                    product_id, 
                    location_src
                )
            
            # Obtenemos el disponible "virtual" actual de nuestro tracker.
            available_qty_tracker = stock_tracker[tracker_key]

            # --- 6c. Consumo Secuencial ---
            # Iteramos sobre las líneas ORDENADAS.
            for procurement, rule in procs_sorted:
                # Extraemos los datos del abastecimiento
                product_qty = procurement.product_qty
                product_uom = procurement.product_uom
                origin = procurement.origin
                values = procurement.values
                procurement_name = procurement.name 
                company_id = procurement.company_id
                location_of_need = procurement.location_id
                
                # Comparamos la necesidad vs. el tracker (no la BD).
                qty_to_take = min(product_qty, available_qty_tracker)
                qty_remaining = product_qty - qty_to_take

                # --- 6d. Parte 1: Tomar del Stock (si hay) ---
                if not float_is_zero(qty_to_take, precision_digits=precision):
                    # Creamos el movimiento de stock por la cantidad que SÍ tenemos.
                    move_values = rule._get_stock_move_values(
                        product_id=product_id,
                        product_qty=qty_to_take,
                        product_uom=product_uom, 
                        location_dest_id=location_of_need, 
                        name=procurement_name,
                        origin=origin,
                        company_id=company_id,
                        values=values
                    )
                    # Forzamos 'make_to_stock' porque lo estamos tomando del disponible.
                    move_values['procure_method'] = 'make_to_stock' 
                    
                    # Creamos el movimiento y lo añadimos a la lista de confirmación.
                    move = this_env.env['stock.move'].create(move_values)
                    moves_to_confirm |= move
                    
                    # ¡CRÍTICO! Actualizamos el tracker para que
                    # la siguiente línea (o la siguiente llamada a _run_pull)
                    # vea el stock actualizado.
                    available_qty_tracker -= qty_to_take
                    stock_tracker[tracker_key] = available_qty_tracker

                # --- 6e. Parte 2: Transferir Necesidad (el faltante) ---
                if not float_is_zero(qty_remaining, precision_digits=precision):
                    # Preparamos un nuevo abastecimiento SÓLO por el faltante.
                    new_values = values.copy()
                    
                    # ¡LA SOLUCIÓN! No forzamos 'make_to_order'.
                    # Simplemente nos excluimos a nosotros mismos.
                    excluded_rules = list(new_values.get('rules_to_exclude', []))
                    excluded_rules.append(rule.id)
                    new_values['rules_to_exclude'] = excluded_rules
                    
                    # Creamos el nuevo abastecimiento por el faltante.
                    new_procurement = this_env.env['procurement.group'].Procurement(
                        product_id, 
                        qty_remaining, 
                        product_uom,
                        location_of_need,
                        procurement.name, 
                        procurement.origin,
                        procurement.company_id, 
                        new_values
                    )
                    
                    # Volvemos a llamar a 'run' usando 'this_env'.
                    # Esto asegura que el tracker (con el stock actualizado)
                    # se pase a la siguiente ejecución de reglas.
                    this_env.env['procurement.group'].run([new_procurement], raise_user_error=False)

        # --- 7. Confirmación Final ---
        # Confirmamos todos los movimientos 'make_to_stock' en un solo lote.
        if moves_to_confirm:
            moves_to_confirm._action_confirm()
            
        return