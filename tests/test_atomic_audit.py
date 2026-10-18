import csv
import json
import tempfile
import unittest
from pathlib import Path
from contract_auditor import save_audit


class ReportTransactionTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.report={'findings':[],'generated_contract':{'version':1,'columns':{}},
                     'summary':{'errors':0,'warnings':0,'info':0}}
    def test_no_findings_still_has_header(self):
        folder=save_audit(self.report,self.root)
        text=(folder/'data_drift_findings.csv').read_text(encoding='utf-8-sig')
        self.assertIn('severity,code,column,message,baseline,current',text)
        self.assertEqual(json.loads((folder/'generated_contract.json').read_text())['version'],1)
    def test_partial_report_is_discarded_on_failure(self):
        bad={**self.report,'generated_contract':{'not_serializable':object()}}
        with self.assertRaises(TypeError):save_audit(bad,self.root)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_formula_like_cell_escaped_only_in_csv(self):
        finding={'severity':'warning','code':'field','column':'email',
                 'message':'=HYPERLINK("x")','baseline':'','current':''}
        out=save_audit({**self.report,'findings':[finding]},self.root)
        with (out/'data_drift_findings.csv').open(encoding='utf-8-sig',newline='') as file:
            first=next(csv.DictReader(file))
        self.assertTrue(first['message'].startswith("'="))
        original=json.loads((out/'data_drift_audit.json').read_text())
        self.assertEqual(original['findings'][0]['message'],finding['message'])
    def test_second_report_does_not_replace_first(self):
        first=save_audit(self.report,self.root)
        second=save_audit(self.report,self.root)
        self.assertNotEqual(first,second)
        self.assertTrue(first.exists());self.assertTrue(second.exists())


if __name__=='__main__':unittest.main()
