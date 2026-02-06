# -*- coding: utf-8 -*-
"""
Servicio de cifrado para API Keys del Asistente IA.
Utiliza Fernet (cryptography) para cifrado simétrico seguro.
"""

import base64
import logging
from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Intentar importar cryptography
try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    _logger.warning(
        "La librería 'cryptography' no está instalada. "
        "El cifrado de API Keys NO estará disponible. "
        "Ejecute: pip install cryptography"
    )


class EncryptionService(models.AbstractModel):
    """
    Servicio abstracto para cifrado/descifrado de API Keys.
    Usa una clave maestra almacenada en ir.config_parameter.
    """
    _name = 'building.encryption.service'
    _description = 'Servicio de Cifrado para API Keys'

    @api.model
    def _check_crypto_available(self):
        """Verifica que la librería cryptography esté disponible."""
        if not CRYPTO_AVAILABLE:
            raise UserError(
                "La librería 'cryptography' es requerida para el cifrado de API Keys.\n"
                "Instálela ejecutando: pip install cryptography"
            )

    @api.model
    def _get_master_key(self):
        """
        Obtiene la clave maestra de cifrado desde ir.config_parameter.
        Retorna None si no está configurada.
        """
        self._check_crypto_available()
        key = self.env['ir.config_parameter'].sudo().get_param(
            'building.encryption_key', default=False
        )
        if not key:
            return None
        # La clave debe ser bytes válidos para Fernet (base64 de 32 bytes)
        try:
            # Validar que sea una clave Fernet válida
            Fernet(key.encode())
            return key.encode()
        except Exception as e:
            _logger.error("Clave de cifrado inválida: %s", str(e))
            return None

    @api.model
    def generate_encryption_key(self):
        """
        Genera una nueva clave de cifrado Fernet.
        Útil para configuración inicial.
        """
        self._check_crypto_available()
        return Fernet.generate_key().decode()

    @api.model
    def encrypt_api_key(self, plain_key):
        """
        Cifra una API Key y retorna (cipher_text, last4).
        
        Args:
            plain_key: La API Key en texto plano
            
        Returns:
            tuple: (texto_cifrado, últimos_4_caracteres)
            
        Raises:
            UserError: Si no hay clave maestra configurada
        """
        if not plain_key:
            return None, None
            
        master_key = self._get_master_key()
        if not master_key:
            raise UserError(
                "No hay clave de cifrado configurada.\n"
                "Vaya a Ajustes > Building Dashboard y configure la clave de cifrado."
            )
        
        try:
            fernet = Fernet(master_key)
            cipher_text = fernet.encrypt(plain_key.encode()).decode()
            last4 = plain_key[-4:] if len(plain_key) >= 4 else plain_key
            return cipher_text, last4
        except Exception as e:
            _logger.error("Error al cifrar API Key: %s", str(e))
            raise UserError("Error al cifrar la API Key. Verifique la clave de cifrado.")

    @api.model
    def decrypt_api_key(self, cipher_text):
        """
        Descifra una API Key cifrada.
        
        Args:
            cipher_text: El texto cifrado
            
        Returns:
            str: La API Key en texto plano
            
        Raises:
            UserError: Si no hay clave maestra o el descifrado falla
        """
        if not cipher_text:
            return None
            
        master_key = self._get_master_key()
        if not master_key:
            raise UserError(
                "No hay clave de cifrado configurada.\n"
                "No es posible descifrar las API Keys."
            )
        
        try:
            fernet = Fernet(master_key)
            plain_key = fernet.decrypt(cipher_text.encode()).decode()
            return plain_key
        except InvalidToken:
            _logger.error("Token de cifrado inválido - posible cambio de clave maestra")
            raise UserError(
                "No se pudo descifrar la API Key.\n"
                "Es posible que la clave de cifrado haya cambiado."
            )
        except Exception as e:
            _logger.error("Error al descifrar API Key: %s", str(e))
            raise UserError("Error al descifrar la API Key.")

    @api.model
    def is_encryption_configured(self):
        """Verifica si el cifrado está correctamente configurado."""
        if not CRYPTO_AVAILABLE:
            return False
        try:
            return self._get_master_key() is not None
        except Exception:
            return False
