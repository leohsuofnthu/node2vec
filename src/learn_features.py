import numpy as np
from typing import Dict, List
from pprint import pprint
import pdb
import json
import argparse
from src.utils import EpochSaver, RELATIONS
import multiprocessing
import random
import gensim
from src.preprocess import *
import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO,
                    datefmt="%Y-%m-%d %H:%M:%S")

FILE_EMBEDDINGS = "features_node2vec.csv"


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


def sample_walks(matrix_prob: Dict, all_nodes: List[str], walks_per_node: int = 10, walk_length: int = 80):
    walks = []
    for i in range(walks_per_node):
        for node in all_nodes:
            walks.append(random_walk(matrix_prob, node, walk_length))

    return walks


def optimize(walks: List[List[str]], user_nodes: List[str], mode: str, path_save: str,
             epochs: int = 10, context_size: int = 10, dim_features: int = 128, path_model: str = None):
    """
    :param epochs: number of epochs to run model
    :param path_save: where to save the embeddings
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
    # minimum term frequency (to define the vocabulary)
    min_count = 2

    if mode == 'train':
        logging.info('Starting Training of Word2Vec Model')
        model = gensim.models.Word2Vec(walks, min_count=min_count, sg=1, size=dim_features,
                                       iter=epochs, workers=cores, negative=n_negative_samples,
                                       window=context_size, callbacks=[epoch_logger])
    elif mode == 'resume':
        logging.info('Resuming Training of Word2Vec Model')
        model = gensim.models.Word2Vec.load(path_model)
        # Start at the learning rate that we previously stopped
        model.train(walks, total_examples=model.corpus_count, epochs=epochs,
                    start_alpha=model.min_alpha_yet_reached, callbacks=[epoch_logger])
    else:
        raise ValueError('Specify valid value for mode (%s)' % mode)

    write_embeddings_to_file(model, user_nodes, path_save)


def write_embeddings_to_file(model: gensim.models.Word2Vec, user_nodes: List[str], path_save: str):
    logging.info('Writting embeddings to file %s' % path_save)
    embeddings = {}
    for v in list(model.wv.vocab):
        # we only keep users' embeddings
        if v in user_nodes:
            vec = list(model.wv.__getitem__(v))
            embeddings[v] = vec

    df = pd.DataFrame(embeddings).T
    df.to_csv(path_save)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=str,
        help="Path to the folder containing the data",
        default=os.path.join(project_root(), "tests", "data"),
    )
    parser.add_argument(
        "--save",
        help="Path of the folder to save the user features (default is same folder as data)",
        default=None,
    )
    parser.add_argument(
        "--walks_per_node",
        help="Number of random samples starting from each node",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--walk_length",
        help="Length of the random walk",
        type=int,
        default=80,
    )
    parser.add_argument(
        "--dim_features",
        help="Dimension of embedding",
        type=int,
        default=128,
    )
    parser.add_argument(
        "--context_size",
        help="Context size for skip-gram model (windows size)",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--mode",
        help="Train or resume training",
        type=str,
        default='train',
    )
    parser.add_argument(
        "--epochs",
        help="Number of epochs to run the model",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--p",
        help="Parameter p of node2vec model",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--q",
        help="Parameter q of node2vec model",
        type=float,
        default=0.5,
    )

    args = parser.parse_args()
    if args.save is None:
        args.save = args.data
    # Get to Relation.csv
    args.data = os.path.join(args.data, RELATIONS)
    args.save = os.path.join(args.save, FILE_EMBEDDINGS)
    logging.info("Loading data...")
    df = load_csv(args.data)
    logging.info("Precomputing transition probabilities...")
    matrix_prob = get_transition_probabilites(df, False, args.p, args.q)
    list_nodes = list_all_nodes(df)
    user_nodes = list_user_nodes(df)

    if args.context_size >= args.walk_length:
        raise ValueError("Context size can't be greater or equal to walk length !")

    logging.info("Sampling walks to create our dataset")
    walks = sample_walks(matrix_prob, list_nodes, args.walks_per_node, args.walk_length)
    logging.info("Starting training of skip-gram model")
    optimize(walks, user_nodes, 'train', args.save, args.epochs, args.context_size, args.dim_features)


if __name__ == "__main__":
    main()