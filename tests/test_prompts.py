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
        self.assertIn("5.  **Business Process Models**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("6.  **Conceptual Solution Architecture**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("7.  **Functional Requirements**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("8.  **Non-Functional Requirements**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("9.  **Data Requirements**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        self.assertIn("10. **Integration & Interface Requirements**", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)

        # Check order implicitly by checking the full string for specific sequence.
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("1.  **Executive Summary**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("5.  **Business Process Models**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("5.  **Business Process Models**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("6.  **Conceptual Solution Architecture**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("6.  **Conceptual Solution Architecture**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("7.  **Functional Requirements**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("7.  **Functional Requirements**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("8.  **Non-Functional Requirements**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("8.  **Non-Functional Requirements**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("9.  **Data Requirements**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("9.  **Data Requirements**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("10. **Integration & Interface Requirements**"))

        # Check for keywords in instructions for modified/new sections
        fr_text_start = INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("7.  **Functional Requirements**")
        nfr_text_start = INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("8.  **Non-Functional Requirements**")
        dr_text_start = INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("9.  **Data Requirements**")
        int_text_start = INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("10. **Integration & Interface Requirements**")

        fr_instructions = INITIAL_BRD_SECTIONS_TASK_TEMPLATE[fr_text_start:nfr_text_start]
        self.assertIn("detailed list", fr_instructions)
        self.assertIn("at least 3-5", fr_instructions)

        nfr_instructions = INITIAL_BRD_SECTIONS_TASK_TEMPLATE[nfr_text_start:dr_text_start]
        self.assertIn("Performance, Security, Usability, and Reliability", nfr_instructions) # Added "and"
        self.assertIn("NFR-001, NFR-002, etc.", nfr_instructions) # Check for numbering format

        dr_instructions = INITIAL_BRD_SECTIONS_TASK_TEMPLATE[dr_text_start:int_text_start]
        self.assertIn("data entities", dr_instructions)
        self.assertIn("DR-001, DR-002, etc.", dr_instructions) # Check for numbering format

        int_instructions = INITIAL_BRD_SECTIONS_TASK_TEMPLATE[int_text_start:] # Goes to end of template
        self.assertIn("integrations or interfaces", int_instructions)
        self.assertIn("INT-001, INT-002, etc.", int_instructions) # Check for numbering format


if __name__ == '__main__':
    unittest.main()
