import pandas as pd
import numpy as np
import pickle
import uuid
from sklearn.metrics.pairwise import cosine_similarity
import mlx.core as mx
import os
from typing import Union, Tuple, Dict

class VectorDB:
    def __init__(self):
        self.embeddings = []
        self.metadata = []

    def add(self, embedding: np.array, text: str, source: str, row: str):
        """Add entry

        Args:
            embedding (np.array): embedding
            text (str): text
            source (str): source document
            row (str): row in the CSV
        """
        if isinstance(embedding, mx.array):
            embedding = np.array(embedding)
        _id = str(uuid.uuid4())
        self.embeddings.append(embedding)
        self.metadata.append({
            "id": _id,
            "text": text,
            "source": source,
            "row": row
        })
    
    @property
    def _uuid_to_index(self):
        return {entry["id"]: i for i, entry in enumerate(self.metadata)}

    @property
    def _index_to_uuid(self):
        return {i: entry["id"] for i, entry in enumerate(self.metadata)}
    
    def query(self, embedding: np.array, top_k=5):
        """Query db based on a single embedding

        Args:
            embedding (np.array): embedding
            top_k (int, optional): top k results. Defaults to 5.

        Raises:
            ValueError: no embeddings in db

        Returns:
            Dict: output dictionary with metadata, similarity and embedding
        """
        if len(self.embeddings)==0:
            raise ValueError("No embeddings in db")
        emeddings = np.array(self.embeddings)
        similarity = cosine_similarity([embedding], emeddings).flatten()
        top_indices = np.argsort(similarity)[-top_k:][::-1]
        
        output = []
        for metadata, similarity, embedding in zip(
            [self.metadata[i] for i in top_indices],
            similarity[top_indices],
            emeddings[top_indices]
        ):
            output.append({
                "metadata": metadata,
                "similarity": similarity,
                "embedding": embedding
            })
        
        return output


    def delete(self, uuid: str):
        """Delete entry

        Args:
            uuid (str): uuid
        """
        idx = self._uuid_to_index[uuid]
        self.embeddings = [embed for i, embed in enumerate(self.embeddings) if i != idx]
        self.metadata = [entry for i, entry in enumerate(self.metadata) if i != idx]

    def drop(self):
        self.embeddings = []
        self.metadata = []

    def load(self, db_path: str):
        """Load db

        Args:
            db_path (str): db path
        """
        self.embeddings = np.load(os.path.join(db_path, "embeddings.npz"))["arr_0"]
        with open(os.path.join(db_path, "metadata.pkl"), 'rb') as f:
            self.metadata = pickle.load(f)
        
    def save(self, db_path: str):
        """Save db

        Args:
            db_path (str): db path
        """
        os.makedirs(db_path, exist_ok=True)
        np.savez(
            os.path.join(db_path, "embeddings.npz"),
            self.embeddings
        )
        # save db with no embeddings key
        with open(os.path.join(db_path, "metadata.pkl"), 'wb') as f:
            pickle.dump(self.metadata, f)
            
    def __getitem__(self, idx: Union[int, str]) -> Tuple[np.array, Dict]:
        """Get item

        Args:
            idx (Union[int, str]): index or uuid

        Raises:
            ValueError: idx must be int or str

        Returns:
            Tuple[np.array, Dict]: embedding, metadata
        """
        if isinstance(idx, str):
            try:
                idx = self._uuid_to_index[idx] # getting integer idx
                embedding = self.embeddings[idx]
                metadata = self.metadata[idx]
            except KeyError:
                raise KeyError(f"uuid {idx} not found")
        
        elif isinstance(idx, int):
            if idx >= len(self.metadata):
                raise IndexError(f"idx {idx} out of range")
            embedding = self.embeddings[idx]
            metadata = self.metadata[idx]
            
        else:
            raise ValueError("idx must be int or str")
        
        return embedding, metadata
    
    def __len__(self):
        return len(self.metadata)