import numpy as np
from typing import Dict, List
from pprint import pprint
import pdb
import json
from src.utils import EpochSaver
import multiprocessing
import random
import gensim
from src.preprocess import *
import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO,
                    datefmt="%Y-%m-%d %H:%M:%S")

PATH_EMBEDDINGS = "features_node2vec.csv"
FEATURES = "features"


def random_walk(matrix_prob: Dict, previous_node: str, length: int):
    """ TODO: Find out how to start the random walk since we
    need information about the previous node to know the probability distribution
    """
    try:
        # Actually using the start node as the previous node and randomly sampling a a start node
        # TODO: Find out how they did in paper
        possible_starts = matrix_prob[previous_node].keys()
        start_node = random.sample(possible_starts, 1)[0]

        walk = [previous_node, start_node]
        for i in range(length):
            # probability distribution
            p_dist = matrix_prob[walk[-2]][walk[-1]]
            # draw a sample
            sample = np.random.choice(list(p_dist.keys()), p=list(p_dist.values()))

            walk.append(sample)
    except KeyError as err:
        raise KeyError(err)

    # remove previous node because it is not sampled according to prob.distribution
    return walk[1:]


def learn_features(matrix_prob: Dict, list_nodes: List[str], user_nodes: List[str], dim_features: int = 128,
                   walks_per_node: int = 10, walk_length: int = 80, context_size: int = 10):
    if context_size >= walk_length:
        raise ValueError("Context size can't be greater or equal to walk length !")

    walks = []
    for i in range(walks_per_node):
        for node in list_nodes:
            walks.append(random_walk(matrix_prob, node, walk_length))

    # pprint(walks)
    optimize(walks, user_nodes, context_size, dim_features, mode='train')


def optimize(walks: List[List[str]], user_nodes: List[str], context_size: int, dim_features: int,
             mode: str, path_model: str = None):
    """
    :param user_nodes: List of all user ids
    :param walks: Input of "sentences"
    :param context_size: Also called window size
    :param dim_features:
    :param mode: {'train' or 'resume'} resume to resume training
    :param path_model: path model if we are resuming training
    :return:
    """

    cores = multiprocessing.cpu_count()

    # save model each epoch
    epoch_logger = EpochSaver('word2vec')

    n_negative_samples = 10
    # number of iterations (or epochs)
    iters = 2
    # minimum term frequency (to define the vocabulary)
    min_count = 2

    if mode == 'train':
        logging.info('Starting Training of Word2Vec Model')
        model = gensim.models.Word2Vec(walks, min_count=min_count, sg=1, size=dim_features,
                                       iter=iters, workers=cores, negative=n_negative_samples,
                                       window=context_size, callbacks=[epoch_logger])
    elif mode == 'resume':
        logging.info('Resuming Training of Word2Vec Model')
        model = gensim.models.Word2Vec.load(path_model)
        # Start at the learning rate that we previously stopped
        model.train(walks, total_examples=model.corpus_count, epochs=iters,
                    start_alpha=model.min_alpha_yet_reached, callbacks=[epoch_logger])
    else:
        raise ValueError('Specify valid value for mode (%s)' % mode)

    write_embeddings_to_file(model, user_nodes, PATH_EMBEDDINGS)


def write_embeddings_to_file(model: gensim.models.Word2Vec, user_nodes: List[str], emb_file: str):
    logging.info('Writting embeddings to file %s' % emb_file)
    embeddings = {}
    for v in list(model.wv.vocab):
        # we only keep users' embeddings
        if v in user_nodes:
            vec = list(model.wv.__getitem__(v))
            embeddings[v] = vec

    df = pd.DataFrame(embeddings).T
    df.to_csv(emb_file)


def main():

    df = load_csv(TEST_CSV)
    matrix_prob = get_transition_probabilites(df, False)
    list_nodes = list_all_nodes(df)
    user_nodes = list_user_nodes(df)
    learn_features(matrix_prob, list_nodes, user_nodes, walks_per_node=3, walk_length=5, context_size=2)


if __name__ == "__main__":
    main()
