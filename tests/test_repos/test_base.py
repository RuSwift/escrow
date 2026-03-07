import unittest
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from settings import Settings
from repos.base import BaseRepository


class MockRepository(BaseRepository):
    """Конкретная реализация для тестирования абстрактного класса"""
    pass


class TestBaseRepository(unittest.TestCase):
    def setUp(self):
        # Создаем моки для зависимостей
        self.mock_session = MagicMock(spec=AsyncSession)
        self.mock_redis = MagicMock(spec=Redis)
        
        # Настраиваем тестовые настройки
        self.settings = Settings()
        # Фиксируем секрет для предсказуемости тестов
        self.settings.secret = MagicMock()
        self.settings.secret.get_secret_value.return_value = "test-secret-key-12345"
        
        self.repo = MockRepository(
            session=self.mock_session,
            redis=self.mock_redis,
            settings=self.settings
        )

    def test_encryption_decryption_cycle(self):
        """Тест полного цикла шифрования и дешифрования"""
        original_text = "Hello, secret world! 12345"
        
        # Шифруем
        encrypted_data = self.repo.encrypt_data(original_text)
        self.assertIsInstance(encrypted_data, str)
        self.assertNotEqual(original_text, encrypted_data)
        
        # Дешифруем
        decrypted_text = self.repo.decrypt_data(encrypted_data)
        self.assertEqual(original_text, decrypted_text)

    def test_encryption_output_format(self):
        """Проверка формата зашифрованных данных (Base64 JSON)"""
        import base64
        import json
        
        plaintext = "test"
        encrypted_data = self.repo.encrypt_data(plaintext)
        
        # Пытаемся декодировать из Base64
        decoded_json_bytes = base64.b64decode(encrypted_data)
        decoded_dict = json.loads(decoded_json_bytes.decode('utf-8'))
        
        # Проверяем наличие обязательных полей AES-GCM
        self.assertIn("iv", decoded_dict)
        self.assertIn("tag", decoded_dict)
        self.assertIn("ciphertext", decoded_dict)

    def test_different_iv_for_same_text(self):
        """Проверка, что для одного и того же текста генерируются разные IV"""
        plaintext = "consistent text"
        
        encrypted1 = self.repo.encrypt_data(plaintext)
        encrypted2 = self.repo.encrypt_data(plaintext)
        
        # Результаты должны быть разными из-за случайного IV
        self.assertNotEqual(encrypted1, encrypted2)
        
        # Но оба должны успешно расшифровываться в один и тот же текст
        self.assertEqual(self.repo.decrypt_data(encrypted1), plaintext)
        self.assertEqual(self.repo.decrypt_data(encrypted2), plaintext)

    def test_decryption_failure_with_wrong_key(self):
        """Проверка ошибки дешифрования при смене ключа"""
        plaintext = "sensitive data"
        encrypted = self.repo.encrypt_data(plaintext)
        
        # Меняем ключ в настройках
        self.settings.secret.get_secret_value.return_value = "different-secret-key"
        
        # Дешифрование должно упасть (ошибка аутентификации GCM или неверный ключ)
        with self.assertRaises(Exception):
            self.repo.decrypt_data(encrypted)


if __name__ == "__main__":
    unittest.main()
