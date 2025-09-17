# tests/core/test_security.py
import pytest
from app.core.security import encrypt_data, decrypt_data

def test_encryption_decryption_cycle():
    """
    Проверяет, что данные после шифрования и дешифрования остаются неизменными.
    Это "счастливый путь".
    """
    # Arrange
    original_data = "my_secret_vk_token_12345"

    # Act
    encrypted_data = encrypt_data(original_data)
    decrypted_data = decrypt_data(encrypted_data)

    # Assert
    assert encrypted_data is not None
    assert encrypted_data != original_data
    assert decrypted_data == original_data

def test_decrypt_invalid_data_returns_none():
    """
    Проверяет пограничный случай: что произойдет при попытке
    дешифровать некорректные данные. Функция должна вернуть None, а не упасть.
    """
    # Arrange
    invalid_encrypted_string = "this-is-not-a-valid-encrypted-string"

    # Act
    decrypted_data = decrypt_data(invalid_encrypted_string)

    # Assert
    assert decrypted_data is None

def test_encrypt_decrypt_none_value():
    """Проверяет корректную обработку None."""
    # Act & Assert
    assert encrypt_data(None) is None
    assert decrypt_data(None) is None