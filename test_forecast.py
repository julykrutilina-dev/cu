import unittest
from pathlib import Path
from forecast import predict, write_chart
from tempfile import TemporaryDirectory

class ForecastTests(unittest.TestCase):
    def test_base_price_and_caps(self):
        r=predict('MOW','AER','2026-06-12',9000)
        self.assertAlmostEqual(r['demand'],r['quantiles']['0.5'])
        self.assertEqual(r['sales'],min(r['seats'],max(0,r['demand'])))
        high=predict('MOW','AER','2026-06-12',1e8)
        self.assertEqual(high['sales'],0)
        low=predict('MOW','AER','2026-06-12',0)
        self.assertEqual(low['sales'],low['seats'])
    def test_sensitivity(self):
        a=predict('MOW','AER','2026-06-12',9000)
        b=predict('MOW','AER','2026-06-12',10000)
        self.assertAlmostEqual(a['demand']-b['demand'],141)
        for q in a['quantiles']:
            self.assertAlmostEqual(a['quantiles'][q]-b['quantiles'][q],141)
    def test_errors(self):
        for args in [('LED','AER','2026-06-12',9000),('MOW','AER','2027-01-01',9000),('MOW','AER','abc',9000),('MOW','AER','2026-06-12',float('nan')),('MOW','AER','2026-06-12',-1)]:
            with self.assertRaises(ValueError): predict(*args)
    def test_chart(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'chart.svg';write_chart(predict('MOW','AER','2026-06-12',9000),p)
            import xml.etree.ElementTree as ET
            self.assertEqual(ET.parse(p).getroot().tag,'{http://www.w3.org/2000/svg}svg')

if __name__=='__main__': unittest.main()
