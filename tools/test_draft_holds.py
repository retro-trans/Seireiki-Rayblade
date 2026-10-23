"""Check that deliberate untranslated holds cannot erase or invent drafts."""
import unittest
from compile_scenario_drafts import authored_entry
from apply_scenario_batch import draft_update
from prepare_scenario_translation import fingerprint


class DraftHoldTests(unittest.TestCase):
    def row(self,**changes):
        row=dict(id='test.row',ja='source<FC:00:41>',en=None,
                 ends_with_newline=False,block_source_sha256='source-block',
                 source_review_needed=False)
        row.update(changes)
        row['source_sha256']=fingerprint(row,row['block_source_sha256'])
        return row

    def batch(self,**changes):
        batch=dict(context='Test context',decisions='Test decision',
                   holds={'test.row':'Pending non-graphic adaptation.'})
        batch.update(changes)
        return batch

    def test_authored_hold_is_untranslated(self):
        self.assertEqual(authored_entry({'hold':'Pending review.'},'content'),
                         (None,'Pending review.'))

    def test_authored_hold_rejects_empty_source_or_reason(self):
        for value,source in [({'hold':''},'content'),({'hold':'  '},'content'),
                             ({'hold':None},'content'),({'hold':'Reason'},'')]:
            with self.assertRaises(ValueError):authored_entry(value,source)

    def test_unknown_author_objects_are_rejected(self):
        with self.assertRaises(ValueError):authored_entry({'hold':'Reason','text':'invented'},'content')

    def test_hold_does_not_change_source(self):
        row=self.row();before=dict(row)
        update=draft_update(row,None,self.batch())
        self.assertEqual(row,before)
        self.assertIsNone(update['en'])
        self.assertEqual(update['status'],'held')

    def test_hold_cannot_erase_translation(self):
        with self.assertRaises(ValueError):draft_update(self.row(en='Existing'),None,self.batch())

    def test_unexplained_null_or_translated_hold_rejected(self):
        with self.assertRaises(ValueError):draft_update(self.row(),None,self.batch(holds={}))
        with self.assertRaises(ValueError):draft_update(self.row(),'Draft<FC:00:41>',self.batch())

    def test_normal_controls_and_source_checks_remain(self):
        batch=self.batch(holds={})
        with self.assertRaises(ValueError):draft_update(self.row(),'Missing control',batch)
        stale=self.row();stale['ja']='changed'
        with self.assertRaises(ValueError):draft_update(stale,None,self.batch())
        with self.assertRaises(ValueError):draft_update(self.row(source_review_needed=True),None,self.batch())
        self.assertEqual(draft_update(self.row(),'Draft<FC:00:41>',batch)['status'],'draft')

    def test_timed_punctuation_still_preserves_controls(self):
        self.assertEqual(authored_entry({'timed_ellipsis':'..'},'\u2025<FC:02:3E>'),
                         ('..<FC:02:3E>',None))


if __name__=='__main__':unittest.main()
