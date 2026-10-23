"""Focused read-only regression checks for multi-page whispered dialogue."""
import unittest
from check_scenario_text import quotation_parity_matches,starts_single_quoted_speech


class ScenarioQuotations(unittest.TestCase):
    def test_three_page_whisper_and_contractions(self):
        pages=[
            ('Speaker\u300eFirst page.',"Speaker: 'Don't worry."),
            ('Middle page.',"They'll question the soldiers' plans."),
            ('Final page.\u300f',"There's nothing to gain.'"),
        ]
        self.assertTrue(starts_single_quoted_speech(pages[0][1]))
        for source,english in pages:
            self.assertTrue(quotation_parity_matches(source,english,True))

    def test_missing_whisper_open_is_rejected(self):
        self.assertFalse(quotation_parity_matches('Speaker\u300eFirst.',"Speaker: First.",True))

    def test_missing_whisper_close_is_rejected(self):
        self.assertFalse(quotation_parity_matches('Final.\u300f',"Final.",True))

    def test_mixed_whisper_close_is_rejected(self):
        self.assertFalse(quotation_parity_matches('Final.\u300f','Final."',True))

    def test_extra_double_quote_in_whisper_is_rejected(self):
        self.assertFalse(quotation_parity_matches('Middle.', 'An extra " mark.',True))

    def test_normal_multiline_speech_is_unchanged(self):
        self.assertTrue(quotation_parity_matches('Speaker\u300cFirst.\nFinal.\u300d',
                                                'Speaker: "First.\nFinal."'))
        self.assertFalse(quotation_parity_matches('Speaker\u300cFirst.\nFinal.\u300d',
                                                 'Speaker: "First.\nFinal.'))

    def test_normal_fe_halves(self):
        self.assertTrue(quotation_parity_matches('Speaker\u300cFirst.','Speaker: "First.'))
        self.assertTrue(quotation_parity_matches('Final.\u300d','Final."'))
        self.assertFalse(quotation_parity_matches('Middle.','An extra " mark.'))

    def test_single_page_whisper(self):
        self.assertTrue(quotation_parity_matches('Speaker\u300eWhole.\u300f',
                                                "Speaker: 'It's fine.'",True))

    def test_contraction_is_not_a_whisper_opener(self):
        self.assertFalse(starts_single_quoted_speech("Speaker: It's fine."))
        self.assertFalse(starts_single_quoted_speech('Speaker: "It is fine."'))

    def test_recovered_voiced_reaction_is_not_a_quote(self):
        source='Assistant\u300cHuh? ...\u3042"\u300d'
        self.assertTrue(quotation_parity_matches(source,'Assistant: "Huh? ...Agh!"'))
        self.assertFalse(quotation_parity_matches(source,'Assistant: "Huh? ...Agh!'))

    def test_other_ascii_quotes_still_count(self):
        self.assertTrue(quotation_parity_matches('Speaker "First.','Speaker: "First.'))
        self.assertFalse(quotation_parity_matches('Speaker "First.','Speaker: First.'))

    def test_voicing_exception_does_not_ignore_other_endings(self):
        self.assertFalse(quotation_parity_matches('Assistant\u300cA"\u300d',
                                                 'Assistant: "A!"'))
        self.assertFalse(quotation_parity_matches('Assistant\u300c\u3042" more\u300d',
                                                 'Assistant: "Agh, more!"'))


if __name__=='__main__':unittest.main()
