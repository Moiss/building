# -*- coding: utf-8 -*-
"""
Test: Cifrado de API Keys
Verifica que el servicio de cifrado funcione correctamente.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'building_dashboard')
class TestEncryption(TransactionCase):
    """Tests para el servicio de cifrado."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.encryption = cls.env['building.encryption.service']
        # Generar y configurar clave de cifrado para tests
        cls.test_key = cls.encryption.generate_encryption_key()
        cls.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', cls.test_key
        )

    def test_01_generate_key(self):
        """Verifica que se genera una clave Fernet válida."""
        key = self.encryption.generate_encryption_key()
        self.assertTrue(key, "Debe generar una clave")
        self.assertEqual(len(key), 44, "La clave Fernet debe tener 44 caracteres (base64)")

    def test_02_encrypt_decrypt_round_trip(self):
        """Verifica que encrypt/decrypt funciona correctamente."""
        plain_key = "AIzaSyD12345678901234567890123456789"
        
        # Cifrar
        cipher_text, last4 = self.encryption.encrypt_api_key(plain_key)
        
        self.assertTrue(cipher_text, "Debe retornar texto cifrado")
        self.assertNotEqual(cipher_text, plain_key, "El texto cifrado NO debe ser igual al original")
        self.assertEqual(last4, "6789", "Debe retornar los últimos 4 caracteres")
        
        # Descifrar
        decrypted = self.encryption.decrypt_api_key(cipher_text)
        self.assertEqual(decrypted, plain_key, "El descifrado debe retornar el valor original")

    def test_03_encrypt_requires_master_key(self):
        """Verifica que falla si no hay clave maestra."""
        # Eliminar clave maestra
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', False
        )
        
        with self.assertRaises(UserError):
            self.encryption.encrypt_api_key("test_key")
        
        # Restaurar para otros tests
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', self.test_key
        )

    def test_04_is_encryption_configured(self):
        """Verifica el método de comprobación de configuración."""
        # Con clave configurada
        self.assertTrue(
            self.encryption.is_encryption_configured(),
            "Debe retornar True si hay clave configurada"
        )
        
        # Sin clave
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', False
        )
        self.assertFalse(
            self.encryption.is_encryption_configured(),
            "Debe retornar False sin clave"
        )
        
        # Restaurar
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', self.test_key
        )

    def test_05_encrypt_none_key(self):
        """Verifica que encrypt con None retorna None."""
        cipher_text, last4 = self.encryption.encrypt_api_key(None)
        self.assertIsNone(cipher_text)
        self.assertIsNone(last4)

    def test_06_decrypt_none_cipher(self):
        """Verifica que decrypt con None retorna None."""
        result = self.encryption.decrypt_api_key(None)
        self.assertIsNone(result)
