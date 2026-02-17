from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMoveBuilding(models.Model):
    """
    Herencia de account.move para agregar campos de
    integración con el módulo de obras (building).
    """
    _inherit = 'account.move'

    has_building_allocation = fields.Boolean(
        string='Aplicada a Obra',
        default=False,
        readonly=True,
        tracking=True,
        help='Indica si esta factura tiene distribución a obras'
    )

    building_allocation_ids = fields.One2many(
        'building.bill.allocation',
        'move_id',
        string='Distribuciones a Obra',
        readonly=True
    )

    building_allocation_count = fields.Integer(
        compute='_compute_building_allocation_count',
        string='# Distribuciones'
    )

    building_allocated_amount = fields.Monetary(
        string='Monto Aplicado a Obras',
        compute='_compute_building_allocation_count',
        currency_field='currency_id'
    )

    is_fully_allocated = fields.Boolean(
        string='Completamente Distribuida',
        compute='_compute_is_fully_allocated',
        store=True,
    )

    @api.depends('building_allocation_ids', 'building_allocation_ids.amount_total',
                 'building_allocation_ids.state', 'amount_total')
    def _compute_is_fully_allocated(self):
        """Verifica si la factura ya tiene el 100% distribuido."""
        for move in self:
            allocated = sum(move.building_allocation_ids.filtered(
                lambda a: a.state == 'active'
            ).mapped('amount_total'))
            # Solo si el monto total es > 0 y coincide
            if move.amount_total > 0:
                move.is_fully_allocated = allocated >= (move.amount_total - 0.01)
            else:
                move.is_fully_allocated = False

    @api.depends('building_allocation_ids', 'building_allocation_ids.amount_total')
    def _compute_building_allocation_count(self):
        for move in self:
            allocations = move.building_allocation_ids
            move.building_allocation_count = len(allocations)
            move.building_allocated_amount = sum(allocations.mapped('amount_total'))

    def action_open_allocate_wizard(self):
        """Abre wizard para distribuir esta factura a obras."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(_('Solo se pueden aplicar facturas de proveedor a obras.'))
        if self.state != 'posted':
            raise UserError(_('La factura debe estar confirmada/publicada.'))
        # NUEVO: Verificar si ya está completamente distribuida
        if self.is_fully_allocated:
            raise UserError(_(
                'Esta factura ya está completamente distribuida a obras. '
                'Si necesita redistribuir, cancele la distribución existente primero.'
            ))
        return {
            'name': _('Aplicar a Obra'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.allocate.bill.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_amount_total': self.amount_total,
            },
        }


    def action_view_building_allocations(self):
        """Ver distribuciones a obras de esta factura."""
        self.ensure_one()
        return {
            'name': _('Distribuciones a Obra - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'building.bill.allocation',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
        }
    
    # =========================================================
    #  CFDI / XML LOADING
    # =========================================================
    
    l10n_mx_cfdi_uuid = fields.Char(string='UUID', copy=False, readonly=True, tracking=True, index=True)
    l10n_mx_cfdi_sat_status = fields.Selection([
        ('not_checked', 'Sin Validar'),
        ('valid', 'Vigente'),
        ('cancelled', 'Cancelado'),
        ('not_found', 'No Encontrado'),
        ('error', 'Error / Sin Conexión')
    ], string='Estatus SAT', default='not_checked', tracking=True, readonly=True)
    
    l10n_mx_cfdi_folio = fields.Char(string='Folio CFDI', readonly=True)
    l10n_mx_cfdi_fecha = fields.Datetime(string='Fecha Timbrado', readonly=True)
    l10n_mx_cfdi_forma_pago = fields.Char(string='Forma Pago', readonly=True)
    l10n_mx_cfdi_metodo_pago = fields.Char(string='Método Pago', readonly=True)
    l10n_mx_cfdi_rfc_emisor = fields.Char(string='RFC Emisor', readonly=True)
    l10n_mx_cfdi_rfc_receptor = fields.Char(string='RFC Receptor', readonly=True)
    l10n_mx_cfdi_amount = fields.Monetary(string='Monto CFDI', currency_field='currency_id', readonly=True, help='Monto exacto del XML para validación')
    l10n_mx_cfdi_xml_file = fields.Binary(string='XML Original', attachment=True, copy=False)
    l10n_mx_cfdi_xml_fname = fields.Char(string='Nombre XML')

    has_cfdi = fields.Boolean(compute='_compute_has_cfdi', store=True)
    
    @api.depends('l10n_mx_cfdi_uuid')
    def _compute_has_cfdi(self):
        for move in self:
            move.has_cfdi = bool(move.l10n_mx_cfdi_uuid)

    def action_open_cfdi_wizard(self):
        """Abre el wizard para cargar XML."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se puede cargar CFDI en facturas borrador.'))
        
        return {
            'name': _('Cargar XML CFDI'),
            'type': 'ir.actions.act_window',
            'res_model': 'building.cfdi.load.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def action_recheck_sat(self):
        """Re-consulta el estatus del CFDI en el SAT."""
        self.ensure_one()
        if not self.l10n_mx_cfdi_uuid:
            raise UserError(_('No hay UUID para validar.'))
        
        # Usar el RFC Receptor del XML si existe, sino el de la compañía
        rfc_receptor = self.l10n_mx_cfdi_rfc_receptor or self.company_id.vat or ''
        # Usar el Monto del XML si existe, sino el total de la factura
        total_verify = self.l10n_mx_cfdi_amount if self.l10n_mx_cfdi_amount else self.amount_total
        
        # Nota: Importamos el wizard para usar su metodo estatico o duplicamos logica
        # Mejor usar metodo auxiliar local para no depender del wizard
        status = self._check_sat_status(
            self.l10n_mx_cfdi_rfc_emisor, 
            rfc_receptor, 
            total_verify, 
            self.l10n_mx_cfdi_uuid
        )
        self.l10n_mx_cfdi_sat_status = status
        
        type_msg = 'success' if status == 'valid' else 'warning'
        if status == 'cancelled': type_msg = 'danger'
        
        # Mapeo de Estatus a Español
        status_labels = {
            'valid': 'Vigente',
            'cancelled': 'Cancelado',
            'not_found': 'No Encontrado',
            'error': 'Error'
        }
        status_label = status_labels.get(status, status)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validación SAT'),
                'message': _('Estatus Actualizado: %s') % status_label,
                'type': type_msg,
                'sticky': False,
            }
        }

    def _check_sat_status(self, rfc_emisor, rfc_receptor, total, uuid):
        """Helper para consultar SAT (copiado de wizard para independencia)."""
        import requests
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
        total_str = '%.6f' % abs(total)
        soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
           <soapenv:Body>
              <tem:Consulta>
                 <tem:expresionImpresa>?re={rfc_emisor}&amp;rr={rfc_receptor}&amp;tt={total_str}&amp;id={uuid}</tem:expresionImpresa>
              </tem:Consulta>
           </soapenv:Body>
        </soapenv:Envelope>"""
        headers = {'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta'}
        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=5)
            if 'Vigente' in response.text: return 'valid'
            if 'Cancelado' in response.text: return 'cancelled'
            if 'No Encontrado' in response.text: return 'not_found'
            return 'error'
        except:
            return 'error'
