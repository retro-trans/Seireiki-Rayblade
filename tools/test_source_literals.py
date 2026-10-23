"""Exact opaque-label preservation, with no general kana exception."""
import unittest
from source_literals import checked_english_prose


class SourceLiteralTests(unittest.TestCase):
    label='03K\u30fc01'

    def test_exact_source_label_is_only_removed_from_checking_copy(self):
        english='Give me the '+self.label+' recording crystal.'
        self.assertEqual(checked_english_prose(self.label+'\u306e',english),
                         'Give me the  recording crystal.')
        self.assertIn(self.label,english)

    def test_ascii_only_english_is_unchanged(self):
        self.assertEqual(checked_english_prose('','Hello.'),'Hello.')

    def test_original_dash_cannot_be_normalized(self):
        for altered in ('03K-01','03K\uff0d01','03K01'):
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                checked_english_prose(self.label,altered)

    def test_source_label_cannot_be_omitted(self):
        with self.assertRaises(ValueError):checked_english_prose(self.label,'The device.')

    def test_source_label_cannot_be_invented(self):
        with self.assertRaises(ValueError):checked_english_prose('',self.label)

    def test_source_label_cannot_be_duplicated(self):
        with self.assertRaises(ValueError):checked_english_prose(self.label,self.label+' '+self.label)

    def test_label_cannot_be_embedded_inside_another_identifier(self):
        for altered in ('A'+self.label,self.label+'B',self.label+'_extra',self.label+'-extra'):
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                checked_english_prose(self.label,altered)

    def test_kana_outside_label_is_rejected(self):
        with self.assertRaises(ValueError):checked_english_prose(self.label,self.label+' \u30a2')

    def test_unknown_model_labels_with_kana_are_rejected(self):
        with self.assertRaises(ValueError):checked_english_prose('04K\u30fc01','04K\u30fc01')

    def test_wrong_model_digits_are_rejected(self):
        with self.assertRaises(ValueError):checked_english_prose(self.label,'03K\u30fc02')


if __name__=='__main__':unittest.main()
