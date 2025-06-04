import unittest
from brd.prompts import STRATA_BRD_PRO_PERSONA, INITIAL_BRD_SECTIONS_TASK_TEMPLATE

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

    def test_initial_brd_sections_template_content(self):
        self.assertIsNotNone(INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIsInstance(INITIAL_BRD_SECTIONS_TASK_TEMPLATE, str)
        self.assertTrue(len(INITIAL_BRD_SECTIONS_TASK_TEMPLATE) > 0)
        self.assertIn("SECTIONS TO GENERATE:", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("1.  **Executive Summary**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("2.  **Business Context & Drivers**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("3.  **Stakeholder Analysis**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("4.  **Vision & Scope**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("5.  **Functional Requirements**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        # Check order implicitly by checking the full string for specific sequence.
        # A more robust way would be regex or parsing, but this covers the main requirement.
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("1.  **Executive Summary**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("5.  **Functional Requirements**"))


if __name__ == '__main__':
    unittest.main()
