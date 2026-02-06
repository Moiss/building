# -*- coding: utf-8 -*-
"""
Test: Wizard de Configuración IA
Verifica que el wizard guarde correctamente las configuraciones.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'building_dashboard')
class TestWizardSave(TransactionCase):
    """Tests para el wizard de configuración IA."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Configurar cifrado
        cls.encryption = cls.env['building.encryption.service']
        cls.test_key = cls.encryption.generate_encryption_key()
        cls.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', cls.test_key
        )
        
        # Crear obra de prueba
        cls.work = cls.env['building.work'].create({
            'name': 'Obra Test Wizard',
        })
        
        # Crear usuario director para tests
        cls.user_director = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Director Wizard',
            'login': 'test_director_wizard',
            'email': 'test_director_wizard@test.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('building_dashboard.group_building_director').id,
            ])],
        })

    def test_01_wizard_save_gemini_config(self):
        """Verifica que el wizard guarde configuración de Gemini."""
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        
        wizard = Wizard.create({
            'company_id': self.env.company.id,
            'work_id': self.work.id,
            'use_work_override': False,
            'gemini_api_key': 'AIzaSyTestKey1234567890',
            'gemini_model': 'gemini-1.5-pro',
        })
        
        # Ejecutar guardado
        wizard.action_save()
        
        # Verificar que se creó la configuración
        config = self.env['building.ai.config'].search([
            ('company_id', '=', self.env.company.id),
            ('provider', '=', 'gemini'),
            ('work_id', '=', False),
        ])
        
        self.assertTrue(config, "Debe existir configuración de Gemini")
        self.assertEqual(config.model_name, 'gemini-1.5-pro')
        self.assertEqual(config.api_key_last4, '7890')
        self.assertNotEqual(
            config.api_key_encrypted, 
            'AIzaSyTestKey1234567890',
            "La key debe estar cifrada"
        )

    def test_02_wizard_save_openai_config(self):
        """Verifica que el wizard guarde configuración de OpenAI."""
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        
        wizard = Wizard.create({
            'company_id': self.env.company.id,
            'openai_api_key': 'sk-proj-TestApiKeyOpenAI123',
            'openai_model': 'gpt-4o',
        })
        
        wizard.action_save()
        
        config = self.env['building.ai.config'].search([
            ('company_id', '=', self.env.company.id),
            ('provider', '=', 'openai'),
        ])
        
        self.assertTrue(config, "Debe existir configuración de OpenAI")
        self.assertEqual(config.api_key_last4, 'I123')

    def test_03_wizard_work_override(self):
        """Verifica configuración específica por obra."""
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        
        wizard = Wizard.create({
            'company_id': self.env.company.id,
            'work_id': self.work.id,
            'use_work_override': True,  # Override por obra
            'gemini_api_key': 'AIzaSyWorkSpecificKey99',
            'gemini_model': 'gemini-1.5-flash',
        })
        
        wizard.action_save()
        
        # Buscar config específica de obra
        config = self.env['building.ai.config'].search([
            ('company_id', '=', self.env.company.id),
            ('work_id', '=', self.work.id),
            ('provider', '=', 'gemini'),
        ])
        
        self.assertTrue(config, "Debe existir config específica de obra")
        self.assertEqual(config.work_id.id, self.work.id)
        self.assertEqual(config.model_name, 'gemini-1.5-flash')

    def test_04_wizard_requires_encryption_key(self):
        """Verifica que falla sin clave de cifrado."""
        # Eliminar clave de cifrado
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', False
        )
        
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        wizard = Wizard.create({
            'company_id': self.env.company.id,
            'gemini_api_key': 'AIzaSyTestKey',
            'gemini_model': 'gemini-1.5-pro',
        })
        
        with self.assertRaises(UserError):
            wizard.action_save()
        
        # Restaurar clave
        self.env['ir.config_parameter'].sudo().set_param(
            'building.encryption_key', self.test_key
        )

    def test_05_wizard_update_existing_config(self):
        """Verifica que actualiza config existente en lugar de crear nueva."""
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        
        # Primera configuración
        wizard1 = Wizard.create({
            'company_id': self.env.company.id,
            'gemini_api_key': 'AIzaSyFirstKey12345',
            'gemini_model': 'gemini-1.5-pro',
        })
        wizard1.action_save()
        
        # Segunda configuración (misma empresa, mismo provider)
        wizard2 = Wizard.create({
            'company_id': self.env.company.id,
            'gemini_api_key': 'AIzaSySecondKey9999',
            'gemini_model': 'gemini-1.5-flash',
        })
        wizard2.action_save()
        
        # Verificar que solo hay una config
        configs = self.env['building.ai.config'].search([
            ('company_id', '=', self.env.company.id),
            ('provider', '=', 'gemini'),
            ('work_id', '=', False),
        ])
        
        self.assertEqual(len(configs), 1, "Solo debe haber una config por scope+provider")
        self.assertEqual(configs.api_key_last4, '9999', "Debe tener la última key")
        self.assertEqual(configs.model_name, 'gemini-1.5-flash')

    def test_06_wizard_computed_status(self):
        """Verifica campos computados del wizard."""
        # Crear config existente
        self.env['building.ai.config'].create({
            'company_id': self.env.company.id,
            'provider': 'gemini',
            'model_name': 'gemini-1.5-pro',
            'api_key_encrypted': 'fake_cipher',
            'api_key_last4': 'TEST',
        })
        
        Wizard = self.env['building.ai.config.wizard'].with_user(self.user_director)
        wizard = Wizard.create({
            'company_id': self.env.company.id,
        })
        
        self.assertEqual(wizard.gemini_status, 'configured')
        self.assertEqual(wizard.gemini_last4, 'TEST')
        self.assertEqual(wizard.openai_status, 'not_configured')
