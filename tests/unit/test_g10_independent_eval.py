"""G10 metric arithmetic, malformed labeling and real subprocess smoke are synthetic."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from benchmarks.g10_independent_eval import read_inputs, score, evaluate


class G10IndependentEvalTests(unittest.TestCase):
    def test_positive_negative_and_rank(self):
        questions = [
            {"id":"p","query":"koridor","expected":"ANSWERABLE","relevant":["doc"]},
            {"id":"n","query":"olmayan","expected":"NO_EVIDENCE","relevant":[]},
        ]
        m = score(questions, [["bad", "doc"], []], [[True,True], []])
        self.assertEqual(m["recall_at_5"], 1)
        self.assertEqual(m["mrr_at_10"], 0.5)
        self.assertEqual(m["negative_false_positive_rate"], 0)
        self.assertEqual(m["citation_exact_rate"], 1)

    def test_manifest_and_label_validation(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            src=base/"sample.txt";src.write_text("test",encoding="utf-8")
            m=base/"manifest.json";j=base/"labels.jsonl"
            data=[{"key":"doc","path":"sample.txt","sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"rights":"Synthetic, created for test"}]
            m.write_text(json.dumps(data),encoding="utf-8")
            j.write_text(json.dumps({"id":"q","query":"test","expected":"ANSWERABLE","relevant":["doc"]})+"\n",encoding="utf-8")
            self.assertEqual(len(read_inputs(base,m,j)[0]),1)
            m.write_text(json.dumps([{**data[0],"path":"../escape.txt"}]),encoding="utf-8")
            with self.assertRaises(ValueError):read_inputs(base,m,j)
            m.write_text(json.dumps(data),encoding="utf-8")
            j.write_text(json.dumps({"id":"q","query":"test","expected":"NO_EVIDENCE","relevant":["doc"]})+"\n",encoding="utf-8")
            with self.assertRaises(ValueError):read_inputs(base,m,j)

    def test_e2e_synthetic_is_never_pilot_pass(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);corpus=base/"docs";corpus.mkdir()
            src=corpus/"x.txt";src.write_text("Bu yerel belgede Koridor adlandırması vardır.\n",encoding="utf-8")
            m=base/"manifest.json"
            m.write_text(json.dumps([{"key":"x","path":"x.txt","sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"rights":"Synthetic only"}]),encoding="utf-8")
            j=base/"labels.jsonl"
            j.write_text("\n".join([
                json.dumps({"id":"pos","query":"Koridor","expected":"ANSWERABLE","relevant":["x"]}),
                json.dumps({"id":"neg","query":"beklenmeyenkelime","expected":"NO_EVIDENCE","relevant":[]})
            ])+"\n",encoding="utf-8")
            result=evaluate(corpus,m,j,base/"out.json")
            self.assertEqual(result["status"],"MEASURED_NOT_ACCEPTED")
            self.assertEqual(result["metrics"]["recall_at_5"],1)
            self.assertEqual(result["metrics"]["negative_false_positive_rate"],0)
