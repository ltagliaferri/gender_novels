import re
import string
from collections import Counter
from pathlib import Path
from gutenberg.cleanup import strip_headers

import nltk
#nltk as part of speech tagger, requires these two packages
#TODO: Figure out how to put these nltk packages in setup.py, not here
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

from gender_novels import common



class Novel(common.FileLoaderMixin):
    """ The Novel class loads and holds the full text and
    metadata (author, title, publication date) of a novel

    >>> from gender_novels import novel
    >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion',
    ...                   'corpus_name': 'sample_novels', 'date': '1818',
    ...                   'filename': 'austen_persuasion.txt'}
    >>> austen = novel.Novel(novel_metadata)
    >>> type(austen.text)
    <class 'str'>
    >>> len(austen.text)
    467018
    """

    def __init__(self, novel_metadata_dict):

        if not hasattr(novel_metadata_dict, 'items'):
            raise ValueError(
                'novel_metadata_dict must be a dictionary or support .items()')

        # Check that the essential attributes for the novel exists.
        for key in ('author', 'date', 'title', 'corpus_name', 'filename'):
            if key not in novel_metadata_dict:
                raise ValueError(f'novel_metadata_dict must have an entry for "{key}". Full ',
                                 f'metadata: {novel_metadata_dict}')

        # check that the author starts with a capital letter
        if not novel_metadata_dict['author'][0].isupper():
            raise ValueError('The last name of the author should be upper case.',
                             f'{novel_metadata_dict["author"]} is likely incorrect in',
                             f'{novel_metadata_dict}.')

        # Check that the date is a year (4 consecutive integers)
        if not re.match(r'^\d{4}$', novel_metadata_dict['date']):
            raise ValueError('The novel date should be a year (4 integers), not',
                             f'{novel_metadata_dict["date"]}. Full metadata: {novel_metadata_dict}')

        self.author = novel_metadata_dict['author']
        self.date = int(novel_metadata_dict['date'])
        self.title = novel_metadata_dict['title']
        self.corpus_name = novel_metadata_dict['corpus_name']
        self.filename = novel_metadata_dict['filename']

        # optional attributes
        self.country_publication = novel_metadata_dict.get('country_publication', None)
        self.notes = novel_metadata_dict.get('notes', None)
        self.author_gender = novel_metadata_dict.get('author_gender', 'unknown')
        self._word_counts_counter = None
        self._word_count = None

        if self.author_gender not in {'female', 'male', 'non-binary', 'unknown', 'both'}:
            raise ValueError('Author gender has to be "female", "male" "non-binary," or "unknown" ',
                             f'but not {self.author_gender}. Full metadata: {novel_metadata_dict}')

        if 'text' in novel_metadata_dict:
            self.text = novel_metadata_dict['text']
        else:

            # Check that the filename looks like a filename (ends in .txt)
            if not self.filename.endswith('.txt'):
                raise ValueError(
                    f'The novel filename ({self.filename}) should end in .txt . Full metadata: '
                    f'{novel_metadata_dict}.')
            self.text = self._load_novel_text()

    @property
    def word_count(self):
        """
        Lazy-loading for Novel.word_count attribute. Returns the number of words in the novel.
        The word_count attribute is useful for the get_word_freq function.
        However, it is performance-wise costly, so it's only loaded when it's actually required.

        >>> from gender_novels import novel
        >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion',
        ...                   'corpus_name': 'sample_novels', 'date': '1818',
        ...                   'filename': 'austen_persuasion.txt'}
        >>> austen = novel.Novel(novel_metadata)
        >>> austen.word_count
        83305

        :return: int
        """

        if self._word_count is None:
            self._word_count = len(self.get_tokenized_text())
        return self._word_count

    def __str__(self):
        """
        Overrides python print method for user-defined objects for Novel class
        Returns the filename without the extension - author and title word
        :return: str

        >>> from gender_novels import novel
        >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion',
        ...                   'corpus_name': 'sample_novels', 'date': '1818',
        ...                   'filename': 'austen_persuasion.txt'}
        >>> austen = novel.Novel(novel_metadata)
        >>> novel_string = str(austen)
        >>> novel_string
        'austen_persuasion'
        """
        name = self.filename[0:len(self.filename)-4]
        return name


    def _load_novel_text(self):
        """Loads the text of a novel and uses the remove_boilerplate_text() and
        remove_table_of_contents() functions on the text of the novel to remove the boilerplate
        text and table of contents from the novel. After these actions, the novel's text should be
        only the actual text of the novel.

        Is a private function as it is unnecessary to access it outside the class.

        :return: str
        """

        file_path = Path('corpora', self.corpus_name, 'texts', self.filename)

        try:
            text = self.load_file(file_path)
        except FileNotFoundError:
            err = "Could not find the novel text file "
            err += "at the expected location ({file_path})."
            raise FileNotFoundError(err)

        # These two functions will ensure that the text becomes only the novel's own text,
        # removing the Project Gutenberg boilerplate and the table of contents.
        text = self._remove_boilerplate_text(text)
        text = self._remove_table_of_contents(text)

        return text


    def _remove_boilerplate_text(self, text):
        """
        Removes the boilerplate text from an input string of a novel.
        Currently only supports boilerplate removal for Project Gutenberg ebooks. Uses the
        strip_headers() function from the gutenberg module, which can remove even nonstandard
        headers.

        (see book number 3780 for one example of a nonstandard header — james_highway.txt in our
        sample corpus; or book number 105, austen_persuasion.txt, which uses the standard Gutenberg
        header but has had some info about the ebook's production inserted after the standard
        boilerplate).

        :return: str

        >>> from gender_novels import novel
        >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion',
        ...                   'corpus_name': 'sample_novels', 'date': '1818',
        ...                   'filename': 'austen_persuasion.txt'}
        >>> austen = novel.Novel(novel_metadata)
        >>> cleaned_text = austen._remove_boilerplate_text(austen._load_novel_text())
        >>> title_line = cleaned_text[0:cleaned_text.find("\\n")]
        >>> title_line
        'Persuasion'
        """

        return strip_headers(text.strip())


    def _remove_table_of_contents(self, text):
        """
        Removes the Table of Contents from an input string of a novel. Written with the intent of
        being used on Table of Contents removal for Project Gutenberg texts.

        This function works from the observation that books in Project Gutenberg always have
        chapter titles that are either
        A) Allcaps words or phrases or
        B) Capitalized Roman Numerals.
        This means that the first chapter can be identified as a line which is either
        A) entirely composed of capital letters or
        B) entirely composed of the letters {I, V, X, L, C, D, M}
        [operating under the assumption that no chapter will exceed 3899 chapters, the maximum
        number that can be obtained with standard Roman Numeral conventions]
        And that all chapter titles are followed by at least one empty line.

        The function looks for a line which is composed entirely of allcaps or Roman Numerals and
        followed only by empty lines until finding a line which is not entirely allcaps.

        :return: str
        TODO(derek): Make this fully functional
        """

        # Finds all positions of line breaks in the text file for the first few lines, tuned off
        # the parameter of charactersearch characters out
        charactersearch = 8000

        lines_of_text = text.split("\n")
        line_breaks = text[0:charactersearch].find("\n")
        # Creates a 2D array where each entry is the [contents of line, position of the line's
        # start, position of the line's end]. The last line break is not considered because,
        # of course, there is no next line after the last line.
        for linebreak in range(len(line_breaks))-1:
            currentlinecontents = text[linebreak:linebreak+1]
            lines_of_text.append([currentlinecontents, linebreak, linebreak+1])

        # Identifies lines which are comprised entirely of allcap characters and puts them in
        # another 2D array. Determines whether a line is entirely allcaps by examining whether
        # each of its characters are members of the set of capital letters plus
        allcap_lines = []
        # for line in lines_of_text:
        #    if line[0]

        return text


    def get_tokenized_text(self):
        """
        Tokenizes the text and returns it as a list of tokens

        This is a very simple way of tokenizing the text. We will replace it soon with a
        better implementation that uses either regex or nltk
        E.g. this version doesn't handle dashes or contractions

        >>> from gender_novels import novel
        >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion', 'date': '1818',
        ...                   'corpus_name': 'sample_novels', 'filename': 'austen_persuasion.txt',
        ...                   'text': '?!All-kinds %$< of pun*ct(uatio)n {a}nd sp+ecial cha/rs'}
        >>> austin = novel.Novel(novel_metadata)
        >>> tokenized_text = austin.get_tokenized_text()
        >>> tokenized_text
        ['allkinds', 'of', 'punctuation', 'and', 'special', 'chars']

        :rtype: list
        """

        # Excluded characters: !"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~
        excluded_characters = set(string.punctuation)
        cleaned_text = ''
        for character in self.text:
            if character not in excluded_characters:
                cleaned_text += character

        tokenized_text = cleaned_text.lower().split()
        return tokenized_text

    def find_quoted_text(self):
        """
        Finds all of the quoted statements in the novel text

        >>> from gender_novels import novel
        >>> test_text = '"This is a quote" and also "This is my quote"'
        >>> novel_metadata = {'author': 'Austen, Jane', 'title': 'Persuasion',
        ...                   'corpus_name': 'sample_novels', 'date': '1818',
        ...                   'filename': 'austen_persuasion.txt', 'text' : test_text}
        >>> test_novel = novel.Novel(novel_metadata)
        >>> test_novel.find_quoted_text()
        ['"This is a quote"', '"This is my quote"']

        # TODO: Make this test pass
        # >>> test_novel.text = 'Test case: "Miss A.E.--," [...] "a quote."'
        # >>> test_novel.find_quoted_text()
        # ['"Miss A.E.-- a quote."']

        # TODO: Make this test pass
        # One approach would be to find the shortest possible closed quote.
        #
        # >>> test_novel.text = 'Test case: "Open quote. [...] "Closed quote."'
        # >>> test_novel.find_quoted_text()
        # ['"Closed quote."']

        TODO(Redlon & Murray): Add and statements so that a broken up quote is treated as a
        TODO(Redlon & Murray): single quote
        TODO: Look for more complicated test cases in our existing novels.

        :return: list of complete quotation strings
        """
        text_list = self.text.split()
        quotes = []
        current_quote = []
        quote_in_progress = False
        quote_is_paused = False

        for word in text_list:
            if word[0] == "\"":
                quote_in_progress = True
                quote_is_paused = False
                current_quote.append(word)
            elif quote_in_progress:
                if not quote_is_paused:
                    current_quote.append(word)
                if word[-1] == "\"":
                    if word[-2] != ',':
                        quote_in_progress = False
                        quote_is_paused = False
                        quotes.append(' '.join(current_quote))
                        current_quote = []
                    else:
                        quote_is_paused = True


        return quotes

    def get_count_of_word(self, word):
        """
        Returns the number of instances of str word in the text.  N.B.: Not case-sensitive.
        >>> from gender_novels import novel
        >>> summary = "Hester was convicted of adultery. "
        >>> summary += "which made her very sad, and then Arthur was also sad, and everybody was "
        >>> summary += "sad and then Arthur died and it was very sad.  Sadness."
        >>> novel_metadata = {'author': 'Hawthorne, Nathaniel', 'title': 'Scarlet Letter',
        ...                   'corpus_name': 'sample_novels', 'date': '2018',
        ...                   'filename': None, 'text': summary}
        >>> scarlett = novel.Novel(novel_metadata)
        >>> scarlett.get_count_of_word("sad")
        4
        >>> scarlett.get_count_of_word('ThisWordIsNotInTheWordCounts')
        0

        :param word: word to be counted in text
        :return: int
        """

        # If word_counts were not previously initialized, do it now and store it for the future.
        if not self._word_counts_counter:
            self._word_counts_counter = Counter(self.get_tokenized_text())

        return self._word_counts_counter[word]

    def get_wordcount_counter(self):
        """
        Returns a counter object of all of the words in the text.
        (The counter can also be accessed as self.word_counts. However, it only gets initialized
        when a user either runs Novel.get_count_of_word or Novel.get_wordcount_counter, hence
        the separate method.)

        >>> from gender_novels import novel
        >>> summary = "Hester was convicted of adultery was convicted."
        >>> novel_metadata = {'author': 'Hawthorne, Nathaniel', 'title': 'Scarlet Letter',
        ...                   'corpus_name': 'sample_novels', 'date': '2018',
        ...                   'filename': None, 'text': summary}
        >>> scarlett = novel.Novel(novel_metadata)
        >>> scarlett.get_wordcount_counter()
        Counter({'was': 2, 'convicted': 2, 'hester': 1, 'of': 1, 'adultery': 1})

        :return: Counter
        """

        # If word_counts were not previously initialized, do it now and store it for the future.
        if not self._word_counts_counter:
            self._word_counts_counter = Counter(self.get_tokenized_text())
        return self._word_counts_counter

    def words_associated(self, word):
        """
        Returns a counter of the words found after given word
        In the case of double/repeated words, the counter would include the word itself and the next
        new word
        Note: words always return lowercase

        >>> from gender_novels import novel
        >>> summary = "She took a lighter out of her purse and handed it over to him."
        >>> summary += " He lit his cigarette and took a deep drag from it, and then began "
        >>> summary += "his speech which ended in a proposal. Her tears drowned the ring."
        >>> summary += " TBH i know nothing about this story."
        >>> novel_metadata = {'author': 'Hawthorne, Nathaniel', 'title': 'Scarlet Letter',
        ...                   'corpus_name': 'sample_novels', 'date': '2018',
        ...                   'filename': None, 'text': summary}
        >>> scarlett = novel.Novel(novel_metadata)
        >>> scarlett.words_associated("his")
        Counter({'cigarette': 1, 'speech': 1})

        :param word:
        :return: a Counter() object with {word:occurrences}
        """
        word = word.lower()
        word_count = Counter()
        check = False
        text = self.get_tokenized_text()

        for w in text:
            if check:
                word_count[w] += 1
                check = False
            if w == word:
                check = True
        return word_count


    def get_word_freq(self, word):
        """
        Returns dictionary with key as word and value as the frequency of appearance in book
        :param words: str
        :return: double

        >>> from gender_novels import novel
        >>> summary = "Hester was convicted of adultery. "
        >>> summary += "which made her very sad, and then Arthur was also sad, and everybody was "
        >>> summary += "sad and then Arthur died and it was very sad.  Sadness."
        >>> novel_metadata = {'author': 'Hawthorne, Nathaniel', 'title': 'Scarlet Letter',
        ...                   'corpus_name': 'sample_novels', 'date': '1900',
        ...                   'filename': None, 'text': summary}
        >>> scarlett = novel.Novel(novel_metadata)
        >>> frequency = scarlett.get_word_freq('sad')
        >>> frequency
        0.13333333333333333
        """

        word_frequency = self.get_count_of_word(word) / self.word_count
        return word_frequency



    def get_part_of_speech_tags(self):
        """
        Returns the part of speech tags as a list of tuples. The first part of each tuple is the
        term, the second one the part of speech tag.
        Note: the same word can have a different part of speech tag. In the example below,
        see "refuse" and "permit"
        >>> from gender_novels.novel import Novel
        >>> summary = "They refuse to permit us to obtain the refuse permit."
        >>> novel_metadata = {'author': 'Hawthorne, Nathaniel', 'title': 'Scarlet Letter',
        ...                   'corpus_name': 'sample_novels', 'date': '1900',
        ...                   'filename': None, 'text': summary}
        >>> novel = Novel(novel_metadata)
        >>> novel.get_part_of_speech_tags()[:4]
        [('They', 'PRP'), ('refuse', 'VBP'), ('to', 'TO'), ('permit', 'VB')]
        >>> novel.get_part_of_speech_tags()[-4:]
        [('the', 'DT'), ('refuse', 'NN'), ('permit', 'NN'), ('.', '.')]

        :rtype: list
        """
        text = nltk.word_tokenize(self.text)
        pos_tags = nltk.pos_tag(text)
        return pos_tags


if __name__ == '__main__':
    from dh_testers.testRunner import main_test
    main_test()
