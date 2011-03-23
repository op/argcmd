# -*- coding: utf-8 -*-
# Copyright (c) 2011 Örjan Persson

import bisect


class Trie(object):
    """Trie algorithm"""

    class Node(object):
        """Trie node"""
        def __init__(self, char):
            self.char = char    # character
            self.count = 0      # number of complete words
            self.children = []  # nodes with matching prefix

        def __cmp__(self, char):
            return cmp(self.char, char)

    def __init__(self):
        self.__root = self.Node(None)

    def _get_node(self, token, allocate=False):
        node = self.__root
        for c in token:
            i = bisect.bisect_left(node.children, c)

            # add non-existing node to children
            if len(node.children) == i or node.children[i].char != c:
                if allocate:
                    node.children.insert(i, self.Node(c))
                else:
                    return None

            node = node.children[i]

        return node

    def insert(self, token):
        node = self._get_node(token, True)
        node.count += 1

    def remove(self, token):
        node = self._get_node(token, False)
        if node is None or node.count <= 0:
            raise KeyError(token)
        node.count -= 1

    def search(self, token):
        node = self._get_node(token)
        if node is None:
            return

        # return all matched words
        queue = [(token, node)]
        while queue:
            token, node = queue.pop()

            # return when the complete word is matching
            for n in range(node.count):
                yield token

            for child in reversed(node.children):
                queue.append((token + child.char, child))
