#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2011 Örjan Persson

import unittest

from argcmd import trie


class TrieTest(unittest.TestCase):
    trie_cls = trie.Trie

    def assert_trie(self, t, search, expected):
        words = [w for w in t.search(search)]
        self.assertEquals(expected, words)

    def test_search(self):
        t = self.trie_cls()

        t.insert('acc')
        t.insert('abed')
        t.insert('abc32')
        t.insert('abc12')
        t.insert('cde')

        self.assert_trie(t, 'a', ['abc12', 'abc32', 'abed', 'acc'])
        self.assert_trie(t, 'abc', ['abc12', 'abc32'])
        self.assert_trie(t, 'abc1', ['abc12'])
        self.assert_trie(t, 'abc12', ['abc12'])
        self.assert_trie(t, 'abc123', [])
        self.assert_trie(t, 'c', ['cde'])
        self.assert_trie(t, 'd', [])

    def test_remove(self):
        t = self.trie_cls()

        t.insert('ba')
        t.insert('ad')
        t.insert('ac')

        self.assert_trie(t, 'a', ['ac', 'ad'])

        t.remove('ad')
        self.assert_trie(t, 'a', ['ac'])

        t.remove('ac')
        self.assert_trie(t, 'a', [])


if __name__ == '__main__':
    unittest.main()
