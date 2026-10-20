"""Self-check for the name parsing: python3 scraper/test_parse.py"""
from common import parse_count, parse_line, parse_size, EXCLUDE, entry

cases = [
    # name, size, count, line
    ("PAMPERS Baby-Dry Maxi Gr. 4 (204 Stück) (8006540785034)", "4", 204, "Baby-Dry"),
    ("Pampers Baby Dry Gr.4 Maxi 9-14kg Windeln Single Pack 31 Stück (Gr. 4, 31 Stk.)", "4", 31, "Baby-Dry"),
    ("Pampers Baby Dry Gr.4+ Maxi Plus 10-15kg Windeln Single Pack 28 Stück", None, 28, "Baby-Dry"),
    ("Pampers Baby Dry Pants (Gr. 4, Tragepack, 27 Stk.)", "4", 27, "Baby-Dry Pants"),
    ("Pampers Premium Protection Pants Size 6, 2x 31 Stück", "6", 62, "Premium Protection Pants"),
    ("Pampers Windeln Harmonie Junior Grösse 5, Packungsgrösse: 152 Stück, Packungsart: Monatsbox", "5", 152, "Harmonie"),
    ("Pampers - Baby-Dry Grösse 4, 204STK", "4", 204, "Baby-Dry"),
    ("Pampers Premium Protection Windeln Gr. 6 13+ kg", "6", None, "Premium Protection"),
    ("Pampers Harmonie New Baby Gr. 1 (2-5 kg) 3 x 35 Windeln", "1", 105, "Harmonie"),
    ("PAMPERS Windeln Baby Dry Diverse Sorten Pro 70-132 Stück", None, None, "Baby-Dry"),
    ("Pampers Baby-Dry Pants Paw Patrol (Gr. 4, Tragepack, 24 Stk.)", "4", 24, "Baby-Dry Pants"),
    ("Pampers Premium Protection Gr. 3 und Gr. 4", None, None, "Premium Protection"),
]
for name, size, count, line in cases:
    got = (parse_size(name), parse_count(name), parse_line(name))
    assert got == (size, count, line), f"{name}: {got} != {(size, count, line)}"
assert EXCLUDE.search("Pampers Harmonie Aqua Feuchttücher 48 Stück")
assert EXCLUDE.search("Pampers Splashers Schwimmwindeln Gr. 4")
assert not EXCLUDE.search("Pampers Baby-Dry Gr. 4 (204 Stück)")
assert entry("X", "n", 53.95, 204, "4", "Baby-Dry", "u")["ppd"] == round(53.95 / 204, 4)
assert entry("X", "n", 53.95, 2, "4", "Baby-Dry", "u") is None  # 27 CHF per diaper = wrong count
print("ok")
assert entry("X", "n", 46.5, 180, "4", "Baby-Dry", "u", shipping=4.9)["ppd"] == round(51.4 / 180, 4)
print("ok shipping")
