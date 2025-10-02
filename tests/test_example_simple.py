#!/usr/bin/env python3
"""
Test simple pour démontrer que le système de tests fonctionne.
Ce test sert d'exemple et devrait toujours passer.
"""

import unittest

class TestExampleSimple(unittest.TestCase):
    """Tests d'exemple simples pour vérifier le système de tests."""
    
    def test_basic_math(self):
        """Test arithmétique de base."""
        self.assertEqual(2 + 2, 4)
        self.assertEqual(3 * 3, 9)
        
    def test_string_operations(self):
        """Test opérations sur les chaînes."""
        self.assertEqual("hello".upper(), "HELLO")
        self.assertTrue("world" in "hello world")
        
    def test_list_operations(self):
        """Test opérations sur les listes."""
        test_list = [1, 2, 3]
        test_list.append(4)
        self.assertEqual(len(test_list), 4)
        self.assertIn(4, test_list)

def test_pytest_style():
    """Test style pytest pour compatibilité."""
    assert 1 + 1 == 2
    assert "test" in "testing"

if __name__ == '__main__':
    unittest.main() 