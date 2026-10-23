import unittest

from shop import api, catalog, export_pdf, paging, web


def ids(result):
    return [p["id"] for p in result["items"]]


class Defaults(unittest.TestCase):
    def test_default_page_is_fifty(self):
        result = api.list_products({})
        self.assertEqual(len(result["items"]), 50)
        self.assertEqual(
            result["meta"], {"page": 1, "page_size": 50, "total": 130, "pages": 3}
        )

    def test_last_page_has_the_rest(self):
        result = api.list_products({"page": "3"})
        self.assertEqual(ids(result), list(range(101, 131)))
        self.assertEqual(result["meta"]["page_size"], 50)

    def test_no_query_at_all(self):
        self.assertEqual(len(api.list_products()["items"]), 50)

    def test_category_filter_uses_the_new_default(self):
        result = api.list_products({"category": "tools"})
        self.assertEqual(result["meta"]["total"], 65)
        self.assertEqual(result["meta"]["pages"], 2)
        self.assertEqual(len(result["items"]), 50)


class RequestedSizes(unittest.TestCase):
    def test_smaller_size_is_honoured(self):
        result = api.list_products({"page_size": "25"})
        self.assertEqual(len(result["items"]), 25)
        self.assertEqual(result["meta"]["pages"], 6)

    def test_fifty_one_is_now_allowed(self):
        self.assertEqual(len(api.list_products({"page_size": "51"})["items"]), 51)

    def test_one_hundred_is_allowed(self):
        result = api.list_products({"page_size": "100"})
        self.assertEqual(len(result["items"]), 100)
        self.assertEqual(result["meta"]["page_size"], 100)

    def test_over_the_cap_is_clamped(self):
        for raw in ("101", "500", "100000"):
            result = api.list_products({"page_size": raw})
            self.assertEqual(result["meta"]["page_size"], 100, raw)
            self.assertEqual(len(result["items"]), 100, raw)

    def test_bad_values_fall_back_to_the_default(self):
        for raw in ("0", "-5", "abc", "", "2.5"):
            result = api.list_products({"page_size": raw})
            self.assertEqual(result["meta"]["page_size"], 50, raw)

    def test_bad_page_numbers_mean_page_one(self):
        for raw in ("0", "-1", "x", ""):
            result = api.list_products({"page": raw})
            self.assertEqual(result["meta"]["page"], 1, raw)
            self.assertEqual(ids(result)[0], 1, raw)

    def test_second_page_of_a_custom_size(self):
        result = api.list_products({"page": "2", "page_size": "60"})
        self.assertEqual(ids(result), list(range(61, 121)))


class PagingFunctions(unittest.TestCase):
    def test_paginate_default(self):
        page = paging.paginate(list(range(120)))
        self.assertEqual(len(page["items"]), 50)
        self.assertEqual(page["pages"], 3)

    def test_paginate_cap(self):
        page = paging.paginate(list(range(300)), 1, 150)
        self.assertEqual(len(page["items"]), 100)

    def test_clamp_values(self):
        self.assertEqual(paging.clamp_page_size(None), 50)
        self.assertEqual(paging.clamp_page_size(75), 75)
        self.assertEqual(paging.clamp_page_size("100"), 100)
        self.assertEqual(paging.clamp_page_size(101), 100)
        self.assertEqual(paging.clamp_page_size(0), 50)


class RenderedText(unittest.TestCase):
    def test_first_page_header_and_rows(self):
        text = web.page("")
        lines = text.split("\n")
        self.assertEqual(lines[0], "Showing 1-50 of 130")
        self.assertEqual(len(lines), 51)
        self.assertEqual(lines[1], "- Product 001")
        self.assertEqual(lines[-1], "- Product 050")

    def test_last_page_header(self):
        text = web.page("page=3")
        self.assertEqual(text.split("\n")[0], "Showing 101-130 of 130")

    def test_custom_size_header(self):
        text = web.page("page_size=25&page=2")
        self.assertEqual(text.split("\n")[0], "Showing 26-50 of 130")

    def test_big_size_header(self):
        text = web.page("page_size=500&page=2")
        self.assertEqual(text.split("\n")[0], "Showing 101-130 of 130")

    def test_category_header(self):
        text = web.page("category=tools")
        self.assertEqual(text.split("\n")[0], "Showing 1-50 of 65")

    def test_page_past_the_end(self):
        text = web.page("page=9")
        self.assertEqual(text, "Showing 0-0 of 130")


class PrintedSheetsUnchanged(unittest.TestCase):
    def test_sheets_still_hold_twenty(self):
        sheets = export_pdf.paginate_for_pdf(catalog.all_products())
        self.assertEqual(len(sheets[0]), 20)
        self.assertEqual(len(sheets), 7)
        self.assertEqual(len(sheets[-1]), 10)


if __name__ == "__main__":
    unittest.main()
