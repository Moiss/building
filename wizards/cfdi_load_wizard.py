# -*- coding: utf-8 -*-
import base64
import logging
import requests
from lxml import etree
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BuildingCfdiLoadWizard(models.TransientModel):
    _name = 'building.cfdi.load.wizard'
    _description = 'Cargar XML CFDI'

    move_id = fields.Many2one('account.move', string='Factura', required=True, readonly=True)
    xml_file = fields.Binary(string='Archivo XML', required=True)
    xml_filename = fields.Char(string='Nombre del Archivo')

    # Campos de previsualización
    preview_uuid = fields.Char(string='UUID', readonly=True, compute='_compute_preview_data', store=True)
    preview_rfc = fields.Char(string='RFC Emisor', readonly=True, compute='_compute_preview_data', store=True)
    preview_nombre = fields.Char(string='Emisor', readonly=True, compute='_compute_preview_data', store=True)
    preview_total = fields.Monetary(string='Total', readonly=True, compute='_compute_preview_data', store=True, currency_field='currency_id')
    preview_fecha = fields.Char(string='Fecha', readonly=True, compute='_compute_preview_data', store=True)
    
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_preview_data', store=True)

    sat_status = fields.Char(string='Estatus SAT', readonly=True)
    sat_status_icon = fields.Selection([
        ('success', 'Vigente'),
        ('warning', 'No Encontrado/Error'),
        ('danger', 'Cancelado')
    ], string='Icono Estatus', readonly=True)

    @api.depends('xml_file')
    def _compute_preview_data(self):
        for wizard in self:
            if not wizard.xml_file:
                wizard.preview_uuid = False
                wizard.preview_rfc = False
                wizard.preview_nombre = False
                wizard.preview_total = 0.0
                wizard.preview_fecha = False
                wizard.currency_id = False
                continue

            try:
                tree = self._parse_xml(wizard.xml_file)
                ns = self._get_namespaces(tree)
                
                # Datos del Comprobante
                root = tree.getroot()
                wizard.preview_total = float(root.get('Total', '0.0'))
                wizard.preview_fecha = root.get('Fecha', '')
                
                # Moneda
                moneda_code = root.get('Moneda', 'MXN')
                currency = self.env['res.currency'].search([('name', '=', moneda_code)], limit=1)
                if not currency:
                    # Fallback a MXN si no encuentra
                    currency = self.env.ref('base.MXN')
                wizard.currency_id = currency

                # Datos del Emisor
                emisor = root.find('cfdi:Emisor', ns)
                if emisor is not None:
                    wizard.preview_rfc = emisor.get('Rfc', '')
                    wizard.preview_nombre = emisor.get('Nombre', '')

                # UUID del Timbre
                tfd = root.find('.//tfd:TimbreFiscalDigital', ns)
                if tfd is not None:
                    wizard.preview_uuid = tfd.get('UUID', '')
                
                # Validar status SAT preliminar (opcional, si se quiere feedback inmediato)
                # Por ahora solo parseamos para preview.
                
            except Exception as e:
                _logger.error(f"Error parsing XML preview: {e}")
                # No levantar error aquí para permitir al usuario ver que algo falló o reintentar
                wizard.preview_uuid = 'Error al leer XML'

    def _parse_xml(self, file_content):
        """Decodifica y parsea el archivo XML."""
        try:
            decoded = base64.b64decode(file_content)
            # Eliminar BOM si existe
            # if decoded.startswith(b'\xef\xbb\xbf'):
            #    decoded = decoded[3:]
            return etree.fromstring(decoded)
        except Exception as e:
            raise UserError(_('El archivo no es un XML válido: %s') % str(e))

    def _get_namespaces(self, tree):
        """Detecta versión 3.3 o 4.0 y retorna namespaces."""
        root = tree.getroot()
        if 'http://www.sat.gob.mx/cfd/4' in root.nsmap.values():
            return {
                'cfdi': 'http://www.sat.gob.mx/cfd/4',
                'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
            }
        elif 'http://www.sat.gob.mx/cfd/3' in root.nsmap.values():
            return {
                'cfdi': 'http://www.sat.gob.mx/cfd/3',
                'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'
            }
        else:
            # Fallback genérico intentando usar el mapa del root
            # A veces el nsmap tiene None como clave para el default
            ns = {k:v for k,v in root.nsmap.items() if k}
            if 'cfdi' not in ns:
                # Si es default namespace
                if None in root.nsmap:
                    ns['cfdi'] = root.nsmap[None]
            ns['tfd'] = 'http://www.sat.gob.mx/TimbreFiscalDigital'
            return ns

    def action_load_and_validate(self):
        """Carga datos, valida en SAT, crea/busca partner y actualiza factura."""
        self.ensure_one()
        if not self.xml_file:
            raise UserError(_('Por favor seleccione un archivo XML.'))

        tree = self._parse_xml(self.xml_file)
        ns = self._get_namespaces(tree)
        root = tree.getroot()

        # 1. Extraer Datos
        try:
            # Comprobante
            serie = root.get('Serie', '')
            folio = root.get('Folio', '')
            fecha_str = root.get('Fecha', '')
            # Convertir fecha '2026-02-15T10:30:00' -> datetime
            # A veces viene con ms o sin T, tratar de ser flexible o usar ISO
            try:
                fecha_cfdi = datetime.fromisoformat(fecha_str)
            except ValueError:
                fecha_cfdi = datetime.strptime(fecha_str[:19], '%Y-%m-%dT%H:%M:%S')

            forma_pago = root.get('FormaPago', '')
            metodo_pago = root.get('MetodoPago', '')
            moneda_code = root.get('Moneda', 'MXN')
            tipo_cambio = float(root.get('TipoCambio', '1.0'))
            subtotal = float(root.get('SubTotal', '0.0'))
            total = float(root.get('Total', '0.0'))

            # Emisor
            emisor = root.find('cfdi:Emisor', ns)
            rfc_emisor = emisor.get('Rfc', '')
            nombre_emisor = emisor.get('Nombre', '')
            
            # Receptor
            receptor = root.find('cfdi:Receptor', ns)
            rfc_receptor = receptor.get('Rfc', '')

            # Timbre
            tfd = root.find('.//tfd:TimbreFiscalDigital', ns)
            if tfd is None:
                raise UserError(_('El XML no tiene Timbre Fiscal Digital (no está timbrado).'))
            
            uuid = tfd.get('UUID').upper()
            
        except AttributeError as e:
            raise UserError(_('Estructura del XML inválida o faltan campos requeridos: %s') % str(e))

        # 2. Verificar duplicados
        duplicated = self.env['account.move'].search([
            ('l10n_mx_cfdi_uuid', '=', uuid),
            ('id', '!=', self.move_id.id),
            ('move_type', 'in', ('in_invoice', 'in_refund'))
        ])
        if duplicated:
            raise UserError(_('Este CFDI (UUID %s) ya está cargado en la factura: %s') % (uuid, duplicated[0].name))

        # 3. Validar Status SAT
        sat_status = self._check_sat_status_soap(rfc_emisor, rfc_receptor, total, uuid)

        # 4. Buscar / Crear Proveedor
        partner = self.env['res.partner'].search([('vat', '=', rfc_emisor)], limit=1)
        if not partner:
            # Crear contacto
            partner = self.env['res.partner'].create({
                'name': nombre_emisor,
                'vat': rfc_emisor,
                'company_type': 'company',
                'supplier_rank': 1,
                'country_id': self.env.ref('base.mx').id,
            })

        # 5. Preparar actualización de factura
        
        # Moneda
        currency = self.env['res.currency'].search([('name', '=', moneda_code)], limit=1)
        if not currency:
             currency = self.env.ref('base.MXN') # Fallback
             
        # Limpiar líneas actuales ??? -> Sí, segun spec
        self.move_id.invoice_line_ids.unlink()

        # Crear nuevas líneas desde Conceptos
        invoice_lines = []
        conceptos = root.find('cfdi:Conceptos', ns)
        
        for concepto in conceptos.findall('cfdi:Concepto', ns):
            descripcion = concepto.get('Descripcion', '')
            cantidad = float(concepto.get('Cantidad', '1.0'))
            precio_unitario = float(concepto.get('ValorUnitario', '0.0'))
            importe = float(concepto.get('Importe', '0.0')) # informativo
            
            # Impuestos
            tax_ids = []
            impuestos_node = concepto.find('cfdi:Impuestos', ns)
            if impuestos_node is not None:
                # Traslados
                traslados = impuestos_node.find('cfdi:Traslados', ns)
                if traslados is not None:
                    for traslado in traslados.findall('cfdi:Traslado', ns):
                        tasa = float(traslado.get('TasaOCuota', '0.0'))
                        # Buscar impuesto (ej: 0.16 -> 16%)
                        percentage = tasa * 100
                        
                        # Buscar impuesto de compra
                        tax_domain = [
                            ('amount', '=', percentage),
                            ('type_tax_use', '=', 'purchase'),
                            ('company_id', '=', self.move_id.company_id.id)
                        ]
                        
                        # Refinar búsqueda por tipo si es posible (IVA vs IEPS) - Simplificado por ahora
                        tax = self.env['account.tax'].search(tax_domain, limit=1)
                        if tax:
                             tax_ids.append(tax.id)
                
                # Retenciones
                retenciones = impuestos_node.find('cfdi:Retenciones', ns)
                if retenciones is not None:
                    for retencion in retenciones.findall('cfdi:Retencion', ns):
                         # La logica de retenciones es similar pero con montos negativos en Odoo usualmente
                         # o configurados como 'purchase' + 'balance' negativo
                         # Implementación simple: buscar por monto negativo si es ISR/IVA Retenido
                         # Esto depende mucho de la config local. Haremos un best effort.
                         pass

            line_vals = {
                'name': descripcion,
                'quantity': cantidad,
                'price_unit': precio_unitario,
                'tax_ids': [(6, 0, tax_ids)],
                # 'product_uom_id': ... sería ideal mapear unidad SAT -> Odoo UoM pero es complejo
            }
            invoice_lines.append((0, 0, line_vals))

        # Actualizar Invoice
        vals = {
            'partner_id': partner.id,
            'ref': f"{serie}{folio}".strip() or uuid[:8],
            'invoice_date': fecha_cfdi.date(),
            'currency_id': currency.id,
            'invoice_line_ids': invoice_lines,
            # Campos CFDI
            'l10n_mx_cfdi_uuid': uuid,
            'l10n_mx_cfdi_sat_status': sat_status,
            'l10n_mx_cfdi_folio': f"{serie}{folio}".strip(),
            'l10n_mx_cfdi_fecha': fecha_cfdi,
            'l10n_mx_cfdi_forma_pago': forma_pago,
            'l10n_mx_cfdi_metodo_pago': metodo_pago,
            'l10n_mx_cfdi_rfc_emisor': rfc_emisor,
            'l10n_mx_cfdi_xml_fname': self.xml_filename or 'cfdi.xml',
        }
        
        # Adjuntar XML
        # Primero crear attachment
        attachment = self.env['ir.attachment'].create({
            'name': self.xml_filename or f"{uuid}.xml",
            'datas': self.xml_file,
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'mimetype': 'application/xml',
        })
        vals['l10n_mx_cfdi_xml_file'] = self.xml_file # Campo Binary en move para acceso rápido
        
        self.move_id.write(vals)

        # Mensajes de retorno
        if sat_status == 'cancelled':
            notification_type = 'danger'
            message = _("⚠️ CFDI cargado pero está CANCELADO en el SAT.")
        elif sat_status == 'valid':
            notification_type = 'success'
            message = _("✅ CFDI cargado y validado Vigente.")
        else:
            notification_type = 'warning'
            message = _("⚠️ CFDI cargado. Estado SAT: %s") % sat_status

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Carga CFDI'),
                'message': message,
                'type': notification_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _check_sat_status_soap(self, rfc_emisor, rfc_receptor, total, uuid):
        """Consulta SOAP al SAT."""
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
        total_str = '%.6f' % abs(total)
        soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
           <soapenv:Body>
              <tem:Consulta>
                 <tem:expresionImpresa>?re={rfc_emisor}&amp;rr={rfc_receptor}&amp;tt={total_str}&amp;id={uuid}</tem:expresionImpresa>
              </tem:Consulta>
           </soapenv:Body>
        </soapenv:Envelope>"""
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta'
        }
        try:
            response = requests.post(url, data=soap_body, headers=headers, timeout=5)
            # Analisis simple del texto plano (xml response)
            resp_text = response.text
            if 'Vigente' in resp_text:
                return 'valid'
            elif 'Cancelado' in resp_text:
                return 'cancelled'
            elif 'No Encontrado' in resp_text:
                return 'not_found'
            else:
                 _logger.warning(f"Respuesta SAT desconocida: {resp_text}")
                 return 'error'
        except Exception as e:
            _logger.error(f"Error conectando SAT: {e}")
            return 'error'
