import pandas as pd
from typing import Dict, List, Tuple
from abc import ABC
import tqdm

from src.data.weighted_dict import WeightedDict
from src.config import logging

# Dictionnary of transition probabilities
Dict_Prob = Dict[str, Dict[str, WeightedDict]]


class DataLoader(ABC):

    def __init__(
            self,
            df: pd.DataFrame,
            col1: str,
            col2: str,
            min_like: int = 1
    ):
        self.USER_ID = col1
        self.LIKE_ID = col2
        self.min_like = min_like

        self.df = df
        self.df[self.USER_ID] = self.df[self.USER_ID].astype(str)
        self.df[self.LIKE_ID] = self.df[self.LIKE_ID].astype(str)
        if len(self.df) == 0:
            raise ValueError(f"Dataframe provided is empty")

    def get_df_likes(self):
        return self.df.groupby(self.LIKE_ID)[self.USER_ID].apply(list)

    def get_df_users(self):
        return self.df.groupby(self.USER_ID)[self.LIKE_ID].apply(list)

    def list_like_nodes(self) -> List[str]:
        return list(self.df[self.LIKE_ID].unique())

    def list_all_nodes(self) -> List[str]:
        users = self.df[self.USER_ID].unique()
        likes = self.df[self.LIKE_ID].unique()
        return list(set(users).union(set(likes)))

    @staticmethod
    def _neighbors_neighbors(
            df_start: pd.DataFrame, df_neighbors: pd.DataFrame, p: float, q: float
    ) -> Dict_Prob:
        dct: Dict_Prob = {}
        df_start = df_start.apply(lambda x: set(x))
        for previous, possible_starts in tqdm.tqdm(df_start.items(), desc="Precomputing neighbors'neighbors",
                                                   total=len(df_start)):
            dct[previous] = {}
            for start in possible_starts:
                # Probability to get back to itself
                dct[previous][start] = WeightedDict()
                dct[previous][start][previous] = 1 / p
                for neighbor in df_neighbors[start]:
                    # Second neighbors
                    if neighbor != previous:
                        if neighbor in possible_starts:
                            # Previous node and start share the same neighbor !
                            dct[previous][start][neighbor] = 1
                        else:
                            # there is a distance of 2 between previous and neighbor
                            dct[previous][start][neighbor] = 1 / q
        return dct

    def _filter_df_min_connections(self, is_users: bool):
        """
        :param is_users: If true, drop users that have less than X connections to items,
        If false drop items that have less than X connections to users
        :return:
        """
        df_drop = self.get_df_users() if is_users else self.get_df_likes()
        len_bef = len(self.df)
        logging.info(f"Dropping columns with less than {self.min_like} connections"
                     f" -> Shape before = {self.df.shape}")
        ids_to_drop = []
        for _id, list_connections in df_drop.iteritems():
            if len(list_connections) < self.min_like:
                ids_to_drop.append(_id)

        column = self.USER_ID if is_users else self.LIKE_ID
        self.df = self.df[~self.df[column].isin(ids_to_drop)]
        logging.info(f"Dropped a total of {len_bef - self.df.shape[0]} rows")

        if len(self.df) == 0:
            raise RuntimeError(
                f"Dataframe is now empty! Either min_like={self.min_like} is too big or input data is invalid"
            )

    def get_transition_probabilites(
            self, p: float = 1., q: float = 1.
    ) -> Tuple[Dict_Prob, List[str]]:
        if self.min_like > 1:
            self._filter_df_min_connections(is_users=False)
        # Calculate this here because we modify dataframe
        all_nodes = self.list_all_nodes()

        df_users = self.get_df_users()
        df_likes = self.get_df_likes()

        df_total = (df_users.append(df_likes)).groupby(level=0).apply(sum)

        logging.info(f"df_total.shape = {df_total.shape}")
        logging.info("Getting All Nodes' neighbors and its neighbors' neighbors")
        all_neighbors = self._neighbors_neighbors(df_total, df_total, p, q)

        return all_neighbors, all_nodes

