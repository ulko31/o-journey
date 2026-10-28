"""Regression checks for the deterministic planning core.
Run from project root: python -m unittest discover -s backend/tests
"""
import unittest
from backend.planner import PlanningRequest,Traveler,parse_interests,extract_budget,plan
class PlanningTests(unittest.TestCase):
    def test_budget_extraction(self):
        self.assertEqual(extract_budget("Бюджет 30 тыс рублей"),30000)
    def test_mood_keywords(self):
        self.assertIn("уединение",parse_interests("Хочу уединённый отдых"))
        self.assertIn("культура",parse_interests("Хочу попробовать новую культуру"))
    def test_no_fabricated_offers(self):
        result=plan(PlanningRequest(message="Хочу в горы и природу",days=5,budget_per_person=30000,travelers=[Traveler()]),use_llm=False)
        self.assertEqual(len(result["scenarios"]),3)
        for scenario in result["scenarios"]:
            self.assertIsNone(scenario["budget"]["total_price"])
            self.assertEqual(scenario["availability"],"not_checked")
            self.assertEqual(scenario["lodging_options"],[])
            self.assertIsNone(scenario["rank_basis"]["indicative_cost_rub"])
    def test_explicit_destination(self):
        result=plan(PlanningRequest(message="Хочу в Ереван, люблю культуру"),use_llm=False)
        self.assertEqual(result["scenarios"][0]["destination"]["name"],"Ереван")
if __name__=="__main__":
    unittest.main()
