import unittest
from brd.prompts import STRATA_BRD_PRO_PERSONA

class TestPrompts(unittest.TestCase):

    def test_persona_loaded(self):
        self.assertIsNotNone(STRATA_BRD_PRO_PERSONA)
        self.assertIsInstance(STRATA_BRD_PRO_PERSONA, str)
        self.assertTrue(len(STRATA_BRD_PRO_PERSONA) > 0)

    def test_persona_key_sections(self):
        self.assertIn("You are \"StrataBRD Pro\"", STRATA_BRD_PRO_PERSONA)
        self.assertIn("Core Competencies:", STRATA_BRD_PRO_PERSONA)
        self.assertIn("Operating Principles:", STRATA_BRD_PRO_PERSONA)
        self.assertIn("REQUIREMENTS HIERARCHY:", STRATA_BRD_PRO_PERSONA)
        self.assertIn("BRD STRUCTURE (Enhanced):", STRATA_BRD_PRO_PERSONA)
        self.assertIn("OUTPUT STANDARDS:", STRATA_BRD_PRO_PERSONA)
        self.assertIn("INTERACTION PROTOCOL:", STRATA_BRD_PRO_PERSONA)

if __name__ == '__main__':
    unittest.main()
