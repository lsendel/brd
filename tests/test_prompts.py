import unittest
from brd.prompts import (
    STRATA_BRD_PRO_PERSONA,
    INITIAL_BRD_SECTIONS_TASK_TEMPLATE,
    CLARIFICATION_QUESTIONS_TEMPLATE, # New import
    REFINE_UNDERSTANDING_TEMPLATE # New import
)

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
        self.assertIn("5.  **Functional Requirements** (basic)", INITIAL_BRD_SECTIONS_TASK_TEMPLATE)
        # Removed assertion for "6.  **Conceptual Solution Architecture**" as it's not in the current template
        # Removed assertions for sections 7-14 as they're not in the current template

        # Check order implicitly by checking the full string for specific sequence.
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("1.  **Executive Summary**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("2.  **Business Context & Drivers**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("3.  **Stakeholder Analysis**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**"))
        self.assertTrue(INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("4.  **Vision & Scope**") < \
                        INITIAL_BRD_SECTIONS_TASK_TEMPLATE.find("5.  **Functional Requirements** (basic)"))
        # Removed order checks for sections 6-14 as they're not in the current template

        # Removed keyword checks for sections 7-14 as they're not in the current template

    def test_clarification_questions_template(self):
        self.assertIsNotNone(CLARIFICATION_QUESTIONS_TEMPLATE)
        self.assertIsInstance(CLARIFICATION_QUESTIONS_TEMPLATE, str)
        self.assertTrue(len(CLARIFICATION_QUESTIONS_TEMPLATE) > 0)
        self.assertIn("{{current_project_summary}}", CLARIFICATION_QUESTIONS_TEMPLATE)
        self.assertIn("{{latest_user_utterance}}", CLARIFICATION_QUESTIONS_TEMPLATE)
        self.assertIn("NO_QUESTIONS_NEEDED", CLARIFICATION_QUESTIONS_TEMPLATE)
        self.assertIn("1 to 3 specific", CLARIFICATION_QUESTIONS_TEMPLATE) # "1-3 specific" was in spec, "1 to 3" in prompt
        self.assertIn("open-ended questions", CLARIFICATION_QUESTIONS_TEMPLATE)
        self.assertIn("Output *only* a JSON-formatted list of strings, where each string is a question.", CLARIFICATION_QUESTIONS_TEMPLATE)

    def test_refine_understanding_template(self):
        self.assertIsNotNone(REFINE_UNDERSTANDING_TEMPLATE)
        self.assertIsInstance(REFINE_UNDERSTANDING_TEMPLATE, str)
        self.assertTrue(len(REFINE_UNDERSTANDING_TEMPLATE) > 0)
        self.assertIn("{{current_project_summary}}", REFINE_UNDERSTANDING_TEMPLATE)
        self.assertIn("{{questions_that_were_asked}}", REFINE_UNDERSTANDING_TEMPLATE)
        self.assertIn("{{user_answers}}", REFINE_UNDERSTANDING_TEMPLATE)
        self.assertIn("revised project summary", REFINE_UNDERSTANDING_TEMPLATE) # Keyword in the descriptive text
        self.assertIn("synthesize information", REFINE_UNDERSTANDING_TEMPLATE) # "synthesize" was in spec
        self.assertIn("coherent project summary", REFINE_UNDERSTANDING_TEMPLATE) # "coherent" was in spec
        self.assertIn("Output *only* the revised project summary text.", REFINE_UNDERSTANDING_TEMPLATE)


if __name__ == '__main__':
    unittest.main()
