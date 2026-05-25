"""Exercise the emitted objects.py — categories, atoms, vocabularies."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from kernels.python_bmf.objects import (  # noqa: E402
    PyBmfCategory,
    BmfAtom,
    BmfModule,
    BmfStatementTree,
    PYTHON_KEYWORDS,
    PYTHON_OPERATORS,
    py_keyword,
    py_name,
    py_string,
)


class CategoriesTests(unittest.TestCase):
    def test_known_categories(self):
        self.assertEqual(int(PyBmfCategory.IMPORT), 501)
        self.assertEqual(int(PyBmfCategory.MATCH_AS), 574)
        self.assertEqual(int(PyBmfCategory.MODULE), 523)

    def test_nodeid(self):
        nid = PyBmfCategory.IMPORT.nodeid()
        self.assertEqual((nid.pkg, nid.level, nid.type, nid.inst), (1, 2, 99, 501))

    def test_category_count(self):
        # 74 categories shipped today; expansion lands as Phases 2+ widen coverage.
        self.assertGreaterEqual(len(list(PyBmfCategory)), 74)


class AtomsTests(unittest.TestCase):
    def test_atom_construction(self):
        a = py_keyword("def")
        self.assertEqual(a.kind, "py-keyword")
        self.assertEqual(a.value, "def")
        n = py_name("foo")
        self.assertEqual(n.kind, "py-name")
        s = py_string("hello")
        self.assertEqual(s.kind, "py-string")


class VocabulariesTests(unittest.TestCase):
    def test_keywords_include_def(self):
        self.assertIn("def", PYTHON_KEYWORDS)
        self.assertIn("class", PYTHON_KEYWORDS)
        self.assertIn("return", PYTHON_KEYWORDS)

    def test_operators_include_arrow(self):
        self.assertIn("->", PYTHON_OPERATORS)
        self.assertIn("==", PYTHON_OPERATORS)
        self.assertIn("//", PYTHON_OPERATORS)


class CompositesTests(unittest.TestCase):
    def test_module_walks_atoms(self):
        atoms = [py_keyword("def"), py_name("foo")]
        tree = BmfStatementTree(
            kind="py-statement-tree",
            indent=0,
            cpython_rule="function_def",
            tokens=atoms,
        )
        mod = BmfModule(statements=[tree])
        self.assertEqual(mod.all_source_atoms(), atoms)


if __name__ == "__main__":
    unittest.main()
