import json
import tempfile
import unittest
from pathlib import Path

from contract_runtime import check_contract, load_contract, save_contract_audit


class SavedContractProTests(unittest.TestCase):
    def contract(self, root, rules):
        file=root/"contract.json"
        file.write_text(json.dumps({"version":1,"columns":rules}),encoding="utf-8")
        return load_contract(file)

    def test_repeatable_contract_catches_types_nulls_duplicates_and_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            csv=root/"current.csv"
            csv.write_text("id,amount,category\n1,10,A\n1,900,Z\n2,,A\n",encoding="utf-8")
            c=self.contract(root,{
                "id":{"required":True,"unique":True},
                "amount":{"required":True,"max_null_rate":0.1,"min":0,"max":100},
                "category":{"required":True,"allowed_values":["A","B"]},
                "obsolete":{"required":True},
            })
            report=check_contract(csv,c)
            self.assertEqual(report["status"],"CONTRACT_VIOLATION")
            codes={x["code"] for x in report["findings"]}
            for code in ("duplicate_unique_value","null_rate_limit","above_max",
                         "outside_allowed_values","required_missing"):
                self.assertIn(code,codes)
            self.assertEqual(len(report["source_sha256"]),64)
            first=save_contract_audit(report,root)
            second=save_contract_audit(report,root)
            self.assertNotEqual(first,second)
            self.assertTrue((first/"contract_result.json").is_file())
            self.assertTrue((second/"contract_findings.csv").is_file())

    def test_unsupported_rule_fails_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            file=root/"contract.json"
            file.write_text(json.dumps({"version":1,"columns":{
                "amount":{"required":True,"regex":"^.*$"}
            }}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Unsupported constraints"):
                load_contract(file)

    def test_existing_saved_baseline_contract_checks_future_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            csv=root/"current.csv"
            csv.write_text("id,amount\n1,10\n2,15\n",encoding="utf-8")
            c=self.contract(root,{"id":{"required":True,"unique":True},
                                  "amount":{"required":True,"kind":"numeric","min":0,"max":20}})
            r=check_contract(csv,c)
            self.assertEqual(r["status"],"NO_VIOLATION_IN_DECLARED_FIELDS")
            self.assertEqual(r["unchecked_columns"],[])

    def test_csv_formula_injection_is_escaped_in_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result={"findings":[{"severity":"error","code":"wrong",
                "column":"=HYPERLINK('evil')","detail":"@SUM(1,2)"}]}
            output=save_contract_audit(result,root)
            body=(output/"contract_findings.csv").read_text(encoding="utf-8-sig")
            self.assertIn("'=HYPERLINK",body)
            self.assertIn("'@SUM",body)


if __name__=="__main__":
    unittest.main()
