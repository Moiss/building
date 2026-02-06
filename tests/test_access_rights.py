# -*- coding: utf-8 -*-
"""
Test: Permisos de Acceso
Verifica que los permisos por grupo funcionen correctamente.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'building_dashboard')
class TestAccessRights(TransactionCase):
    """Tests para permisos de acceso."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Crear usuarios de prueba
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        
        # Usuario Contabilidad (solo lectura)
        cls.user_accounting = Users.create({
            'name': 'Test Contabilidad',
            'login': 'test_accounting',
            'email': 'test_accounting@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('building_dashboard.group_building_accounting').id,
            ])],
        })
        
        # Usuario Compras
        cls.user_purchases = Users.create({
            'name': 'Test Compras',
            'login': 'test_purchases',
            'email': 'test_purchases@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('building_dashboard.group_building_purchases').id,
            ])],
        })
        
        # Usuario Director
        cls.user_director = Users.create({
            'name': 'Test Director',
            'login': 'test_director',
            'email': 'test_director@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('building_dashboard.group_building_director').id,
            ])],
        })
        
        # Crear obra de prueba
        cls.work = cls.env['building.work'].create({
            'name': 'Obra de Prueba',
            'budget_total': 1000000,
        })
        
        # Configurar cifrado para tests de AI Config
        encryption = cls.env['building.encryption.service']
        test_key = encryption.generate_encryption_key()
        cls.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', test_key
        )

    def test_01_accounting_can_read_work(self):
        """Contabilidad puede leer obras."""
        work = self.work.with_user(self.user_accounting)
        # Debe poder leer sin errores
        name = work.name
        self.assertEqual(name, 'Obra de Prueba')

    def test_02_accounting_cannot_write_work(self):
        """Contabilidad NO puede escribir obras."""
        work = self.work.with_user(self.user_accounting)
        with self.assertRaises(AccessError):
            work.write({'name': 'Nombre Modificado'})

    def test_03_director_can_write_work(self):
        """Director puede escribir obras."""
        work = self.work.with_user(self.user_director)
        work.write({'name': 'Obra Modificada por Director'})
        self.assertEqual(work.name, 'Obra Modificada por Director')

    def test_04_purchases_cannot_write_ai_config(self):
        """Compras NO puede escribir en AI Config."""
        AIConfig = self.env['building.ai.config'].with_user(self.user_purchases)
        
        with self.assertRaises(AccessError):
            AIConfig.create({
                'company_id': self.env.company.id,
                'provider': 'gemini',
                'model_name': 'gemini-1.5-pro',
                'api_key_encrypted': 'fake_encrypted_key',
                'api_key_last4': '1234',
            })

    def test_05_director_can_write_ai_config(self):
        """Director puede escribir en AI Config."""
        AIConfig = self.env['building.ai.config'].with_user(self.user_director)
        
        config = AIConfig.create({
            'company_id': self.env.company.id,
            'provider': 'gemini',
            'model_name': 'gemini-1.5-pro',
            'api_key_encrypted': 'fake_encrypted_key',
            'api_key_last4': '1234',
        })
        
        self.assertTrue(config.id, "Director debe poder crear AI Config")

    def test_06_purchases_can_write_stages(self):
        """Compras puede escribir en etapas (limitado)."""
        stage = self.env['building.work.stage'].create({
            'name': 'Etapa Test',
            'work_id': self.work.id,
        })
        
        stage_as_purchases = stage.with_user(self.user_purchases)
        stage_as_purchases.write({'progress_pct': 50})
        self.assertEqual(stage_as_purchases.progress_pct, 50)
