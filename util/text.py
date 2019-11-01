from __future__ import absolute_import, division, print_function

import codecs
import numpy as np
import re
import struct

from util.flags import FLAGS
from six.moves import range

class Alphabet(object):
    def __init__(self, config_file):
        self._config_file = config_file
        self._label_to_str = {}
        self._str_to_label = {}
        self._size = 0
        if config_file:
            with codecs.open(config_file, 'r', 'utf-8') as fin:
                for line in fin:
                    if line[0:2] == '\\#':
                        line = '#\n'
                    elif line[0] == '#':
                        continue
                    self._label_to_str[self._size] = line[:-1] # remove the line ending
                    self._str_to_label[line[:-1]] = self._size
                    self._size += 1

    def _string_from_label(self, label):
        return self._label_to_str[label]

    def _label_from_string(self, string):
        try:
            return self._str_to_label[string]
        except KeyError as e:
            raise KeyError(
                'ERROR: Your transcripts contain characters (e.g. \'{}\') which do not occur in data/alphabet.txt! Use ' \
                'util/check_characters.py to see what characters are in your [train,dev,test].csv transcripts, and ' \
                'then add all these to data/alphabet.txt.'.format(string)
            ).with_traceback(e.__traceback__)

    def has_char(self, char):
        return char in self._str_to_label

    def encode(self, string):
        res = []
        for char in string:
            res.append(self._label_from_string(char))
        return res

    def decode(self, labels):
        res = ''
        for label in labels:
            res += self._string_from_label(label)
        return res

    def serialize(self):
        res = bytearray()
        res += struct.pack('<h', self._size)
        for key, value in self._label_to_str.items():
            value = value.encode('utf-8')
            res += struct.pack('<hh{}s'.format(len(value)), key, len(value), value)
        return bytes(res)

    @staticmethod
    def deserialize(buf):
        #pylint: disable=protected-access
        res = Alphabet(config_file=None)

        offset = 0
        def unpack_and_fwd(fmt, buf):
            nonlocal offset
            result = struct.unpack_from(fmt, buf, offset)
            offset += struct.calcsize(fmt)
            return result

        res.size = unpack_and_fwd('<h', buf)[0]
        for _ in range(res.size):
            label, val_len = unpack_and_fwd('<hh', buf)
            val = unpack_and_fwd('<{}s'.format(val_len), buf)[0].decode('utf-8')
            res._label_to_str[label] = val
            res._str_to_label[val] = label

        return res

    def size(self):
        return self._size

    def config_file(self):
        return self._config_file


def text_to_char_array(series, alphabet):
    r"""
    Given a Pandas Series containing transcript string, map characters to
    integers and return a numpy array representing the processed string.
    """
    try:
        transcript = np.asarray(alphabet.encode(series['transcript']))
        if not len(transcript):
            raise ValueError('While processing: {}\nFound an empty transcript! You must include a transcript for all training data.'.format(series['wav_filename']))
        return transcript
    except KeyError as e:
        # Provide the row context (especially wav_filename) for alphabet errors
        raise ValueError('While processing: {}\n{}'.format(series['wav_filename'], e))


# The following code is from: http://hetland.org/coding/python/levenshtein.py

# This is a straightforward implementation of a well-known algorithm, and thus
# probably shouldn't be covered by copyright to begin with. But in case it is,
# the author (Magnus Lie Hetland) has, to the extent possible under law,
# dedicated all copyright and related and neighboring rights to this software
# to the public domain worldwide, by distributing it under the CC0 license,
# version 1.0. This software is distributed without any warranty. For more
# information, see <http://creativecommons.org/publicdomain/zero/1.0>

def levenshtein(a, b):
    "Calculates the Levenshtein distance between a and b."
    n, m = len(a), len(b)
    if n > m:
        # Make sure n <= m, to use O(min(n,m)) space
        a, b = b, a
        n, m = m, n

    current = list(range(n+1))
    for i in range(1, m+1):
        previous, current = current, [i]+[0]*n
        for j in range(1, n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)

    return current[n]

# Validate and normalize transcriptions. Returns a cleaned version of the label
# or None if it's invalid.
def validate_label(label):
    # For now we can only handle [a-z ']
    if re.search(r"[0-9]|[(<\[\]&*{]", label) is not None:
        return None

    label = label.replace("-", " ")
    label = label.replace("_", " ")
    label = re.sub("[ ]{2,}", " ", label)
    label = label.replace(".", "")
    label = label.replace(",", "")
    label = label.replace("?", "")
    label = label.replace("\"", "")
    label = label.strip()
    label = label.lower()

    return label if label else None
