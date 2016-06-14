# -*- encoding: utf-8 -*-
import logging
import numpy as np
from scipy.sparse import csr_matrix
from strephit.commons.pos_tag import TTPosTagger
from sklearn.feature_extraction import DictVectorizer

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """ Extracts features from sentences. Will process sentences one by one
        accumulating their features and finalizes them into the final
        training set.

        It should be used to extract features prior to classification,
        in which case the fe arguments can be used to group tokens of
        the same entity into a single chunk while ignoring the actual
        frame element name, e.g. `fes = dict(enumerate(entities))`
    """

    def __init__(self, language, window_width=2, collapse_fes=True):
        """ Initializes the extractor.

            :param language: The language of the sentences that will be used
            :param window_width: how many tokens to look before and after a each
             token when building its features.
            :param collapse_fes: Whether to collapse FEs to a single token
             or to keep them split.
        """
        self.language = language
        self.tagger = TTPosTagger(language)
        self.window_width = window_width
        self.collapse_fes = collapse_fes
        self.unk_feature = 'UNK'
        self.start()

    def start(self):
        """ Clears the features accumulated so far and starts over.
        """
        self.samples = []
        self.vocabulary = set()
        self.labels = set()

    def process_sentence(self, sentence, fes, add_unknown, gazetteer):
        """ Extracts and accumulates features for the given sentence

            :param unicode sentence: Text of the sentence
            :param dict fes: Dictionary with FEs and corresponding chunks
            :param bol add_unknown: Whether unknown tokens should be added
             to the index of treaded as a special, unknown token.
             Set to True when building the training set and to False
             when building the features used to classify new sentences
            :param dict gazetteer: Additional features to add when a given
             chunk is found in the sentence. Keys should be chunks and
             values should be list of features
            :return: Nothing
        """

        def add_feature_to(sample, feature_name, feature_value):
            if add_unknown or feature_value in self.vocabulary:
                sample[feature_name] = feature_value
                self.vocabulary.add(feature_value)
            else:
                sample[feature_name] = self.unk_feature

        tagged = self.sentence_to_tokens(sentence, fes)
        for position in xrange(len(tagged)):
            # add the unknown feature to every sample to trick the dict vectorizer into
            # thinking that there is a feature like that. will be useful when add_unknown
            # is false, because by default the dict vectorizer skips unseen labels
            sample = {'unk': self.unk_feature}

            for i in xrange(max(position - self.window_width, 0),
                            min(position + self.window_width + 1, len(tagged))):
                rel = i - position

                add_feature_to(sample, 'TERM%+d' % rel, tagged[i][0])
                add_feature_to(sample, 'POS%+d' % rel, tagged[i][1])
                add_feature_to(sample, 'LEMMA%+d' % rel, tagged[i][2])

                for feat in gazetteer.get(tagged[i][0], []):
                    sample['GAZ%+d' % rel] = feat

            label = 'O' if len(tagged[i]) == 3 else tagged[i][3]
            self.labels.add(label)
            self.samples.append((sample, label))

    def get_features(self):
        """ Returns the final training set

            :return: A matrix whose rows are samples and columns are features and a
             row vector with the sample label (i.e. the correct answer for the classifier)
            :rtype: tuple
        """
        samples, labels = zip(*self.samples)

        vect = DictVectorizer()
        features = vect.fit_transform(samples)

        label_index = {label: i for i, label in enumerate(self.labels)}
        labels = np.array([label_index[label] for label in labels])

        return features, labels

    def sentence_to_tokens(self, sentence, fes):
        """ Transforms a sentence into a list of tokens. Appends the FE type
            to all tokens composing a certain FE and optionally group them into
            a single token.

            :param unicode sentence: Text of the sentence
            :param dict fes: mapping FE -> chunk
            :return: List of tokens
        """

        tagged = self.tagger.tag_one(sentence, skip_unknown=False)

        for fe, chunk in fes.iteritems():
            if chunk is None:
                continue

            fe_tokens = self.tagger.tokenize(chunk)
            if not fe_tokens:
                continue

            # find fe_tokens into tagged
            found = False
            i = j = 0
            while i < len(tagged):
                if fe_tokens[j].lower() == tagged[i][0].lower():
                    j += 1
                    if j == len(fe_tokens):
                        found = True
                        break
                else:
                    j = 0
                i += 1

            if found:
                position = i - len(fe_tokens) + 1
                pos = 'ENT' if len(fe_tokens) > 1 else tagged[position][1]

                if self.collapse_fes:
                    # make a single token with the whole chunk
                    tagged = tagged[:position] + [[chunk, pos, chunk, fe]] + tagged[position + len(fe_tokens):]
                else:
                    # set custom lemma and label for the tokens of the FE
                    for i in xrange(position, position + len(fe_tokens)):
                        token, pos, _ = tagged[i]
                        tagged[i] = (token, pos, 'ENT', fe)
            else:
                logger.debug('cunk "%s" of fe "%s" not found in sentence "%s". Overlapping chunks?',
                             chunk, fe, sentence)

        return tagged

    def __getstate__(self):
        return (self.language, self.unk_feature, self.window_width,
                self.samples, self.vocabulary, self.labels, self.collapse_fes)

    def __setstate__(self, (language, unk_feature, window_width, samples, vocabulary, labels, collapse_fes)):
        self.__init__(language, window_width)
        self.samples = samples
        self.vocabulary = vocabulary
        self.unk_feature = unk_feature
        self.collapse_fes = collapse_fes
        self.labels = labels

    def __str__(self):
        return '%s(window_width=%d, collapse_fes=%r)' % (
            self.__class__.__name__, self.window_width, self.collapse_fes
        )
