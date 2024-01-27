import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_llm.model import create_model
from transformers import AutoTokenizer
from typing import Literal, List, Tuple, Union
from mlx_llm.model import create_model, create_tokenizer

class EmbeddingModel:
    
    def __init__(
        self, 
        model_name: str,
        max_length: int, 
        mode: Literal['last', 'avg']="last"
    ):
        """Embedding model

        Args:
            model_name (str): model name
            max_length (int): max length of the input sequence (embedding size)
            mode (Literal['last', 'avg'], optional): pooling mode. Defaults to "last".
        """
        assert mode in ['last', 'avg'], "mode must be either 'last' or 'avg'"
        self.model = create_model(model_name=model_name, weights=True, strict=False)
        self.tokenizer = create_tokenizer(model_name)
        self.max_length = max_length
        
        self.model.eval()
        self.mode = mode
        
    
    def last_token_pool(self, embeds: mx.array, attn_mask: mx.array) -> mx.array:
        """Last token pool embeddings

        Args:
            embeds (mx.array): embeddings
            attn_mask (mx.array): attention mask

        Returns:
            mx.array: last token pooled embeddings
        """
        left_padding = (attn_mask[:, -1].sum() == attn_mask.shape[0])
        if left_padding:
            return embeds[:, -1]
        else:
            sequence_lengths = attn_mask.sum(axis=1) - 1
            batch_size = embeds.shape[0]
            return embeds[mx.arange(batch_size), sequence_lengths]
        
    def average_pool(self, embeds: mx.array, attn_mask: mx.array) -> mx.array:
        """Average pool embeddings

        Args:
            embeds (mx.array): embeddings
            attn_mask (mx.array): attention mask

        Returns:
            mx.array: average pooled embeddings
        """
        embeds = mx.multiply(embeds, attn_mask[..., None])
        return embeds.sum(axis=1) / attn_mask.sum(axis=1)[..., None]

    
    def normalize(self, embeds: mx.array):
        """Normalize embeddings

        Args:
            embeds (mx.array): embeddings

        Returns:
            mx.array: normalized embeddings
        """
        embeds = embeds / mx.linalg.norm(embeds, ord=2, axis=1)[..., None]
        return mx.array(embeds)
    
    def prepare_tokens(self, text: List) -> Tuple[List, List]:
        """Prepare tokens for the model

        Args:
            text (List): input text

        Returns:
            Tuple[List, List]: input ids and attention mask
        """
        tokens = self.tokenizer(
            text, 
            max_length=self.max_length-1, 
            return_attention_mask=False, 
            padding=False, 
            truncation=True
        )
        
        tokens['input_ids'] = [
            input_ids + [self.tokenizer.eos_token_id] for input_ids in tokens['input_ids']
        ]
        
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        tokens = self.tokenizer.pad(
            tokens, 
            padding=True, 
            return_attention_mask=True, 
            return_tensors='np'
        )
        
        x = mx.array(tokens["input_ids"].tolist())
        attn_mask = mx.array(tokens["attention_mask"].tolist())
        
        return x, attn_mask
        
    def __call__(self, text: Union[List[str], str]) -> mx.array:
        """Compute embedding for the input tokens.

        Args:
            text (Union[List[str], str]): input text

        Returns:
            mx.array: embedded tokens
        """
        
        if isinstance(text, str):
            text = [text]
        
        x, attn_mask = self.prepare_tokens(text)
        embeds = self.model.embed(x)
        if self.mode == 'last':
            embeds = self.last_token_pool(embeds, attn_mask)
        if self.mode == 'avg':
            embeds = self.average_pool(embeds, attn_mask)
        embeds = self.normalize(embeds)        
        return embeds